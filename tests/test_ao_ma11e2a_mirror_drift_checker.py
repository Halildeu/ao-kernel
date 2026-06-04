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
            },
            {
                "id": "E-2",
                "title": "[Epic 2] Live adapter execution",
                "labels": ["epic-2", "mirror:authority"],
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
        },
    }
    path = tmp_path / "projection.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _attach_subissues_manifest(
    projection_manifest: Path,
    *,
    issue_number: int = 900,
    labels: list[str] | None = None,
) -> Path:
    """Attach a minimal v5_subissues_mirror manifest to a projection fixture."""
    subissues = {
        "schema_version": "v5-subissues-mirror.v1",
        "sub_issues": {
            "E-1-1": {
                "issue_number": issue_number,
                "slice_id": "E-1-1",
                "labels": labels or ["epic-1", "risk:normal", "status:done"],
            }
        },
    }
    subissues_path = projection_manifest.parent / "v5_subissues_mirror.v1.json"
    subissues_path.write_text(json.dumps(subissues, indent=2), encoding="utf-8")

    manifest = json.loads(projection_manifest.read_text(encoding="utf-8"))
    manifest["runtime_created_state"]["sub_issues_mirror_ref"] = {
        "mirror_manifest_path": "v5_subissues_mirror.v1.json",
        "created_count": 1,
    }
    manifest["runtime_created_state"]["project_board"]["items_count"] = 3
    projection_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return projection_manifest


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


def test_subissue_manifest_issue_is_not_extra_and_does_not_require_parent_anchor(tmp_path):
    manifest = _attach_subissues_manifest(_make_manifest(tmp_path))
    responses = _make_synced_responses()
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"].append(
        {
            "number": 900,
            # Retro sub-slice mirror issues use a compact body, not the parent
            # `## V5 Anchor` block. The drift checker should still verify
            # inventory + labels without manufacturing anchor drift.
            "body": "**Parent epic:** #774\n\n**Slice ID:** E-1-1\n",
            "labels": [
                {"name": "epic-1"},
                {"name": "risk:normal"},
                {"name": "status:done"},
            ],
        }
    )
    responses["graphql:project_items:PVT_xxx"] = {
        "items": [
            {"id": "i1", "content": {"number": 774}},
            {"id": "i2", "content": {"number": 775}},
            {"id": "i3", "content": {"number": 900}},
        ]
    }
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert report.exit_decision == ExitDecision.SYNCED
    assert report.drift == []
    assert report.expected_counts["issues"] == 3


def test_subissue_manifest_still_rejects_unexpected_extra_issue(tmp_path):
    manifest = _attach_subissues_manifest(_make_manifest(tmp_path))
    responses = _make_synced_responses()
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"].append(
        {
            "number": 901,
            "body": "**Slice ID:** E-unknown\n",
            "labels": [{"name": "epic-1"}],
        }
    )
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert any(d.category == "missing_issue" and d.object_id == "900" for d in report.drift)
    assert any(d.category == "extra_issue" and d.object_id == "901" for d in report.drift)


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


def test_anchor_known_template_fields_and_digest_annotation_are_accepted(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    responses["/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"][0]["body"] = (
        "## V5 Anchor\n"
        "- **spm_anchor:** `AO-MA-SPM-V5-EPIC-1`\n"
        "- **slice_id:** `V5-EPIC-1`\n"
        "- **ao_authority_artifact:** `.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`\n"
        f"- **artifact_sha256:** `{_VALID_ARTIFACT_SHA}`\n"
        f"- **plan_digest:** `{_VALID_PLAN_DIGEST}` (manifest `.claude/plans/v5_issue_projection.v1.json`)\n"
        "- **risk_class_source:** `computed_normal` (computed; NOT manually downgraded)\n"
        "- **evidence_classes:** [plan_doc, projection_manifest]\n"
        "- **consensus_state:** `agreed`\n"
    )
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert not any(d.category == "anchor_schema_mismatch" for d in report.drift)
    assert not any(d.category == "anchor_sha_format_invalid" for d in report.drift)


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


def test_project_item_count_ignores_non_issue_project_items(tmp_path):
    manifest = _make_manifest(tmp_path)
    responses = _make_synced_responses()
    responses["graphql:project_items:PVT_xxx"] = {
        "items": [
            {"id": "i1", "content": {"number": 774}},
            {"id": "i2", "content": {"number": 775}},
            {"id": "draft1", "content": None},
        ]
    }
    caller = _make_caller(responses)
    report = check_github_mirror_drift(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        now_iso=_now(),
    )
    assert report.exit_decision == ExitDecision.SYNCED
    assert report.drift == []


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
