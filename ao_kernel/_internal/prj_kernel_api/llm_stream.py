"""SSE stream parser and provider-native delta extractor.

Parses Server-Sent Events (SSE) from LLM provider HTTP responses and extracts
text deltas, usage info, and stream lifecycle events.

SSE spec compliance:
- Lines starting with ':' are comments (ignored)
- Empty line = event boundary
- Multi-line 'data:' fields are concatenated with newline
- 'data: [DONE]' terminates stream
- 'event:' field recognized but not required

Provider wire formats:
- Anthropic Messages API: content_block_delta → delta.text
- OpenAI Chat Completions: choices[0].delta.content
- Google Gemini: candidates[0].content.parts[0].text
- OpenAI-compatible (deepseek, qwen, xai): same as OpenAI
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class StreamEvent:
    """A single parsed streaming event.

    Attributes:
        event_type: text_delta, usage, message_start, content_block_start,
                    content_block_stop, message_stop, done, error
        text: Delta text only (NOT accumulated). Empty for non-text events.
        index: Content block index (0 for single-block responses).
        raw: Raw provider event dict. None if capture_events=False.
    """

    event_type: str
    text: str = ""
    index: int = 0
    raw: dict[str, Any] | None = None


# ── SSE Line Parser ─────────────────────────────────────────────────


def _parse_sse_lines(response) -> Iterator[dict[str, str]]:
    """Parse raw SSE lines from a file-like HTTP response.

    Yields dicts with keys: 'event' (optional), 'data'.
    Handles multi-line data, comments, and empty-line boundaries.
    """
    event_type = ""
    data_lines: list[str] = []

    for raw_line in response:
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace")
        else:
            line = raw_line

        line = line.rstrip("\r\n")

        # Comment line
        if line.startswith(":"):
            continue

        # Empty line = dispatch event
        if not line:
            if data_lines:
                yield {"event": event_type, "data": "\n".join(data_lines)}
                event_type = ""
                data_lines = []
            continue

        # Field parsing
        if ":" in line:
            field_name, _, field_value = line.partition(":")
            # SSE spec: strip single leading space from value
            if field_value.startswith(" "):
                field_value = field_value[1:]
        else:
            field_name = line
            field_value = ""

        if field_name == "data":
            data_lines.append(field_value)
        elif field_name == "event":
            event_type = field_value

    # Flush remaining (some servers don't send trailing empty line)
    if data_lines:
        yield {"event": event_type, "data": "\n".join(data_lines)}


# ── Provider Delta Extractors ───────────────────────────────────────


def extract_delta_text(event_data: dict[str, Any], provider_id: str) -> str:
    """Extract text delta from a parsed SSE event payload.

    Returns empty string if event contains no text delta.
    """
    if provider_id == "claude":
        return _extract_anthropic_delta(event_data)
    if provider_id == "google":
        return _extract_google_delta(event_data)
    # openai, deepseek, qwen, xai — all OpenAI-compatible
    return _extract_openai_delta(event_data)


def _extract_anthropic_delta(data: dict[str, Any]) -> str:
    """Anthropic Messages API: content_block_delta → delta.text"""
    evt_type = data.get("type", "")
    if evt_type == "content_block_delta":
        delta = data.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            return delta.get("text", "")
    return ""


def _extract_openai_delta(data: dict[str, Any]) -> str:
    """OpenAI Chat Completions: choices[0].delta.content"""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def _extract_google_delta(data: dict[str, Any]) -> str:
    """Google Gemini: candidates[0].content.parts[0].text"""
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    first = candidates[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        return ""
    first_part = parts[0]
    if not isinstance(first_part, dict):
        return ""
    return first_part.get("text", "")


# ── Usage Extraction ────────────────────────────────────────────────


def extract_stream_usage(
    event_data: dict[str, Any], provider_id: str
) -> dict[str, int] | None:
    """Extract token usage from streaming event (typically final event).

    Returns {input_tokens, output_tokens} or None.
    """
    if provider_id == "claude":
        # Anthropic: message_delta or message_stop contains usage
        if event_data.get("type") in ("message_delta", "message_stop"):
            usage = event_data.get("usage")
            if isinstance(usage, dict):
                return {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                }
        # Also check top-level message for input_tokens
        msg = event_data.get("message")
        if isinstance(msg, dict):
            usage = msg.get("usage")
            if isinstance(usage, dict):
                return {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                }
        return None

    # OpenAI-compatible: usage field in final chunk
    usage = event_data.get("usage")
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
        }

    # Google: usageMetadata
    meta = event_data.get("usageMetadata")
    if isinstance(meta, dict):
        return {
            "input_tokens": meta.get("promptTokenCount", 0),
            "output_tokens": meta.get("candidatesTokenCount", 0),
        }

    return None


# ── Event Classification ────────────────────────────────────────────


def _classify_event(
    event_data: dict[str, Any], provider_id: str
) -> str:
    """Classify event type from parsed data."""
    if provider_id == "claude":
        evt = event_data.get("type", "")
        mapping = {
            "message_start": "message_start",
            "content_block_start": "content_block_start",
            "content_block_delta": "text_delta",
            "content_block_stop": "content_block_stop",
            "message_delta": "usage",
            "message_stop": "done",
        }
        return mapping.get(evt, evt)

    # OpenAI-compatible
    choices = event_data.get("choices", [])
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        finish = first.get("finish_reason")
        if finish is not None:
            return "done"
        delta = first.get("delta", {})
        if isinstance(delta, dict) and delta.get("content") is not None:
            return "text_delta"
        return "other"

    # Google
    candidates = event_data.get("candidates", [])
    if isinstance(candidates, list) and candidates:
        first = candidates[0] if isinstance(candidates[0], dict) else {}
        if first.get("finishReason"):
            return "done"
        return "text_delta"

    return "other"


def _extract_index(event_data: dict[str, Any], provider_id: str) -> int:
    """Extract content block index from event."""
    if provider_id == "claude":
        return event_data.get("index", 0)
    choices = event_data.get("choices", [])
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        return first.get("index", 0)
    return 0


# ── Main Iterator ───────────────────────────────────────────────────


def iter_stream_events(
    response,
    provider_id: str,
    *,
    capture_raw: bool = True,
) -> Iterator[StreamEvent]:
    """Parse SSE response and yield StreamEvent objects.

    Args:
        response: File-like HTTP response from urlopen().
        provider_id: LLM provider identifier.
        capture_raw: If True, attach raw event dict to StreamEvent.raw.
    """
    for sse in _parse_sse_lines(response):
        data_str = sse["data"]

        # [DONE] termination
        if data_str.strip() == "[DONE]":
            yield StreamEvent(event_type="done")
            return

        # Parse JSON payload
        try:
            event_data = json.loads(data_str)
        except json.JSONDecodeError:
            yield StreamEvent(event_type="error", text=f"JSON parse error: {data_str[:100]}")
            continue

        if not isinstance(event_data, dict):
            continue

        # Error events
        error = event_data.get("error")
        if isinstance(error, dict):
            yield StreamEvent(
                event_type="error",
                text=error.get("message", str(error)),
                raw=event_data if capture_raw else None,
            )
            continue

        event_type = _classify_event(event_data, provider_id)
        text = extract_delta_text(event_data, provider_id)
        index = _extract_index(event_data, provider_id)

        # Check for usage in this event
        usage = extract_stream_usage(event_data, provider_id)
        if usage and event_type not in ("done",):
            yield StreamEvent(
                event_type="usage",
                index=index,
                raw=event_data if capture_raw else None,
            )

        yield StreamEvent(
            event_type=event_type,
            text=text,
            index=index,
            raw=event_data if capture_raw else None,
        )
