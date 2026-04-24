"""Confirmed create-only root exports for repo-intelligence artifacts.

RI-5b is intentionally narrow: it consumes the existing RI-5a
``.ao/context/repo_export_plan.json`` artifact, requires an exact confirmation
token, acquires path-scoped write ownership, and writes only absent supported
root files. It never recomputes a hidden plan, overwrites root files, calls an
LLM, talks to the network, or exposes MCP write behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from ao_kernel._internal.repo_intelligence.artifacts import (
    REPO_EXPORT_PLAN_FILENAME,
    validate_repo_export_plan,
    validate_repo_root_export_result,
)
from ao_kernel._internal.repo_intelligence.export_plan import (
    CONFIRM_RI5B_ROOT_EXPORT,
    DEFAULT_TARGET_SPECS,
    ExportTargetSpec,
    render_repo_export_target_content,
    supported_repo_export_targets,
)
from ao_kernel._internal.shared.utils import sha256_file, sha256_text, write_text_atomic
from ao_kernel.coordination import (
    ClaimRegistry,
    PathWriteLeaseSet,
    acquire_path_write_claims,
    load_coordination_policy,
    release_path_write_claims,
)


JsonDict = dict[str, Any]
_OWNER_AGENT_ID = "ao-kernel-ri5b-root-export"
_SUPPORTED_SPECS = {spec.target: spec for spec in DEFAULT_TARGET_SPECS}


class RepoRootExportError(ValueError):
    """Raised when confirmed root export must fail closed before writing."""


@dataclass(frozen=True)
class _TargetCandidate:
    target: str
    root_path: str
    path: Path
    action: str
    content: str
    generated_sha256: str
    generated_byte_count: int
    before: JsonDict


def export_repo_roots(
    *,
    project_root: str | Path,
    workspace_root: str | Path,
    targets: Sequence[str],
    confirm_root_export: str,
    owner_agent_id: str = _OWNER_AGENT_ID,
) -> JsonDict:
    """Perform an explicitly confirmed create-only root export.

    The function validates all requested targets and acquires all write claims
    before any root file write. Failures raise :class:`RepoRootExportError` and
    leave root authority files untouched except for best-effort rollback if an
    unexpected write/verify failure occurs after claims are acquired.
    """
    project = Path(project_root).resolve()
    workspace = Path(workspace_root).resolve()
    _ensure_roots(project, workspace)

    requested_targets = _normalize_targets(targets)
    if confirm_root_export != CONFIRM_RI5B_ROOT_EXPORT:
        raise RepoRootExportError(
            f"exact confirmation token required: {CONFIRM_RI5B_ROOT_EXPORT}"
        )

    plan_path = workspace / "context" / REPO_EXPORT_PLAN_FILENAME
    plan = _load_plan(plan_path)
    _verify_plan_identity(plan, project, workspace)
    _verify_source_artifacts(project, workspace, plan)

    candidates = _build_candidates(project, plan, requested_targets)
    _preflight_candidates(candidates)

    registry = ClaimRegistry(project)
    policy = load_coordination_policy(project)
    lease_set: PathWriteLeaseSet | None = None
    written: list[_TargetCandidate] = []
    ownership_by_path: dict[str, JsonDict] = {}
    try:
        try:
            lease_set = acquire_path_write_claims(
                registry,
                project,
                owner_agent_id=owner_agent_id,
                paths=[candidate.root_path for candidate in candidates],
                policy=policy,
            )
        except Exception as exc:
            detail = str(exc) or exc.__class__.__name__
            raise RepoRootExportError(f"path ownership unavailable: {detail}") from exc
        ownership_by_path = _ownership_payload_by_path(lease_set)
        _preflight_candidates(candidates)
        for candidate in candidates:
            if candidate.action == "unchanged":
                continue
            write_text_atomic(candidate.path, candidate.content)
            written.append(candidate)
        result = _build_result(
            project=project,
            workspace=workspace,
            plan_path=plan_path,
            candidates=candidates,
            ownership_by_path=ownership_by_path,
        )
        validate_repo_root_export_result(result)
        return result
    except Exception:
        _rollback_created_files(written)
        raise
    finally:
        if lease_set is not None:
            release_path_write_claims(registry, lease_set)


def _ensure_roots(project: Path, workspace: Path) -> None:
    if not project.is_dir():
        raise RepoRootExportError(f"project root not found: {project}")
    if not workspace.is_dir():
        raise RepoRootExportError(
            f".ao workspace not found at {workspace}. Run 'ao-kernel init' first."
        )
    try:
        workspace.relative_to(project)
    except ValueError as exc:
        raise RepoRootExportError(
            f"workspace root must be inside project root: {workspace}"
        ) from exc


def _normalize_targets(targets: Sequence[str]) -> tuple[str, ...]:
    requested = tuple(dict.fromkeys(target.strip() for target in targets if target.strip()))
    if not requested:
        raise RepoRootExportError("at least one explicit root export target is required")
    supported = set(supported_repo_export_targets())
    unsupported = sorted(set(requested) - supported)
    if unsupported:
        raise RepoRootExportError(
            f"unsupported root export target(s): {', '.join(unsupported)}"
        )
    return requested


def _load_plan(plan_path: Path) -> JsonDict:
    if plan_path.is_symlink():
        raise RepoRootExportError(f"repo export plan must not be a symlink: {plan_path}")
    if not plan_path.is_file():
        raise RepoRootExportError(f"repo export plan not found: {plan_path}")
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        validate_repo_export_plan(plan)
    except Exception as exc:
        raise RepoRootExportError(f"repo export plan is invalid: {exc}") from exc
    return dict(plan)


def _verify_plan_identity(plan: Mapping[str, Any], project: Path, workspace: Path) -> None:
    if plan.get("project_root") != ".":
        raise RepoRootExportError("repo export plan project_root must be '.'")
    expected_workspace = _display_workspace(project, workspace)
    if plan.get("workspace_root") != expected_workspace:
        raise RepoRootExportError(
            "repo export plan workspace_root does not match requested workspace"
        )
    confirmation = plan.get("confirmation") or {}
    if confirmation.get("token") != CONFIRM_RI5B_ROOT_EXPORT:
        raise RepoRootExportError("repo export plan confirmation token is invalid")


def _verify_source_artifacts(project: Path, workspace: Path, plan: Mapping[str, Any]) -> None:
    source_artifacts = plan.get("source_artifacts")
    if not isinstance(source_artifacts, Mapping):
        raise RepoRootExportError("repo export plan source_artifacts must be an object")
    for source_id, raw_record in source_artifacts.items():
        if not isinstance(raw_record, Mapping):
            raise RepoRootExportError(f"source artifact {source_id!s} is invalid")
        display_path = str(raw_record.get("path") or "")
        path = _resolve_source_path(project, workspace, display_path)
        expected_present = bool(raw_record.get("present"))
        actual_present = path.is_file() and not path.is_symlink()
        if actual_present != expected_present:
            raise RepoRootExportError(
                f"source artifact stale: {display_path} presence changed"
            )
        if bool(raw_record.get("required")) and not actual_present:
            raise RepoRootExportError(
                f"required source artifact is missing: {display_path}"
            )
        expected_sha = raw_record.get("sha256")
        if actual_present and sha256_file(path) != expected_sha:
            raise RepoRootExportError(
                f"source artifact stale: {display_path} digest changed"
            )


def _build_candidates(
    project: Path,
    plan: Mapping[str, Any],
    requested_targets: Sequence[str],
) -> list[_TargetCandidate]:
    target_records = plan.get("targets")
    if not isinstance(target_records, list):
        raise RepoRootExportError("repo export plan targets must be an array")
    by_target: dict[str, Mapping[str, Any]] = {}
    for raw_target in target_records:
        if isinstance(raw_target, Mapping):
            by_target[str(raw_target.get("target"))] = raw_target

    candidates: list[_TargetCandidate] = []
    source_artifacts = plan["source_artifacts"]
    for target in requested_targets:
        record = by_target.get(target)
        if record is None:
            raise RepoRootExportError(f"target {target!r} is absent from repo export plan")
        spec = _SUPPORTED_SPECS[target]
        candidates.append(_candidate_from_record(project, spec, record, source_artifacts))
    return candidates


def _candidate_from_record(
    project: Path,
    spec: ExportTargetSpec,
    record: Mapping[str, Any],
    source_artifacts: Mapping[str, Mapping[str, Any]],
) -> _TargetCandidate:
    root_path = str(record.get("root_path") or "")
    path = _resolve_target_path(project, root_path)
    if root_path != spec.root_path:
        raise RepoRootExportError(
            f"target {spec.target!r} root_path does not match supported path {spec.root_path}"
        )
    if record.get("content_source") != spec.content_source:
        raise RepoRootExportError(f"target {spec.target!r} content_source is invalid")
    if record.get("confirmation_token") != CONFIRM_RI5B_ROOT_EXPORT:
        raise RepoRootExportError(f"target {spec.target!r} confirmation token is invalid")

    action = str(record.get("action") or "")
    if action == "blocked":
        raise RepoRootExportError(f"target {spec.target!r} is blocked in repo export plan")
    if action == "update":
        raise RepoRootExportError(
            f"target {spec.target!r} requires update; RI-5b first slice is create-only"
        )
    if action not in {"create", "unchanged"}:
        raise RepoRootExportError(f"target {spec.target!r} action is invalid: {action}")

    content = render_repo_export_target_content(
        target=spec.target,
        title=spec.title,
        source_artifacts=source_artifacts,
    )
    generated_sha = sha256_text(content)
    if record.get("generated_content_sha256") != generated_sha:
        raise RepoRootExportError(
            f"target {spec.target!r} generated content digest is stale"
        )

    return _TargetCandidate(
        target=spec.target,
        root_path=root_path,
        path=path,
        action=action,
        content=content,
        generated_sha256=generated_sha,
        generated_byte_count=len(content.encode("utf-8")),
        before=_snapshot(path),
    )


def _preflight_candidates(candidates: Sequence[_TargetCandidate]) -> None:
    for candidate in candidates:
        if candidate.path.is_symlink():
            raise RepoRootExportError(f"target {candidate.root_path} is a symlink")
        if candidate.path.exists() and not candidate.path.is_file():
            raise RepoRootExportError(
                f"target {candidate.root_path} exists but is not a file"
            )
        if candidate.action == "create" and candidate.path.exists():
            raise RepoRootExportError(
                f"target {candidate.root_path} now exists; rebuild export plan"
            )
        if candidate.action == "unchanged":
            snapshot = _snapshot(candidate.path)
            if snapshot["sha256"] != candidate.generated_sha256:
                raise RepoRootExportError(
                    f"target {candidate.root_path} is no longer unchanged"
                )


def _build_result(
    *,
    project: Path,
    workspace: Path,
    plan_path: Path,
    candidates: Sequence[_TargetCandidate],
    ownership_by_path: Mapping[str, JsonDict],
) -> JsonDict:
    target_results: list[JsonDict] = []
    for candidate in candidates:
        after = _snapshot(candidate.path)
        if after["sha256"] != candidate.generated_sha256:
            raise RepoRootExportError(
                f"target {candidate.root_path} post-write verification failed"
            )
        result = "unchanged" if candidate.action == "unchanged" else "written"
        target_results.append(
            {
                "target": candidate.target,
                "root_path": candidate.root_path,
                "action_from_plan": candidate.action,
                "result": result,
                "deny_code": None,
                "message": (
                    "root file already matched generated content"
                    if result == "unchanged"
                    else "root file created from confirmed export plan"
                ),
                "before": candidate.before,
                "after": after,
                "generated_content_sha256": candidate.generated_sha256,
                "generated_byte_count": candidate.generated_byte_count,
                "ownership": ownership_by_path[candidate.root_path],
            }
        )

    return {
        "schema_version": "1",
        "artifact_kind": "repo_root_export_result",
        "project_root": ".",
        "workspace_root": _display_workspace(project, workspace),
        "plan_path": _display_path(project, plan_path),
        "confirmation": {
            "required_token": CONFIRM_RI5B_ROOT_EXPORT,
            "provided": True,
            "accepted": True,
        },
        "targets": target_results,
        "summary": {
            "target_count": len(target_results),
            "written_count": sum(1 for item in target_results if item["result"] == "written"),
            "unchanged_count": sum(1 for item in target_results if item["result"] == "unchanged"),
            "denied_count": 0,
            "skipped_count": 0,
        },
        "support_widening": False,
    }


def _ownership_payload_by_path(lease_set: PathWriteLeaseSet) -> dict[str, JsonDict]:
    by_path: dict[str, JsonDict] = {}
    for lease in lease_set.leases:
        payload = {
            "required": True,
            "status": "released",
            "resource_id": lease.scope.resource_id,
            "claim_id": lease.claim.claim_id,
            "fencing_token": lease.claim.fencing_token,
        }
        for path in lease.scope.paths:
            by_path[path] = payload
    return by_path


def _rollback_created_files(written: Sequence[_TargetCandidate]) -> None:
    for candidate in reversed(written):
        if candidate.before["exists"]:
            continue
        if not candidate.path.is_file():
            continue
        if sha256_file(candidate.path) == candidate.generated_sha256:
            candidate.path.unlink()


def _resolve_source_path(project: Path, workspace: Path, display_path: str) -> Path:
    relative = _safe_relative_path(display_path)
    if relative.parts[:1] == (".ao",):
        tail = Path(*relative.parts[1:])
        return (workspace / tail).resolve()
    return (project / Path(*relative.parts)).resolve()


def _resolve_target_path(project: Path, display_path: str) -> Path:
    relative = _safe_relative_path(display_path)
    raw_candidate = project / Path(*relative.parts)
    candidate = raw_candidate.parent.resolve(strict=False) / raw_candidate.name
    try:
        candidate.relative_to(project)
    except ValueError as exc:
        raise RepoRootExportError(
            f"target path escapes project root: {display_path}"
        ) from exc
    return candidate


def _safe_relative_path(display_path: str) -> PurePosixPath:
    if not display_path:
        raise RepoRootExportError("path must not be empty")
    path = PurePosixPath(display_path)
    if path.is_absolute():
        raise RepoRootExportError(f"path must be repo-relative: {display_path}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise RepoRootExportError(f"path must not escape project root: {display_path}")
    return path


def _snapshot(path: Path) -> JsonDict:
    return {
        "exists": path.is_file() and not path.is_symlink(),
        "sha256": sha256_file(path) if path.is_file() and not path.is_symlink() else None,
    }


def _display_workspace(project: Path, workspace: Path) -> str:
    try:
        return workspace.relative_to(project).as_posix()
    except ValueError:
        return str(workspace)


def _display_path(project: Path, path: Path) -> str:
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return str(path)
