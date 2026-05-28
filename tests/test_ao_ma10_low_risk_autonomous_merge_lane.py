from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md"
RECEIPT = ROOT / ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json"
SCHEMA = ROOT / "ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json"
AO_MA_1 = ROOT / ".claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md"
GPP_STATUS = ROOT / ".claude/plans/gpp_status.v1.json"


def _load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _git_capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=20,
    )


def _resolve_pr_diff_base() -> tuple[str | None, str]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            base = (event.get("pull_request") or {}).get("base") or {}
            sha = base.get("sha")
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha):
                has = _git_capture(["cat-file", "-e", sha])
                if has.returncode != 0:
                    _git_capture(["fetch", "origin", sha, "--depth=1"])
                    has = _git_capture(["cat-file", "-e", sha])
                if has.returncode == 0:
                    return sha, "github_event_payload"
        except (OSError, json.JSONDecodeError):
            pass

    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
        fetch_proc = _git_capture(["fetch", "origin", base_ref, "--depth=1"])
        if fetch_proc.returncode == 0:
            mb = _git_capture(["merge-base", "HEAD", "FETCH_HEAD"])
            if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
                return mb.stdout.strip(), f"fetch:{base_ref}"

    mb = _git_capture(["merge-base", "HEAD", "origin/main"])
    if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
        return mb.stdout.strip(), "origin/main"

    mb = _git_capture(["merge-base", "HEAD", "main"])
    if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
        return mb.stdout.strip(), "local_main"

    return None, "none"


def test_ao_ma10_schema_is_valid_draft_2020_12() -> None:
    schema = _load_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_ao_ma10_receipt_validates_against_schema() -> None:
    schema = _load_json(SCHEMA)
    receipt = _load_json(RECEIPT)
    Draft202012Validator(schema).validate(receipt)
    assert receipt["schema_version"] == "ao-ma-10-low-risk-autonomous-merge-lane.v1"


def test_ao_ma10_pins_release_authority_and_guard_flags() -> None:
    receipt = _load_json(RECEIPT)
    assert receipt["planning_only"] is True
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False


def test_ao_ma10_low_risk_criteria_are_schema_pinned() -> None:
    receipt = _load_json(RECEIPT)
    criteria = receipt["low_risk_criteria"]
    assert ".github/" in "\n".join(criteria["prohibited_path_patterns"])
    assert "^\\.github/CODEOWNERS$" in criteria["prohibited_path_patterns"]
    assert "^\\.claude/plans/gpp_status\\.v1\\.json$" in criteria["prohibited_path_patterns"]
    assert "^scripts/ao_release_gate" in criteria["prohibited_path_patterns"]
    assert "^scripts/local_gpp_gate" in criteria["prohibited_path_patterns"]
    assert "ao_release_gate_success" in criteria["required_signals"]
    assert "context_bound_cross_provider_review_agree" in criteria["required_signals"]
    assert "local_gpp_gate_accepts" in criteria["required_signals"]
    assert "no_admin_bypass" in criteria["required_signals"]
    assert "no_live_adapter_execution" in criteria["required_signals"]


def test_ao_ma10_merge_agent_activation_locked_not_started() -> None:
    receipt = _load_json(RECEIPT)
    prereqs = receipt["merge_agent_activation_prerequisites"]
    assert len(prereqs) == 10
    by_id = {item["id"]: item["status"] for item in prereqs}
    assert by_id["negative_high_risk_blocked_smoke"] == "done"
    assert by_id["stale_evidence_blocked_smoke"] == "done"
    assert by_id["same_provider_review_blocked_smoke"] == "done"
    assert by_id["missing_verifier_blocked_smoke"] == "done"
    assert by_id["positive_low_risk_autonomous_merge_smoke"] == "not_started"
    assert by_id["admin_bypass_absence_verified"] == "not_started"
    assert by_id["merge_agent_identity_and_permissions_recorded"] == "not_started"


def test_ao_ma10_high_risk_consensus_is_bounded_and_escalates() -> None:
    receipt = _load_json(RECEIPT)
    consensus = receipt["high_risk_consensus"]
    assert consensus["required_providers"] == ["openai", "anthropic"]
    assert consensus["optional_registered_providers"] == ["minimax"]
    assert consensus["consensus_required"] is True
    assert consensus["same_provider_review_allowed"] is False
    assert consensus["max_autonomous_rounds"] == 3
    assert consensus["escalate_to_human_after_max_rounds"] is True


