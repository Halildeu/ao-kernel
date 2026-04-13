from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_change(change_obj: Any, schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(change_obj), key=lambda e: e.json_path)
    msgs: list[str] = []
    for err in errors[:25]:
        where = err.json_path or "$"
        msgs.append(f"{where}: {err.message}")
    return msgs


def _find_milestone(roadmap_obj: dict[str, Any], milestone_id: str) -> dict[str, Any] | None:
    milestones = roadmap_obj.get("milestones")
    if not isinstance(milestones, list):
        return None
    for ms in milestones:
        if isinstance(ms, dict) and ms.get("id") == milestone_id:
            return ms
    return None


def _coerce_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("CHANGE_INVALID: replace_milestone_steps requires steps[]")
    out: list[dict[str, Any]] = []
    for idx, step in enumerate(value):
        if not isinstance(step, dict):
            raise ValueError(f"CHANGE_INVALID: steps[{idx}] must be an object")
        step_type = step.get("type")
        if not isinstance(step_type, str) or not step_type.strip():
            raise ValueError(f"CHANGE_INVALID: steps[{idx}].type missing")
        out.append(dict(step))
    return out


def apply_change_to_roadmap_obj(*, roadmap_obj: dict[str, Any], change_obj: dict[str, Any]) -> dict[str, Any]:
    change_type = change_obj.get("type")
    if change_type != "modify":
        raise ValueError(f"CHANGE_TYPE_UNSUPPORTED: {change_type!r}")

    target = change_obj.get("target") if isinstance(change_obj.get("target"), dict) else {}
    target_milestone_id = target.get("milestone_id")
    if not isinstance(target_milestone_id, str) or not target_milestone_id.strip():
        raise ValueError("CHANGE_INVALID: target.milestone_id missing")

    patches = change_obj.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("CHANGE_INVALID: patches must be a non-empty list")

    # Copy top-level (shallow) so callers can keep originals.
    updated = dict(roadmap_obj)
    updated_milestones = []
    for ms in roadmap_obj.get("milestones", []) if isinstance(roadmap_obj.get("milestones"), list) else []:
        updated_milestones.append(dict(ms) if isinstance(ms, dict) else ms)
    updated["milestones"] = updated_milestones

    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError("CHANGE_INVALID: patch entry must be an object")
        op = patch.get("op")
        milestone_id = patch.get("milestone_id")
        if not isinstance(milestone_id, str) or not milestone_id:
            raise ValueError("CHANGE_INVALID: patch.milestone_id missing")
        if milestone_id != target_milestone_id:
            raise ValueError("CHANGE_INVALID: patch.milestone_id must match target.milestone_id")

        ms = _find_milestone(updated, milestone_id)
        if ms is None:
            raise ValueError(f"CHANGE_INVALID: milestone not found: {milestone_id}")

        if op == "append_milestone_note":
            note = patch.get("note")
            if not isinstance(note, str) or not note.strip():
                raise ValueError("CHANGE_INVALID: append_milestone_note requires note")
            notes = ms.get("notes")
            if not isinstance(notes, list):
                notes = []
            notes = [str(x) for x in notes if str(x).strip()]
            notes.append(note)
            ms["notes"] = notes

        elif op == "replace_milestone_notes":
            notes = patch.get("notes")
            if not isinstance(notes, list):
                raise ValueError("CHANGE_INVALID: replace_milestone_notes requires notes[]")
            ms["notes"] = [str(x) for x in notes if str(x).strip()]

        elif op == "replace_milestone_steps":
            ms["steps"] = _coerce_steps(patch.get("steps"))

        elif op == "replace_milestone_title":
            title = patch.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError("CHANGE_INVALID: replace_milestone_title requires title")
            ms["title"] = title

        else:
            raise ValueError(f"PATCH_OP_UNSUPPORTED: {op!r}")

    return updated
