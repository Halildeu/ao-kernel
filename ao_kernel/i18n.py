"""ao_kernel.i18n — CLI message localization.

Resolution order: AO_KERNEL_LANG > LC_ALL > LC_MESSAGES > LANG > "en"

Only user-facing CLI messages are localized. Command names, flags,
JSON keys, and API responses are always English.

Supported locales: en, tr
"""

from __future__ import annotations

import os

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "workspace_created": "Workspace created: {path}",
        "workspace_already_exists": "Workspace already exists: {path}",
        "error_no_workspace": "Error: No workspace found. Run 'ao-kernel init' first.",
        "error_corrupted": "Error: {detail}",
        "error_mcp_missing": (
            "Error: MCP server requires the 'mcp' package.\n"
            "Install with: pip install ao-kernel[mcp]"
        ),
        "usage_mcp_serve": "Usage: ao-kernel mcp serve",
    },
    "tr": {
        "workspace_created": "Workspace oluşturuldu: {path}",
        "workspace_already_exists": "Workspace zaten mevcut: {path}",
        "error_no_workspace": "Hata: Workspace bulunamadı. Önce 'ao-kernel init' çalıştırın.",
        "error_corrupted": "Hata: {detail}",
        "error_mcp_missing": (
            "Hata: MCP server için 'mcp' paketi gerekli.\n"
            "Kurmak için: pip install ao-kernel[mcp]"
        ),
        "usage_mcp_serve": "Kullanım: ao-kernel mcp serve",
    },
}

_resolved_locale: str | None = None


def _resolve_locale() -> str:
    """Resolve locale from environment. Cached after first call."""
    global _resolved_locale
    if _resolved_locale is not None:
        return _resolved_locale

    for var in ("AO_KERNEL_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "").strip().lower()
        if val.startswith("tr"):
            _resolved_locale = "tr"
            return "tr"
        if val.startswith("en"):
            _resolved_locale = "en"
            return "en"

    _resolved_locale = "en"
    return "en"


def msg(key: str, **kwargs: str) -> str:
    """Get a localized message by key.

    Falls back to English if key not found in current locale.
    """
    locale = _resolve_locale()
    messages = _MESSAGES.get(locale, _MESSAGES["en"])
    template = messages.get(key) or _MESSAGES["en"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def reset_locale() -> None:
    """Reset cached locale (for testing)."""
    global _resolved_locale
    _resolved_locale = None
