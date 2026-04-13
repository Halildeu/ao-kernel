from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.roadmap.evidence import write_json


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _plan_id_from_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()[:16]


def validate_roadmap(roadmap_obj: Any, schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(roadmap_obj), key=lambda e: e.json_path)
    msgs: list[str] = []
    for err in errors[:25]:
        where = err.json_path or "$"
        msgs.append(f"{where}: {err.message}")
    return msgs


@dataclass(frozen=True)
class CompileResult:
    status: str
    plan_id: str
    plan: dict[str, Any]
    plan_path: Path
    milestones_included: list[str]


def compile_roadmap(
    *,
    roadmap_path: Path,
    schema_path: Path,
    cache_root: Path,
    out_path: Path | None = None,
    milestone_ids: list[str] | None = None,
) -> CompileResult:
    roadmap_path = roadmap_path.resolve()
    raw = roadmap_path.read_bytes()
    roadmap_obj = json.loads(raw.decode("utf-8"))

    errors = validate_roadmap(roadmap_obj, schema_path)
    if errors:
        raise ValueError("ROADMAP_SCHEMA_INVALID: " + "; ".join(errors))

    milestones_all = roadmap_obj.get("milestones", [])
    if not isinstance(milestones_all, list):
        raise ValueError("ROADMAP_INVALID: milestones must be a list")

    # Optional milestone filtering (v0.2): compile a subset plan deterministically.
    requested_ids: list[str] = []
    if milestone_ids is not None:
        requested_ids = [str(x) for x in milestone_ids if str(x).strip()]
        if not requested_ids:
            raise ValueError("ROADMAP_INVALID: milestone_ids is empty")

    milestones_filtered: list[dict[str, Any]] = []
    included_ids: list[str] = []
    if requested_ids:
        req_set = set(requested_ids)
        for ms in milestones_all:
            if not isinstance(ms, dict):
                continue
            ms_id = ms.get("id")
            if isinstance(ms_id, str) and ms_id in req_set:
                milestones_filtered.append(ms)
                included_ids.append(ms_id)
        missing = [mid for mid in requested_ids if mid not in set(included_ids)]
        if missing:
            raise ValueError("ROADMAP_MILESTONE_NOT_FOUND: " + ",".join(missing))
    else:
        for ms in milestones_all:
            if isinstance(ms, dict):
                ms_id = ms.get("id")
                if isinstance(ms_id, str):
                    included_ids.append(ms_id)
                milestones_filtered.append(ms)

    selection_fingerprint = ",".join(included_ids)
    plan_id = _plan_id_from_bytes(raw + b"|milestones=" + selection_fingerprint.encode("utf-8"))
    plan_dir = (cache_root / "roadmap_plans" / plan_id).resolve()
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "plan.json"

    roadmap_id = str(roadmap_obj["roadmap_id"])
    roadmap_version = str(roadmap_obj["version"])
    iso_core_required = bool(roadmap_obj.get("iso_core_required", False))
    global_gates = roadmap_obj.get("global_gates", [])
    roadmap_obj.get("milestones", [])  # reserved for milestone gating

    steps: list[dict[str, Any]] = []

    # v0.1: if iso_core_required, inject a deterministic preflight step with default tenant/files.
    if iso_core_required:
        steps.append(
            {
                "step_id": "PREFLIGHT:ISO_CORE",
                "milestone_id": "_PREFLIGHT",
                "phase": "PREFLIGHT",
                "template": {
                    "type": "iso_core_check",
                    "tenant": "TENANT-DEFAULT",
                    "required_files": [
                        "context.v1.md",
                        "stakeholders.v1.md",
                        "scope.v1.md",
                        "criteria.v1.md",
                    ],
                },
            }
        )

    if isinstance(global_gates, list) and global_gates:
        for i, st in enumerate(global_gates, start=1):
            steps.append(
                {
                    "step_id": f"GLOBAL:G:{i:03d}",
                    "milestone_id": "_GLOBAL",
                    "phase": "GATE",
                    "template": st,
                }
            )

    plan_milestones: list[dict[str, Any]] = []
    for ms in milestones_filtered:
        ms_id = str(ms["id"])
        title = str(ms.get("title", ""))
        constraints = ms.get("constraints") if isinstance(ms.get("constraints"), dict) else {}
        deliverables = []
        if isinstance(ms.get("steps"), list):
            deliverables = ms.get("steps")
        elif isinstance(ms.get("deliverables"), list):
            deliverables = ms.get("deliverables")
        gates = ms.get("gates") if isinstance(ms.get("gates"), list) else []

        for i, st in enumerate(deliverables, start=1):
            steps.append(
                {
                    "step_id": f"{ms_id}:D:{i:03d}",
                    "milestone_id": ms_id,
                    "phase": "DELIVERABLE",
                    "template": st,
                }
            )
        for i, st in enumerate(gates, start=1):
            steps.append(
                {
                    "step_id": f"{ms_id}:G:{i:03d}",
                    "milestone_id": ms_id,
                    "phase": "GATE",
                    "template": st,
                }
            )

        plan_milestones.append(
            {
                "id": ms_id,
                "title": title,
                "constraints": constraints,
                "deliverables_count": len(deliverables),
                "gates_count": len(gates),
            }
        )

    plan: dict[str, Any] = {
        "version": "v1",
        "roadmap_id": roadmap_id,
        "roadmap_version": roadmap_version,
        "iso_core_required": iso_core_required,
        "global_gates_count": int(len(global_gates) if isinstance(global_gates, list) else 0),
        "milestones": plan_milestones,
        "milestones_included": included_ids,
        "steps": steps,
    }

    write_json(plan_path, plan)
    if out_path is not None:
        write_json(out_path, plan)

    return CompileResult(status="OK", plan_id=plan_id, plan=plan, plan_path=plan_path, milestones_included=included_ids)
