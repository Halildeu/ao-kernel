"""Unified response parser — single source for JSON extraction + schema validation.

Replaces duplicated _extract_first_json_object in claude_provider.py and openai_provider.py.
Provides schema validation via jsonschema for structured output.
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_first_json_object(text: str) -> dict | None:
    """Extract the first JSON object from text.

    Strategy:
    1. Try full text as JSON
    2. Regex search for {...} pattern
    Falls back to None if no valid JSON object found.
    """
    text = text.strip()
    if not text:
        return None
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
        return None
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        value = json.loads(m.group(0))
        if isinstance(value, dict):
            return value
        return None
    except json.JSONDecodeError:
        return None


def validate_json_response(
    data: dict,
    schema: dict,
) -> tuple[bool, list[str]]:
    """Validate a JSON response against a JSON Schema.

    Returns (is_valid, error_messages). Fail-closed: import error raises.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RuntimeError("jsonschema required for structured output validation") from exc

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.json_path)
    if not errors:
        return True, []
    return False, [f"{e.json_path}: {e.message}" for e in errors[:5]]


def parse_structured_response(
    text: str,
    *,
    expected_schema: dict | None = None,
) -> dict[str, Any]:
    """Parse and optionally validate a structured JSON response.

    Returns:
        {
            "parsed_json": dict | None,
            "parse_method": "json_direct" | "regex_fallback" | "failed",
            "validation_passed": bool | None,
            "validation_errors": list[str],
        }
    """
    result: dict[str, Any] = {
        "parsed_json": None,
        "parse_method": "failed",
        "validation_passed": None,
        "validation_errors": [],
    }

    stripped = text.strip()
    if not stripped:
        return result

    # Try direct JSON parse
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            result["parsed_json"] = obj
            result["parse_method"] = "json_direct"
        else:
            result["parsed_json"] = None
    except json.JSONDecodeError:
        pass

    # Fallback to regex extraction
    if result["parsed_json"] is None:
        obj = extract_first_json_object(stripped)
        if obj is not None:
            result["parsed_json"] = obj
            result["parse_method"] = "regex_fallback"

    # Schema validation if requested and parsing succeeded
    if expected_schema is not None and result["parsed_json"] is not None:
        valid, errors = validate_json_response(result["parsed_json"], expected_schema)
        result["validation_passed"] = valid
        result["validation_errors"] = errors

    return result
