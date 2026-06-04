"""V5 Epic 2 E-2-7 invariants: pre-supersession checklist.

E-2-7 is a prerequisite artifact only. It defines the 18 mandatory conditions
for a future Epic 9 PR-Xfinal, while keeping all guard flags closed and keeping
proposal-state authority out of the Epic 2 artifact.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "pre_supersession_checklist.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
DOC_PATH = ROOT / ".claude" / "plans" / "EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md"
PLAN_PATH = ROOT / ".claude" / "plans" / "EPIC-2-LIVE-ADAPTER-EXECUTION.md"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _condition_names() -> list[str]:
    names: list[str] = []
    for item in _schema()["properties"]["checklist"]["prefixItems"]:
        names.append(item["allOf"][1]["properties"]["name"]["const"])
    return names


def _valid_payload() -> dict[str, Any]:
    return {
        "schema_version": "pre_supersession_checklist.v1",
        "artifact_kind": "pre_supersession_checklist",
        "repo": "Halildeu/ao-kernel",
        "work_package": "E-2-7",
        "guard_flip_authority": "epic_9_only",
        "all_conditions_required": True,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "live_adapter_execution_current_state": False,
        "checklist": [
            {"name": name, "status": "unmet", "evidence_ref": None, "attestor": None}
            for name in _condition_names()
        ],
    }


def _is_valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def test_schema_present_valid_draft_2020_12() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ao:pre-supersession-checklist:v1"


def test_valid_reference_payload_validates() -> None:
    assert _is_valid(_valid_payload())


def test_schema_pins_exactly_eighteen_conditions_in_order() -> None:
    names = _condition_names()
    assert names == [
        "Operator authority block",
        "Cross-AI consensus 2-way minimum",
        "7-day live test window",
        "Cost ceiling enforced plus breach evidence plus rollback path",
        "All required CI green",
        "Public claim language sync",
        "Operator-bound rollback procedure",
        "Secret rotation completion",
        "Pricing source freshness",
        "Workflow content SHA pin plus base SHA plus head SHA",
        "Protected environment reviewer proof",
        "Provider/model allowlist",
        "Provider SLA ToS data-retention region policy proof",
        "Budget overrun follow-up issue automation",
        "Branch-protection ruleset source-pin drift check",
        "Required-check name/source collision check",
        "Post-window deauthorization plus secret scope removal",
        "Audit retention plus tamper evidence",
    ]
    assert len(names) == 18
    assert len(set(names)) == 18
    checklist_schema = _schema()["properties"]["checklist"]
    assert checklist_schema["minItems"] == 18
    assert checklist_schema["maxItems"] == 18
    assert checklist_schema["items"] is False


def test_all_guard_flags_are_const_false() -> None:
    schema = _schema()
    for flag in (
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
        "live_adapter_execution_current_state",
    ):
        assert schema["properties"][flag]["const"] is False
        bad = _valid_payload()
        bad[flag] = True
        assert not _is_valid(bad), f"{flag}=true must be rejected"


def test_authority_and_all_conditions_are_pinned() -> None:
    for field, bad in (
        ("guard_flip_authority", "local_gate"),
        ("all_conditions_required", False),
        ("work_package", "E-9-1"),
        ("repo", "other/repo"),
    ):
        payload = _valid_payload()
        payload[field] = bad
        assert not _is_valid(payload), f"{field} pin must reject {bad!r}"


def test_status_evidence_ref_and_attestor_shape() -> None:
    payload = _valid_payload()
    payload["checklist"][0]["status"] = "met"
    payload["checklist"][0]["evidence_ref"] = "urn:ao:evidence:e-2-7:operator-authority"
    payload["checklist"][0]["attestor"] = "Halildeu"
    assert _is_valid(payload)

    bad_status = copy.deepcopy(payload)
    bad_status["checklist"][0]["status"] = "partial"
    assert not _is_valid(bad_status)

    bad_uri = copy.deepcopy(payload)
    bad_uri["checklist"][0]["evidence_ref"] = ""
    assert not _is_valid(bad_uri)

    bad_attestor = copy.deepcopy(payload)
    bad_attestor["checklist"][0]["attestor"] = ""
    assert not _is_valid(bad_attestor)


def test_condition_order_and_cardinality_are_enforced() -> None:
    too_short = _valid_payload()
    too_short["checklist"] = too_short["checklist"][:-1]
    assert not _is_valid(too_short)

    too_long = _valid_payload()
    too_long["checklist"].append({"name": "Extra", "status": "unmet", "evidence_ref": None, "attestor": None})
    assert not _is_valid(too_long)

    swapped = _valid_payload()
    swapped["checklist"][0], swapped["checklist"][1] = swapped["checklist"][1], swapped["checklist"][0]
    assert not _is_valid(swapped)


def test_recursive_strict_closure() -> None:
    root_extra = _valid_payload()
    root_extra["extra"] = "not allowed"
    assert not _is_valid(root_extra)

    item_extra = _valid_payload()
    item_extra["checklist"][0]["extra"] = "not allowed"
    assert not _is_valid(item_extra)


def test_only_local_refs_are_used() -> None:
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                assert ref.startswith("#/"), f"non-local $ref forbidden: {ref}"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(_schema())


def test_schema_has_no_epic_9_proposal_state_field() -> None:
    raw = json.dumps(_schema(), sort_keys=True)
    assert "live_adapter_execution_proposed_state" not in raw
    assert "proposed_state" not in raw


def test_markdown_mirrors_schema_condition_names() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")
    doc_names = re.findall(r"^\d+[.] \*\*(.*?)\*\*", text, flags=re.MULTILINE)
    assert doc_names == _condition_names()
    assert "support_widening = false" in text
    assert "production_platform_claim = false" in text
    assert "live_adapter_execution = false" in text
    assert "live_adapter_execution_current_state = false" in text


def test_plan_e_2_7_and_schema_doc_stay_aligned() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")
    assert "E-2-7 \u2192 3-way **always**" in plan
    assert "Checklist (artifact only)" in plan
    assert SCHEMA_NAME in plan
    assert DOC_PATH.name in plan
