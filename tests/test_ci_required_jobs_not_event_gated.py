"""CI-FIX invariant (CNS-20260531-001): required test.yml jobs must not be
event-gated, so a cosmetic `edited` PR event cannot shadow-skip a required
status-check context and flip the PR to mergeStateStatus=blocked.

Root cause this locks against: test.yml triggers on `pull_request` incl.
`edited`. The event-gate job sets should_run=false for a non-retarget edit. If
the required jobs (lint, test (3.11/3.12/3.13), coverage, typecheck,
packaging-smoke) — and the ao-release-gate chain that posts the ruleset-required
ao-release-gate-technical/-review contexts — are gated on
`if: needs.event-gate.outputs.should_run`, an edit re-fires the workflow on the
SAME head SHA and those jobs emit conclusion=skipped check-runs that shadow the
earlier success. With strict classic branch protection the PR then blocks even
though CI is not red.

Fix invariants (all asserted here):
- the five classic-required jobs do NOT depend on event-gate (always run);
- the ao-release-gate job and its container-smoke upstreams do NOT depend on
  event-gate either (they back the ruleset-required contexts);
- the only expensive job that stays event-gated is benchmark-fast (backs no
  required / release-gate chain);
- a workflow-level concurrency group cancels superseded runs per PR;
- there is no fail-open (`if: always()` / `continue-on-error`) on a required
  job that could let a not-run gate report success.

This test parses the workflow as TEXT (no PyYAML — CI installs only the
[dev,llm,metrics] extras for the test/coverage jobs, which do not include
PyYAML; the existing test_ao_release_gate_enforce_job.py uses the same
text-based approach).
"""

from __future__ import annotations

import re
from pathlib import Path

_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "test.yml"

# Jobs whose names back required classic branch-protection status checks.
_REQUIRED_JOBS = ("lint", "test", "coverage", "typecheck", "packaging-smoke")
# Jobs that back the ao-release-gate fail-closed chain and therefore must run on
# every event (de-facto required even though their own names are not required
# branch-protection contexts).
_AO_RELEASE_GATE_UPSTREAM_SMOKES = ("policy-container-smoke", "release-gate-container-smoke")
# The one expensive job that backs no required / release-gate chain and may stay
# event-gated for cost control.
_GATED_NONREQUIRED_JOBS = ("benchmark-fast",)


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _job_block(name: str) -> str:
    """Return the text block of a top-level job (2-space indent key) up to the
    next top-level job key. Pure-text, no YAML parser."""
    lines = _text().splitlines()
    header = f"  {name}:"
    start = None
    for i, line in enumerate(lines):
        if line == header or line.startswith(header):
            start = i
            break
    if start is None:
        raise AssertionError(f"job {name!r} not found in test.yml")
    block = [lines[start]]
    for line in lines[start + 1 :]:
        # A new top-level job starts at exactly 2-space indent + non-space.
        if line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":"):
            break
        block.append(line)
    return "\n".join(block)


def _if_clause(block: str) -> str:
    """Extract the `if:` clause text of a job block (single or block scalar)."""
    out: list[str] = []
    capturing = False
    for line in block.splitlines():
        stripped = line.strip()
        if not capturing and (stripped.startswith("if:")):
            out.append(stripped[len("if:") :].strip())
            capturing = True
            continue
        if capturing:
            # if: | block scalar continuation is indented deeper than the key
            if line.startswith("      ") or line.startswith("        "):
                out.append(stripped)
            elif stripped == "":
                continue
            else:
                break
    return " ".join(out)


def _needs(block: str) -> str:
    """Return the raw `needs:` region text of a job block (list or inline)."""
    out: list[str] = []
    capturing = False
    for line in block.splitlines():
        stripped = line.strip()
        if not capturing and stripped.startswith("needs:"):
            out.append(stripped)
            capturing = True
            continue
        if capturing:
            if stripped.startswith("- ") or (line.startswith("      ") and stripped):
                out.append(stripped)
            else:
                break
    return " ".join(out)


