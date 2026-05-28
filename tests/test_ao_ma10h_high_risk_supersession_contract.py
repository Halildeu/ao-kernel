"""AO-MA-10h high-risk supersession contract invariants."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "ao-ma-10-high-risk-supersession-evidence.schema.v1.json"
FIXTURE = ROOT / "tests" / "fixtures" / "ao_ma_10h" / "high_risk_supersession.valid.json"
RECEIPT = ROOT / ".claude" / "plans" / "AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.v1.json"
PLAN = ROOT / ".claude" / "plans" / "AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.md"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _receipt() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RECEIPT.read_text(encoding="utf-8")))


def _git_capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        timeout=20,
    )


def _resolve_diff_base() -> str | None:
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
                    return sha
        except (OSError, json.JSONDecodeError):
            pass

    for ref in ("origin/main", "main"):
        mb = _git_capture(["merge-base", "HEAD", ref])
        if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
            return mb.stdout.strip()

    return None


def _errors(payload: dict[str, Any]) -> list[Any]:
    return list(Draft202012Validator(_schema()).iter_errors(payload))


def test_ao_ma10h_schema_is_valid_draft_2020_12() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ao:ao-ma-10-high-risk-supersession-evidence:v1"


def test_ao_ma10h_valid_fixture_validates() -> None:
    assert _errors(_fixture()) == []


def test_ao_ma10h_rejects_same_or_missing_required_provider() -> None:
    duplicate = _fixture()
    duplicate["reviewer_providers"] = ["openai", "openai"]
    duplicate["provider_verdicts"][1]["provider_id"] = "openai"
    assert _errors(duplicate)

    missing = _fixture()
    missing["reviewer_providers"] = ["openai", "minimax"]
    missing["provider_verdicts"][1]["provider_id"] = "minimax"
    assert _errors(missing)


def test_ao_ma10h_rejects_non_agree_or_stale_evidence() -> None:
    non_agree = _fixture()
    non_agree["consensus_status"] = "REVISE"
    assert _errors(non_agree)

    provider_revise = _fixture()
    provider_revise["provider_verdicts"][0]["verdict"] = "REVISE"
    assert _errors(provider_revise)

    stale = _fixture()
    stale["freshness"]["status"] = "stale"
    assert _errors(stale)


def test_ao_ma10h_rejects_guard_or_ai_authority_flip() -> None:
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        mutated = _fixture()
        mutated["guard_flags"][flag] = True
        assert _errors(mutated)

    provider_flag = _fixture()
    provider_flag["provider_verdicts"][0]["support_widening"] = True
    assert _errors(provider_flag)

    ai_authority = _fixture()
    ai_authority["ai_output_release_authority"] = True
    assert _errors(ai_authority)


def test_ao_ma10h_rejects_secret_or_mutation_claim() -> None:
    secret = _fixture()
    secret["secrets_recorded"] = True
    assert _errors(secret)

    mutation = _fixture()
    mutation["mutations_performed"] = True
    assert _errors(mutation)


def test_ao_ma10h_records_runtime_context_equality_requirement() -> None:
    """JSON Schema cannot compare nested provider contexts to top-level context."""

    mismatched = _fixture()
    mismatched["provider_verdicts"][1]["context_binding"]["diff_digest"] = (
        "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )

    # The schema validates shape. The future runtime validator must enforce
    # cross-provider context equality before using this artifact as authority
    # evidence.
    assert _errors(mismatched) == []

    text = PLAN.read_text(encoding="utf-8")
    assert "any provider context differs from top-level context" in text
    assert _receipt()["future_runtime_acceptance"]["json_schema_cross_provider_context_equality_limit_recorded"] is True


def test_ao_ma10h_receipt_pins_hard_stops() -> None:
    receipt = _receipt()
    assert receipt["planning_only"] is True
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False

    forbidden = set(receipt["current_slice_forbidden_actions"])
    assert "workflow_mutation" in forbidden
    assert "codeowners_mutation" in forbidden
    assert "ruleset_mutation" in forbidden
    assert "branch_protection_mutation" in forbidden
    assert "release_gate_runtime_mutation" in forbidden
    assert "gpp_status_mutation" in forbidden
    assert "auto_merge_execution" in forbidden


def test_ao_ma10h_current_slice_diff_excludes_runtime_and_github_mutation() -> None:
    base = _resolve_diff_base()
    in_ci_pr = os.environ.get("CI") == "true" and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
    if base is None:
        if in_ci_pr:
            pytest.fail("AO-MA-10h diff base could not be resolved")
        pytest.skip("AO-MA-10h diff base could not be resolved")

    proc = _git_capture(["diff", "--name-only", f"{base}..HEAD"])
    if proc.returncode != 0:
        if in_ci_pr:
            pytest.fail(f"AO-MA-10h git diff failed: {proc.stderr}")
        pytest.skip(f"AO-MA-10h git diff failed: {proc.stderr}")
    changed = proc.stdout.splitlines()

    if "AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.md" not in "\n".join(changed):
        pytest.skip("AO-MA-10h introducer files not present in this diff")
    if ".claude/plans/AO-MA-10J-REQUIRED-CHECK-HIGH-RISK-WIRING.md" in changed:
        pytest.skip("AO-MA-10j wiring slice supersedes the AO-MA-10h no-workflow-mutation introducer invariant")

    # Introducer-PR detection (pattern parity with RI-7.1, RI-7.2, RI-7.5,
    # RI-7.8a, RI-7.8b-bc1-6a/6b/6c-fast-follow and AO-MA-10 runtime).
    # This invariant pins the *introducer* PR's scope to contract-only.
    # Subsequent slices that legitimately extend the H contract semantics
    # (e.g., adding ``binding_mode`` 3-state classification) MODIFY the
    # file rather than ADD it. The introducer fact is fixed at landing
    # time; later evolutions land via their own scoped review.
    introducer_proc = _git_capture(
        [
            "diff",
            "--name-only",
            "--diff-filter=A",
            f"{base}..HEAD",
            "--",
            ".claude/plans/AO-MA-10H-HIGH-RISK-SUPERSESSION-CONTRACT.md",
        ]
    )
    if introducer_proc.returncode != 0:
        if in_ci_pr:
            pytest.fail(f"AO-MA-10h introducer probe failed: {introducer_proc.stderr}")
        pytest.skip(f"AO-MA-10h introducer probe failed: {introducer_proc.stderr}")
    is_introducer = bool(introducer_proc.stdout.strip())
    if not is_introducer:
        pytest.skip(
            "AO-MA-10h contract MODIFIED (not ADDED) in this diff; state-at-landing "
            "pin applies, introducer-only scope check skipped"
        )

    forbidden_prefixes = (
        ".github/",
        "deploy/",
        "scripts/ao_release_gate",
        "scripts/local_gpp_gate",
    )
    forbidden_exact = {
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/plans/gpp_status.v1.json",
        "ao_kernel/ao_release_gate.py",
        "local-gpp-gate-evidence.schema.v1.json",
    }
    for path in changed:
        assert not path.startswith(forbidden_prefixes), path
        assert path not in forbidden_exact, path


def test_ao_ma10h_plan_records_current_bootstrap_boundary() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "Current base code cannot consume high-risk supersession evidence yet" in text
    assert "GitHub branch protection still requires non-author/codeowner review" in text
    assert "contract first -> runtime validator -> GitHub enforcement model update -> smoke" in text
