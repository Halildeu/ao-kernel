"""Deterministic key rendering for the context doc-bridge (internal)."""

from __future__ import annotations

import re

_LEADING_NUM = re.compile(r"^(\d+)")
_ALLOWED_PLACEHOLDERS = {"stem", "index", "num"}
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def stem_of(filename: str) -> str:
    return re.sub(r"\.md$", "", filename, flags=re.IGNORECASE)


def num_of(filename: str) -> str:
    m = _LEADING_NUM.match(filename)
    return m.group(1) if m else stem_of(filename)


def validate_template(template: str) -> None:
    """Reject templates referencing unknown placeholders (fail-closed)."""
    unknown = {n for n in _PLACEHOLDER.findall(template) if n not in _ALLOWED_PLACEHOLDERS}
    if unknown:
        raise ValueError(
            f"key_template {template!r} uses unknown placeholder(s): "
            f"{sorted(unknown)}; allowed: {sorted(_ALLOWED_PLACEHOLDERS)}"
        )


def render_key(template: str, *, stem: str = "", index: int = 0, num: str = "") -> str:
    validate_template(template)
    return template.format(stem=stem, index=index, num=num)
