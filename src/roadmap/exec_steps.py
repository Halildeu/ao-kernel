from __future__ import annotations
from src.shared.utils import write_json_atomic, write_text_atomic

import difflib
import fnmatch
import json
import os
from pathlib import Path
from typing import Any

from src.roadmap.exec_contracts import ChangeCounter, _CoreImmutabilityPolicy, _ExecutionState
from src.roadmap.exec_evidence import _git_status_porcelain, _normalize_rel_path, _now_iso8601, _snapshot_tree
from src.roadmap.step_templates import (
    RoadmapStepError,
    VirtualFS,
    step_add_ci_gate_script,
    step_add_schema_file,
    step_assert_core_paths_exist,
    step_assert_pointer_target_exists,
    step_assert_paths_exist,
    step_create_file,
    step_create_json_from_template,
    step_ensure_dir,
    step_iso_core_check,
    step_patch_file,
    step_patch_policy_report_inject,
    step_run_cmd,
)
from src.roadmap.evidence import write_step_evidence


def _count_diff_lines(old: str, new: str) -> int:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="a", tofile="b", n=0)
    count = 0
    for line in diff:
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def _validate_plan_shape(plan: Any) -> None:
    if not isinstance(plan, dict):
        raise ValueError("PLAN_INVALID: plan must be an object")
    if plan.get("version") != "v1":
        raise ValueError("PLAN_INVALID: plan.version must be v1")
    if not isinstance(plan.get("roadmap_id"), str) or not plan.get("roadmap_id"):
        raise ValueError("PLAN_INVALID: missing roadmap_id")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("PLAN_INVALID: steps must be a non-empty list")
    for st in steps:
        if not isinstance(st, dict):
            raise ValueError("PLAN_INVALID: step entry must be object")
        if not isinstance(st.get("step_id"), str) or not st.get("step_id"):
            raise ValueError("PLAN_INVALID: step_id missing")
        if not isinstance(st.get("milestone_id"), str) or not st.get("milestone_id"):
            raise ValueError("PLAN_INVALID: milestone_id missing")
        if not isinstance(st.get("phase"), str) or not st.get("phase"):
            raise ValueError("PLAN_INVALID: phase missing")
        tpl = st.get("template")
        if not isinstance(tpl, dict) or not isinstance(tpl.get("type"), str):
            raise ValueError("PLAN_INVALID: template.type missing")


def _readonly_cmd_allowlisted(cmd: str) -> bool:
    import shlex

    try:
        argv = shlex.split(cmd)
    except Exception:
        return False

    allowlisted = [
        ["python", "ci/validate_schemas.py"],
        ["python", "-m", "src.ops.manage", "smoke", "--level", "fast"],
        ["python", "-m", "src.ops.manage", "policy-check", "--source", "fixtures"],
        ["python", "ci/check_script_budget.py", "--out", ".cache/script_budget/report.json"],
    ]
    return any(argv == allowed for allowed in allowlisted)


