"""Structured output format builder — provider+model-native response_format.

Builds the correct wire format for each provider's structured output API:
- Claude: response_format with type=json_schema (model-level fallback)
- OpenAI: response_format with type=json_schema (Chat/Responses API)
- Google: response_mime_type + response_schema
- Others: None (not supported, falls back to regex parsing)
"""

from __future__ import annotations

from typing import Any, Dict


# Models known to support structured output (json_schema mode).
# Models not in this set fall back to regex parsing.
_CLAUDE_STRUCTURED_OUTPUT_MODELS = frozenset({
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-opus-4-5-20251101",
    "claude-opus-4-6-20260401",
    "claude-haiku-4-5-20251001",
})

_OPENAI_STRUCTURED_OUTPUT_MODELS = frozenset({
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4o-2024-08-06",
    "gpt-5.2-mini",
    "gpt-5.3-codex",
    "gpt-5.4",
    "o3",
    "o3-mini",
    "o4-mini",
})


def model_supports_structured_output(provider_id: str, model: str) -> bool:
    """Check if a provider+model combination supports structured output.

    Conservative: returns False for unknown models (fail-closed).
    """
    if provider_id == "claude":
        return _matches_model_set(model, _CLAUDE_STRUCTURED_OUTPUT_MODELS)
    if provider_id in ("openai", "xai"):
        return _matches_model_set(model, _OPENAI_STRUCTURED_OUTPUT_MODELS)
    if provider_id == "google":
        return True  # Gemini models generally support JSON mode
    if provider_id == "deepseek":
        return True  # DeepSeek supports json_object mode
    return False


def _matches_model_set(model: str, model_set: frozenset[str]) -> bool:
    """Check if model matches any entry in model_set.

    Supports exact match and prefix match (e.g., 'claude-sonnet-4' matches 'claude-sonnet-4-20250514').
    """
    if model in model_set:
        return True
    for known in model_set:
        if model.startswith(known.rsplit("-", 1)[0]):
            return True
    return False


def build_response_format_claude(
    model: str,
    schema: dict | None = None,
) -> Dict[str, Any] | None:
    """Build Claude-native response_format.

    Returns None if model doesn't support structured output.
    Without schema: {type: json_object} (free-form JSON)
    With schema: {type: json_schema, json_schema: {name, schema}} (constrained)
    """
    if not model_supports_structured_output("claude", model):
        return None
    if schema is None:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "structured_response",
            "schema": schema,
        },
    }


def build_response_format_openai(
    model: str,
    schema: dict | None = None,
) -> Dict[str, Any] | None:
    """Build OpenAI-native response_format.

    Returns None if model doesn't support structured output.
    Without schema: {type: json_object}
    With schema: {type: json_schema, json_schema: {name, strict, schema}}
    """
    if not model_supports_structured_output("openai", model):
        return None
    if schema is None:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "structured_response",
            "strict": True,
            "schema": schema,
        },
    }


def build_response_format_google(
    model: str,
    schema: dict | None = None,
) -> Dict[str, Any] | None:
    """Build Google Gemini response format params.

    Returns dict of extra body params to merge (not nested under response_format).
    """
    if schema is None:
        return {"response_mime_type": "application/json"}
    return {
        "response_mime_type": "application/json",
        "response_schema": schema,
    }


def build_response_format_deepseek(
    model: str,
    schema: dict | None = None,
) -> Dict[str, Any] | None:
    """Build DeepSeek response format (OpenAI-compatible)."""
    if schema is None:
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "structured_response",
            "schema": schema,
        },
    }


def build_response_format(
    provider_id: str,
    model: str,
    schema: dict | None = None,
) -> Dict[str, Any] | None:
    """Build provider+model-native response_format.

    Returns None if provider/model doesn't support structured output.
    Caller should fall back to regex parsing when None is returned.
    """
    builders = {
        "claude": build_response_format_claude,
        "openai": build_response_format_openai,
        "xai": build_response_format_openai,  # xAI uses OpenAI-compatible API
        "google": build_response_format_google,
        "deepseek": build_response_format_deepseek,
    }
    builder = builders.get(provider_id)
    if builder is None:
        return None
    return builder(model, schema)
