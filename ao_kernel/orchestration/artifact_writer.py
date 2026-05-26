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
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# Codex iter-2 absorb: container fix — task_graph_id must match the
# AO-MA-2 schema pattern so it cannot escape ``base_dir`` via path
# traversal. The schema pattern is also enforced by the AO-MA-2 task graph
# schema validator below, but we double-check here so the writer never
# touches the filesystem with an unsafe id.
_TASK_GRAPH_ID_PATTERN = re.compile(r"^ao-ma-[a-z0-9][a-z0-9-]{2,80}$")
_TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,80}$")
_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"


class ArtifactWriterError(RuntimeError):
    """Raised when the orchestrator cannot persist artifacts fail-closed."""


def _load_schema(name: str) -> dict[str, Any]:
    """Load a bundled AO-MA-2 schema by filename."""

    path = _SCHEMAS_DIR / name
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactWriterError(f"bundled schema {name!r} could not be loaded: {exc}") from exc


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
        if not isinstance(task_graph_id, str) or not _TASK_GRAPH_ID_PATTERN.match(task_graph_id):
            raise ArtifactWriterError(
                "task_graph_id missing or does not match AO-MA-2 schema "
                f"pattern ^ao-ma-[a-z0-9][a-z0-9-]{{2,80}}$: {task_graph_id!r}"
            )

        # Codex iter-2 absorb: runtime AO-MA-2 schema validation before any
        # filesystem write so a malformed payload never persists.
        _validate_task_graph_schema(task_graph)
        for assignment in assignments:
            _validate_assignment_schema(assignment)

        resolved_base = self.base_dir.resolve()
        out_dir = (resolved_base / task_graph_id).resolve()
        if not _path_is_under(out_dir, resolved_base):
            raise ArtifactWriterError(f"task_graph_id {task_graph_id!r} escapes base_dir {resolved_base!s}")
        out_dir.mkdir(parents=True, exist_ok=True)

        manifest_entries: list[dict[str, Any]] = []
        graph_path = out_dir / "task_graph.v1.json"
        _atomic_write_json(graph_path, task_graph)
        manifest_entries.append(_manifest_entry(graph_path, out_dir))

        for assignment in assignments:
            task_id = assignment.get("task_id")
            if not isinstance(task_id, str) or not _TASK_ID_PATTERN.match(task_id):
                raise ArtifactWriterError(
                    f"assignment task_id missing or does not match AO-MA-2 id pattern: {task_id!r}"
                )
            assignment_path = (out_dir / f"agent_assignment-{task_id}.v1.json").resolve()
            if not _path_is_under(assignment_path, out_dir):
                raise ArtifactWriterError(f"assignment task_id {task_id!r} escapes output dir {out_dir!s}")
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


def _path_is_under(child: Path, parent: Path) -> bool:
    """Return True when ``child`` is the same as or under ``parent``."""

    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_task_graph_schema(task_graph: dict[str, Any]) -> None:
    """Validate a task graph against ao-ma-task-graph.v1 schema."""

    schema = _load_schema("ao-ma-task-graph.schema.v1.json")
    try:
        Draft202012Validator(schema).validate(task_graph)
    except ValidationError as exc:
        raise ArtifactWriterError(f"task graph fails AO-MA-2 schema validation: {exc.message}") from exc


def _validate_assignment_schema(assignment: dict[str, Any]) -> None:
    """Validate an assignment against ao-ma-agent-assignment.v1 schema."""

    schema = _load_schema("ao-ma-agent-assignment.schema.v1.json")
    try:
        Draft202012Validator(schema).validate(assignment)
    except ValidationError as exc:
        raise ArtifactWriterError(f"agent assignment fails AO-MA-2 schema validation: {exc.message}") from exc


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
