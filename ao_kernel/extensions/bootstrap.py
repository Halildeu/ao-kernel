"""Bootstrap — wire bundled extension manifests to their code-owned handlers.

D7 preservation: **no** auto-discovery, **no** entry_points, **no**
manifest-driven module imports. Each bundled handler registration is
spelled out in ``register_default_handlers()``. Adding a new bundled
handler is a two-line change here plus a new module under
``ao_kernel/extensions/handlers/``.

Workspace extensions should NOT be registered here — they live under
the caller's control. The SDK-facing path for workspace extensions is
``AoKernelClient.action_registry.register(...)`` directly.

Failure mode: a single handler raising during registration must not
prevent the others from being wired. We log at WARNING and continue.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ao_kernel.extensions.dispatch import ActionRegistry
    from ao_kernel.extensions.loader import ExtensionRegistry

logger = logging.getLogger(__name__)


def register_default_handlers(
    actions: "ActionRegistry",
    *,
    extensions: "ExtensionRegistry | None" = None,
) -> int:
    """Register all bundled handlers. Returns number successfully registered.

    The ``extensions`` registry (optional) lets us skip handlers whose
    manifest is absent, disabled, or blocked by compat/policy. Without
    the registry we register everything unconditionally — matches the
    library-mode behavior where discovery is not required.
    """
    registered = 0
    for extension_id, module_path in _DEFAULT_HANDLERS:
        if not _manifest_activatable(extensions, extension_id):
            logger.debug("skipping handler %s: manifest not activatable", extension_id)
            continue
        try:
            module = __import__(module_path, fromlist=["register"])
            module.register(actions)
            registered += 1
        except Exception as exc:  # noqa: BLE001 — one bad handler must not block the rest
            logger.warning(
                "extension handler registration failed for %s (%s): %s",
                extension_id, module_path, exc,
            )
    return registered


def default_handler_extension_ids() -> frozenset[str]:
    """Return the bundled extension IDs with explicit runtime handlers."""
    return frozenset(extension_id for extension_id, _module_path in _DEFAULT_HANDLERS)


def _manifest_activatable(
    extensions: "ExtensionRegistry | None", extension_id: str,
) -> bool:
    """Return True when no extensions registry was supplied, or when the
    extension is present, enabled, and free of activation blockers."""
    if extensions is None:
        return True
    manifest = extensions.get(extension_id)
    if manifest is None:
        return False
    if not manifest.enabled:
        return False
    if manifest.activation_blockers:
        return False
    return True


# Order matters for deterministic conflict resolution; we register in the
# order declared here. Keeping the list explicit (not computed) is the
# whole point of D7 preservation.
_DEFAULT_HANDLERS: list[tuple[str, str]] = [
    ("PRJ-HELLO", "ao_kernel.extensions.handlers.prj_hello"),
]


__all__ = ["register_default_handlers", "default_handler_extension_ids"]
