"""Streaming result normalization — convert StreamResult to standard response dict.

Bridges streaming results into the same format as normalize_response() for
downstream consumers that expect the non-streaming contract.

Includes tool call delta reconstruction for stream+tools support (v0.3.0).
For PARTIAL results: text is returned but quality gate evaluation is skipped.
"""

from __future__ import annotations

from typing import Any


def normalize_stream_result(
    result: Any,  # StreamResult from llm_stream_transport
    provider_id: str,
) -> dict[str, Any]:
    """Convert StreamResult to normalize_response()-compatible dict.

    Returns:
        {text, usage, tool_calls, raw_json, provider_id, stream_metadata}
    """
    # Reconstruct tool calls from captured events
    tool_calls = []
    if result.events:
        tool_calls = reconstruct_tool_calls(result.events, provider_id)

    return {
        "text": result.text,
        "usage": result.usage,
        "tool_calls": tool_calls,
        "raw_json": None,
        "provider_id": provider_id,
        "stream_metadata": {
            "status": result.status,
            "complete": result.complete,
            "finish_reason": result.finish_reason,
            "chunk_count": result.chunk_count,
            "elapsed_ms": result.elapsed_ms,
            "first_token_ms": result.first_token_ms,
            "error_code": result.error_code,
        },
    }


def reconstruct_tool_calls(
    events: list[dict[str, Any]],
    provider_id: str,
) -> list[dict[str, Any]]:
    """Reconstruct complete tool calls from streaming delta events.

    Streaming tool calls arrive as deltas:
    - OpenAI: choices[0].delta.tool_calls[{index, id, function.name, function.arguments}]
    - Anthropic: content_block_start(type=tool_use) + content_block_delta(partial_json)

    Returns list of complete tool calls in normalized format.
    """
    if provider_id == "claude":
        return _reconstruct_anthropic_tools(events)
    return _reconstruct_openai_tools(events)


def _reconstruct_openai_tools(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct OpenAI tool calls from delta events."""
    tools: dict[int, dict[str, Any]] = {}  # index → {id, name, arguments}

    for event in events:
        choices = event.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
        tool_deltas = delta.get("tool_calls", [])

        for tc in tool_deltas:
            if not isinstance(tc, dict):
                continue
            idx = tc.get("index", 0)
            if idx not in tools:
                tools[idx] = {"id": "", "name": "", "arguments": ""}

            if tc.get("id"):
                tools[idx]["id"] = tc["id"]
            func = tc.get("function", {})
            if isinstance(func, dict):
                if func.get("name"):
                    tools[idx]["name"] = func["name"]
                if func.get("arguments"):
                    tools[idx]["arguments"] += func["arguments"]

    return [
        {
            "id": t["id"],
            "type": "function",
            "function": {"name": t["name"], "arguments": t["arguments"]},
        }
        for t in tools.values()
        if t["name"]
    ]


def _reconstruct_anthropic_tools(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct Anthropic tool calls from content blocks."""
    tools: dict[int, dict[str, Any]] = {}

    for event in events:
        evt_type = event.get("type", "")

        if evt_type == "content_block_start":
            block = event.get("content_block", {})
            if isinstance(block, dict) and block.get("type") == "tool_use":
                idx = event.get("index", 0)
                tools[idx] = {
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input_json": "",
                }

        elif evt_type == "content_block_delta":
            idx = event.get("index", 0)
            delta = event.get("delta", {})
            if isinstance(delta, dict) and delta.get("type") == "input_json_delta":
                if idx in tools:
                    tools[idx]["input_json"] += delta.get("partial_json", "")

    import json
    result = []
    for t in tools.values():
        try:
            args = json.loads(t["input_json"]) if t["input_json"] else {}
        except (json.JSONDecodeError, ValueError):
            args = {}
        result.append({
            "id": t["id"],
            "type": "function",
            "function": {"name": t["name"], "arguments": json.dumps(args)},
        })
    return result


def is_stream_complete(normalized: dict[str, Any]) -> bool:
    """Check if a normalized streaming response is complete."""
    meta = normalized.get("stream_metadata")
    if meta is None:
        return True
    return bool(meta.get("complete", False))
