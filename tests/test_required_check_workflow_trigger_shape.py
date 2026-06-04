"""Required-check workflow trigger invariants.

The canonical ``Test`` workflow owns several branch-protection required check
names. PR metadata edits must run the full required-check surface rather than
being skipped by the event gate, because stale skipped runs can block autonomous
merge even when the latest full run is green.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
TRIGGER_SCRIPT = ROOT / ".claude" / "scripts" / "trigger-test-workflow.sh"


def _trigger_types(text: str, trigger_name: str) -> list[str]:
    """Return the YAML list under ``on.<trigger_name>.types``.

    This intentionally stays as a small text parser so the invariant is not
    affected by YAML 1.1's ``on`` boolean corner case in older PyYAML builds.
    """

    lines = text.splitlines()
    trigger_line = f"  {trigger_name}:"
    for index, line in enumerate(lines):
        if line == trigger_line:
            break
    else:
        raise AssertionError(f"missing trigger {trigger_name!r}")

    in_types = False
    values: list[str] = []
    for line in lines[index + 1 :]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        if line == "    types:":
            in_types = True
            continue
        if in_types:
            if line.startswith("      - "):
                values.append(line.removeprefix("      - ").strip())
                continue
            if line.startswith("    ") and line.strip():
                break
    return values


def test_required_test_workflow_runs_full_gate_for_pr_edited() -> None:
    text = TEST_WORKFLOW.read_text(encoding="utf-8")
    pull_request_types = _trigger_types(text, "pull_request")

    assert pull_request_types == [
        "opened",
        "reopened",
        "synchronize",
        "ready_for_review",
        "edited",
    ]
    assert "opened|reopened|synchronize|ready_for_review|edited" in text
    assert "pull_request:retargeted" not in text
    assert ".changes.base.ref.from" not in text


def test_review_events_still_rerun_required_gate_after_review_changes() -> None:
    text = TEST_WORKFLOW.read_text(encoding="utf-8")
    review_types = _trigger_types(text, "pull_request_review")

    assert review_types == ["submitted", "edited", "dismissed"]


def test_required_test_workflow_keeps_manual_dispatch_fallback() -> None:
    workflow_text = TEST_WORKFLOW.read_text(encoding="utf-8")
    script_text = TRIGGER_SCRIPT.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow_text
    assert "Manual rerun reason (e.g. stacked retarget)" in workflow_text

    assert "gh workflow run test.yml" in script_text
    assert "manual-retarget-check" in script_text
