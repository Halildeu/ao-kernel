"""V5 sub-issue mirror status reconciliation invariants.

The GitHub mirror is visibility, not authority. This test pins the repo-side
mirror manifest after the V5 preflight bundle series so stale pending-PR
references cannot reappear as source-of-truth progress.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBISSUES_PATH = ROOT / ".claude" / "plans" / "v5_subissues_mirror.v1.json"
PROJECTION_PATH = ROOT / ".claude" / "plans" / "v5_issue_projection.v1.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"


def _subissues() -> dict:
    return json.loads(SUBISSUES_PATH.read_text(encoding="utf-8"))


def _projection() -> dict:
    return json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_reconciled_subissue_status_counts_are_pinned() -> None:
    data = _subissues()
    status_counts = data["counts"]["status_counts"]

    assert data["counts"]["total_created"] == 62
    assert status_counts == {"merged": 60, "planned": 1, "blocked": 1}
    assert data["status_reconciliation"]["merged_subissues_count"] == 60
    assert data["status_reconciliation"]["planned_or_blocked_subissues"] == ["E-1-5", "E-9-1"]


def test_no_stale_pending_pr_references_remain_in_subissue_status_refs() -> None:
    data = _subissues()
    offenders = [
        (slice_id, item["status_ref"])
        for slice_id, item in data["sub_issues"].items()
        if "pending PR #" in item["status_ref"]
    ]
    assert offenders == []


def test_merged_subissues_use_done_label_and_non_merged_subissues_are_explicit() -> None:
    data = _subissues()
    for slice_id, item in data["sub_issues"].items():
        labels = set(item["labels"])
        if item["status"] == "merged":
            assert "status:done" in labels, slice_id
        elif slice_id == "E-1-5":
            assert item["status"] == "planned"
            assert "status:planned" in labels
        elif slice_id == "E-9-1":
            assert item["status"] == "blocked"
            assert "status:blocked" in labels
        else:
            raise AssertionError(f"unexpected non-merged subissue: {slice_id} -> {item['status']}")


def test_projection_reconciliation_metadata_preserves_v5_boundary() -> None:
    projection = _projection()
    reconciliation = projection["runtime_created_state"]["sub_issues_mirror_ref"]["status_reconciliation"]

    assert reconciliation["merged_subissues_count"] == 60
    assert reconciliation["planned_subissues"] == ["E-1-5"]
    assert reconciliation["blocked_subissues"] == ["E-9-1"]
    assert "matrix_complete=false" in reconciliation["production_readiness_boundary"]
    assert "pr_xfinal_open_allowed=false" in reconciliation["production_readiness_boundary"]


def test_reconciliation_does_not_complete_v5_production_matrix_or_flip_guards() -> None:
    matrix = _matrix()
    projection = _projection()

    assert matrix["matrix_complete"] is False
    assert matrix["pr_xfinal_open_allowed"] is False
    assert matrix["support_widening"] is False
    assert matrix["production_platform_claim"] is False
    assert matrix["live_adapter_execution"] is False

    assert projection["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
