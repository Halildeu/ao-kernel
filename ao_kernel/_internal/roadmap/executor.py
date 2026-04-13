from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ao_kernel._internal.roadmap.compiler import compile_roadmap
from ao_kernel._internal.roadmap.evidence import init_evidence_dir, write_integrity_manifest, write_json
from ao_kernel._internal.roadmap.exec_contracts import _ExecutionState
from ao_kernel._internal.roadmap.exec_evidence import _git_info, _now_iso8601, _prepare_readonly_baselines, _sha256_bytes
from ao_kernel._internal.roadmap.exec_steps import (
    _apply_plan_steps,
    _collect_milestone_constraints,
    _load_core_immutability_policy,
    _validate_plan_shape,
)
from ao_kernel._internal.roadmap.step_templates import VirtualFS


def _resolve_roots(
    *,
    core_root: Path,
    workspace_root: Path,
    cache_root: Path,
    evidence_root: Path,
) -> tuple[Path, Path, Path, Path]:
    return (
        core_root.resolve(),
        workspace_root.resolve(),
        cache_root.resolve(),
        evidence_root.resolve(),
    )


def _validate_dry_run_mode(dry_run_mode: str) -> None:
    if dry_run_mode not in {"simulate", "readonly"}:
        raise ValueError("INVALID_DRY_RUN_MODE: expected simulate|readonly")


def _load_and_validate_plan(
    *,
    roadmap_path: Path,
    core_root: Path,
    cache_root: Path,
    milestone_ids: list[str] | None,
) -> tuple[dict[str, Any], str]:
    schema_path = core_root / "schemas" / "roadmap.schema.json"
    if not schema_path.exists():
        raise ValueError("MISSING_SCHEMA: schemas/roadmap.schema.json not found")

    compile_res = compile_roadmap(
        roadmap_path=roadmap_path,
        schema_path=schema_path,
        cache_root=cache_root,
        out_path=None,
        milestone_ids=milestone_ids,
    )
    plan = compile_res.plan
    plan_id = compile_res.plan_id

    _validate_plan_shape(plan)
    return plan, plan_id


def _build_run_id(plan_id: str) -> str:
    return "roadmap-" + (_sha256_bytes(f"{plan_id}:{time.time_ns()}".encode("utf-8"))[:16])


def _write_plan_evidence(
    *,
    roadmap_path: Path,
    plan: dict[str, Any],
    evidence_paths: Any,
) -> tuple[str, str]:
    roadmap_obj_for_evidence = json.loads(roadmap_path.read_text(encoding="utf-8"))
    write_json(evidence_paths.roadmap_path, roadmap_obj_for_evidence)
    write_json(evidence_paths.plan_path, plan)

    roadmap_hash = _sha256_bytes(evidence_paths.roadmap_path.read_bytes())
    plan_hash = _sha256_bytes(evidence_paths.plan_path.read_bytes())
    return roadmap_hash, plan_hash


def _build_summary(
    *,
    run_id: str,
    plan: dict[str, Any],
    plan_id: str,
    dry_run: bool,
    dry_run_mode: str,
    milestone_ids: list[str] | None,
    workspace_root: Path,
    core_root: Path,
    roadmap_hash: str,
    plan_hash: str,
) -> dict[str, Any]:
    return {
        "version": "v1",
        "run_id": run_id,
        "status": "OK",
        "roadmap_id": plan.get("roadmap_id"),
        "roadmap_version": plan.get("roadmap_version"),
        "plan_id": plan_id,
        "dry_run": bool(dry_run),
        "dry_run_mode": str(dry_run_mode),
        "milestones_requested": milestone_ids or None,
        "milestones_executed": [],
        "workspace_root": str(workspace_root),
        "git": _git_info(core_root),
        "hashes": {"roadmap_json_sha256": roadmap_hash, "plan_json_sha256": plan_hash},
        "started_at": _now_iso8601(),
        "finished_at": None,
        "duration_ms": None,
        "failed_step_id": None,
        "failed_milestone_id": None,
        "failed_error_code": None,
        "failed_message": None,
        "failed_cmd": None,
        "failed_return_code": None,
        "failed_stderr_preview": None,
        "failed_stdout_preview": None,
        "gate_results": [],
    }


def _execute_plan(
    *,
    plan: dict[str, Any],
    summary: dict[str, Any],
    evidence_paths: Any,
    roadmap_path: Path,
    core_root: Path,
    core_policy: dict[str, Any],
    workspace_root: Path,
    dry_run: bool,
    dry_run_mode: str,
    baseline_git_status: Any,
    baseline_workspace_snapshot: Any,
    started: float,
) -> dict[str, Any]:
    state = _ExecutionState(virtual_fs=VirtualFS(files={}), counters_by_milestone={}, write_allowlist=None, dlq=None)
    milestone_constraints = _collect_milestone_constraints(plan)

    try:
        _apply_plan_steps(
            plan=plan,
            state=state,
            summary=summary,
            evidence_paths=evidence_paths,
            roadmap_path=roadmap_path,
            milestone_constraints=milestone_constraints,
            core_root=core_root,
            core_policy=core_policy,
            workspace_root=workspace_root,
            dry_run=dry_run,
            dry_run_mode=dry_run_mode,
            baseline_git_status=baseline_git_status,
            baseline_workspace_snapshot=baseline_workspace_snapshot,
        )

    except Exception:
        if state.dlq is None:
            state.dlq = {
                "stage": "ROADMAP_APPLY",
                "error_code": "UNHANDLED_ERROR",
                "message": "Roadmap apply failed",
                "step_id": summary.get("failed_step_id"),
                "milestone_id": summary.get("failed_milestone_id"),
                "ts": _now_iso8601(),
            }
            summary["status"] = "FAIL"
        write_json(evidence_paths.dlq_path, state.dlq)
    finally:
        finished = time.monotonic()
        summary["finished_at"] = _now_iso8601()
        summary["duration_ms"] = int((finished - started) * 1000)
        write_json(evidence_paths.summary_path, summary)
        write_integrity_manifest(evidence_paths.run_dir)

    return summary


