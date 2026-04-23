from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.extension_truth_ratchet import build_report, render_text


def _row(report: dict[str, object], extension_id: str) -> dict[str, object]:
    rows = report["rows"]
    assert isinstance(rows, list)
    for candidate in rows:
        assert isinstance(candidate, dict)
        if candidate.get("extension_id") == extension_id:
            return candidate
    raise AssertionError(f"extension row not found: {extension_id}")


def test_build_report_has_expected_buckets_and_queue() -> None:
    report = build_report()
    summary = report["summary"]
    assert summary["total_extensions"] >= 1
    assert summary["runtime_backed"] >= 2
    assert summary["contract_only"] >= 1
    assert summary["quarantined"] >= 1

    queue = report["ordered_queue"]
    assert "PRJ-CONTEXT-ORCHESTRATION" in queue["promotion_candidate"]
    assert "PRJ-RELEASE-AUTOMATION" in queue["remap_priority"]
    assert "PRJ-EXECUTORPORT" in queue["retire_candidate"]


def test_known_extension_classifications_are_stable() -> None:
    report = build_report()

    context_orch = _row(report, "PRJ-CONTEXT-ORCHESTRATION")
    assert context_orch["bucket"] == "promotion_candidate"
    assert context_orch["priority_score"] is None

    executorport = _row(report, "PRJ-EXECUTORPORT")
    assert executorport["bucket"] == "retire_candidate"
    assert executorport["priority_score"] is None

    cockpit = _row(report, "PRJ-UI-COCKPIT-LITE")
    assert cockpit["bucket"] == "quarantine_keep"
    assert cockpit["priority_score"] is None


def test_render_text_contains_key_sections() -> None:
    rendered = render_text(build_report())
    assert "truth_inventory_ratchet" in rendered
    assert "queue.promotion_candidate:" in rendered
    assert "queue.remap_priority:" in rendered
    assert "queue.retire_candidate:" in rendered


def test_script_wrapper_executes_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/truth_inventory_ratchet.py", "--output", "json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "summary" in payload
    assert "ordered_queue" in payload
