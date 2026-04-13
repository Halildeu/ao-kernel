"""ao_kernel.roadmap — Public roadmap execution facade.

Clean import path for governed change execution.

Usage:
    from ao_kernel.roadmap import compile_roadmap, apply_roadmap
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def compile_roadmap(
    roadmap_path: str | Path,
    *,
    workspace_root: str | Path,
    schema_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compile a roadmap file into an executable plan.

    Args:
        roadmap_path: Path to roadmap JSON file
        workspace_root: Workspace root directory
        schema_path: Optional schema for validation

    Returns compiled plan dict.
    """
    from ao_kernel._internal.roadmap.compiler import compile_roadmap as _compile
    from ao_kernel._internal.shared.resource_loader import load_resource_path

    ws = Path(workspace_root)
    rp = Path(roadmap_path)

    sp = Path(schema_path) if schema_path else load_resource_path("schemas", "roadmap.schema.json")
    if sp is None:
        # No schema found — compile without validation
        sp = ws / ".cache" / "schemas" / "roadmap.schema.json"

    result = _compile(
        roadmap_path=rp,
        schema_path=sp,
        cache_root=ws / ".cache",
    )
    return {
        "status": result.status,
        "plan_id": result.plan_id,
        "plan": result.plan,
        "plan_path": str(result.plan_path),
        "milestones_included": result.milestones_included,
    }


def apply_roadmap(
    roadmap_path: str | Path,
    *,
    workspace_root: str | Path,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Apply a roadmap. Default dry_run=True for safety.

    Args:
        roadmap_path: Path to roadmap JSON file
        workspace_root: Workspace root directory
        dry_run: If True, simulate only (default: True for fail-closed)
    """
    from ao_kernel._internal.roadmap.executor import apply_roadmap as _apply

    ws = Path(workspace_root)
    return _apply(
        roadmap_path=Path(roadmap_path),
        core_root=ws,
        workspace_root=ws,
        cache_root=ws / ".cache",
        evidence_root=ws / ".cache" / "evidence",
        dry_run=dry_run,
    )


__all__ = ["compile_roadmap", "apply_roadmap"]
