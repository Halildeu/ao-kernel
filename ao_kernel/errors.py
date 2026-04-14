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
