"""AO-MA-11A-2 environment wiring evidence invariants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

import ao_kernel

_REPO_ROOT = Path(ao_kernel.__file__).resolve().parent.parent
_SCHEMA = (
    _REPO_ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "ao-ma-11a-2-environment-wiring-evidence.schema.v1.json"
)
_EVIDENCE = _REPO_ROOT / ".claude" / "plans" / "AO-MA-11A-2-ENVIRONMENT-WIRING-EVIDENCE.v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_schema_is_valid_draft202012() -> None:
    schema = _load_json(_SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-11a-2-environment-wiring-evidence:v1"
    assert schema["additionalProperties"] is False


def test_environment_wiring_evidence_satisfies_schema() -> None:
    schema = _load_json(_SCHEMA)
    evidence = _load_json(_EVIDENCE)
    errors = list(Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], f"environment evidence schema errors: {[e.message for e in errors]}"


def test_environment_wiring_is_single_operator_fail_closed_surface() -> None:
    evidence = _load_json(_EVIDENCE)
    assert evidence["environment_name"] == "ao-ma-plan-approval"
    assert evidence["environment_exists"] is True
    assert evidence["required_reviewers_count"] >= 1
    assert evidence["required_reviewers"] == [{"type": "User", "login": "Halildeu", "id": 186576227}]
    assert evidence["prevent_self_review"] is True
    assert evidence["can_admins_bypass"] is False
    assert evidence["release_authority"] == "ao-release-gate+github-ruleset"
    assert evidence["ai_output_release_authority"] is False
    assert evidence["secrets_recorded"] is False
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_environment_wiring_evidence_hashes_match_bound_artifacts() -> None:
    evidence = _load_json(_EVIDENCE)
    assert evidence["workflow_sha256"] == _sha256(_REPO_ROOT / evidence["workflow_path"])
    assert evidence["plan_doc_sha256"] == _sha256(_REPO_ROOT / evidence["plan_doc_path"])
    assert evidence["gate_cli_sha256"] == _sha256(_REPO_ROOT / evidence["gate_cli_path"])
    assert evidence["gate_report_schema_sha256"] == _sha256(_REPO_ROOT / evidence["gate_report_schema_path"])
