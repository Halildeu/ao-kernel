"""AO-MA-11E-2b sync engine unit tests.

Pins:
- Dry-run produces planned changes but NO applied changes.
- Apply requires full confirmation chain (typed + accepted digest + network + token).
- Apply with valid chain produces applied_changes.
- Idempotent: same input → same plan.
- Foreign labels preserved (mirror-managed namespace only).
- Environment preflight fail-closed when missing/no-reviewers.
- Token never leaks into report.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.ao_ma.github_mirror_sync import (
    ChangeRecord,
    SyncState,
    compute_canonical_plan_digest,
    render_issue_body,
    sync_v5_mirror,
)


# ---- Canonical digest invariants (Codex iter-2 absorb) ----


def test_canonical_digest_excludes_checked_at():
    """Same plan + different checked_at → same digest."""
    base = {
        "schema_version": "ao-ma-github-mirror-sync-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "checked_at": "2026-06-01T00:00:00Z",
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 1, "labels": 0, "project_items": 0},
        "planned_changes": [
            {
                "category": "issue_body_rewrite",
                "object_type": "issue",
                "object_id": "774",
                "before": "x",
                "after": "y",
            }
        ],
    }
    other_time = dict(base)
    other_time["checked_at"] = "2026-06-02T00:00:00Z"
    assert compute_canonical_plan_digest(base) == compute_canonical_plan_digest(other_time)


def test_canonical_digest_changes_when_plan_changes():
    """Different planned_changes → different digest."""
    base = {
        "schema_version": "ao-ma-github-mirror-sync-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "checked_at": "2026-06-01T00:00:00Z",
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 1, "labels": 0, "project_items": 0},
        "planned_changes": [],
    }
    with_change = dict(base)
    with_change["planned_changes"] = [
        {
            "category": "issue_body_rewrite",
            "object_type": "issue",
            "object_id": "774",
            "before": "x",
            "after": "y",
        }
    ]
    assert compute_canonical_plan_digest(base) != compute_canonical_plan_digest(with_change)


def test_canonical_digest_excludes_volatile_fields():
    """sync_state, applied_changes, environment_preflight ignored."""
    base = {
        "schema_version": "ao-ma-github-mirror-sync-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 0, "labels": 0, "project_items": 0},
        "planned_changes": [],
    }
    augmented = dict(base)
    augmented["applied_changes"] = [
        {
            "category": "issue_body_rewrite",
            "object_type": "issue",
            "object_id": "1",
            "before": "x",
            "after": "y",
        }
    ]
    augmented["sync_state"] = "applied"
    augmented["environment_preflight"] = {
        "environment_name": "x",
        "environment_exists": True,
        "required_reviewers_count": 5,
        "environment_preflight_decision": "pass",
    }
    augmented["reason"] = "some reason"
    augmented["checked_at"] = "2099-12-31T23:59:59Z"
    assert compute_canonical_plan_digest(base) == compute_canonical_plan_digest(augmented)


def test_canonical_digest_format_is_sha256_prefixed():
    digest = compute_canonical_plan_digest({})
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_canonical_digest_stable_under_planned_changes_reordering():
    """Codex iter-3 §3 absorb: digest MUST be stable when planned_changes is in
    a different order (set iteration would otherwise produce non-deterministic
    output across runs/PYTHONHASHSEED values).
    """
    base = {
        "schema_version": "ao-ma-github-mirror-sync-report.v1",
        "projection_manifest": "x.json",
        "manifest_sha256": "sha256:" + "0" * 64,
        "github_owner": "Halildeu",
        "github_repo": "ao-kernel",
        "expected_counts": {"issues": 0, "labels": 0, "project_items": 0},
        "planned_changes": [
            {
                "category": "label_add",
                "object_type": "label",
                "object_id": "774:epic-1",
                "before": None,
                "after": "epic-1",
            },
            {
                "category": "label_add",
                "object_type": "label",
                "object_id": "775:epic-2",
                "before": None,
                "after": "epic-2",
            },
            {
                "category": "issue_body_rewrite",
                "object_type": "issue",
                "object_id": "774",
                "before": "x",
                "after": "y",
            },
        ],
    }
    reordered = dict(base)
    reordered["planned_changes"] = list(reversed(base["planned_changes"]))
    assert compute_canonical_plan_digest(base) == compute_canonical_plan_digest(reordered), (
        "digest MUST be stable when planned_changes order varies"
    )


def test_plan_label_changes_emit_in_sorted_order(tmp_path):
    """Codex iter-3 §3 absorb: plan computation emits sorted set-difference
    iteration (label_add + label_remove), so digest is stable across runs.
    """
    # Build manifest with multiple expected mirror labels for a single issue
    manifest = {
        "schema_version": "v5-issue-projection.v1",
        "labels": [],
        "first_wave_issues": [
            {
                "id": "E-1",
                "title": "x",
                "labels": ["epic-1", "guard-flip:live_adapter", "status:planned"],
                "body_anchor": {
                    "spm_anchor": "X",
                    "slice_id": "Y",
                    "ao_authority_artifact": "p",
                    "artifact_sha256": _VALID_ARTIFACT_SHA,
                    "plan_digest": _VALID_PLAN_DIGEST,
                },
                "metadata": {},
            }
        ],
        "runtime_created_state": {
            "milestone": {"number": 3, "title": "x"},
            "issues_created": {"E-1": 774},
            "project_board": {"number": 3, "node_id": "PVT_x", "items_count": 1},
            "issue_anchor_pin": {
                "artifact_sha256_at_issue_creation": _VALID_ARTIFACT_SHA,
                "plan_digest_at_issue_creation": _VALID_PLAN_DIGEST,
            },
        },
    }
    path = tmp_path / "m.json"
    path.write_text(json.dumps(manifest))

    # Caller returns issue with NO mirror labels
    def caller(method, path_, body=None):
        if path_ == ("/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100"):
            return [{"number": 774, "body": "x", "labels": []}]
        if path_ == "graphql:project_items:PVT_x":
            return {
                "items": [
                    {
                        "id": "i1",
                        "content": {
                            "number": 774,
                            "url": "https://github.com/Halildeu/ao-kernel/issues/774",
                        },
                    }
                ]
            }
        raise KeyError(path_)

    report = sync_v5_mirror(
        projection_manifest_path=path,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=False,
        now_iso=_now(),
    )
    # Extract label_add object_ids in emission order
    label_adds = [c.object_id for c in report.planned_changes if c.category == "label_add"]
    assert label_adds == sorted(label_adds), f"label_add changes MUST be emitted in sorted order; got {label_adds}"


_VALID_ARTIFACT_SHA = "sha256:" + "0" * 64
_VALID_PLAN_DIGEST = "sha256:" + "f" * 64
_VALID_ACCEPTED_DIGEST = "sha256:" + "a" * 64
_APPLY_CONFIRMATION = "AO-MA-11E-2B-APPLY"


def _make_manifest(tmp_path: Path) -> Path:
    manifest = {
        "schema_version": "v5-issue-projection.v1",
        "labels": ["epic-1", "epic-2", "mirror:authority"],
        "first_wave_issues": [
            {
                "id": "E-1",
                "title": "[Epic 1] Test",
                "labels": ["epic-1", "mirror:authority"],
                "body_anchor": {
                    "spm_anchor": "AO-MA-SPM-V5-EPIC-1",
                    "slice_id": "V5-EPIC-1",
                    "ao_authority_artifact": "x.md",
                    "artifact_sha256": _VALID_ARTIFACT_SHA,
                    "plan_digest": _VALID_PLAN_DIGEST,
                },
                "metadata": {
                    "risk_class_source": "computed_normal",
                    "evidence_classes": ["a", "b"],
                },
            },
        ],
        "runtime_created_state": {
            "milestone": {"number": 3, "title": "x"},
            "issues_created": {"E-1": 774},
            "project_board": {"number": 3, "node_id": "PVT_xxx", "items_count": 1},
            "issue_anchor_pin": {
                "artifact_sha256_at_issue_creation": _VALID_ARTIFACT_SHA,
                "plan_digest_at_issue_creation": _VALID_PLAN_DIGEST,
            },
        },
    }
    path = tmp_path / "projection.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _make_caller_synced(expected_body: str):
    """Caller returning issue state that matches expected body (no drift)."""

    def caller(method: str, path: str, body: Any = None) -> Any:
        if path == "/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100":
            return [
                {
                    "number": 774,
                    "body": expected_body,
                    "labels": [{"name": "epic-1"}, {"name": "mirror:authority"}],
                }
            ]
        if path == "graphql:project_items:PVT_xxx":
            return {
                "items": [
                    {
                        "id": "i1",
                        "content": {
                            "number": 774,
                            "url": "https://github.com/Halildeu/ao-kernel/issues/774",
                        },
                    }
                ]
            }
        if path == "/repos/Halildeu/ao-kernel/environments/ao-ma-mirror-sync":
            return {
                "name": "ao-ma-mirror-sync",
                "protection_rules": [{"type": "required_reviewers", "reviewers": [{"id": 1}]}],
            }
        raise KeyError(path)

    return caller


def _make_caller_drift(expected_body: str = ""):
    """Caller returning drifted issue state (different body)."""

    def caller(method: str, path: str, body: Any = None) -> Any:
        if path == "/repos/Halildeu/ao-kernel/issues?milestone=3&state=all&per_page=100":
            return [
                {
                    "number": 774,
                    "body": "OLD BODY WITH DRIFT",
                    "labels": [{"name": "epic-1"}, {"name": "mirror:authority"}],
                }
            ]
        if path == "graphql:project_items:PVT_xxx":
            return {
                "items": [
                    {
                        "id": "i1",
                        "content": {
                            "number": 774,
                            "url": "https://github.com/Halildeu/ao-kernel/issues/774",
                        },
                    }
                ]
            }
        if path == "/repos/Halildeu/ao-kernel/environments/ao-ma-mirror-sync":
            return {
                "name": "ao-ma-mirror-sync",
                "protection_rules": [{"type": "required_reviewers", "reviewers": [{"id": 1}]}],
            }
        # Write paths during apply
        if method in ("PATCH", "POST", "DELETE"):
            return {"ok": True}
        raise KeyError(path)

    return caller


def _now() -> str:
    return "2026-06-01T08:00:00Z"


# ---- Dry-run ----


def test_dry_run_produces_planned_no_applied(tmp_path):
    manifest = _make_manifest(tmp_path)
    caller = _make_caller_drift()
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=False,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.DRY_RUN_COMPLETE
    assert len(report.planned_changes) >= 1  # at least body rewrite
    assert report.applied_changes == []
    assert report.to_exit_code() == 0


def test_dry_run_synced_state_has_no_planned(tmp_path):
    manifest = _make_manifest(tmp_path)
    meta = json.loads(manifest.read_text())["first_wave_issues"][0]
    expected_body = render_issue_body(anchor=meta["body_anchor"], metadata=meta["metadata"], title=meta["title"])
    caller = _make_caller_synced(expected_body)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=False,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.DRY_RUN_COMPLETE
    assert report.planned_changes == []
    assert report.applied_changes == []


# ---- Apply confirmation chain ----


def test_apply_rejects_missing_confirmation(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation=None,
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.USAGE_ERROR
    assert "confirmation" in (report.reason or "").lower()


def test_apply_rejects_wrong_confirmation(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation="WRONG-TOKEN",
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.USAGE_ERROR


def test_apply_rejects_missing_accepted_digest(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest=None,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.USAGE_ERROR
    assert "accepted" in (report.reason or "").lower() or "digest" in (report.reason or "").lower()


def test_apply_rejects_invalid_digest_format(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest="not-a-valid-sha",
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.USAGE_ERROR


def test_apply_rejects_no_network(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=False,
        token_present=True,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.USAGE_ERROR


def test_apply_rejects_no_token(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_present=False,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.USAGE_ERROR


# ---- Apply with full chain ----


def test_apply_with_full_chain_writes_changes(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.APPLIED
    assert len(report.applied_changes) >= 1


# ---- Environment preflight ----


def test_apply_aborts_when_environment_missing(tmp_path):
    manifest = _make_manifest(tmp_path)

    def caller(method, path, body=None):
        if "environments/ao-ma-mirror-sync" in path:
            raise RuntimeError("HTTP 404: Not Found")
        raise KeyError(path)

    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.APPLY_ABORTED
    assert report.environment_preflight.environment_preflight_decision == "fail_closed_missing"


def test_apply_aborts_when_no_required_reviewers(tmp_path):
    manifest = _make_manifest(tmp_path)

    def caller(method, path, body=None):
        if "environments/ao-ma-mirror-sync" in path:
            return {"name": "ao-ma-mirror-sync", "protection_rules": []}
        raise KeyError(path)

    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=True,
        confirmation=_APPLY_CONFIRMATION,
        accepted_dry_run_report_digest=_VALID_ACCEPTED_DIGEST,
        now_iso=_now(),
    )
    assert report.sync_state == SyncState.APPLY_ABORTED
    assert report.environment_preflight.environment_preflight_decision == "fail_closed_no_reviewers"


# ---- Idempotency ----


def test_idempotent_same_input_same_plan(tmp_path):
    manifest = _make_manifest(tmp_path)
    caller = _make_caller_drift()
    r1 = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=False,
        now_iso=_now(),
    )
    r2 = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=caller,
        network_allowed=True,
        token_present=True,
        apply_mode=False,
        now_iso=_now(),
    )
    # Same input → same plan structure
    assert len(r1.planned_changes) == len(r2.planned_changes)


# ---- Token redaction ----


def test_report_dict_never_contains_token_value(tmp_path):
    manifest = _make_manifest(tmp_path)
    report = sync_v5_mirror(
        projection_manifest_path=manifest,
        gh_api_caller=_make_caller_drift(),
        network_allowed=True,
        token_env="GH_TOKEN",
        token_present=True,
        apply_mode=False,
        now_iso=_now(),
    )
    serialized = json.dumps(report.to_dict())
    assert "ghp_" not in serialized
    assert "gho_" not in serialized


# ---- Issue body template ----


def test_render_body_emits_strict_5_field_anchor():
    body = render_issue_body(
        anchor={
            "spm_anchor": "X",
            "slice_id": "Y",
            "ao_authority_artifact": "p",
            "artifact_sha256": _VALID_ARTIFACT_SHA,
            "plan_digest": _VALID_PLAN_DIGEST,
        },
        metadata={"risk_class_source": "computed_normal", "evidence_classes": ["a"]},
        title="x",
    )
    assert "## V5 Anchor (manifest-driven binding)" in body
    assert "## V5 Metadata" in body
    assert "**spm_anchor:** `X`" in body
    assert "**risk_class_source:** `computed_normal`" in body
    # No display suffix in SHA values
    assert f"`{_VALID_ARTIFACT_SHA}` (" not in body


def test_render_body_no_display_suffix_in_sha_values():
    body = render_issue_body(
        anchor={
            "spm_anchor": "X",
            "slice_id": "Y",
            "ao_authority_artifact": "p",
            "artifact_sha256": _VALID_ARTIFACT_SHA,
            "plan_digest": _VALID_PLAN_DIGEST,
        },
        metadata={},
        title="x",
    )
    # plan_digest must be pure sha256 value, no "(manifest ...)" suffix
    plan_digest_line = [line for line in body.split("\n") if "**plan_digest:**" in line][0]
    assert plan_digest_line.strip().endswith("`")  # ends with backtick (no trailing text)


# ---- ChangeRecord validation ----


def test_change_record_rejects_unknown_category():
    with pytest.raises(ValueError):
        ChangeRecord(
            category="bad_category",
            object_type="issue",
            object_id="1",
            before=None,
            after=None,
        )


def test_change_record_rejects_unknown_object_type():
    with pytest.raises(ValueError):
        ChangeRecord(
            category="issue_body_rewrite",
            object_type="bad_type",
            object_id="1",
            before=None,
            after=None,
        )
