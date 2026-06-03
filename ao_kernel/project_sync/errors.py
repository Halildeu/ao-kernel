"""Typed exceptions for ao_kernel.project_sync.

All errors inherit from ProjectSyncError so callers can catch broadly while
still distinguishing failure modes when needed.
"""

from __future__ import annotations


class ProjectSyncError(Exception):
    """Base for all project-sync errors."""


class ProjectV2APIError(ProjectSyncError):
    """gh GraphQL or REST call failed (network, auth, schema, rate limit).

    The ``stderr`` attribute (if set) carries the gh CLI stderr payload so
    operators can inspect it without re-running the call.
    """

    def __init__(self, message: str, *, stderr: str | None = None) -> None:
        super().__init__(message)
        self.stderr = stderr


class ManifestDriftError(ProjectSyncError):
    """The repo manifest and GitHub state disagree.

    Raised only when ``--strict`` is set (or ``DriftHealer.heal`` is asked
    to enforce). Operators get the diff via the report payload.
    """


class FieldDerivationError(ProjectSyncError):
    """A required field could not be derived from issue metadata.

    Examples: missing ``epic-*`` label when an Epic field is required, body
    text lacking the ``Depends on #N`` clause, risk label out of allowed
    enum.
    """


class GhCliNotAvailableError(ProjectSyncError):
    """``gh`` CLI is not on PATH or is too old to support the GraphQL surface.

    The module shells out to ``gh`` rather than pulling httpx/requests in as
    new required dependencies (CLAUDE.md §12: no new required deps).
    """