def _is_event_gated(name: str) -> bool:
    block = _job_block(name)
    return "should_run" in _if_clause(block) or "event-gate" in _needs(block)


# ---------------------------------------------------------------------------
# Required jobs must not be event-gated
# ---------------------------------------------------------------------------
def test_required_jobs_are_not_event_gated() -> None:
    for name in _REQUIRED_JOBS:
        assert not _is_event_gated(name), f"{name} must NOT be event-gated (shadow-skip risk)"


def test_required_jobs_have_no_fail_open() -> None:
    for name in _REQUIRED_JOBS:
        block = _job_block(name)
        assert "always()" not in _if_clause(block), f"{name} must not use always()"
        assert "continue-on-error: true" not in block, f"{name} must not continue-on-error"


def test_packaging_smoke_still_waits_for_other_required_jobs() -> None:
    needs = _needs(_job_block("packaging-smoke"))
    for dep in ("test", "coverage", "lint", "typecheck"):
        assert dep in needs, f"packaging-smoke should still need {dep}"
    assert "event-gate" not in needs


# ---------------------------------------------------------------------------
# ao-release-gate chain must not be event-gated either
# ---------------------------------------------------------------------------
def test_ao_release_gate_is_not_should_run_gated() -> None:
    block = _job_block("ao-release-gate")
    cond = _if_clause(block)
    assert "should_run" not in cond, "ao-release-gate must NOT gate on event-gate.should_run"
    assert "always()" in cond, "ao-release-gate must keep always() so a failed upstream still surfaces a verdict"
    needs = _needs(block)
    for dep in ("lint", "test", "coverage", "typecheck", "packaging-smoke"):
        assert dep in needs, f"ao-release-gate should still need {dep} (fail-closed chain)"


def test_ao_release_gate_fail_closed_short_circuit_present() -> None:
    text = _text()
    assert "needs.event-gate.result != 'success'" in text
    assert "Fail closed if any required CI job did not succeed" in text


def test_ao_release_gate_upstream_smokes_are_ungated() -> None:
    gate_needs = _needs(_job_block("ao-release-gate"))
    for name in _AO_RELEASE_GATE_UPSTREAM_SMOKES:
        assert not _is_event_gated(name), f"{name} must NOT be event-gated (it backs ao-release-gate)"
        assert name in gate_needs, f"{name} should remain in ao-release-gate.needs (fail-closed chain)"


# ---------------------------------------------------------------------------
# Only benchmark-fast stays gated; concurrency; retarget guard
# ---------------------------------------------------------------------------
def test_expensive_nonrequired_jobs_stay_event_gated() -> None:
    for name in _GATED_NONREQUIRED_JOBS:
        assert _is_event_gated(name), f"{name} should stay event-gated (cost control)"


def test_workflow_concurrency_cancels_superseded_runs() -> None:
    text = _text()
    # Exactly one top-level concurrency block, keyed on the PR, cancel-in-progress.
    top_level = [ln for ln in text.splitlines() if ln.startswith("concurrency:")]
    assert len(top_level) == 1, "there must be exactly one top-level concurrency block"
    m = re.search(r"^concurrency:\n((?:  .*\n)+)", text, re.MULTILINE)
    assert m, "top-level concurrency block not found"
    body = m.group(1)
    assert "cancel-in-progress: true" in body
    assert "pull_request.number" in body


def test_event_gate_retarget_guard_preserved() -> None:
    block = _job_block("event-gate")
    assert "changes.base.ref.from" in block
    assert "pull_request:retargeted" in block


def test_required_contexts_not_restricted_by_event_name() -> None:
    """The classic-required jobs must not be conditioned on a specific
    event_name that would exclude one of the PR triggers."""
    for name in _REQUIRED_JOBS:
        cond = _if_clause(_job_block(name))
        assert "github.event_name ==" not in cond, f"{name} must not restrict by event_name"
