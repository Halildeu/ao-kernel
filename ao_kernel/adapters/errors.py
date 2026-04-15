"""Adapter subsystem exceptions.

Typed hierarchy for adapter manifest lifecycle errors. Callers switch on
exception type (or ``reason`` field) rather than parse messages. Loader
reports structural or content failures via ``SkippedManifest`` records
in ``LoadReport`` without raising; the exceptions here cover direct
lookup failures and programmer-facing API errors.
"""

from __future__ import annotations


class AdapterError(Exception):
    """Base for all adapter-related errors."""


class AdapterManifestNotFoundError(AdapterError):
    """Registry has no adapter matching the requested id."""

    def __init__(self, *, adapter_id: str) -> None:
        self.adapter_id = adapter_id
        super().__init__(f"Adapter {adapter_id!r} not found in registry")


class AdapterManifestCorruptedError(AdapterError):
    """Manifest file exists but fails load-time invariants.

    ``reason`` enumerates:
    - ``json_decode``: file is not valid JSON.
    - ``schema_invalid``: JSON does not conform to
      ``agent-adapter-contract.schema.v1.json``.
    - ``adapter_id_mismatch``: ``raw["adapter_id"]`` does not match the
      identifier derived from the filename (path-traversal / wrong-file
      defence).
    - ``read_error``: filesystem read failed (permissions, I/O).
    - ``not_an_object``: JSON top-level is not an object (e.g. array,
      scalar).
    - ``duplicate_adapter_id``: two or more manifests claim the same
      ``adapter_id``; deterministic loading rejects the later arrival.
    """

    _REASONS = frozenset({
        "json_decode",
        "schema_invalid",
        "adapter_id_mismatch",
        "read_error",
        "not_an_object",
        "duplicate_adapter_id",
    })

    def __init__(
        self,
        *,
        source_path: str,
        reason: str,
        details: str = "",
    ) -> None:
        self.source_path = source_path
        self.reason = reason
        self.details = details
        super().__init__(
            f"Adapter manifest at {source_path!r} corrupted "
            f"({reason}): {details}"
        )


class AdapterRegistryEmptyError(AdapterError):
    """Registry contains no adapters when one was required.

    Raised when callers need at least one registered adapter (e.g. for
    cross-reference validation of a workflow that declares
    ``expected_adapter_refs``) but the registry has not been populated.
    """

    def __init__(self) -> None:
        super().__init__(
            "AdapterRegistry is empty; workflow cross-references cannot be "
            "resolved. Populate via load_workspace() before cross-ref check."
        )
