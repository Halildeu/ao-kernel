"""Public facade for ``ao_kernel.adapters``.

Adapter manifest lifecycle primitives:

- **Errors** — typed exception hierarchy (``AdapterError``,
  ``AdapterManifestNotFoundError``, ``AdapterManifestCorruptedError``,
  ``AdapterRegistryEmptyError``).
- **Manifest loader** — ``AdapterRegistry`` loads
  ``<workspace_root>/.ao/adapters/*.manifest.v1.json``, validates
  against PR-A0 ``agent-adapter-contract.schema.v1.json``, exposes
  ``get`` / ``list_adapters`` / ``missing_capabilities`` /
  ``supports_capabilities``.

Narrow surface (plan v2 W2): internal helpers
(``_expected_id_from_filename``, ``_parse_manifest``, validator/schema
cache accessors) are NOT re-exported. Tests that need them import from
``ao_kernel.adapters.manifest_loader`` directly.
"""

from __future__ import annotations

from ao_kernel.adapters.errors import (
    AdapterError,
    AdapterManifestCorruptedError,
    AdapterManifestNotFoundError,
    AdapterRegistryEmptyError,
)
from ao_kernel.adapters.manifest_loader import (
    AdapterManifest,
    AdapterRegistry,
    LoadReport,
    SkippedManifest,
)

__all__ = [
    # Errors
    "AdapterError",
    "AdapterManifestNotFoundError",
    "AdapterManifestCorruptedError",
    "AdapterRegistryEmptyError",
    # Manifest loader
    "AdapterManifest",
    "AdapterRegistry",
    "LoadReport",
    "SkippedManifest",
]
