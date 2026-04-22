"""Path-scoped write ownership helpers built on top of ``ClaimRegistry``.

This module does not introduce a second coordination system. It projects
workspace paths onto the existing claim/fencing runtime so callers can claim
write ownership over path *areas* using the same SSOT, evidence, takeover and
fencing machinery already shipped in :mod:`ao_kernel.coordination`.

v1 scope model:

- Granularity is **top-level area** (same signal model as ``ops overlap-check``).
- Multiple paths under the same top-level area map to the same resource id.
- Multi-area acquisition is **sequential, not atomic**. If one later acquire
  fails, earlier acquired claims are released best-effort in reverse order.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from ao_kernel.coordination.claim import Claim
from ao_kernel.coordination.policy import CoordinationPolicy
from ao_kernel.coordination.registry import ClaimRegistry


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PathWriteScope:
    """Canonical top-level write scope for one or more workspace paths."""

    area: str
    resource_id: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class PathWriteLease:
    """A claimed path scope together with the underlying coordination claim."""

    scope: PathWriteScope
    claim: Claim


@dataclass(frozen=True)
class PathWriteLeaseSet:
    """Sequentially acquired write-scope leases for one owner agent."""

    owner_agent_id: str
    leases: tuple[PathWriteLease, ...]


def _project_root(workspace_root: Path | str) -> Path:
    """Accept either project root or ``.ao`` workspace dir and return project root."""
    resolved = Path(workspace_root).resolve()
    if resolved.name == ".ao":
        return resolved.parent
    return resolved


def _ensure_matching_registry_root(
    registry: ClaimRegistry,
    workspace_root: Path | str,
) -> Path:
    """Fail closed when helper inputs point at different project roots."""
    helper_root = _project_root(workspace_root)
    registry_root = _project_root(registry._workspace_root)
    if helper_root != registry_root:
        raise ValueError(
            "workspace_root does not match ClaimRegistry workspace root: "
            f"{helper_root!s} != {registry_root!s}"
        )
    return helper_root


def normalize_workspace_relative_path(
    workspace_root: Path | str,
    path: Path | str,
) -> str:
    """Return a canonical workspace-relative POSIX path.

    ``workspace_root`` may be either the project root or the ``.ao`` directory.
    ``path`` may be absolute or relative. Absolute paths must stay under the
    project root after resolution; relative paths are resolved under it.
    """
    project_root = _project_root(workspace_root)
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()

    try:
        relative = resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(
            f"path {candidate!s} resolves outside project root {project_root!s}"
        ) from exc

    relative_posix = PurePosixPath(relative.as_posix())
    if not relative_posix.parts:
        raise ValueError("path must point to a file or directory under the project root")
    if any(part in {"", ".", ".."} for part in relative_posix.parts):
        raise ValueError(
            f"path {candidate!s} does not normalize to a stable workspace-relative path"
        )
    return relative_posix.as_posix()


def top_level_write_area(relative_path: str) -> str:
    """Return the v1 write-ownership area for a workspace-relative path."""
    path = PurePosixPath(relative_path)
    if not path.parts:
        raise ValueError("relative_path must not be empty")
    return path.parts[0]


def build_path_write_resource_id(area: str) -> str:
    """Build a deterministic, validator-safe resource id for a write area.

    Human readability matters for audits, but the id also must be collision-safe
    for arbitrary directory names. We therefore combine a readable slug with a
    short content hash of the original area string.
    """
    if not area:
        raise ValueError("area must not be empty")

    slug_chars: list[str] = []
    for ch in area:
        if ch.isascii() and (ch.isalnum() or ch in "._-"):
            slug_chars.append(ch)
        else:
            slug_chars.append("_")
    slug = "".join(slug_chars).strip("._-")
    if not slug:
        slug = "area"

    digest = hashlib.sha256(area.encode("utf-8")).hexdigest()[:12]
    return f"write-area.{slug}.{digest}"


def build_path_write_scopes(
    workspace_root: Path | str,
    paths: Iterable[Path | str],
) -> tuple[PathWriteScope, ...]:
    """Group paths into deterministic top-level-area write scopes."""
    grouped: dict[str, set[str]] = {}
    for path in paths:
        relative = normalize_workspace_relative_path(workspace_root, path)
        area = top_level_write_area(relative)
        grouped.setdefault(area, set()).add(relative)

    if not grouped:
        raise ValueError("at least one path is required to build write scopes")

    scopes = [
        PathWriteScope(
            area=area,
            resource_id=build_path_write_resource_id(area),
            paths=tuple(sorted(relative_paths)),
        )
        for area, relative_paths in grouped.items()
    ]
    return tuple(sorted(scopes, key=lambda item: (item.area, item.resource_id)))


def acquire_path_write_claims(
    registry: ClaimRegistry,
    workspace_root: Path | str,
    *,
    owner_agent_id: str,
    paths: Iterable[Path | str],
    policy: CoordinationPolicy | None = None,
) -> PathWriteLeaseSet:
    """Acquire write ownership for the top-level areas covering ``paths``.

    Acquisition is sequential and sorted by area/resource_id for deterministic
    lock ordering across callers. If a later acquire fails, already-acquired
    scopes are released best-effort in reverse order and the original exception
    is re-raised.
    """
    project_root = _ensure_matching_registry_root(registry, workspace_root)
    scopes = build_path_write_scopes(project_root, paths)
    acquired: list[PathWriteLease] = []

    try:
        for scope in scopes:
            claim = registry.acquire_claim(
                scope.resource_id,
                owner_agent_id,
                policy,
            )
            acquired.append(PathWriteLease(scope=scope, claim=claim))
    except Exception:
        for lease in reversed(acquired):
            try:
                registry.release_claim(
                    lease.scope.resource_id,
                    lease.claim.claim_id,
                    owner_agent_id,
                )
            except Exception as rollback_exc:
                logger.warning(
                    "path ownership rollback release failed: resource_id=%s owner=%s cause=%r",
                    lease.scope.resource_id,
                    owner_agent_id,
                    rollback_exc,
                    extra={
                        "resource_id": lease.scope.resource_id,
                        "owner_agent_id": owner_agent_id,
                        "cause": repr(rollback_exc),
                    },
                )
        raise

    return PathWriteLeaseSet(
        owner_agent_id=owner_agent_id,
        leases=tuple(acquired),
    )


def release_path_write_claims(
    registry: ClaimRegistry,
    lease_set: PathWriteLeaseSet,
) -> None:
    """Release path write claims in reverse acquisition order."""
    for lease in reversed(lease_set.leases):
        registry.release_claim(
            lease.scope.resource_id,
            lease.claim.claim_id,
            lease_set.owner_agent_id,
        )
