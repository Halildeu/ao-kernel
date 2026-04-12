"""Streaming result normalization — convert StreamResult to standard response dict.

Bridges streaming results into the same format as normalize_response() for
downstream consumers that expect the non-streaming contract.

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
        {text, usage, tool_calls, raw_json, provider_id,
         stream_metadata: {status, complete, finish_reason, chunk_count,
                          elapsed_ms, first_token_ms}}
    """
    return {
        "text": result.text,
        "usage": result.usage,
        "tool_calls": [],  # Text-only streaming; tool calls not supported yet
        "raw_json": None,  # No single raw JSON for streaming
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


def is_stream_complete(normalized: dict[str, Any]) -> bool:
    """Check if a normalized streaming response is complete.

    Downstream quality gate should skip evaluation for incomplete streams.
    """
    meta = normalized.get("stream_metadata")
    if meta is None:
        return True  # Non-streaming response, assume complete
    return bool(meta.get("complete", False))