def _prepare_baselines_and_policy(
    *,
    core_root: Path,
    workspace_root: Path,
    dry_run: bool,
    dry_run_mode: str,
) -> tuple[Any, Any, dict[str, Any]]:
    baseline_git_status, baseline_workspace_snapshot = _prepare_readonly_baselines(
        core_root=core_root,
        workspace_root=workspace_root,
        dry_run=dry_run,
        dry_run_mode=dry_run_mode,
    )

    if not workspace_root.exists() or not workspace_root.is_dir():
        raise ValueError(f"WORKSPACE_ROOT_INVALID: {workspace_root}")

    core_policy = _load_core_immutability_policy(core_root=core_root, workspace_root=workspace_root)
    return baseline_git_status, baseline_workspace_snapshot, core_policy


def _build_apply_result(
    *,
    summary: dict[str, Any],
    run_id: str,
    evidence_paths: Any,
    core_root: Path,
    dry_run: bool,
    dry_run_mode: str,
) -> dict[str, Any]:
    return {
        "status": "OK" if summary.get("status") == "OK" else "FAIL",
        "run_id": run_id,
        "evidence_path": str(evidence_paths.run_dir.relative_to(core_root))
        if evidence_paths.run_dir.is_relative_to(core_root)
        else str(evidence_paths.run_dir),
        "dry_run": bool(dry_run),
        "dry_run_mode": str(dry_run_mode),
        "milestones_executed": summary.get("milestones_executed"),
        "failed_step_id": summary.get("failed_step_id"),
        "failed_milestone_id": summary.get("failed_milestone_id"),
        "failed_error_code": summary.get("failed_error_code"),
        "failed_message": summary.get("failed_message"),
        "failed_cmd": summary.get("failed_cmd"),
        "failed_return_code": summary.get("failed_return_code"),
        "failed_stderr_preview": summary.get("failed_stderr_preview"),
        "failed_stdout_preview": summary.get("failed_stdout_preview"),
    }


def apply_roadmap(
    *,
    roadmap_path: Path,
    core_root: Path,
    workspace_root: Path,
    cache_root: Path,
    evidence_root: Path,
    dry_run: bool,
    dry_run_mode: str = "simulate",
    milestone_ids: list[str] | None = None,
) -> dict[str, Any]:
    core_root, workspace_root, cache_root, evidence_root = _resolve_roots(
        core_root=core_root,
        workspace_root=workspace_root,
        cache_root=cache_root,
        evidence_root=evidence_root,
    )

    _validate_dry_run_mode(dry_run_mode)
    baseline_git_status, baseline_workspace_snapshot, core_policy = _prepare_baselines_and_policy(
        core_root=core_root,
        workspace_root=workspace_root,
        dry_run=dry_run,
        dry_run_mode=dry_run_mode,
    )

    plan, plan_id = _load_and_validate_plan(
        roadmap_path=roadmap_path,
        core_root=core_root,
        cache_root=cache_root,
        milestone_ids=milestone_ids,
    )

    run_id = _build_run_id(plan_id)
    started = time.monotonic()

    evidence_paths = init_evidence_dir(evidence_root, run_id)
    roadmap_hash, plan_hash = _write_plan_evidence(
        roadmap_path=roadmap_path,
        plan=plan,
        evidence_paths=evidence_paths,
    )

    summary = _build_summary(
        run_id=run_id,
        plan=plan,
        plan_id=plan_id,
        dry_run=dry_run,
        dry_run_mode=dry_run_mode,
        milestone_ids=milestone_ids,
        workspace_root=workspace_root,
        core_root=core_root,
        roadmap_hash=roadmap_hash,
        plan_hash=plan_hash,
    )

    summary = _execute_plan(
        plan=plan,
        summary=summary,
        evidence_paths=evidence_paths,
        roadmap_path=roadmap_path,
        core_root=core_root,
        core_policy=core_policy,
        workspace_root=workspace_root,
        dry_run=dry_run,
        dry_run_mode=dry_run_mode,
        baseline_git_status=baseline_git_status,
        baseline_workspace_snapshot=baseline_workspace_snapshot,
        started=started,
    )

    return _build_apply_result(
        summary=summary,
        run_id=run_id,
        evidence_paths=evidence_paths,
        core_root=core_root,
        dry_run=dry_run,
        dry_run_mode=dry_run_mode,
    )
