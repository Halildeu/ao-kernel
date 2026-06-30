"""Machine-enforced invariants for the V5 governed control-plane gap audit."""

from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_PATH = (
    _REPO_ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "v5-governed-control-plane-gap-audit.schema.v1.json"
)
_ARTIFACT_PATH = _REPO_ROOT / "docs" / "V5-GOVERNED-CONTROL-PLANE-GAP-AUDIT.v1.json"
_GPP_STATUS_PATH = ".claude/plans/gpp_status.v1.json"
_GUARD_TRUE_PATTERN = re.compile(
    r'^\+\s*"(support_widening_allowed|production_platform_claim_allowed|'
    r'live_adapter_execution_allowed)"\s*:\s*true\b',
    re.MULTILINE,
)


def _load_json(path: Path) -> dict[str, Any]:
    assert path.exists(), f"missing artifact: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _schema() -> dict[str, Any]:
    return _load_json(_SCHEMA_PATH)


def _artifact() -> dict[str, Any]:
    return _load_json(_ARTIFACT_PATH)


def _validator() -> Draft202012Validator:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _git_diff(*args: str) -> str:
    proc = subprocess.run(
        ["git", "diff", "--unified=0", *args, "--", _GPP_STATUS_PATH],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_gap_audit_schema_and_artifact_validate() -> None:
    """The committed audit artifact must validate against its strict schema."""
    errors = list(_validator().iter_errors(_artifact()))
    assert errors == []


def test_gap_audit_keeps_release_boundary_closed() -> None:
    """The audit artifact must not authorize V5 tag/publish or AI release authority."""
    artifact = _artifact()

    assert artifact["guard_flags"] == {
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }
    assert artifact["release_boundary"] == {
        "v5_tag_publish_allowed": False,
        "release_target": "v4.x-governed-control-plane",
        "release_authority": "ao-release-gate-plus-github-branch-protection",
        "ai_output_release_authority": False,
        "fake_minimax_evidence_allowed": False,
        "operator_bound_supersession_required": True,
    }


def test_gap_audit_records_remaining_v5_tag_blockers() -> None:
    """V5 publish remains blocked while RI productization stays non-promotional."""
    items = {item["id"]: item for item in _artifact()["gap_items"]}

    assert items["minimax-provider-evidence-for-997"]["status"] == "done"
    assert (
        items["minimax-provider-evidence-for-997"]["owner_boundary"]
        == "repo_owned_gate"
    )
    assert "PR #997 merged as 12e26204" in (
        items["minimax-provider-evidence-for-997"]["current_evidence"]
    )
    assert "Fake MiniMax AGREE evidence remains forbidden" in (
        items["minimax-provider-evidence-for-997"]["current_evidence"]
    )
    assert items["minimax-provider-evidence-for-997"]["blocking_for_v5_tag_publish"] is False
    ri_item = items["repo-intelligence-promotion-decision"]
    assert ri_item["status"] == "closed_non_promotion"
    assert ri_item["owner_boundary"] == "operator"
    assert ri_item["blocking_for_v5_tag_publish"] is False
    assert "RI-7.8c" in ri_item["evidence_required"]
    assert "RI-7.8c-FINAL-PROMOTE-DECISION.v1.json" in ri_item["current_evidence"]
    assert "non-promotion" in ri_item["current_evidence"]
    assert "beta read-only onboarding" in ri_item["current_evidence"]
    assert "not a general-purpose production promotion" in ri_item["current_evidence"]

    assert items["v5-major-release-supersession"]["status"] == "operator_bound"
    assert items["v4-governed-control-plane-release-checklist"]["status"] == "done"

    blockers = [
        item["id"]
        for item in items.values()
        if item["blocking_for_v5_tag_publish"] is True
    ]
    assert blockers == ["v5-major-release-supersession"]


def test_gap_audit_schema_rejects_guard_or_release_authority_drift() -> None:
    """Schema validation must fail if critical false-pinned fields turn true."""
    validator = _validator()
    artifact = _artifact()

    mutated = copy.deepcopy(artifact)
    mutated["guard_flags"]["support_widening_allowed"] = True
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["release_boundary"]["v5_tag_publish_allowed"] = True
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["release_boundary"]["fake_minimax_evidence_allowed"] = True
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["release_boundary"]["ai_output_release_authority"] = True
    assert list(validator.iter_errors(mutated))


def test_gap_audit_schema_rejects_injected_extra_fields() -> None:
    """Every object layer is closed to extra evidence-injection fields."""
    validator = _validator()
    artifact = _artifact()

    mutated = copy.deepcopy(artifact)
    mutated["unexpected"] = "bypass"
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["guard_flags"]["unexpected"] = "bypass"
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["release_boundary"]["unexpected"] = "bypass"
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["gap_items"][0]["unexpected"] = "bypass"
    assert list(validator.iter_errors(mutated))

    mutated = copy.deepcopy(artifact)
    mutated["forbidden_change_audit"]["unexpected"] = "bypass"
    assert list(validator.iter_errors(mutated))


def test_gpp_status_pr_diff_does_not_flip_guard_flags_true() -> None:
    """Any PR diff that flips GPP guard flags false->true is forbidden."""
    artifact = _artifact()
    assert artifact["forbidden_change_audit"] == {
        "source_path": _GPP_STATUS_PATH,
        "git_diff_base": "origin/main...HEAD",
        "git_diff_guard_flags": [
            "support_widening_allowed",
            "production_platform_claim_allowed",
            "live_adapter_execution_allowed",
        ],
        "false_to_true_flip_allowed": False,
        "machine_enforced_by": "tests/test_v5_governed_control_plane_gap_audit.py",
    }

    combined_diff = "\n".join(
        [
            _git_diff("origin/main...HEAD"),
            _git_diff("--cached"),
            _git_diff(),
        ]
    )
    assert not _GUARD_TRUE_PATTERN.search(combined_diff), combined_diff