def test_ao_ma10_docs_state_planning_only_no_runtime_cutover() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "planning-only" in text
    assert "AO-MA-10a0  GitHub readiness snapshot" in text
    assert "MiniMax remains a provider-integration prerequisite" in text
    assert "The merge agent is **not active**" in text
    assert "No workflow mutation." in text
    assert "No ruleset or branch-protection mutation." in text
    assert "No CODEOWNERS mutation." in text
    assert "No merge-agent activation in this slice." in text
    assert "No auto-merge execution in this slice." in text


def test_ao_ma10_updates_ao_ma1_plan_without_claiming_cutover() -> None:
    text = AO_MA_1.read_text(encoding="utf-8")
    assert "AO-MA-10" in text
    assert "Low-risk autonomous merge lane cutover plan" in text
    assert "AO-MA-10 is planning-only" in text


def test_ao_ma10_gpp_status_guards_remain_closed() -> None:
    status = _load_json(GPP_STATUS)
    assert status["support_widening_allowed"] is False
    assert status["production_platform_claim_allowed"] is False
    assert status["live_adapter_execution_allowed"] is False


def test_ao_ma10_pr_scope_excludes_runtime_workflow_ruleset_and_codeowners() -> None:
    """AO-MA-10 PR scope assertion.

    Fast-follow sistemik bug fix (AO-MA-10 introducer-PR detection):
    the scope allowlist + forbidden_patterns assertion was firing on
    every PR after AO-MA-10 landed, rejecting any PR whose diff did
    not match AO-MA-10's specific scope (six AO-MA-10-owned artifact
    files). On unrelated PRs (RI-7.x slices, AO-MA-N fast-follows,
    future B-path slices, etc.) the assertion is a category error
    and blocks legitimate merges.

    Pattern parity with PR #662 (AO-MA-8) and PR #666 (RI-7.1): detect
    the AO-MA-10 introducer PR by checking whether the diff touches at
    least one of the four AO-MA-10-owned artifact paths in
    `ao_ma_10_introducer_signature` below (excluding the shared
    `local-ai-review-evidence.v1.json` which every PR touches). On
    non-introducer PRs the invariant skips; the full-scope assertion
    for the AO-MA-10 introducer is preserved.

    Fail-closed: if the diff base cannot be resolved or git diff
    fails, the test fails closed in CI PR context (existing behavior
    below preserved).
    """
    base, source = _resolve_pr_diff_base()
    in_ci_pr = os.environ.get("CI") == "true" and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
    if base is None:
        message = "no PR diff base resolved"
        if in_ci_pr:
            pytest.fail(message)
        pytest.skip(message)

    proc = _git_capture(["diff", "--name-only", f"{base}..HEAD"])
    if proc.returncode != 0:
        message = f"git diff against {source} failed: {proc.stderr}"
        if in_ci_pr:
            pytest.fail(message)
        pytest.skip(message)

    changed = {line.strip() for line in proc.stdout.splitlines() if line.strip()}

    # Introducer detection uses ADDED files only (--diff-filter=A). MODIFIED
    # AO-MA-10 surfaces (e.g. successor B-path slice editing the AO-MA-10 test
    # for systemic invariant alignment) MUST NOT trigger AO-MA-10 introducer
    # pattern. Without --diff-filter=A, every successor PR that touches an
    # AO-MA-10 file false-positives as the AO-MA-10 introducer and the
    # full-scope allowlist assertion category-errors.
    added_proc = _git_capture(["diff", "--diff-filter=A", "--name-only", f"{base}..HEAD"])
    if added_proc.returncode != 0:
        added_files: set[str] = set()
    else:
        added_files = {line.strip() for line in added_proc.stdout.splitlines() if line.strip()}

    # AO-MA-10 introducer-PR detection (fast-follow sistemik bug fix).
    # On non-introducer PRs the scope assertion is a category error;
    # skip with a precise reason.
    ao_ma_10_introducer_signature = {
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json",
        ".claude/plans/AO-MA-10A2-EVIDENCE-SCHEMAS.md",
        ".claude/plans/AO-MA-10A2-EVIDENCE-SCHEMAS.v1.json",
        ".claude/plans/AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.md",
        ".claude/plans/AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-high-risk-supersession-evidence.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-provider-consensus.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-evidence-bundle.schema.v1.json",
        "tests/test_ao_ma10h_high_risk_supersession_contract.py",
        "tests/test_ao_ma10_low_risk_autonomous_merge_lane.py",
        "tests/test_ao_ma10_evidence_schemas.py",
        "tests/test_ao_ma10_negative_fail_closed.py",
        # NOTE: tests/test_ri78b_bc1_6a_*.py is OWNED by RI-7.8b-bc1-6a, NOT
        # AO-MA-10. It was erroneously included here; successor B-path slices
        # (e.g. RI-7.8b-bc1-6b adding introducer-PR detection to that file)
        # legitimately touch it without being the AO-MA-10 introducer.
        # Removed under RI-7.8b-bc1-6b inline systemic fix.
    }
    # Only ADDED AO-MA-10 surfaces qualify as introducer signal. MODIFIED
    # surfaces (e.g. successor B-path slice editing this very test for
    # systemic invariant alignment) MUST NOT false-positive as the AO-MA-10
    # introducer.
    if not (added_files & ao_ma_10_introducer_signature):
        pytest.skip(
            "PR is not the AO-MA-10 introducer PR (no AO-MA-10-specific path "
            "ADDED in diff; modifications-only do not trigger AO-MA-10 scope "
            "allowlist invariant)"
        )

    allowlist = {
        ".claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json",
        ".claude/plans/AO-MA-10A0-GITHUB-READINESS-SNAPSHOT.v1.json",
        ".claude/plans/AO-MA-10A1-AUTONOMOUS-MERGE-ELIGIBILITY.v1.json",
        ".claude/plans/AO-MA-10A2-EVIDENCE-SCHEMAS.md",
        ".claude/plans/AO-MA-10A2-EVIDENCE-SCHEMAS.v1.json",
        ".claude/plans/AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.md",
        ".claude/plans/AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.v1.json",
        ".claude/plans/GPP-2B-AO-RELEASE-GATE-REQUIRED-CHECK-MAPPING.md",
        "ao_kernel/defaults/schemas/ao-ma-10-autonomous-merge-eligibility.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-evidence-bundle.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-github-readiness-snapshot.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-high-risk-supersession-evidence.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-provider-consensus.schema.v1.json",
        "ao_kernel/ao_release_gate.py",
        "scripts/ao_release_gate_build_payload.py",
        "scripts/ao_release_gate_decision.py",
        "scripts/ao_ma10_autonomous_merge_eligibility.py",
        "scripts/ao_ma10_evidence_bundle.py",
        "scripts/ao_ma10_github_readiness_snapshot.py",
        "tests/fixtures/ao_ma_10/autonomous_merge_eligibility.blocked.valid.json",
        "tests/fixtures/ao_ma_10/autonomous_merge_eligibility.ready.valid.json",
        "tests/fixtures/ao_ma_10a2/evidence_bundle.valid.json",
        "tests/fixtures/ao_ma_10a2/provider_consensus.anthropic.valid.json",
        "tests/fixtures/ao_ma_10a2/provider_consensus.openai.valid.json",
        "tests/fixtures/ao_ma_10h/high_risk_supersession.valid.json",
        "tests/test_ao_release_gate.py",
        "tests/test_ao_release_gate_build_payload.py",
        "tests/test_gpp2b_mapping_drift_guard.py",
        "tests/test_ao_ma10_evidence_schemas.py",
        "tests/test_ao_ma10_negative_fail_closed.py",
        "tests/test_ao_ma10h_high_risk_supersession_contract.py",
        "tests/test_ao_ma10_low_risk_autonomous_merge_lane.py",
        "tests/test_ao_ma10_autonomous_merge_eligibility.py",
        "tests/test_ao_ma10_github_readiness_snapshot.py",
        "tests/test_ri78a_live_evidence_pre_authorization_invariant.py",
        "tests/test_ri78b_bc1_6a_execution_window_authorization_invariant.py",
        "tests/fixtures/ao_ma_10/github_readiness_snapshot.blocked.valid.json",
        "local-ai-review-evidence.v1.json",
    }
    assert changed <= allowlist, f"AO-MA-10 touches files outside allowlist: {sorted(changed - allowlist)}"

    ao_ma_10b_release_gate_scope = {
        "ao_kernel/ao_release_gate.py",
        "scripts/ao_release_gate_build_payload.py",
        "scripts/ao_release_gate_decision.py",
    }

    forbidden_patterns = (
        r"^\.github/",
        r"^\.github/CODEOWNERS$",
        r"^AGENTS\.md$",
        r"^CLAUDE\.md$",
        r"^\.claude/plans/gpp_status\.v1\.json$",
        r"^ao_kernel/orchestration/",
        r"^scripts/ao_release_gate",
        r"^scripts/local_gpp_gate",
        r"^ao_kernel/ao_release_gate",
    )
    for path in changed:
        if path in ao_ma_10b_release_gate_scope:
            continue
        for pattern in forbidden_patterns:
            assert not re.search(pattern, path), f"forbidden AO-MA-10 path changed: {path}"
