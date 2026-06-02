"""V5 Epic 8 E-8-5 invariants: tutorial presence + claim discipline.

Docs-only slice. The tutorial MUST:
- Exist at docs/TUTORIAL-BUILD-AO-MA-SPM-PROGRAM.md
- Cover the 7-step path (init -> slice -> consensus -> impl -> evidence ->
  PR -> operator approval gate)
- Disclaim production-readiness; 3 guard flags const false
- Reference ADR-0003/0004 + E-8-1 deployment guide + E-1-1 wiring
- Not flip any guard flag
- Not claim live provider calls without operator-bound supersession
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL_PATH = REPO_ROOT / "docs" / "TUTORIAL-BUILD-AO-MA-SPM-PROGRAM.md"

PROHIBITED_TOKENS = (
    "production ready",
    "production-ready",
    "ga release",
    "general availability",
    "fully supported",
    "we are production",
    "live in production",
)


def _strip_fenced_blocks(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append(line)
    return "\n".join(out)


# ---- 1. Presence + structure (7) ----------------------------------------


def test_tutorial_exists() -> None:
    assert TUTORIAL_PATH.exists(), f"tutorial missing at {TUTORIAL_PATH}"


def test_tutorial_step_1_workspace_init() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "Initialize the Workspace" in text
    assert "ao-kernel init" in text
    assert "ao-kernel doctor" in text


def test_tutorial_step_2_define_slice() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "Define Your First Slice" in text
    assert "SLICE-001" in text


def test_tutorial_step_3_plan_time_consensus() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "Plan-Time Cross-AI Consensus" in text
    assert "Anthropic" in text
    assert "OpenAI" in text or "Codex" in text


def test_tutorial_step_4_impl_against_stub() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "AoKernelClient" in text
    assert "Stub Worker" in text or "stub worker" in text


def test_tutorial_step_5_verify_evidence() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "Verify Evidence" in text
    assert "ao-kernel evidence timeline" in text or "evidence replay" in text


def test_tutorial_step_6_open_pr_and_step_7_operator_gate() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "Open a Pull Request" in text
    assert "ao-release-gate" in text
    assert "Operator Approval Gate" in text
    assert "ao-ma-plan-approval" in text


# ---- 2. Claim discipline (4) ---------------------------------------------


def test_tutorial_three_guard_flags_const_false_disclaimer() -> None:
    text = TUTORIAL_PATH.read_text().lower()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text
    assert "const false" in text or "`const false`" in text


def test_tutorial_no_production_ready_positive_claim() -> None:
    prose = re.sub(r"[\s>*]+", " ", _strip_fenced_blocks(TUTORIAL_PATH.read_text()).lower())
    for token in PROHIBITED_TOKENS:
        idx = 0
        while True:
            idx = prose.find(token, idx)
            if idx == -1:
                break
            window = prose[max(0, idx - 80) : idx + len(token) + 5]
            negated = any(
                cue in window
                for cue in (
                    "not a",
                    "not an",
                    "is not",
                    "no production",
                    "documentation only",
                    "does not",
                )
            )
            assert negated, (
                f"tutorial contains positive claim token {token!r}; "
                f"context: ...{prose[max(0, idx - 40) : idx + len(token) + 40]!r}"
            )
            idx += len(token)


def test_tutorial_references_operator_bound_final_supersession() -> None:
    text = TUTORIAL_PATH.read_text().lower()
    assert "operator-bound supersession" in text
    assert "final" in text


def test_tutorial_does_not_authorize_live_provider_calls() -> None:
    """E-2-1 will flip live_adapter_execution; this tutorial MUST defer."""
    text = TUTORIAL_PATH.read_text().lower()
    # Must mention that live provider calls require operator-bound supersession
    assert "operator-bound supersession" in text
    # Must not state that this tutorial enables live calls
    forbidden = (
        "live provider calls are enabled",
        "live adapter execution is on",
        "live_adapter_execution = true",
        "live_adapter_execution: true",
    )
    for f in forbidden:
        assert f not in text, f"tutorial overclaims live provider: {f!r}"


# ---- 3. Cross references (4) --------------------------------------------


def test_tutorial_references_adr_0003_0004() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "ADR-0003" in text or "import-only" in text
    assert "ADR-0004" in text or "ADR-0004 HARD RULE" in text or "cross-ai peer review" in text.lower()


def test_tutorial_links_e_8_1_deployment_guide() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "PRODUCTION-DEPLOYMENT-GUIDE.md" in text


def test_tutorial_links_e_8_3_operator_runbook() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "OPERATOR-RUNBOOK.md" in text


def test_tutorial_mentions_e_1_1_environment_wiring() -> None:
    text = TUTORIAL_PATH.read_text()
    assert "E-1-1" in text or "GitHub Environment" in text


# ---- 4. Governance ZERO TOUCH (1) ---------------------------------------


def test_no_workflow_mutation() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = proc.stdout.split()
    for path in changed:
        assert not path.startswith(".github/workflows/"), f"E-8-5 must not touch workflows: {path}"