def _load_core_immutability_policy(*, core_root: Path, workspace_root: Path) -> _CoreImmutabilityPolicy:
    defaults = _CoreImmutabilityPolicy(
        enabled=True,
        default_mode="locked",
        allow_env_var="CORE_UNLOCK",
        allow_env_value="1",
        core_write_mode="locked",
        ssot_write_allowlist=tuple(),
        require_unlock_reason=False,
        evidence_required_when_unlocked=True,
        blocked_write_error_code="CORE_IMMUTABLE_WRITE_BLOCKED",
        core_git_required=True,
    )
    ws_policy = workspace_root / "policies" / "policy_core_immutability.v1.json"
    core_policy = core_root / "policies" / "policy_core_immutability.v1.json"
    policy_path = ws_policy if ws_policy.exists() else core_policy
    if not policy_path.exists():
        return defaults
    try:
        obj = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if not isinstance(obj, dict):
        return defaults
    override_path = workspace_root / ".cache" / "policy_overrides" / "policy_core_immutability.override.v1.json"
    if override_path.exists():
        try:
            override_obj = json.loads(override_path.read_text(encoding="utf-8"))
        except Exception:
            override_obj = {}
        if isinstance(override_obj, dict):
            override_allowlist = override_obj.get("ssot_write_allowlist")
            if isinstance(override_allowlist, list):
                obj = dict(obj)
                obj["ssot_write_allowlist"] = override_allowlist
    enabled = bool(obj.get("enabled", defaults.enabled))
    default_mode = obj.get("default_mode", defaults.default_mode)
    if default_mode not in {"locked"}:
        default_mode = defaults.default_mode
    allow_obj = obj.get("allow_core_writes_only_when", {})
    if not isinstance(allow_obj, dict):
        allow_obj = {}
    allow_env_var = allow_obj.get("env_var", defaults.allow_env_var)
    allow_env_value = allow_obj.get("env_value", defaults.allow_env_value)
    if not isinstance(allow_env_var, str) or not allow_env_var.strip():
        allow_env_var = defaults.allow_env_var
    if not isinstance(allow_env_value, str) or not allow_env_value.strip():
        allow_env_value = defaults.allow_env_value
    core_write_mode = obj.get("core_write_mode", defaults.core_write_mode)
    if core_write_mode not in {"locked", "ssot_only_when_unlocked"}:
        core_write_mode = defaults.core_write_mode
    raw_allowlist = obj.get("ssot_write_allowlist", list(defaults.ssot_write_allowlist))
    if not isinstance(raw_allowlist, list):
        raw_allowlist = list(defaults.ssot_write_allowlist)
    ssot_write_allowlist = tuple(sorted({str(x) for x in raw_allowlist if isinstance(x, str) and x.strip()}))
    require_unlock_reason = bool(obj.get("require_unlock_reason", defaults.require_unlock_reason))
    evidence_required_when_unlocked = bool(
        obj.get("evidence_required_when_unlocked", defaults.evidence_required_when_unlocked)
    )
    blocked_write_error_code = obj.get("blocked_write_error_code", defaults.blocked_write_error_code)
    if not isinstance(blocked_write_error_code, str) or not blocked_write_error_code.strip():
        blocked_write_error_code = defaults.blocked_write_error_code
    core_git_required = bool(obj.get("core_git_required", defaults.core_git_required))
    return _CoreImmutabilityPolicy(
        enabled=enabled,
        default_mode=str(default_mode),
        allow_env_var=str(allow_env_var),
        allow_env_value=str(allow_env_value),
        core_write_mode=str(core_write_mode),
        ssot_write_allowlist=ssot_write_allowlist,
        require_unlock_reason=require_unlock_reason,
        evidence_required_when_unlocked=evidence_required_when_unlocked,
        blocked_write_error_code=str(blocked_write_error_code),
        core_git_required=core_git_required,
    )


def _core_unlock_requested(policy: _CoreImmutabilityPolicy) -> bool:
    unlock_ok = str(os.environ.get(policy.allow_env_var, "")).strip() == str(policy.allow_env_value)
    if not unlock_ok:
        return False
    if policy.require_unlock_reason:
        return bool(str(os.environ.get("CORE_UNLOCK_REASON", "")).strip())
    return True


def _get_counter(counters_by_milestone: dict[str, ChangeCounter], ms_id: str) -> ChangeCounter:
    if ms_id not in counters_by_milestone:
        counters_by_milestone[ms_id] = ChangeCounter(paths_touched=set(), diff_lines=0)
    return counters_by_milestone[ms_id]


def _is_write_allowed(write_allowlist: list[str] | None, rel_path: str) -> bool:
    if write_allowlist is None:
        return True
    p = _normalize_rel_path(Path(rel_path).as_posix())
    for pref in write_allowlist:
        pref_s = str(pref).strip().replace("\\", "/").strip("/")
        if not pref_s:
            continue
        if p == pref_s or p.startswith(pref_s + "/"):
            return True
    return False


def _is_ssot_write_allowed(allowlist: tuple[str, ...], rel_path: str) -> bool:
    if not allowlist:
        return False
    p = _normalize_rel_path(Path(rel_path).as_posix())
    for pref in allowlist:
        pref_s = str(pref).strip().replace("\\", "/").strip("/")
        if not pref_s:
            continue
        if p == pref_s or p.startswith(pref_s + "/"):
            return True
    return False


def _collect_milestone_constraints(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    milestone_constraints: dict[str, dict[str, Any]] = {}
    milestones = plan.get("milestones", [])
    for ms in milestones if isinstance(milestones, list) else []:
        if not isinstance(ms, dict):
            continue
        ms_id = ms.get("id")
        constraints = ms.get("constraints") if isinstance(ms.get("constraints"), dict) else {}
        if isinstance(ms_id, str):
            milestone_constraints[ms_id] = constraints
    return milestone_constraints


def _constraints_for_step(
    milestone_constraints: dict[str, dict[str, Any]], ms_id: str
) -> tuple[list[str], int | None, int | None, dict[str, Any]]:
    constraints = milestone_constraints.get(ms_id, {})
    forbidden_raw = constraints.get("forbidden_paths") if isinstance(constraints.get("forbidden_paths"), list) else []
    forbidden = [str(x) for x in forbidden_raw]
    max_files_changed = constraints.get("max_files_changed") if isinstance(constraints.get("max_files_changed"), int) else None
    max_diff_lines = constraints.get("max_diff_lines") if isinstance(constraints.get("max_diff_lines"), int) else None
    return (forbidden, max_files_changed, max_diff_lines, constraints)


def _enforce_milestone_caps(
    *, counter: ChangeCounter, ms_id: str, max_files_changed: int | None, max_diff_lines: int | None
) -> None:
    if isinstance(max_files_changed, int) and len(counter.paths_touched) > max_files_changed:
        raise RoadmapStepError("MAX_FILES_CHANGED", f"Exceeded max_files_changed={max_files_changed} for milestone {ms_id}")
    if isinstance(max_diff_lines, int) and counter.diff_lines > max_diff_lines:
        raise RoadmapStepError("MAX_DIFF_LINES", f"Exceeded max_diff_lines={max_diff_lines} for milestone {ms_id}")


def _handle_note_step(*, tpl: dict[str, Any]) -> tuple[dict[str, Any], str]:
    text = tpl.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RoadmapStepError("STEP_INVALID", "note requires text(str)")
    return ({"status": "OK", "side_effects": {"note": {"text": text}}}, "")


def _handle_workspace_root_guard_step(*, tpl: dict[str, Any], workspace_root: Path) -> tuple[dict[str, Any], str]:
    paths = tpl.get("paths")
    if not isinstance(paths, list) or not paths:
        raise RoadmapStepError("STEP_INVALID", "workspace_root_guard requires paths[]")
    checked: list[str] = []
    for raw in paths:
        rel = Path(str(raw)).as_posix()
        abs_p = (workspace_root / rel).resolve()
        try:
            abs_p.relative_to(workspace_root)
        except Exception as e:
            raise RoadmapStepError("WORKSPACE_ROOT_VIOLATION", f"Path escapes workspace_root: {rel}") from e
        checked.append(rel)
    return ({"status": "OK", "side_effects": {"workspace_root_guard": {"paths": checked}}}, "")


def _handle_write_file_allowlist_step(*, tpl: dict[str, Any], state: _ExecutionState) -> tuple[dict[str, Any], str]:
    allowed = tpl.get("allowed_paths")
    if not isinstance(allowed, list) or not allowed:
        raise RoadmapStepError("STEP_INVALID", "write_file_allowlist requires allowed_paths[]")
    cleaned = [Path(str(x)).as_posix().strip("/") for x in allowed if str(x).strip()]
    if not cleaned:
        raise RoadmapStepError("STEP_INVALID", "write_file_allowlist allowed_paths[] cannot be empty")
    state.write_allowlist = cleaned
    return ({"status": "OK", "side_effects": {"write_allowlist": {"allowed_paths": cleaned}}}, "")


def _is_forbidden(rel_path: str, patterns: list[str]) -> str | None:
    p = _normalize_rel_path(Path(rel_path).as_posix())
    for pat in patterns:
        pat_s = str(pat).strip()
        if not pat_s:
            continue
        if pat_s.endswith("/"):
            if p.startswith(pat_s):
                return pat_s
        if fnmatch.fnmatch(p, pat_s):
            return pat_s
    return None


def _require_writable_path(
    *,
    rel: str,
    forbidden: list[str],
    write_allowlist: list[str] | None,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
) -> None:
    root = workspace_root.resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except Exception as e:
        raise RoadmapStepError("WORKSPACE_ROOT_VIOLATION", f"Path escapes workspace_root: {rel}") from e
    if core_policy.enabled and core_policy.default_mode == "locked" and root == core_root.resolve():
        if not _core_unlock_requested(core_policy):
            raise RoadmapStepError(
                core_policy.blocked_write_error_code,
                "core write blocked (locked mode)",
                {"blocked_path": rel},
            )
        if core_policy.core_write_mode == "ssot_only_when_unlocked":
            if not _is_ssot_write_allowed(core_policy.ssot_write_allowlist, rel):
                raise RoadmapStepError(
                    core_policy.blocked_write_error_code,
                    "core write blocked (ssot allowlist)",
                    {"blocked_path": rel},
                )
    bad = _is_forbidden(rel, forbidden)
    if bad:
        raise RoadmapStepError("FORBIDDEN_PATH", f"Path is forbidden by pattern {bad!r}: {rel}")
    if not _is_write_allowed(write_allowlist, rel):
        raise RoadmapStepError("POLICY_VIOLATION", "WRITE_NOT_ALLOWED")


def _write_core_unlock_blocked_report(
    *,
    workspace_root: Path,
    error_code: str,
    blocked_path: str,
    step_id: str,
    milestone_id: str,
    unlock_env_var: str,
    unlock_env_value: str,
) -> None:
    report_path = workspace_root / ".cache" / "reports" / "core_unlock_blocked.v1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    unlock_requested = str(os.environ.get(unlock_env_var, "")).strip() == unlock_env_value
    reason_present = bool(str(os.environ.get("CORE_UNLOCK_REASON", "")).strip())
    report = {
        "version": "v1",
        "generated_at": _now_iso8601(),
        "error_code": error_code,
        "blocked_path": blocked_path,
        "step_id": step_id,
        "milestone_id": milestone_id,
        "core_unlock_requested": bool(unlock_requested),
        "core_unlock_reason_present": bool(reason_present),
        "reason_missing": bool(unlock_requested and not reason_present),
        "notes": ["PROGRAM_LED=true", "NO_NETWORK=true"],
    }
    write_json_atomic(report_path, report)


def _handle_create_file_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("path", ""))).as_posix()
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    content = tpl.get("content")
    overwrite = tpl.get("overwrite")
    if not isinstance(content, str) or not isinstance(overwrite, bool):
        raise RoadmapStepError("STEP_INVALID", "create_file requires content(str) and overwrite(bool)")
    old = state.virtual_fs.get_text(rel, workspace_root) or ""
    res = step_create_file(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        path=rel,
        content=content,
        overwrite=overwrite,
        dry_run=dry_run,
    )
    new = state.virtual_fs.get_text(rel, workspace_root) or content
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, _count_diff_lines(old, new))
    return (res, "")


def _handle_ensure_dir_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("path", ""))).as_posix()
    if not rel:
        raise RoadmapStepError("STEP_INVALID", "ensure_dir requires path")
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    res = step_ensure_dir(workspace=workspace_root, path=rel, dry_run=dry_run)
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, 0)
    return (res, "")


def _handle_patch_file_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("path", ""))).as_posix()
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    patches = tpl.get("patches")
    if not isinstance(patches, list) or not patches:
        raise RoadmapStepError("STEP_INVALID", "patch_file requires patches[]")
    old = state.virtual_fs.get_text(rel, workspace_root)
    if old is None:
        raise RoadmapStepError("FILE_NOT_FOUND", f"File not found: {rel}")
    res = step_patch_file(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        path=rel,
        patches=patches,
        dry_run=dry_run,
    )
    new = state.virtual_fs.get_text(rel, workspace_root) or old
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, _count_diff_lines(old, new))
    return (res, "")


def _handle_create_json_from_template_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("path", ""))).as_posix()
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    overwrite = tpl.get("overwrite")
    if not isinstance(overwrite, bool):
        raise RoadmapStepError("STEP_INVALID", "create_json_from_template requires overwrite(bool)")
    res, old, new = step_create_json_from_template(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        path=rel,
        json_obj=tpl.get("json"),
        overwrite=overwrite,
        dry_run=dry_run,
    )
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, _count_diff_lines(old, new))
    return (res, "")


def _handle_add_schema_file_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("path", ""))).as_posix()
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    res, old, new = step_add_schema_file(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        path=rel,
        schema_json=tpl.get("schema_json"),
        dry_run=dry_run,
    )
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, _count_diff_lines(old, new))
    return (res, "")


def _handle_add_ci_gate_script_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("path", ""))).as_posix()
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    content = tpl.get("content")
    overwrite = tpl.get("overwrite")
    if not isinstance(content, str) or not isinstance(overwrite, bool):
        raise RoadmapStepError("STEP_INVALID", "add_ci_gate_script requires content(str) and overwrite(bool)")
    res, old, new = step_add_ci_gate_script(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        path=rel,
        content=content,
        overwrite=overwrite,
        dry_run=dry_run,
    )
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, _count_diff_lines(old, new))
    return (res, "")


def _handle_patch_policy_report_inject_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    workspace_root: Path,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    rel = Path(str(tpl.get("target", ""))).as_posix()
    _require_writable_path(
        rel=rel,
        forbidden=forbidden,
        write_allowlist=state.write_allowlist,
        workspace_root=workspace_root,
        core_root=core_root,
        core_policy=core_policy,
    )
    marker = tpl.get("marker")
    insert_text = tpl.get("insert_text")
    if not isinstance(marker, str) or not isinstance(insert_text, str):
        raise RoadmapStepError("STEP_INVALID", "patch_policy_report_inject requires marker(str) and insert_text(str)")
    res, old, new = step_patch_policy_report_inject(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        target=rel,
        marker=marker,
        insert_text=insert_text,
        dry_run=dry_run,
    )
    _get_counter(state.counters_by_milestone, ms_id).touch(rel, _count_diff_lines(old, new))
    return (res, "")


