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
    assert {item["status"] for item in prereqs} == {"not_started"}
    ids = {item["id"] for item in prereqs}
    assert "positive_low_risk_autonomous_merge_smoke" in ids
    assert "negative_high_risk_blocked_smoke" in ids
    assert "stale_evidence_blocked_smoke" in ids
    assert "same_provider_review_blocked_smoke" in ids
    assert "missing_verifier_blocked_smoke" in ids
    assert "admin_bypass_absence_verified" in ids


def test_ao_ma10_high_risk_consensus_is_bounded_and_escalates() -> None:
    receipt = _load_json(RECEIPT)
    consensus = receipt["high_risk_consensus"]
    assert consensus["required_providers"] == ["openai", "anthropic", "minimax"]
    assert consensus["consensus_required"] is True
    assert consensus["same_provider_review_allowed"] is False
    assert consensus["max_autonomous_rounds"] == 3
    assert consensus["escalate_to_human_after_max_rounds"] is True


def test_ao_ma10_docs_state_planning_only_no_runtime_cutover() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "planning-only" in text
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
    allowlist = {
        ".claude/plans/AO-MA-1-MULTI-AGENT-ORCHESTRATION-DESIGN.md",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.md",
        ".claude/plans/AO-MA-10-LOW-RISK-AUTONOMOUS-MERGE-LANE.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-10-low-risk-autonomous-merge-lane.schema.v1.json",
        "tests/test_ao_ma10_low_risk_autonomous_merge_lane.py",
        "local-ai-review-evidence.v1.json",
    }
    assert changed <= allowlist, f"AO-MA-10 touches files outside allowlist: {sorted(changed - allowlist)}"

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
        for pattern in forbidden_patterns:
            assert not re.search(pattern, path), f"forbidden AO-MA-10 path changed: {path}"
