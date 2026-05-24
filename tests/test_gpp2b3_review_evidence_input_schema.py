"""GPP-2B-3 contract test for the ao-release-gate attested review evidence input.

The acceptance-profile schema
``ao-release-gate-review-evidence-input.schema.v1.json`` constrains which
``local-gpp-gate-evidence.v1`` artifacts a future ao-release-gate
``cross_ai_review`` check would accept. These tests pin that contract: a valid
``operator_may_merge`` artifact is accepted, and every acceptance-critical
deviation is rejected.

Design-only slice: no ``ao_release_gate.py`` wiring consumes this schema yet.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

_PROFILE = "ao-release-gate-review-evidence-input.schema.v1.json"
_FULL = "local-gpp-gate-evidence.schema.v1.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict:
    path = _repo_root() / "ao_kernel" / "defaults" / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _accepting_artifact() -> dict:
    """A real local-gpp-gate-evidence.v1 artifact recording operator_may_merge."""
    return {
        "schema_version": "local-gpp-gate-evidence.v1",
        "decision": "operator_may_merge",
        "repo": "Halildeu/ao-kernel",
        "work_package": "GPP-2B-3",
        "generated_at": "2026-05-22T00:00:00Z",
        "checks": {
            "startup_preflight_passed": True,
            "gpp_status_checked": True,
            "scope_allowed": True,
            "tests_passed": True,
            "secret_scan_passed": True,
            "reviewer_agree": True,
            "cross_provider_verified": True,
            "forbidden_actions_absent": True,
        },
        "findings": [],
        "reviewer_findings_count": 0,
        "gpp_2_status": "closed",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }


def test_acceptance_profile_is_valid_schema() -> None:
    """The acceptance-profile schema is a valid Draft 2020-12 schema."""
    profile = _schema(_PROFILE)
    Draft202012Validator.check_schema(profile)
    assert profile["$id"] == "urn:ao:ao-release-gate-review-evidence-input:v1"


def test_accepting_artifact_passes_full_schema_then_profile() -> None:
    """A real operator_may_merge artifact passes the full evidence schema and
    then the acceptance profile — the documented two-step validation order.

    The artifact deliberately carries the gate-output-only fields
    (generated_at, findings, reviewer_findings_count); the profile accepting it
    proves the acceptance profile keeps additionalProperties open by design.
    """
    artifact = _accepting_artifact()
    assert {"generated_at", "findings", "reviewer_findings_count"} <= set(artifact)
    full_errors = list(Draft202012Validator(_schema(_FULL)).iter_errors(artifact))
    assert full_errors == [], f"artifact rejected by full evidence schema: {full_errors}"
    profile_errors = list(Draft202012Validator(_schema(_PROFILE)).iter_errors(artifact))
    assert profile_errors == [], f"artifact rejected by acceptance profile: {profile_errors}"


def test_profile_rejects_fail_closed_decision() -> None:
    """A fail_closed artifact is not accepting review evidence."""
    artifact = _accepting_artifact()
    artifact["decision"] = "fail_closed"
    assert not Draft202012Validator(_schema(_PROFILE)).is_valid(artifact)


def test_profile_rejects_reviewer_disagreement() -> None:
    """reviewer_agree=false fails the acceptance profile."""
    artifact = _accepting_artifact()
    artifact["checks"]["reviewer_agree"] = False
    assert not Draft202012Validator(_schema(_PROFILE)).is_valid(artifact)


def test_profile_rejects_same_provider_review() -> None:
    """cross_provider_verified=false fails the acceptance profile."""
    artifact = _accepting_artifact()
    artifact["checks"]["cross_provider_verified"] = False
    assert not Draft202012Validator(_schema(_PROFILE)).is_valid(artifact)


def test_profile_rejects_open_gpp_guards() -> None:
    """A non-blocked GPP-2 status or any open GPP guard flag fails the profile."""
    validator = Draft202012Validator(_schema(_PROFILE))
    for field, bad_value in (
        ("gpp_2_status", "active"),
        ("support_widening", True),
        ("production_platform_claim", True),
        ("live_adapter_execution", True),
    ):
        artifact = _accepting_artifact()
        artifact[field] = bad_value
        assert not validator.is_valid(artifact), f"profile wrongly accepted open {field}"
