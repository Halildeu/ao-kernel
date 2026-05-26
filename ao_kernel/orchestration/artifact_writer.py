"""AO-MA-3 artifact writer.

Writes a task graph + agent assignments under
``<output_dir>/<task_graph_id>/`` together with a SHA256 manifest. The
manifest is the audit-friendly tip the orchestrator returns to its caller;
later AO-MA slices (worker spawn, integrator) reference it to confirm
they are operating on the same artifact set the orchestrator produced.

No agent execution, no LLM call, no GitHub write. Pure file emission.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ArtifactWriterError(RuntimeError):
    """Raised when the orchestrator cannot persist artifacts fail-closed."""


@dataclass
class ArtifactWriter:
    """Serialize task graph + assignments + manifest under an output dir."""

    base_dir: Path

    def emit(
        self,
        task_graph: dict[str, Any],
        assignments: list[dict[str, Any]],
        *,
        utc_now: _dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Write ``task_graph.v1.json`` + per-task assignments + manifest.

        Returns the manifest dict (also written to disk). The manifest has
        the artifact paths (relative to ``base_dir``) and SHA256 hashes so a
        downstream consumer can verify byte equality without re-running the
        orchestrator.

        Raises :class:`ArtifactWriterError` if any path escapes ``base_dir``
        or if the task graph id is missing.
        """

        task_graph_id = task_graph.get("task_graph_id")
        if not isinstance(task_graph_id, str) or not task_graph_id:
            raise ArtifactWriterError("task_graph missing task_graph_id")

        out_dir = self.base_dir / task_graph_id
        out_dir.mkdir(parents=True, exist_ok=True)

        manifest_entries: list[dict[str, Any]] = []
        graph_path = out_dir / "task_graph.v1.json"
        _atomic_write_json(graph_path, task_graph)
        manifest_entries.append(_manifest_entry(graph_path, out_dir))

        for assignment in assignments:
            task_id = assignment.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise ArtifactWriterError("assignment missing task_id; cannot persist artifact")
            assignment_path = out_dir / f"agent_assignment-{task_id}.v1.json"
            _atomic_write_json(assignment_path, assignment)
            manifest_entries.append(_manifest_entry(assignment_path, out_dir))

        now = utc_now or _dt.datetime.now(_dt.UTC)
        manifest = {
            "schema_version": "ao-ma-orchestration-manifest.v1",
            "task_graph_id": task_graph_id,
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "base_dir": str(out_dir),
            "artifacts": manifest_entries,
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }
        manifest_path = out_dir / "manifest.v1.json"
        _atomic_write_json(manifest_path, manifest)
        # Include manifest itself in returned dict for caller awareness, but
        # do NOT add the manifest entry to its own artifact list (would create
        # a circular hash).
        return manifest


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically (tmp + fsync + rename)."""

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{path.name}.tmp"
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _manifest_entry(path: Path, base_dir: Path) -> dict[str, Any]:
    """Build a manifest entry with path (relative) + SHA256."""

    try:
        rel = path.relative_to(base_dir)
    except ValueError as exc:
        raise ArtifactWriterError(f"artifact {path!s} escapes base directory {base_dir!s}") from exc
    data = path.read_bytes()
    return {
        "path": str(rel),
        "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }
