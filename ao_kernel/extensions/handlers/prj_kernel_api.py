"""Runtime-backed handlers for PRJ-KERNEL-API.

Read-only actions stay available:
``system_status`` and ``doc_nav_check``.

Write-side actions are now runtime-backed with an explicit safety contract:
``project_status``, ``roadmap_follow``, and ``roadmap_finish``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ao_kernel

from ao_kernel._internal.shared.utils import write_bytes_atomic, write_json_atomic
from ao_kernel.extensions.loader import ExtensionRegistry

EXTENSION_ID = "PRJ-KERNEL-API"
READ_ONLY_ACTIONS = ("system_status", "doc_nav_check")
WRITE_ACTIONS = ("project_status", "roadmap_follow", "roadmap_finish")
SUPPORTED_ACTIONS = READ_ONLY_ACTIONS + WRITE_ACTIONS

REQUIRED_WRITE_CONFIRMATION = "I_UNDERSTAND_SIDE_EFFECTS"
ROADMAP_STATE_REL_PATH = ".ao/state/kernel_api_roadmap_state.v1.json"
PROJECT_STATUS_REL_PATH = ".ao/reports/project_status.v1.json"
WRITE_AUDIT_REL_PATH = ".ao/reports/kernel_api_write_audit.v1.jsonl"
ALLOWED_WRITE_PREFIXES = (".ao/state/", ".ao/reports/")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_contract() -> dict[str, Any]:
    return {
        "dry_run_default": True,
        "require_workspace_root": True,
        "require_confirm_for_write": True,
        "confirm_token": REQUIRED_WRITE_CONFIRMATION,
        "allowed_write_prefixes": list(ALLOWED_WRITE_PREFIXES),
        "rollback_on_partial_failure": True,
    }


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return parsed


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _project_status_signature(data: dict[str, Any]) -> str:
    normalized = dict(data)
    normalized.pop("generated_at", None)
    normalized.pop("request_id", None)
    return _canonical_json(normalized)


def _safe_relative(workspace_root: Path, target: Path) -> str:
    try:
        rel = target.resolve().relative_to(workspace_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace_root: {target}") from exc
    rel_norm = rel.as_posix()
    if not any(
        rel_norm == prefix.rstrip("/") or rel_norm.startswith(prefix)
        for prefix in ALLOWED_WRITE_PREFIXES
    ):
        raise ValueError(f"Path outside write allowlist: {rel_norm}")
    return rel_norm


def _resolve_workspace_root(action: str, params: dict[str, Any]) -> tuple[Path | None, dict[str, Any] | None]:
    raw = params.get("workspace_root")
    if not isinstance(raw, str) or not raw.strip():
        return (
            None,
            _error_envelope(
                action,
                error_code="WORKSPACE_ROOT_REQUIRED",
                message="workspace_root is required for write-side actions",
                status="BLOCKED",
            ),
        )
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        return (
            None,
            _error_envelope(
                action,
                error_code="WORKSPACE_ROOT_INVALID",
                message=f"workspace_root is not a directory: {root}",
                status="BLOCKED",
            ),
        )
    return root, None


def _resolve_write_mode(action: str, params: dict[str, Any]) -> tuple[bool | None, dict[str, Any] | None]:
    dry_run = params.get("dry_run", True)
    if not isinstance(dry_run, bool):
        return (
            None,
            _error_envelope(
                action,
                error_code="INVALID_DRY_RUN",
                message="dry_run must be boolean",
                status="BLOCKED",
            ),
        )
    if not dry_run:
        confirm = params.get("confirm_write")
        if confirm != REQUIRED_WRITE_CONFIRMATION:
            return (
                None,
                _error_envelope(
                    action,
                    error_code="WRITE_CONFIRM_REQUIRED",
                    message=(
                        "set confirm_write to the required token before write-side execution"
                    ),
                    status="BLOCKED",
                ),
            )
    return dry_run, None


def _default_roadmap_state() -> dict[str, Any]:
    return {
        "version": "v1",
        "active_roadmap_id": None,
        "status": "idle",
        "last_step_id": None,
        "updated_at": None,
        "finished_at": None,
        "history": [],
    }


def _load_roadmap_state(state_path: Path) -> dict[str, Any]:
    current = _load_json_dict(state_path)
    if current is None:
        return _default_roadmap_state()
    merged = _default_roadmap_state()
    merged.update(current)
    history = merged.get("history")
    if not isinstance(history, list):
        merged["history"] = []
    return merged


def _append_history(
    state: dict[str, Any],
    *,
    event: str,
    roadmap_id: str,
    step_id: str | None = None,
) -> None:
    history = state.get("history")
    if not isinstance(history, list):
        history = []
    entry: dict[str, Any] = {
        "event": event,
        "roadmap_id": roadmap_id,
        "timestamp": _now_iso(),
    }
    if step_id:
        entry["step_id"] = step_id
    history.append(entry)
    state["history"] = history[-100:]


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


def _write_with_audit_and_rollback(
    *,
    workspace_root: Path,
    target_path: Path,
    payload: dict[str, Any],
    audit_path: Path,
    audit_entry: dict[str, Any],
    force_fail_after_primary_write: bool,
) -> tuple[bool, str | None]:
    _safe_relative(workspace_root, target_path)
    _safe_relative(workspace_root, audit_path)

    existed = target_path.exists()
    previous = target_path.read_bytes() if existed else b""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(target_path, payload)

    try:
        if force_fail_after_primary_write:
            raise RuntimeError("forced failure after primary write")
        _append_jsonl(audit_path, audit_entry)
        return True, None
    except Exception as exc:  # noqa: BLE001
        try:
            if existed:
                write_bytes_atomic(target_path, previous)
            elif target_path.exists():
                target_path.unlink()
        except Exception as rollback_exc:  # noqa: BLE001
            return False, f"{exc}; rollback_failed={rollback_exc}"
        return False, str(exc)


def _truth_payload() -> dict[str, Any]:
    registry = ExtensionRegistry()
    registry.load_from_defaults()
    summary = registry.truth_summary()
    return {
        "total_extensions": summary.total_extensions,
        "runtime_backed": summary.runtime_backed,
        "contract_only": summary.contract_only,
        "quarantined": summary.quarantined,
        "remap_candidate_refs": summary.remap_candidate_refs,
        "missing_runtime_refs": summary.missing_runtime_refs,
        "runtime_backed_ids": list(summary.runtime_backed_ids),
        "quarantined_ids": list(summary.quarantined_ids),
    }


def _extension_payload() -> dict[str, Any]:
    registry = ExtensionRegistry()
    registry.load_from_defaults()
    manifest = registry.get(EXTENSION_ID)
    if manifest is None:
        return {
            "extension_id": EXTENSION_ID,
            "present": False,
            "truth_tier": "missing",
            "runtime_handler_registered": False,
            "missing_runtime_refs": [],
            "remap_candidate_refs": [],
            "kernel_api_actions": [],
        }
    return {
        "extension_id": manifest.extension_id,
        "present": True,
        "truth_tier": manifest.truth_tier,
        "runtime_handler_registered": manifest.runtime_handler_registered,
        "missing_runtime_refs": list(manifest.missing_runtime_refs),
        "remap_candidate_refs": list(manifest.remap_candidate_refs),
        "kernel_api_actions": list(manifest.entrypoints.get("kernel_api_actions", [])),
    }


def _envelope(action: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "OK",
        "action": action,
        "extension_id": EXTENSION_ID,
        "result": result,
    }


def _error_envelope(
    action: str,
    *,
    error_code: str,
    message: str,
    status: str = "FAIL",
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "action": action,
        "extension_id": EXTENSION_ID,
        "error": {"code": error_code, "message": message},
        "result": result or {},
    }


def system_status(params: dict[str, Any]) -> dict[str, Any]:
    """Return runtime truth snapshot for the installed package."""
    return _envelope(
        "system_status",
        {
            "version": ao_kernel.__version__,
            "supported_actions": list(SUPPORTED_ACTIONS),
            "read_only_actions": list(READ_ONLY_ACTIONS),
            "write_actions": list(WRITE_ACTIONS),
            "write_side_contract": _write_contract(),
            "extension_truth": _truth_payload(),
            "params_echo": {
                key: params[key]
                for key in sorted(params)
                if key in {"detail", "request_id"}
            },
        },
    )


def doc_nav_check(params: dict[str, Any]) -> dict[str, Any]:
    """Return the package-local manifest/ref truth used by doctor audit."""
    return _envelope(
        "doc_nav_check",
        {
            "extension": _extension_payload(),
            "supported_actions": list(SUPPORTED_ACTIONS),
            "read_only_actions": list(READ_ONLY_ACTIONS),
            "write_actions": list(WRITE_ACTIONS),
            "write_side_contract": _write_contract(),
            "network_required": False,
            "workspace_write": False,
            "params_echo": {
                key: params[key]
                for key in sorted(params)
                if key in {"detail", "request_id"}
            },
        },
    )


def project_status(params: dict[str, Any]) -> dict[str, Any]:
    action = "project_status"
    workspace_root, ws_error = _resolve_workspace_root(action, params)
    if ws_error is not None or workspace_root is None:
        return ws_error or _error_envelope(
            action,
            error_code="WORKSPACE_ROOT_REQUIRED",
            message="workspace_root is required",
            status="BLOCKED",
        )

    dry_run, mode_error = _resolve_write_mode(action, params)
    if mode_error is not None or dry_run is None:
        return mode_error or _error_envelope(
            action,
            error_code="INVALID_DRY_RUN",
            message="dry_run parsing failed",
            status="BLOCKED",
        )

    report_path = workspace_root / PROJECT_STATUS_REL_PATH
    state_path = workspace_root / ROADMAP_STATE_REL_PATH
    audit_path = workspace_root / WRITE_AUDIT_REL_PATH

    try:
        rel_report = _safe_relative(workspace_root, report_path)
        rel_audit = _safe_relative(workspace_root, audit_path)
    except ValueError as exc:
        return _error_envelope(
            action,
            error_code="WRITE_PATH_VIOLATION",
            message=str(exc),
            status="BLOCKED",
        )

    try:
        roadmap_state = _load_roadmap_state(state_path)
    except Exception as exc:  # noqa: BLE001
        return _error_envelope(
            action,
            error_code="ROADMAP_STATE_INVALID",
            message=str(exc),
        )

    report_payload: dict[str, Any] = {
        "version": "v1",
        "generated_at": _now_iso(),
        "extension_id": EXTENSION_ID,
        "workspace_root": str(workspace_root),
        "truth": _truth_payload(),
        "roadmap_state": roadmap_state,
        "request_id": params.get("request_id"),
    }

    try:
        current = _load_json_dict(report_path)
    except Exception as exc:  # noqa: BLE001
        return _error_envelope(
            action,
            error_code="PROJECT_STATUS_INVALID",
            message=str(exc),
        )
    idempotent = (
        current is not None
        and _project_status_signature(current) == _project_status_signature(report_payload)
    )

    if dry_run:
        return _envelope(
            action,
            {
                "dry_run": True,
                "write_applied": False,
                "idempotent": idempotent,
                "workspace_root": str(workspace_root),
                "report_path": rel_report,
                "audit_path": rel_audit,
                "roadmap_state_status": roadmap_state.get("status"),
            },
        )

    if idempotent:
        return _envelope(
            action,
            {
                "dry_run": False,
                "write_applied": False,
                "idempotent": True,
                "workspace_root": str(workspace_root),
                "report_path": rel_report,
                "audit_path": rel_audit,
            },
        )

    force_fail = bool(params.get("_force_fail_after_primary_write", False))
    ok, write_err = _write_with_audit_and_rollback(
        workspace_root=workspace_root,
        target_path=report_path,
        payload=report_payload,
        audit_path=audit_path,
        audit_entry={
            "version": "v1",
            "timestamp": _now_iso(),
            "action": action,
            "workspace_root": str(workspace_root),
            "report_path": rel_report,
            "idempotent": False,
        },
        force_fail_after_primary_write=force_fail,
    )
    if not ok:
        return _error_envelope(
            action,
            error_code="WRITE_PARTIAL_FAILURE_ROLLBACK",
            message=str(write_err),
            result={
                "dry_run": False,
                "write_applied": False,
                "rollback_applied": True,
                "report_path": rel_report,
            },
        )

    return _envelope(
        action,
        {
            "dry_run": False,
            "write_applied": True,
            "idempotent": False,
            "workspace_root": str(workspace_root),
            "report_path": rel_report,
            "audit_path": rel_audit,
        },
    )


def roadmap_follow(params: dict[str, Any]) -> dict[str, Any]:
    action = "roadmap_follow"
    workspace_root, ws_error = _resolve_workspace_root(action, params)
    if ws_error is not None or workspace_root is None:
        return ws_error or _error_envelope(
            action,
            error_code="WORKSPACE_ROOT_REQUIRED",
            message="workspace_root is required",
            status="BLOCKED",
        )

    dry_run, mode_error = _resolve_write_mode(action, params)
    if mode_error is not None or dry_run is None:
        return mode_error or _error_envelope(
            action,
            error_code="INVALID_DRY_RUN",
            message="dry_run parsing failed",
            status="BLOCKED",
        )

    roadmap_id = params.get("roadmap_id")
    if not isinstance(roadmap_id, str) or not roadmap_id.strip():
        return _error_envelope(
            action,
            error_code="ROADMAP_ID_REQUIRED",
            message="roadmap_id must be a non-empty string",
            status="BLOCKED",
        )
    roadmap_id = roadmap_id.strip()

    step_id_raw = params.get("step_id", "")
    step_id = step_id_raw.strip() if isinstance(step_id_raw, str) else ""
    allow_takeover = bool(params.get("allow_takeover", False))

    state_path = workspace_root / ROADMAP_STATE_REL_PATH
    audit_path = workspace_root / WRITE_AUDIT_REL_PATH
    try:
        rel_state = _safe_relative(workspace_root, state_path)
        rel_audit = _safe_relative(workspace_root, audit_path)
        current_state = _load_roadmap_state(state_path)
    except Exception as exc:  # noqa: BLE001
        return _error_envelope(
            action,
            error_code="ROADMAP_STATE_INVALID",
            message=str(exc),
        )

    active_roadmap = current_state.get("active_roadmap_id")
    current_status = current_state.get("status")
    if (
        isinstance(active_roadmap, str)
        and active_roadmap
        and active_roadmap != roadmap_id
        and current_status == "following"
        and not allow_takeover
    ):
        return _error_envelope(
            action,
            error_code="ROADMAP_CONFLICT",
            message=f"active roadmap is {active_roadmap}; set allow_takeover=true to switch",
            status="BLOCKED",
            result={"active_roadmap_id": active_roadmap},
        )

    idempotent = (
        current_status == "following"
        and active_roadmap == roadmap_id
        and current_state.get("last_step_id") == (step_id or None)
    )

    if dry_run:
        return _envelope(
            action,
            {
                "dry_run": True,
                "write_applied": False,
                "idempotent": idempotent,
                "state_path": rel_state,
                "audit_path": rel_audit,
                "roadmap_id": roadmap_id,
                "step_id": step_id or None,
                "allow_takeover": allow_takeover,
            },
        )

    if idempotent:
        return _envelope(
            action,
            {
                "dry_run": False,
                "write_applied": False,
                "idempotent": True,
                "state_path": rel_state,
                "audit_path": rel_audit,
                "roadmap_id": roadmap_id,
                "step_id": step_id or None,
            },
        )

    new_state = dict(current_state)
    new_state["version"] = "v1"
    new_state["active_roadmap_id"] = roadmap_id
    new_state["status"] = "following"
    new_state["last_step_id"] = step_id or None
    new_state["updated_at"] = _now_iso()
    new_state["finished_at"] = None
    _append_history(new_state, event=action, roadmap_id=roadmap_id, step_id=step_id or None)

    force_fail = bool(params.get("_force_fail_after_primary_write", False))
    ok, write_err = _write_with_audit_and_rollback(
        workspace_root=workspace_root,
        target_path=state_path,
        payload=new_state,
        audit_path=audit_path,
        audit_entry={
            "version": "v1",
            "timestamp": _now_iso(),
            "action": action,
            "roadmap_id": roadmap_id,
            "step_id": step_id or None,
            "state_path": rel_state,
        },
        force_fail_after_primary_write=force_fail,
    )
    if not ok:
        return _error_envelope(
            action,
            error_code="WRITE_PARTIAL_FAILURE_ROLLBACK",
            message=str(write_err),
            result={
                "dry_run": False,
                "write_applied": False,
                "rollback_applied": True,
                "state_path": rel_state,
            },
        )

    return _envelope(
        action,
        {
            "dry_run": False,
            "write_applied": True,
            "idempotent": False,
            "state_path": rel_state,
            "audit_path": rel_audit,
            "roadmap_id": roadmap_id,
            "step_id": step_id or None,
            "status": "following",
        },
    )


def roadmap_finish(params: dict[str, Any]) -> dict[str, Any]:
    action = "roadmap_finish"
    workspace_root, ws_error = _resolve_workspace_root(action, params)
    if ws_error is not None or workspace_root is None:
        return ws_error or _error_envelope(
            action,
            error_code="WORKSPACE_ROOT_REQUIRED",
            message="workspace_root is required",
            status="BLOCKED",
        )

    dry_run, mode_error = _resolve_write_mode(action, params)
    if mode_error is not None or dry_run is None:
        return mode_error or _error_envelope(
            action,
            error_code="INVALID_DRY_RUN",
            message="dry_run parsing failed",
            status="BLOCKED",
        )

    roadmap_id = params.get("roadmap_id")
    if not isinstance(roadmap_id, str) or not roadmap_id.strip():
        return _error_envelope(
            action,
            error_code="ROADMAP_ID_REQUIRED",
            message="roadmap_id must be a non-empty string",
            status="BLOCKED",
        )
    roadmap_id = roadmap_id.strip()

    step_id_raw = params.get("step_id", "")
    step_id = step_id_raw.strip() if isinstance(step_id_raw, str) else ""
    allow_takeover = bool(params.get("allow_takeover", False))

    state_path = workspace_root / ROADMAP_STATE_REL_PATH
    audit_path = workspace_root / WRITE_AUDIT_REL_PATH
    try:
        rel_state = _safe_relative(workspace_root, state_path)
        rel_audit = _safe_relative(workspace_root, audit_path)
        current_state = _load_roadmap_state(state_path)
    except Exception as exc:  # noqa: BLE001
        return _error_envelope(
            action,
            error_code="ROADMAP_STATE_INVALID",
            message=str(exc),
        )

    active_roadmap = current_state.get("active_roadmap_id")
    current_status = current_state.get("status")

    if current_status == "finished" and active_roadmap == roadmap_id:
        idempotent = True
    else:
        idempotent = False
        if (
            isinstance(active_roadmap, str)
            and active_roadmap
            and active_roadmap != roadmap_id
            and current_status == "following"
            and not allow_takeover
        ):
            return _error_envelope(
                action,
                error_code="ROADMAP_CONFLICT",
                message=f"active roadmap is {active_roadmap}; set allow_takeover=true to finish another roadmap",
                status="BLOCKED",
                result={"active_roadmap_id": active_roadmap},
            )
        if not active_roadmap and current_status != "finished":
            return _error_envelope(
                action,
                error_code="ROADMAP_NOT_FOLLOWING",
                message="no active roadmap to finish; run roadmap_follow first",
                status="BLOCKED",
            )

    if dry_run:
        return _envelope(
            action,
            {
                "dry_run": True,
                "write_applied": False,
                "idempotent": idempotent,
                "state_path": rel_state,
                "audit_path": rel_audit,
                "roadmap_id": roadmap_id,
                "step_id": step_id or None,
            },
        )

    if idempotent:
        return _envelope(
            action,
            {
                "dry_run": False,
                "write_applied": False,
                "idempotent": True,
                "state_path": rel_state,
                "audit_path": rel_audit,
                "roadmap_id": roadmap_id,
                "step_id": step_id or None,
                "status": "finished",
            },
        )

    new_state = dict(current_state)
    new_state["version"] = "v1"
    new_state["active_roadmap_id"] = roadmap_id
    new_state["status"] = "finished"
    new_state["last_step_id"] = step_id or current_state.get("last_step_id")
    new_state["updated_at"] = _now_iso()
    new_state["finished_at"] = _now_iso()
    _append_history(new_state, event=action, roadmap_id=roadmap_id, step_id=step_id or None)

    force_fail = bool(params.get("_force_fail_after_primary_write", False))
    ok, write_err = _write_with_audit_and_rollback(
        workspace_root=workspace_root,
        target_path=state_path,
        payload=new_state,
        audit_path=audit_path,
        audit_entry={
            "version": "v1",
            "timestamp": _now_iso(),
            "action": action,
            "roadmap_id": roadmap_id,
            "step_id": step_id or None,
            "state_path": rel_state,
        },
        force_fail_after_primary_write=force_fail,
    )
    if not ok:
        return _error_envelope(
            action,
            error_code="WRITE_PARTIAL_FAILURE_ROLLBACK",
            message=str(write_err),
            result={
                "dry_run": False,
                "write_applied": False,
                "rollback_applied": True,
                "state_path": rel_state,
            },
        )

    return _envelope(
        action,
        {
            "dry_run": False,
            "write_applied": True,
            "idempotent": False,
            "state_path": rel_state,
            "audit_path": rel_audit,
            "roadmap_id": roadmap_id,
            "step_id": step_id or None,
            "status": "finished",
        },
    )


def register(registry: Any) -> None:
    """Register PRJ-KERNEL-API action tranche."""
    registry.register("system_status", system_status, extension_id=EXTENSION_ID)
    registry.register("doc_nav_check", doc_nav_check, extension_id=EXTENSION_ID)
    registry.register("project_status", project_status, extension_id=EXTENSION_ID)
    registry.register("roadmap_follow", roadmap_follow, extension_id=EXTENSION_ID)
    registry.register("roadmap_finish", roadmap_finish, extension_id=EXTENSION_ID)
