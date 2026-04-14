"""LLM response normalization — provider-agnostic text + metadata extraction.

Extracted from adapter_llm_actions.py (PR0 seam extraction).
Single responsibility: given raw response bytes, extract text content,
usage info, and (future) tool calls into a normalized dict.
"""

from __future__ import annotations

import json
from typing import Any, Dict


def extract_llm_output_text(resp_bytes: bytes) -> str:
    """Extract text content from provider response bytes.

    Handles:
    - Anthropic Messages API: content[].type=="text"
    - OpenAI Chat Completions: choices[].message.content
    - OpenAI Responses API: output[].content[].text / output_text
    - Fallback: raw UTF-8 text
    """
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return resp_bytes.decode("utf-8", errors="ignore").strip()

    if not isinstance(obj, dict):
        return resp_bytes.decode("utf-8", errors="ignore").strip()

    # Anthropic Messages API: {"content":[{"type":"text","text":"..."}], ...}
    content = obj.get("content")
    if isinstance(content, list) and content:
        texts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
        if texts:
            return "\n".join(texts).strip()

    # OpenAI Chat Completions: {"choices":[{"message":{"content":"..."}}]}
    choices = obj.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else None
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                content_val = msg.get("content")
                if isinstance(content_val, str):
                    return content_val.strip()
                if isinstance(content_val, list) and content_val:
                    parts = []
                    for block in content_val:
                        if not isinstance(block, dict):
                            continue
                        text = block.get("text")
                        if isinstance(text, str) and text.strip():
                            parts.append(text)
                    if parts:
                        return "\n".join(parts).strip()
            first_text = first.get("text")
            if isinstance(first_text, str):
                return first_text.strip()

    # OpenAI Responses API: {"output":[{"content":[{"text":"..."}]}]}
    output = obj.get("output")
    if isinstance(output, list) and output:
        texts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)
        if texts:
            return "\n".join(texts).strip()

    if isinstance(obj.get("output_text"), str):
        return str(obj.get("output_text", "")).strip()

    return resp_bytes.decode("utf-8", errors="ignore").strip()


def extract_usage(resp_bytes: bytes) -> Dict[str, Any] | None:
    """Extract token usage from provider response.

    Returns dict with input_tokens, output_tokens or None.
    """
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return None

    if not isinstance(obj, dict):
        return None

    usage = obj.get("usage")
    if isinstance(usage, dict):
        return {
            "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens") or 0,
            "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens") or 0,
        }
    return None


def normalize_response(
    resp_bytes: bytes,
    *,
    provider_id: str,
) -> Dict[str, Any]:
    """Normalize a provider response into a standard dict.

    Returns: {text, usage, raw_json, provider_id, tool_calls}
    """
    from ao_kernel._internal.prj_kernel_api.tool_calling import extract_tool_calls

    text = extract_llm_output_text(resp_bytes)
    usage = extract_usage(resp_bytes)
    tool_calls = extract_tool_calls(provider_id, resp_bytes)

    raw_json: dict[str, Any] | None = None
    try:
        parsed = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
        if isinstance(parsed, dict):
            raw_json = parsed
    except Exception:
        pass

    return {
        "text": text,
        "usage": usage,
        "tool_calls": tool_calls,
        "raw_json": raw_json,
        "provider_id": provider_id,
    }


def extract_embeddings(resp_bytes: bytes, *, provider_id: str) -> list[float] | None:
    """Extract embedding vector from provider response.

    Google: embedding.values
    OpenAI: data[0].embedding
    """
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None

    if provider_id == "google":
        emb = obj.get("embedding")
        if isinstance(emb, dict):
            values = emb.get("values")
            if isinstance(values, list):
                return values
        return None

    data = obj.get("data")
    if isinstance(data, list) and data:
        first = data[0] if isinstance(data[0], dict) else {}
        embedding = first.get("embedding")
        if isinstance(embedding, list):
            return embedding
    return None


def extract_moderation(resp_bytes: bytes) -> Dict[str, Any] | None:
    """Extract moderation results from OpenAI-compatible response."""
    try:
        obj = json.loads(resp_bytes.decode("utf-8", errors="ignore"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    results = obj.get("results")
    if isinstance(results, list) and results:
        first = results[0] if isinstance(results[0], dict) else {}
        return {
            "flagged": bool(first.get("flagged", False)),
            "categories": first.get("categories", {}),
            "category_scores": first.get("category_scores", {}),
        }
    return None
