"""Handler for PRJ-HELLO extension — reference activation target (B3f, CNS-008).

Ships the single ``hello_world`` kernel_api_action. Pure function, offline,
no I/O — suitable as a smoke target for the dispatch wiring without
coupling the test suite to a live LLM provider.
"""

from __future__ import annotations

from typing import Any

EXTENSION_ID = "PRJ-HELLO"


def hello_world(params: dict[str, Any]) -> dict[str, Any]:
    """Return a greeting echo.

    Accepts an optional ``name`` param; defaults to ``"ao-kernel"``. The
    response shape mirrors the MCP decision envelope so downstream
    evidence tooling can log it without special-casing extension output.
    """
    name = params.get("name", "ao-kernel")
    if not isinstance(name, str) or not name.strip():
        name = "ao-kernel"
    return {
        "ok": True,
        "action": "hello_world",
        "extension_id": EXTENSION_ID,
        "greeting": f"Hello, {name}!",
    }


def register(registry: Any) -> None:
    """Register every action this handler module exports.

    Called from ``ao_kernel.extensions.bootstrap.register_default_handlers``.
    """
    registry.register(
        "hello_world",
        hello_world,
        extension_id=EXTENSION_ID,
    )
