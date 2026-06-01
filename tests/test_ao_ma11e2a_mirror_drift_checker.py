"""AO-MA-11E-2a invariant tests for GitHub mirror drift checker.

Pure-stdlib tests; no real GitHub API calls (gh_api_caller mocked).
Pin: every drift category trigger + happy path + exit code semantics +
secret redaction + schema conformance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.ao_ma.github_mirror_drift import (
    DriftFinding,
    DriftReport,
    ExitDecision,
    check_github_mirror_drift,
    parse_issue_anchor,
)


# ---- Fixture: minimal valid projection manifest ----


_VALID_ARTIFACT_SHA = "sha256:" + "0" * 64
_VALID_PLAN_DIGEST = "sha256:" + "f" * 64


def _make_manifest(tmp_path: Path) -> Path:
    manifest = {
        "schema_version": "v5-issue-projection.v1",
        "milestone": {
            "title": "v5.0.0 — Full Production Promotion",
            "due_on": "2026-12-31T00:00:00Z",
        },
        "labels": ["epic-1", "epic-2"],
        "first_wave_issues": [
            {
                "id": "E-1",
                "title": "[Epic 1] AO-MA-SPM follow-up",
                "labels": ["epic-1", "mirror:authority"],
                "body_anchor": {
                    "spm_anchor": "AO-MA-SPM-V5-EPIC-1",
                    "slice_id": "V5-EPIC-1",
                    "ao_authority_artifact": ".claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md",
                },
            },
            {
                "id": "E-2",
                "title": "[Epic 2] Live adapter execution",
                "labels": ["epic-2", "mirror:authority"],
                "body_anchor": {
                    "spm_anchor": "AO-MA-SPM-V5-EPIC-2",
                    "slice_id": "V5-EPIC-2",
                    "ao_authority_artifact": ".claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md",
                },
            },
        ],
        "runtime_created_state": {
            "milestone": {
                "number": 3,
                "title": "v5.0.0 — Full Production Promotion",
                "due_on": "2026-12-31T00:00:00Z",
            },
            "issues_created": {"E-1": 774, "E-2": 775},
            "project_board": {
                "number": 3,
                "node_id": "PVT_xxx",
                "items_count": 2,
            },
            "issue_anchor_pin": {
                "artifact_sha256_at_issue_creation": _VALID_ARTIFACT_SHA,
                "plan_digest_at_issue_creation": _VALID_PLAN_DIGEST,
                "master_plan_sha256_at_issue_creation": "sha256:" + "a" * 64,
            },
        },
    }
    path = tmp_path / "projection.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _valid_anchor_body(*, spm_anchor: str, slice_id: str) -> str:
    return (
        "## V5 Anchor\n"
        f"- **spm_anchor:** `{spm_anchor}`\n"
        f"- **slice_id:** `{slice_id}`\n"
        "- **ao_authority_artifact:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`\n"
        f"- **artifact_sha256:** `{_VALID_ARTIFACT_SHA}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )


def _make_synced_responses() -> dict[str, Any]:
    """Return canned API responses for the synced happy path."""
    return {
        "/repos/Halildeu/ao-kernel/milestones/3": {
            "number": 3,
            "title": "v5.0.0 — Full Production Promotion",
            "due_on": "2026-12-31T00:00:00Z",
        },
        "/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100": [
            {
                "number": 774,
                "body": _valid_anchor_body(spm_anchor="AO-MA-SPM-V5-EPIC-1", slice_id="V5-EPIC-1"),
                "labels": [{"name": "epic-1"}, {"name": "mirror:authority"}],
            },
            {
                "number": 775,
                "body": _valid_anchor_body(spm_anchor="AO-MA-SPM-V5-EPIC-2", slice_id="V5-EPIC-2"),
                "labels": [{"name": "epic-2"}, {"name": "mirror:authority"}],
            },
        ],
        "graphql:project_items:PVT_xxx": {
            "items": [
                {"id": "i1", "content": {"number": 774}},
                {"id": "i2", "content": {"number": 775}},
            ]
        },
    }


def _make_caller(responses: dict[str, Any]):
    """Build a deterministic gh_api_caller from a path → response map."""

    def caller(method: str, path: str) -> Any:
        if path not in responses:
            raise KeyError(f"unexpected api path: {path}")
        return responses[path]

    return caller


def _now() -> str:
    return "2026-06-01T07:00:00Z"


# ---- Happy path ----


def test_happy_path_synced_no_drift(tmp_path):
    manifest = _make_manifest(tmp_path)
    caller = _make_caller(_make_synced_responses())
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        now_iso=_now(),
    )
    assert report.exit_decision == ExitDecision.SYNCED
    assert report.drift == []
    assert report.to_exit_code() == 0


# ---- Network not allowed ----


def test_network_not_allowed_short_circuits(tmp_path):
    manifest = _make_manifest(tmp_path)
    caller = _make_caller({})  # caller never invoked
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=False,
        now_iso=_now(),
    )
    assert report.exit_decision == ExitDecision.NETWORK_NOT_ALLOWED
    assert report.to_exit_code() == 2


# ---- Drift categories ----


def test_missing_milestone(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    responses["/repos/Halildeu/ao-kernel/milestones/3"] = None
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "missing_milestone" for d in report.drift)
    assert report.exit_decision == ExitDecision.MIRROR_DRIFT_DETECTED


def test_milestone_metadata_mismatch(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    responses["/repos/Halildeu/ao-kernel/milestones/3"]["title"] = "wrong title"
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "milestone_metadata_mismatch" for d in report.drift)
    assert report.exit_decision == ExitDecision.MIRROR_DRIFT_DETECTED


def test_missing_issue(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Drop issue 775
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"] = [
        responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]
    ]
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "missing_issue" and d.object_id == "775" for d in report.drift)


def test_extra_issue(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Add unexpected issue 999
    extra = {
        "number": 999,
        "body": _valid_anchor_body(spm_anchor="X", slice_id="X"),
        "labels": [{"name": "mirror:authority"}],
    }
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"].append(extra)
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "extra_issue" and d.object_id == "999" for d in report.drift)


def test_anchor_value_mismatch(tmp_path):
    """Codex iter-1 §1 absorb: anchor format-valid but value WRONG must drift."""
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Issue 774 body has format-valid anchor but wrong spm_anchor value
    wrong_body = (
        "## V5 Anchor\n"
        "- **spm_anchor:** `WRONG-ANCHOR-VALUE`\n"
        "- **slice_id:** `V5-EPIC-1`\n"
        "- **ao_authority_artifact:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`\n"
        f"- **artifact_sha256:** `{_VALID_ARTIFACT_SHA}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] = wrong_body
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    # Anchor format passes but value comparison drifts
    drift_categories = [d.category for d in report.drift]
    assert "anchor_mismatch" in drift_categories
    assert report.exit_decision.value == "mirror_drift_detected"


def test_anchor_sha_value_mismatch(tmp_path):
    """Codex iter-1 §1: artifact_sha256 must match issue_anchor_pin runtime value."""
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    wrong_sha = "sha256:" + "9" * 64  # format-valid but wrong value
    wrong_body = (
        "## V5 Anchor\n"
        "- **spm_anchor:** `AO-MA-SPM-V5-EPIC-1`\n"
        "- **slice_id:** `V5-EPIC-1`\n"
        "- **ao_authority_artifact:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`\n"
        f"- **artifact_sha256:** `{wrong_sha}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] = wrong_body
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "anchor_mismatch" for d in report.drift)


def test_project_item_url_mismatch_same_count(tmp_path):
    """Codex iter-1 §2 absorb: same item count but wrong URLs MUST drift."""
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Replace expected item URLs with wrong ones (same count = 2)
    responses["graphql:project_items:PVT_xxx"] = {
        "items": [
            {"id": "i1", "content": {"number": 999, "url": "https://github.com/Halildeu/ao-kernel/issues/999"}},
            {"id": "i2", "content": {"number": 998, "url": "https://github.com/Halildeu/ao-kernel/issues/998"}},
        ]
    }
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "project_item_url_mismatch" for d in report.drift)
    assert report.exit_decision.value == "mirror_drift_detected"


def test_pagination_cap_exceeds_returns_usage_error(tmp_path):
    """Codex iter-1 §F absorb: expected_issue_count > 100 must fail-closed."""
    manifest_dict = {
        "schema_version": "v5-issue-projection.v1",
        "labels": [],
        "first_wave_issues": [],
        "runtime_created_state": {
            "milestone": {"number": 3, "title": "x"},
            "issues_created": {f"E-{i}": 1000 + i for i in range(101)},  # 101 > 100
            "project_board": {"number": 3, "node_id": "PVT_x", "items_count": 101},
            "issue_anchor_pin": {},
        },
    }
    path = tmp_path / "big.json"
    path.write_text(json.dumps(manifest_dict), encoding="utf-8")
    caller = _make_caller({})
    report = check_github_mirror_drift(
        projection_manifest_path=path,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert report.exit_decision.value == "usage_error"
    assert report.to_exit_code() == 2


def test_label_mismatch(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Issue 774 missing epic-1 label
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["labels"] = [
        {"name": "mirror:authority"}
    ]
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "label_mismatch" and d.object_id == "774" for d in report.drift)


def test_anchor_missing(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Issue 774 body missing spm_anchor
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] = (
        "## V5 Anchor\n"
        "- **slice_id:** `V5-EPIC-1`\n"
        "- **ao_authority_artifact:** `path`\n"
        f"- **artifact_sha256:** `{_VALID_ARTIFACT_SHA}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "anchor_mismatch" and d.object_id == "774" for d in report.drift)


def test_anchor_duplicate(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Issue 774 body has duplicate spm_anchor
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] += (
        "- **spm_anchor:** `DUPLICATE-ANCHOR`\n"
    )
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "anchor_mismatch" and d.object_id == "774" for d in report.drift)


def test_anchor_unknown_field(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Issue 774 body has unknown anchor field
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] += (
        "- **unauthorized_field:** `value`\n"
    )
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "anchor_schema_mismatch" and d.object_id == "774" for d in report.drift)


def test_anchor_sha_format_invalid(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    # Issue 774 body has invalid sha
    bad_body = (
        "## V5 Anchor\n"
        "- **spm_anchor:** `X`\n"
        "- **slice_id:** `X`\n"
        "- **ao_authority_artifact:** `path`\n"
        "- **artifact_sha256:** `not-a-valid-sha`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] = bad_body
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "anchor_sha_format_invalid" and d.object_id == "774" for d in report.drift)


def test_anchor_placeholder_unresolved(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    placeholder_body = (
        "## V5 Anchor\n"
        "- **spm_anchor:** `X`\n"
        "- **slice_id:** `X`\n"
        "- **ao_authority_artifact:** `path`\n"
        "- **artifact_sha256:** `{computed_at_PR-X2_runtime}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] = placeholder_body
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "anchor_placeholder_unresolved" and d.object_id == "774" for d in report.drift)


def test_project_missing(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    responses["graphql:project_items:PVT_xxx"] = None
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "project_missing" for d in report.drift)


def test_project_item_count_mismatch(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    responses["graphql:project_items:PVT_xxx"] = {"items": [{"id": "i1"}]}  # only 1
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "project_item_count_mismatch" for d in report.drift)


# ---- API error ----


def test_api_error_short_circuits(tmp_path):
    manifest = _make_manifest(tmp_path)

    def broken_caller(method, path):
        raise RuntimeError("simulated gh API failure")

    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=broken_caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert report.exit_decision == ExitDecision.API_ERROR
    assert report.to_exit_code() == 3


# ---- Schema conformance + redaction ----


def test_report_dict_matches_schema_envelope(tmp_path):
    manifest = _make_manifest(tmp_path)
    caller = _make_caller(_make_synced_responses())
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        now_iso=_now(),
    )
    d = report.to_dict()
    # Schema envelope required keys
    for k in (
        "schema_version",
        "projection_manifest",
        "manifest_sha256",
        "checked_at",
        "network_allowed",
        "token_env",
        "token_present",
        "github_owner",
        "github_repo",
        "expected_counts",
        "drift",
        "exit_decision",
    ):
        assert k in d, f"missing key: {k}"
    assert d["schema_version"] == "ao-ma-github-mirror-drift-report.v1"
    assert d["manifest_sha256"].startswith("sha256:")
    assert len(d["manifest_sha256"]) == len("sha256:") + 64


def test_report_never_contains_token_value(tmp_path):
    manifest = _make_manifest(tmp_path)
    caller = _make_caller(_make_synced_responses())
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_env="GH_TOKEN",
        token_present=True,
        now_iso=_now(),
    )
    json_text = json.dumps(report.to_dict())
    # The core module never receives the token value; ensure no plausible token
    # appears anywhere in serialized output (defense in depth).
    assert "ghp_" not in json_text
    assert "gho_" not in json_text


# ---- Exit codes ----


def test_exit_code_synced():
    r = DriftReport(
        projection_manifest="x",
        manifest_sha256="sha256:" + "0" * 64,
        checked_at=_now(),
        network_allowed=True,
        token_env="GH_TOKEN",
        token_present=False,
        github_owner="o",
        github_repo="r",
        expected_counts={"issues": 0, "labels": 0, "project_items": 0},
        drift=[],
        exit_decision=ExitDecision.SYNCED,
    )
    assert r.to_exit_code() == 0


def test_exit_code_drift():
    r = DriftReport(
        projection_manifest="x",
        manifest_sha256="sha256:" + "0" * 64,
        checked_at=_now(),
        network_allowed=True,
        token_env="GH_TOKEN",
        token_present=False,
        github_owner="o",
        github_repo="r",
        expected_counts={"issues": 0, "labels": 0, "project_items": 0},
        drift=[],
        exit_decision=ExitDecision.MIRROR_DRIFT_DETECTED,
    )
    assert r.to_exit_code() == 1


def test_exit_code_network_not_allowed():
    r = DriftReport(
        projection_manifest="x",
        manifest_sha256="sha256:" + "0" * 64,
        checked_at=_now(),
        network_allowed=False,
        token_env="GH_TOKEN",
        token_present=False,
        github_owner="o",
        github_repo="r",
        expected_counts={"issues": 0, "labels": 0, "project_items": 0},
        drift=[],
        exit_decision=ExitDecision.NETWORK_NOT_ALLOWED,
    )
    assert r.to_exit_code() == 2


def test_exit_code_api_error():
    r = DriftReport(
        projection_manifest="x",
        manifest_sha256="sha256:" + "0" * 64,
        checked_at=_now(),
        network_allowed=True,
        token_env="GH_TOKEN",
        token_present=False,
        github_owner="o",
        github_repo="r",
        expected_counts={"issues": 0, "labels": 0, "project_items": 0},
        drift=[],
        exit_decision=ExitDecision.API_ERROR,
    )
    assert r.to_exit_code() == 3


# ---- Anchor parser unit tests ----


def test_parse_anchor_strict_happy():
    body = _valid_anchor_body(spm_anchor="X", slice_id="Y")
    r = parse_issue_anchor(body)
    assert r.missing == []
    assert r.duplicates == []
    assert r.unknown == []
    assert r.sha_format_invalid == []
    assert r.placeholders_unresolved == []
    assert r.fields["spm_anchor"] == "X"
    assert r.fields["slice_id"] == "Y"


def test_parse_anchor_outside_anchor_section_ignored():
    body = (
        "## Some Other Section\n"
        "- **spm_anchor:** `OUTSIDE`\n"
        "\n"
        "## V5 Anchor\n"
        "- **spm_anchor:** `INSIDE`\n"
        "- **slice_id:** `S`\n"
        "- **ao_authority_artifact:** `p`\n"
        f"- **artifact_sha256:** `{_VALID_ARTIFACT_SHA}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}`\n"
    )
    r = parse_issue_anchor(body)
    assert r.fields["spm_anchor"] == "INSIDE"


def test_drift_finding_rejects_unknown_category():
    with pytest.raises(ValueError):
        DriftFinding(
            category="not_a_real_category",
            severity="blocker",
            object_type="issue",
            object_id="1",
            expected=None,
            actual=None,
        )


def test_drift_finding_rejects_unknown_severity():
    with pytest.raises(ValueError):
        DriftFinding(
            category="missing_issue",
            severity="warning",
            object_type="issue",
            object_id="1",
            expected=None,
            actual=None,
        )
