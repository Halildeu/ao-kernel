"""Typed exceptions for ao-kernel."""

from __future__ import annotations


class WorkspaceNotFoundError(FileNotFoundError):
    """No workspace directory found (.ao/ or legacy)."""


class WorkspaceCorruptedError(ValueError):
    """Workspace exists but workspace.json is invalid or missing required fields."""


class DefaultsNotFoundError(FileNotFoundError):
    """A bundled default resource was not found in ao_kernel/defaults/."""
