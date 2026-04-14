"""Typed exceptions for ao-kernel."""

from __future__ import annotations


class WorkspaceNotFoundError(FileNotFoundError):
    """No workspace directory found (.ao/ or legacy)."""


class WorkspaceCorruptedError(ValueError):
    """Workspace exists but workspace.json is invalid or missing required fields."""


class DefaultsNotFoundError(FileNotFoundError):
    """A bundled default resource was not found in ao_kernel/defaults/."""


class SessionCorruptedError(RuntimeError):
    """Session context is corrupted or invalid — fail-closed.

    Raised when a session file exists but cannot be loaded (e.g. invalid JSON,
    schema mismatch, hash verification failure). Callers should decide whether
    to create a fresh session or propagate the error.
    """


class VectorStoreConfigError(ValueError):
    """Vector store configuration is invalid (missing DSN, bad backend name, etc.)."""


class VectorStoreConnectError(RuntimeError):
    """Vector store backend instantiation failed (connect error, driver missing).

    Only raised under strict mode. Non-strict mode falls back to deterministic
    ordering with a warning.
    """


class CanonicalStoreCorruptedError(RuntimeError):
    """Canonical decision store file exists but its contents cannot be trusted.

    Raised when the on-disk ``canonical_decisions.v1.json`` is unparseable
    or structurally invalid. Previously ``load_store`` silently returned
    an empty store — CNS-20260414-010 iter-2 flagged the silent-empty path
    as a data-loss hazard. Callers that want to recover from corruption
    should catch this exception explicitly and invoke a repair workflow
    (``ao-kernel doctor``, manual restore from evidence, etc.).
    """


class CanonicalRevisionConflict(RuntimeError):
    """A CAS write rejected because the store moved past ``expected_revision``.

    Raised by :func:`ao_kernel.context.canonical_store.save_store_cas` when
    the caller supplied an ``expected_revision`` that no longer matches
    the current store revision. Callers typically handle this by reading
    the current revision, re-applying their change on top, and retrying.
    """