def _handle_change_proposal_apply_step(
    *,
    tpl: dict[str, Any],
    state: _ExecutionState,
    core_root: Path,
    workspace_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    roadmap_path: Path,
    ms_id: str,
    dry_run: bool,
) -> tuple[dict[str, Any], str]:
    change_path = tpl.get("change_path")
    if not isinstance(change_path, str) or not change_path.strip():
        raise RoadmapStepError("STEP_INVALID", "change_proposal_apply requires change_path(str)")

    ch_rel = Path(change_path).as_posix()
    ch_abs = (core_root / ch_rel).resolve()
    try:
        ch_abs.relative_to(core_root)
    except Exception as e:
        raise RoadmapStepError("WORKSPACE_ROOT_VIOLATION", "change_path escapes core_root") from e

    roadmap_target_raw = tpl.get("roadmap_path")
    if roadmap_target_raw is None:
        rm_abs = roadmap_path.resolve()
    else:
        if not isinstance(roadmap_target_raw, str) or not roadmap_target_raw.strip():
            raise RoadmapStepError("STEP_INVALID", "change_proposal_apply roadmap_path must be a non-empty string")
        rm_rel = Path(roadmap_target_raw).as_posix()
        rm_abs = (core_root / rm_rel).resolve()
    try:
        rm_abs.relative_to(core_root)
    except Exception as e:
        raise RoadmapStepError("WORKSPACE_ROOT_VIOLATION", "roadmap_path escapes core_root") from e

    if dry_run:
        return (
            {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_apply_change": {"change": ch_rel, "roadmap": rm_abs.as_posix()}}},
            "",
        )

    if core_policy.enabled and core_policy.default_mode == "locked" and workspace_root.resolve() == core_root.resolve():
        if not _core_unlock_requested(core_policy):
            raise RoadmapStepError(
                core_policy.blocked_write_error_code,
                "core write blocked (locked mode)",
                {"blocked_path": ch_rel},
            )
    if workspace_root != core_root:
        raise RoadmapStepError(
            "WORKSPACE_ROOT_VIOLATION",
            "core write blocked outside workspace_root",
            {"blocked_path": ch_rel},
        )

    try:
        from src.roadmap.change_proposals import apply_change_to_roadmap_obj, load_json, validate_change
        from src.roadmap.compiler import validate_roadmap
    except Exception as e:
        raise RoadmapStepError("STEP_INVALID", "change_proposal_apply imports failed") from e

    change_obj = load_json(ch_abs)
    change_schema = core_root / "schemas" / "roadmap-change.schema.json"
    errors = validate_change(change_obj, change_schema)
    if errors:
        raise RoadmapStepError("SCHEMA_INVALID", "roadmap-change.schema.json validation failed")

    current_obj = load_json(rm_abs)
    r_errors = validate_roadmap(current_obj, core_root / "schemas" / "roadmap.schema.json")
    if r_errors:
        raise RoadmapStepError("SCHEMA_INVALID", "roadmap.schema.json validation failed")

    updated_obj = apply_change_to_roadmap_obj(roadmap_obj=current_obj, change_obj=change_obj)
    r2_errors = validate_roadmap(updated_obj, core_root / "schemas" / "roadmap.schema.json")
    if r2_errors:
        raise RoadmapStepError("SCHEMA_INVALID", "roadmap invalid after change apply")

    old_text = json.dumps(current_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    new_text = json.dumps(updated_obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    write_text_atomic(rm_abs, new_text)

    rm_rel_for_counter = rm_abs.relative_to(workspace_root).as_posix()
    _get_counter(state.counters_by_milestone, ms_id).touch(rm_rel_for_counter, _count_diff_lines(old_text, new_text))
    return ({"status": "OK", "side_effects": {"applied_change": {"change": ch_rel, "roadmap": rm_rel_for_counter}}}, "")


def _handle_incubator_sanitize_scan_step(*, tpl: dict[str, Any], workspace_root: Path) -> tuple[dict[str, Any], str]:
    scan_path = tpl.get("path")
    if not isinstance(scan_path, str) or not scan_path.strip():
        raise RoadmapStepError("STEP_INVALID", "incubator_sanitize_scan requires path(str)")
    rel_dir = Path(scan_path).as_posix()
    abs_dir = (workspace_root / rel_dir).resolve()
    try:
        abs_dir.relative_to(workspace_root)
    except Exception as e:
        raise RoadmapStepError("WORKSPACE_ROOT_VIOLATION", "sanitize scan path escapes workspace_root") from e

    forbidden_tokens_raw = tpl.get("forbidden_tokens")
    forbidden_tokens = (
        [str(x) for x in forbidden_tokens_raw if isinstance(x, str) and x.strip()]
        if isinstance(forbidden_tokens_raw, list)
        else None
    )

    try:
        from src.roadmap.sanitize import findings_fingerprint, scan_directory
    except Exception as e:
        raise RoadmapStepError("STEP_INVALID", "sanitize imports failed") from e

    ok, findings = scan_directory(root=abs_dir, forbidden_tokens=forbidden_tokens)
    if not ok:
        raise RoadmapStepError("SANITIZE_VIOLATION", "Incubator sanitize scan failed")
    return (
        {
            "status": "OK",
            "side_effects": {
                "sanitize_scan": {
                    "path": rel_dir,
                    "findings_count": len(findings),
                    "findings_fingerprint": findings_fingerprint(findings),
                }
            },
        },
        "",
    )


def _enforce_readonly_clean(
    *,
    core_root: Path,
    baseline_git_status: str | None,
    workspace_root: Path,
    baseline_workspace_snapshot: dict[str, str] | None,
) -> None:
    current_status = _git_status_porcelain(core_root)
    if current_status is None or baseline_git_status is None:
        raise RoadmapStepError("POLICY_VIOLATION", "READONLY_MODE_REQUIRES_GIT")
    if current_status != baseline_git_status:
        raise RoadmapStepError("POLICY_VIOLATION", "READONLY_MODE_VIOLATION")
    if baseline_workspace_snapshot is not None:
        current_ws = _snapshot_tree(
            workspace_root,
            ignore_prefixes=[
                ".cache",
                "evidence",
                "dlq",
                "__pycache__",
            ],
        )
        if current_ws != baseline_workspace_snapshot:
            raise RoadmapStepError("POLICY_VIOLATION", "READONLY_WORKSPACE_VIOLATION")


def _handle_run_cmd_step(
    *,
    tpl: dict[str, Any],
    core_root: Path,
    workspace_root: Path,
    dry_run: bool,
    dry_run_mode: str,
    baseline_git_status: str | None,
    baseline_workspace_snapshot: dict[str, str] | None,
    step_phase: str | None,
    ms_id: str,
    step_id: str,
    summary: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    cmd = tpl.get("cmd")
    must_succeed = tpl.get("must_succeed")
    apply_only = tpl.get("apply_only", False)
    if not isinstance(cmd, str) or not isinstance(must_succeed, bool):
        raise RoadmapStepError("STEP_INVALID", "run_cmd requires cmd(str) and must_succeed(bool)")
    if not isinstance(apply_only, bool):
        raise RoadmapStepError("STEP_INVALID", "run_cmd apply_only must be boolean if present")

    cmd = cmd.replace("${WORKSPACE_ROOT}", str(workspace_root))

    run_this_cmd = not (dry_run and dry_run_mode == "simulate")
    if dry_run and apply_only:
        run_this_cmd = False

    if dry_run and dry_run_mode == "readonly" and run_this_cmd and not _readonly_cmd_allowlisted(cmd):
        raise RoadmapStepError("POLICY_VIOLATION", "READONLY_CMD_NOT_ALLOWED")

    env_overrides: dict[str, str] = {"ORCH_WORKSPACE_ROOT": str(workspace_root)}
    if dry_run and dry_run_mode == "readonly" and run_this_cmd:
        env_overrides["ORCH_ROADMAP_READONLY"] = "1"

    res, logs = step_run_cmd(
        workspace=core_root,
        cmd=cmd,
        must_succeed=must_succeed,
        dry_run=(dry_run and not run_this_cmd),
        env_overrides=env_overrides,
    )
    if step_phase == "GATE":
        summary["gate_results"].append(
            {
                "milestone_id": ms_id,
                "step_id": step_id,
                "cmd": cmd,
                "status": res.get("status"),
                "return_code": res.get("return_code"),
            }
        )
    if dry_run and dry_run_mode == "readonly" and run_this_cmd:
        _enforce_readonly_clean(
            core_root=core_root,
            baseline_git_status=baseline_git_status,
            workspace_root=workspace_root,
            baseline_workspace_snapshot=baseline_workspace_snapshot,
        )
    return (res, logs)


def _handle_assert_paths_exist_step(
    *, tpl: dict[str, Any], workspace_root: Path, state: _ExecutionState, dry_run: bool
) -> tuple[dict[str, Any], str]:
    paths = tpl.get("paths")
    if not isinstance(paths, list) or not paths:
        raise RoadmapStepError("STEP_INVALID", "assert_paths_exist requires paths[]")
    apply_only = tpl.get("apply_only", False)
    if not isinstance(apply_only, bool):
        raise RoadmapStepError("STEP_INVALID", "assert_paths_exist apply_only must be boolean if present")
    if dry_run and apply_only:
        return (
            {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_assert": {"paths": [Path(str(x)).as_posix() for x in paths]}}},
            "",
        )
    res = step_assert_paths_exist(
        workspace=workspace_root,
        virtual_fs=state.virtual_fs,
        paths=[str(x) for x in paths],
    )
    return (res, "")


def _handle_iso_core_check_step(*, tpl: dict[str, Any], workspace_root: Path) -> tuple[dict[str, Any], str]:
    tenant = tpl.get("tenant")
    required_files = tpl.get("required_files")
    if not isinstance(tenant, str) or not isinstance(required_files, list) or not required_files:
        raise RoadmapStepError("STEP_INVALID", "iso_core_check requires tenant(str) and required_files[]")
    res = step_iso_core_check(
        workspace=workspace_root,
        tenant=tenant,
        required_files=[str(x) for x in required_files],
    )
    return (res, "")


def _handle_assert_core_paths_exist_step(*, tpl: dict[str, Any], core_root: Path) -> tuple[dict[str, Any], str]:
    paths = tpl.get("paths")
    if not isinstance(paths, list) or not paths:
        raise RoadmapStepError("STEP_INVALID", "assert_core_paths_exist requires paths[]")
    res = step_assert_core_paths_exist(
        core_root=core_root,
        paths=[str(x) for x in paths],
    )
    return (res, "")


def _handle_assert_pointer_target_exists_step(
    *, tpl: dict[str, Any], workspace_root: Path, dry_run: bool
) -> tuple[dict[str, Any], str]:
    pointer_path = tpl.get("pointer_path")
    if not isinstance(pointer_path, str) or not pointer_path:
        raise RoadmapStepError("STEP_INVALID", "assert_pointer_target_exists requires pointer_path")
    apply_only = tpl.get("apply_only", False)
    if not isinstance(apply_only, bool):
        raise RoadmapStepError("STEP_INVALID", "assert_pointer_target_exists apply_only must be boolean if present")
    if dry_run and apply_only:
        return (
            {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_assert_pointer": {"pointer_path": str(pointer_path)}}},
            "",
        )
    res = step_assert_pointer_target_exists(
        workspace=workspace_root,
        pointer_path=str(pointer_path),
    )
    return (res, "")


def _dispatch_step_template(
    *,
    tpl_type: str,
    tpl: dict[str, Any],
    state: _ExecutionState,
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    workspace_root: Path,
    roadmap_path: Path,
    ms_id: str,
    forbidden: list[str],
    dry_run: bool,
    dry_run_mode: str,
    baseline_git_status: str | None,
    baseline_workspace_snapshot: dict[str, str] | None,
    step_phase: str | None,
    step_id: str,
    summary: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if tpl_type == "note":
        return _handle_note_step(tpl=tpl)
    if tpl_type == "workspace_root_guard":
        return _handle_workspace_root_guard_step(tpl=tpl, workspace_root=workspace_root)
    if tpl_type == "write_file_allowlist":
        return _handle_write_file_allowlist_step(tpl=tpl, state=state)
    if tpl_type == "create_file":
        return _handle_create_file_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "ensure_dir":
        return _handle_ensure_dir_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "patch_file":
        return _handle_patch_file_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "create_json_from_template":
        return _handle_create_json_from_template_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "add_schema_file":
        return _handle_add_schema_file_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "add_ci_gate_script":
        return _handle_add_ci_gate_script_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "patch_policy_report_inject":
        return _handle_patch_policy_report_inject_step(
            tpl=tpl,
            state=state,
            workspace_root=workspace_root,
            core_root=core_root,
            core_policy=core_policy,
            ms_id=ms_id,
            forbidden=forbidden,
            dry_run=dry_run,
        )
    if tpl_type == "change_proposal_apply":
        return _handle_change_proposal_apply_step(
            tpl=tpl,
            state=state,
            core_root=core_root,
            workspace_root=workspace_root,
            core_policy=core_policy,
            roadmap_path=roadmap_path,
            ms_id=ms_id,
            dry_run=dry_run,
        )
    if tpl_type == "incubator_sanitize_scan":
        return _handle_incubator_sanitize_scan_step(tpl=tpl, workspace_root=workspace_root)
    if tpl_type == "run_cmd":
        return _handle_run_cmd_step(
            tpl=tpl,
            core_root=core_root,
            workspace_root=workspace_root,
            dry_run=dry_run,
            dry_run_mode=dry_run_mode,
            baseline_git_status=baseline_git_status,
            baseline_workspace_snapshot=baseline_workspace_snapshot,
            step_phase=step_phase,
            ms_id=ms_id,
            step_id=step_id,
            summary=summary,
        )
    if tpl_type == "assert_paths_exist":
        return _handle_assert_paths_exist_step(tpl=tpl, workspace_root=workspace_root, state=state, dry_run=dry_run)
    if tpl_type == "assert_pointer_target_exists":
        return _handle_assert_pointer_target_exists_step(tpl=tpl, workspace_root=workspace_root, dry_run=dry_run)
    if tpl_type == "assert_core_paths_exist":
        return _handle_assert_core_paths_exist_step(tpl=tpl, core_root=core_root)
    if tpl_type == "iso_core_check":
        return _handle_iso_core_check_step(tpl=tpl, workspace_root=workspace_root)
    raise RoadmapStepError("UNKNOWN_STEP", f"Unknown step type: {tpl_type}")


def _apply_plan_steps(
    *,
    plan: dict[str, Any],
    state: _ExecutionState,
    summary: dict[str, Any],
    evidence_paths: Any,
    roadmap_path: Path,
    milestone_constraints: dict[str, dict[str, Any]],
    core_root: Path,
    core_policy: _CoreImmutabilityPolicy,
    workspace_root: Path,
    dry_run: bool,
    dry_run_mode: str,
    baseline_git_status: str | None,
    baseline_workspace_snapshot: dict[str, str] | None,
) -> None:
    for step in plan["steps"]:
        step_id = step["step_id"]
        ms_id = step["milestone_id"]
        tpl = step["template"]
        tpl_type = tpl.get("type")
        step_phase = step.get("phase")

        if ms_id not in summary["milestones_executed"]:
            summary["milestones_executed"].append(ms_id)

        forbidden, max_files_changed, max_diff_lines, constraints = _constraints_for_step(milestone_constraints, ms_id)
        step_input = {
            "step_id": step_id,
            "milestone_id": ms_id,
            "phase": step_phase,
            "template": tpl,
            "constraints": constraints,
        }

        logs = ""
        step_output: dict[str, Any] = {"step_id": step_id, "status": "OK", "type": tpl_type, "side_effects": {}}
        try:
            if not isinstance(tpl_type, str):
                raise RoadmapStepError("STEP_INVALID", "template.type missing")
            res, logs = _dispatch_step_template(
                tpl_type=tpl_type,
                tpl=tpl,
                state=state,
                core_root=core_root,
                core_policy=core_policy,
                workspace_root=workspace_root,
                roadmap_path=roadmap_path,
                ms_id=ms_id,
                forbidden=forbidden,
                dry_run=dry_run,
                dry_run_mode=dry_run_mode,
                baseline_git_status=baseline_git_status,
                baseline_workspace_snapshot=baseline_workspace_snapshot,
                step_phase=str(step_phase) if isinstance(step_phase, str) else None,
                step_id=step_id,
                summary=summary,
            )
            step_output.update(res)

            _enforce_milestone_caps(
                counter=_get_counter(state.counters_by_milestone, ms_id),
                ms_id=ms_id,
                max_files_changed=max_files_changed,
                max_diff_lines=max_diff_lines,
            )
        except RoadmapStepError as e:
            step_output["status"] = "FAIL"
            step_output["error_code"] = e.error_code
            step_output["message"] = e.message
            if getattr(e, "details", None):
                step_output["details"] = e.details
                if isinstance(e.details, dict) and "blocked_path" in e.details:
                    step_output["blocked_path"] = e.details.get("blocked_path")
                    if e.error_code == core_policy.blocked_write_error_code:
                        _write_core_unlock_blocked_report(
                            workspace_root=workspace_root,
                            error_code=str(e.error_code),
                            blocked_path=str(e.details.get("blocked_path")),
                            step_id=str(step_id),
                            milestone_id=str(ms_id),
                            unlock_env_var=str(core_policy.allow_env_var),
                            unlock_env_value=str(core_policy.allow_env_value),
                        )
            details = e.details if isinstance(getattr(e, "details", None), dict) else {}
            state.dlq = {
                "stage": "ROADMAP_STEP",
                "error_code": e.error_code,
                "message": e.message,
                "step_id": step_id,
                "milestone_id": ms_id,
                "details": details,
                "ts": _now_iso8601(),
            }
            summary["status"] = "FAIL"
            summary["failed_step_id"] = step_id
            summary["failed_milestone_id"] = ms_id
            summary["failed_error_code"] = e.error_code
            summary["failed_message"] = e.message
            summary["failed_cmd"] = details.get("cmd")
            summary["failed_return_code"] = details.get("return_code")
            summary["failed_stderr_preview"] = details.get("stderr_tail")
            summary["failed_stdout_preview"] = details.get("stdout_tail")
            raise
        finally:
            write_step_evidence(paths=evidence_paths, step_id=step_id, step_input=step_input, step_output=step_output, logs=logs)
