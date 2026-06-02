"""V5 Epic 8 E-8-3 invariants: operator runbook presence + claim discipline.

Docs-only slice. The runbook MUST:
- Exist at docs/OPERATOR-RUNBOOK.md
- Cover five operator scenarios (rollback, tag revert, pause,
  emergency stop, incident triage)
- Disclaim production-readiness; 3 guard flags const false
- Reference E-6-6 incident playbook + E-5-* observability slices
- Not flip any guard flag
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_PATH = REPO_ROOT / "docs" / "OPERATOR-RUNBOOK.md"

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


# ---- 1. Presence + structure (6) -----------------------------------------


def test_runbook_exists() -> None:
    assert RUNBOOK_PATH.exists(), f"operator runbook missing at {RUNBOOK_PATH}"


def test_runbook_covers_rollback_scenario() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "Rollback" in text
    assert "kubectl rollout undo" in text
    assert "pip install 'ao-kernel" in text


def test_runbook_covers_tag_revert_scenario() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "Tag Revert" in text
    assert "Yank" in text or "yank" in text
    assert "CHANGELOG" in text


def test_runbook_covers_pause_scenario() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "Pause" in text or "Graceful Stop" in text
    assert "SIGTERM" in text
    assert "scale" in text.lower()


def test_runbook_covers_emergency_stop_scenario() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "Emergency Stop" in text
    assert "Revoke" in text or "revoke" in text
    assert "snapshot" in text.lower()


def test_runbook_covers_incident_triage_tree() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "Triage" in text or "triage" in text
    assert "governance violation" in text.lower()


# ---- 2. Claim discipline (4) ---------------------------------------------


def test_runbook_three_guard_flags_const_false_disclaimer() -> None:
    text = RUNBOOK_PATH.read_text().lower()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text
    assert "const false" in text or "`const false`" in text


def test_runbook_no_production_ready_positive_claim() -> None:
    prose = re.sub(r"[\s>*]+", " ", _strip_fenced_blocks(RUNBOOK_PATH.read_text()).lower())
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
                )
            )
            assert negated, (
                f"operator runbook contains positive claim token {token!r}; "
                f"context: ...{prose[max(0, idx - 40) : idx + len(token) + 40]!r}"
            )
            idx += len(token)


def test_runbook_references_operator_bound_final_supersession() -> None:
    text = RUNBOOK_PATH.read_text().lower()
    assert "operator-bound supersession" in text
    assert "final" in text


def test_runbook_does_not_flip_guard_flags_in_prose() -> None:
    prose = _strip_fenced_blocks(RUNBOOK_PATH.read_text()).lower()
    forbidden = (
        "support_widening = true",
        "support_widening: true",
        "production_platform_claim = true",
        "production_platform_claim: true",
        "live_adapter_execution = true",
        "live_adapter_execution: true",
    )
    for token in forbidden:
        assert token not in prose, f"runbook must not flip guard flag: {token!r}"


# ---- 3. Cross references + operator boundaries (4) ----------------------


def test_runbook_references_e_6_6_incident_playbook() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "E-6-6" in text
    assert "incident-response" in text


def test_runbook_references_e_5_observability_slices() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "E-5-2" in text
    assert "E-5-3" in text
    assert "E-5-4" in text


def test_runbook_lists_operator_owned_scenarios() -> None:
    text = RUNBOOK_PATH.read_text().lower()
    for scenario in (
        "credential rotation",
        "customer notification",
        "postmortem",
        "vendor escalation",
    ):
        assert scenario in text, f"operator-owned scenario missing: {scenario}"


def test_runbook_links_deployment_guide() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "PRODUCTION-DEPLOYMENT-GUIDE.md" in text


# ---- 4. Governance ZERO TOUCH (1) ----------------------------------------


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
        assert not path.startswith(".github/workflows/"), f"E-8-3 must not touch workflows: {path}"
