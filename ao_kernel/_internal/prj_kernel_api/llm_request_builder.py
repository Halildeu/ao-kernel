"""LLM request body + headers builder — provider-native wire formats.

Extracted from adapter_llm_actions_runtime.py (PR0 seam extraction).
Single responsibility: given provider_id, model, messages and params,
produce the HTTP request dict (body, headers, url) in provider-native format.

PR4b: capability-aware building + multi-modal endpoint routing.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ao_kernel._internal.providers.capability_model import ProviderCapability, negotiate, resolve_manifest

_XAI_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content
        )
    return str(content) if content else ""


def to_anthropic_messages(
    messages: List[Dict[str, Any]],
) -> tuple[str | None, List[Dict[str, Any]]]:
    """Convert generic messages to Anthropic Messages API format.

    Returns (system_text_or_none, anthropic_messages).
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if str(role or "").strip().lower() in ("system", "developer"):
            system_parts.append(_as_text(content).strip())
            continue
        role_str = str(role or "").strip().lower()
        if role_str not in {"user", "assistant"}:
            role_str = "user"
        text = _as_text(content)
        out.append({"role": role_str, "content": [{"type": "text", "text": text}]})
    system = "\n\n".join([p for p in system_parts if p]).strip()
    return (system if system else None), out


def build_live_request(
    *,
    provider_id: str,
    model: str,
    messages: List[Dict[str, Any]],
    base_url: str,
    api_key: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    request_id: str | None = None,
    response_format: Dict[str, Any] | None = None,
    tools: List[Dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """Build provider-native HTTP request for a live LLM call.

    Returns dict with keys: url, headers, body_bytes, body_json (for logging).

    Args:
        stream: If True, adds stream flag to request body and adjusts
                endpoint for providers that require it (e.g., Google).
                Raises ValueError if stream=True and tools are provided
                (tool streaming not yet supported — fail-closed).
    """
    # stream=True with tools is now supported (v0.3.0)
    # Tool call deltas are reconstructed by llm_stream_normalizer
    if provider_id == "claude":
        system, anthropic_messages = to_anthropic_messages(messages)
        req_body: dict[str, Any] = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": int(max_tokens) if isinstance(max_tokens, int) and max_tokens > 0 else 256,
        }
        if system:
            req_body["system"] = system
        if temperature is not None:
            req_body["temperature"] = temperature
        if response_format is not None:
            req_body["response_format"] = response_format
        if tools:
            from ao_kernel._internal.prj_kernel_api.tool_calling import build_tools_param
            req_body["tools"] = build_tools_param(provider_id, tools)
        if tool_choice is not None:
            req_body["tool_choice"] = tool_choice
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        req_body = {
            "model": model,
            "messages": messages,
        }
        if temperature is not None:
            req_body["temperature"] = temperature
        if max_tokens is not None:
            req_body["max_tokens"] = max_tokens
        if response_format is not None:
            req_body["response_format"] = response_format
        if tools:
            from ao_kernel._internal.prj_kernel_api.tool_calling import build_tools_param
            req_body["tools"] = build_tools_param(provider_id, tools)
        if tool_choice is not None:
            req_body["tool_choice"] = tool_choice
        if request_id and provider_id not in {"google", "openai", "qwen", "xai", "claude"}:
            req_body["request_id"] = request_id
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    if provider_id == "xai":
        headers["Accept"] = "application/json"
        headers["User-Agent"] = _XAI_USER_AGENT

    # Streaming support
    if stream:
        req_body["stream"] = True
        if provider_id == "xai":
            headers["Accept"] = "text/event-stream"

    # Google streaming requires different endpoint
    url = base_url
    if stream and provider_id == "google":
        # Google Gemini: /models/{model}:generateContent → :streamGenerateContent
        url = base_url.replace(":generateContent", ":streamGenerateContent")
        if "?alt=sse" not in url:
            url += "?alt=sse" if "?" not in url else "&alt=sse"

    body_bytes = json.dumps(req_body, ensure_ascii=False).encode("utf-8")

    return {
        "url": url,
        "headers": headers,
        "body_bytes": body_bytes,
        "body_json": req_body,
    }


# --- Capability-aware request building (PR4b) ---

def check_capabilities_before_request(
    *,
    provider_id: str,
    model: str,
    has_tools: bool = False,
    has_response_format: bool = False,
    repo_root: str | None = None,
) -> tuple[bool, str, list[str]]:
    """Pre-flight capability check before building request.

    Returns (ok, provider_id, missing_capability_names).
    If not ok, caller should degrade or fail with CAPABILITY_NOT_SUPPORTED.
    """
    manifest = resolve_manifest(provider_id, model, repo_root=repo_root)
    required: set[ProviderCapability] = {ProviderCapability.CHAT}

    if has_tools:
        required.add(ProviderCapability.TOOL_USE)
    if has_response_format:
        required.add(ProviderCapability.STRUCTURED_OUTPUT)

    satisfied, missing = negotiate(required, manifest)
    return satisfied, provider_id, [c.value for c in missing]


def build_embeddings_request(
    *,
    provider_id: str,
    model: str,
    input_text: str,
    base_url: str,
    api_key: str,
) -> Dict[str, Any]:
    """Build embeddings request for supported providers.

    Provider-specific endpoints:
    - Google: /models/{model}:embedContent
    - OpenAI/others: /embeddings
    """
    if provider_id == "google":
        url = f"{base_url.rstrip('/')}/models/{model}:embedContent"
        req_body = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": input_text}]},
            "taskType": "SEMANTIC_SIMILARITY",
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
    else:
        url = f"{base_url.rstrip('/')}/embeddings"
        req_body = {
            "model": model,
            "input": input_text,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    return {
        "url": url,
        "headers": headers,
        "body_bytes": json.dumps(req_body, ensure_ascii=False).encode("utf-8"),
        "body_json": req_body,
    }


def build_moderation_request(
    *,
    provider_id: str,
    input_text: str,
    base_url: str,
    api_key: str,
) -> Dict[str, Any]:
    """Build moderation request (OpenAI-compatible)."""
    url = f"{base_url.rstrip('/')}/moderations"
    req_body = {"input": input_text}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    return {
        "url": url,
        "headers": headers,
        "body_bytes": json.dumps(req_body, ensure_ascii=False).encode("utf-8"),
        "body_json": req_body,
    }
