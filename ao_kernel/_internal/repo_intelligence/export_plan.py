"""Deterministic repo-intelligence root export planning.

RI-5a is a preview-only lane: it can inspect repo-intelligence artifacts and
write a plan under ``.ao/context`` but must never write root authority files.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ao_kernel._internal.repo_intelligence.artifacts import (
    AGENT_PACK_FILENAME,
    PYTHON_IMPORT_GRAPH_FILENAME,
    PYTHON_SYMBOL_INDEX_FILENAME,
    REPO_CHUNKS_FILENAME,
    REPO_MAP_FILENAME,
    REPO_VECTOR_INDEX_MANIFEST_FILENAME,
)
from ao_kernel._internal.shared.utils import now_iso8601

JsonDict = dict[str, Any]

CONFIRM_RI5B_ROOT_EXPORT = "CONFIRM_RI5B_ROOT_EXPORT_V1"
REPO_EXPORT_PLAN_GENERATOR = "ao-kernel-repo-export-planner"
REPO_EXPORT_PLAN_VERSION = "repo-export-plan.v1"


@dataclass(frozen=True)
class SourceArtifactSpec:
    source_id: str
    path: str
    required: bool


@dataclass(frozen=True)
class ExportTargetSpec:
    target: str
    root_path: str
    title: str
    content_source: str


SOURCE_ARTIFACT_SPECS: tuple[SourceArtifactSpec, ...] = (
    SourceArtifactSpec("repo_map", f".ao/context/{REPO_MAP_FILENAME}", True),
    SourceArtifactSpec("import_graph", f".ao/context/{PYTHON_IMPORT_GRAPH_FILENAME}", False),
    SourceArtifactSpec("symbol_index", f".ao/context/{PYTHON_SYMBOL_INDEX_FILENAME}", False),
    SourceArtifactSpec("repo_chunks", f".ao/context/{REPO_CHUNKS_FILENAME}", False),
    SourceArtifactSpec("agent_pack", f".ao/context/{AGENT_PACK_FILENAME}", True),
    SourceArtifactSpec(
        "repo_vector_index_manifest",
        f".ao/context/{REPO_VECTOR_INDEX_MANIFEST_FILENAME}",
        False,
    ),
)

DEFAULT_TARGET_SPECS: tuple[ExportTargetSpec, ...] = (
    ExportTargetSpec(
        target="codex",
        root_path="CODEX_CONTEXT.md",
        title="Codex Context",
        content_source="repo-intelligence-agent-pack.v1",
    ),
    ExportTargetSpec(
        target="agents",
        root_path="AGENTS.md",
        title="Agent Instructions",
        content_source="repo-intelligence-agent-pack.v1",
    ),
)


def supported_repo_export_targets() -> tuple[str, ...]:
    """Return supported RI-5a target ids in canonical output order."""
    return tuple(spec.target for spec in DEFAULT_TARGET_SPECS)


def build_repo_export_plan(
    *,
    project_root: str | Path,
    workspace_root: str | Path,
    targets: Sequence[str],
    target_specs: Sequence[ExportTargetSpec] = DEFAULT_TARGET_SPECS,
) -> JsonDict:
    """Build a deterministic RI-5a root export preview plan."""
    project = Path(project_root).resolve()
    workspace = Path(workspace_root).resolve()
    _ensure_valid_roots(project, workspace)

    requested_targets = _normalize_targets(targets, target_specs)
    source_artifacts = _source_artifact_records(project, workspace)
    missing_required = [
        record["path"]
        for record in source_artifacts.values()
        if bool(record["required"]) and not bool(record["present"])
    ]

    target_records: list[JsonDict] = []
    diagnostics: list[JsonDict] = []
    for spec in target_specs:
        if spec.target not in requested_targets:
            continue
        record = _target_record(
            project_root=project,
            workspace_root=workspace,
            spec=spec,
            source_artifacts=source_artifacts,
            missing_required=missing_required,
        )
        target_records.append(record)
        diagnostics.extend(
            {
                "code": item["code"],
                "severity": item["severity"],
                "target": spec.target,
                "message": item["message"],
            }
            for item in record["diagnostics"]
        )

    diagnostics.extend(
        {
            "code": "required_source_missing",
            "severity": "error",
            "source_path": path,
            "message": f"required source artifact is missing: {path}",
        }
        for path in missing_required
    )
    diagnostics.sort(key=lambda item: (str(item.get("code", "")), str(item.get("target", "")), str(item.get("source_path", ""))))

    plan: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "repo_export_plan",
        "generator": {
            "name": REPO_EXPORT_PLAN_GENERATOR,
            "version": REPO_EXPORT_PLAN_VERSION,
            "generated_at": now_iso8601(),
        },
        "project_root": ".",
        "project_root_name": project.name,
        "workspace_root": _display_workspace(project, workspace),
        "source_artifacts": source_artifacts,
        "targets": target_records,
        "confirmation": {
            "required_for_write": True,
            "token": CONFIRM_RI5B_ROOT_EXPORT,
            "scope": "RI-5b root authority writes only; RI-5a never writes root files.",
        },
        "summary": {
            "target_count": len(target_records),
            "create": sum(1 for item in target_records if item["action"] == "create"),
            "update": sum(1 for item in target_records if item["action"] == "update"),
            "unchanged": sum(1 for item in target_records if item["action"] == "unchanged"),
            "blocked": sum(1 for item in target_records if item["action"] == "blocked"),
            "missing_required_source_artifacts": len(missing_required),
        },
        "diagnostics": diagnostics,
    }
    return plan


def render_repo_export_target_content(
    *,
    target: str,
    title: str,
    source_artifacts: Mapping[str, Mapping[str, Any]],
) -> str:
    """Render deterministic preview content for a future RI-5b root file."""
    lines = [
        f"# {title}",
        "",
        "<!-- Generated preview by ao-kernel RI-5a. Do not write this file without RI-5b confirmation. -->",
        "",
        "## Generation Boundary",
        "",
        "- This content is preview-only.",
        "- RI-5a writes only `.ao/context/repo_export_plan.json`.",
        f"- Future root writes require `{CONFIRM_RI5B_ROOT_EXPORT}`.",
        "",
        "## Source Artifacts",
        "",
    ]
    for source_id in sorted(source_artifacts):
        record = source_artifacts[source_id]
        present = "present" if record["present"] else "missing"
        sha = record["sha256"] or "none"
        required = "required" if record["required"] else "optional"
        lines.append(f"- `{record['path']}`: {present}, {required}, sha256={sha}")
    lines.extend(
        [
            "",
            "## Target",
            "",
            f"- target: `{target}`",
            "- content_source: `repo-intelligence-agent-pack.v1`",
            "",
        ]
    )
    return "\n".join(lines)


def _ensure_valid_roots(project_root: Path, workspace_root: Path) -> None:
    if not project_root.is_dir():
        raise ValueError(f"project root not found: {project_root}")
    if not workspace_root.is_dir():
        raise ValueError(f".ao workspace not found at {workspace_root}. Run 'ao-kernel init' first.")
    try:
        workspace_root.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"workspace root must be inside project root: {workspace_root}") from exc


def _normalize_targets(
    targets: Sequence[str],
    target_specs: Sequence[ExportTargetSpec],
) -> set[str]:
    requested = {target.strip() for target in targets if target and target.strip()}
    if not requested:
        raise ValueError("at least one export-plan target is required")
    supported = {spec.target for spec in target_specs}
    unsupported = sorted(requested - supported)
    if unsupported:
        raise ValueError(f"unsupported export-plan target(s): {', '.join(unsupported)}")
    return requested


def _source_artifact_records(project_root: Path, workspace_root: Path) -> dict[str, JsonDict]:
    records: dict[str, JsonDict] = {}
    for spec in SOURCE_ARTIFACT_SPECS:
        path = _project_relative_path(project_root, workspace_root, spec.path)
        present = path.is_file() and not path.is_symlink()
        records[spec.source_id] = {
            "path": spec.path,
            "sha256": _sha256_file(path) if present else None,
            "required": spec.required,
            "present": present,
        }
    return records


def _target_record(
    *,
    project_root: Path,
    workspace_root: Path,
    spec: ExportTargetSpec,
    source_artifacts: Mapping[str, Mapping[str, Any]],
    missing_required: Sequence[str],
) -> JsonDict:
    diagnostics: list[JsonDict] = []
    target_path, target_path_error = _safe_target_path(project_root, spec.root_path)
    generated_content = render_repo_export_target_content(
        target=spec.target,
        title=spec.title,
        source_artifacts=source_artifacts,
    )
    generated_bytes = generated_content.encode("utf-8")
    existing_file = False
    existing_sha256: str | None = None
    action = "create"

    if target_path_error is not None:
        action = "blocked"
        diagnostics.append(_target_diagnostic("target_path_invalid", target_path_error))
    elif target_path is not None and target_path.is_symlink():
        action = "blocked"
        existing_file = True
        diagnostics.append(_target_diagnostic("target_path_symlink", f"{spec.root_path} is a symlink"))
    elif target_path is not None and target_path.exists() and not target_path.is_file():
        action = "blocked"
        existing_file = True
        diagnostics.append(_target_diagnostic("target_path_not_file", f"{spec.root_path} exists but is not a file"))
    elif target_path is not None and target_path.is_file():
        existing_file = True
        existing_sha256 = _sha256_file(target_path)
        if existing_sha256 == _sha256_bytes(generated_bytes):
            action = "unchanged"
        else:
            action = "blocked"
            diagnostics.append(
                _target_diagnostic(
                    "root_file_conflict",
                    f"{spec.root_path} already exists with different content",
                )
            )

    if missing_required:
        action = "blocked"
        for path in missing_required:
            diagnostics.append(_target_diagnostic("required_source_missing", f"required source artifact is missing: {path}"))

    diagnostics.sort(key=lambda item: (str(item["code"]), str(item["message"])))
    return {
        "target": spec.target,
        "root_path": spec.root_path,
        "action": action,
        "existing_file": existing_file,
        "existing_sha256": existing_sha256,
        "generated_content_sha256": _sha256_bytes(generated_bytes),
        "generated_byte_count": len(generated_bytes),
        "generated_line_count": generated_content.count("\n") + 1,
        "content_source": spec.content_source,
        "confirmation_token": CONFIRM_RI5B_ROOT_EXPORT,
        "diagnostics": diagnostics,
    }


def _project_relative_path(project_root: Path, workspace_root: Path, relative_path: str) -> Path:
    if relative_path.startswith(".ao/"):
        return workspace_root / relative_path.removeprefix(".ao/")
    return project_root / relative_path


def _safe_target_path(project_root: Path, relative_path: str) -> tuple[Path | None, str | None]:
    raw = Path(relative_path)
    if raw.is_absolute():
        return None, f"target path must be repo-relative: {relative_path}"
    if any(part == ".." for part in raw.parts):
        return None, f"target path must not escape project root: {relative_path}"
    return project_root / raw, None


def _target_diagnostic(code: str, message: str) -> JsonDict:
    return {
        "code": code,
        "severity": "error",
        "message": message,
    }


def _display_workspace(project_root: Path, workspace_root: Path) -> str:
    try:
        return workspace_root.relative_to(project_root).as_posix()
    except ValueError:
        return str(workspace_root)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
