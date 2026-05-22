"""Tests for the ao-release-gate shadow fallback synthesizer (GPP-2D-2c)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module() -> Any:
    module_path = _repo_root() / "scripts" / "ao_release_gate_synthesize_error_decision.py"
    spec = importlib.util.spec_from_file_location("ao_release_gate_synthesize_error_decision", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthesizer_produces_error_fail_closed_decision(tmp_path: Path) -> None:
    """The synthesizer always emits the canonical error_fail_closed shape."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    rc = mod.main([str(output)])
    assert rc == 0
    decision = json.loads(output.read_text(encoding="utf-8"))

    assert decision["decision"] == "error_fail_closed"
    assert decision["allow"] is False
    assert decision["dry_run"] is True
    assert decision["merge_authority_enabled"] is False
    assert decision["conclusion_mode"] == "shadow"
    assert decision["finding_code"] == "error_fail_closed"
    assert decision["app_slug"] == "ao-release-gate"
    assert decision["program_id"] == "GPP-2v"


def test_synthesizer_carries_shadow_pre_decision_finding(tmp_path: Path) -> None:
    """The synthesizer writes the workflow-only finding code that the
    decision core never emits, so audit logs can identify shadow-fallback
    runs distinctly from core-produced error_fail_closed decisions."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main([str(output)])
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert "ao_release_gate_shadow_pre_decision_step_failed" in decision["findings"]


def test_synthesizer_github_check_run_is_neutral_shadow_advisory(tmp_path: Path) -> None:
    """The shadow advisory job posts no check-run, but the synthetic
    artifact still carries a neutral conclusion so an operator reading
    the artifact sees the shadow-advisory mapping rather than failure."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main([str(output)])
    decision = json.loads(output.read_text(encoding="utf-8"))
    check_run = decision["github_check_run"]
    assert check_run["name"] == "ao-release-gate"
    assert check_run["status"] == "completed"
    assert check_run["conclusion"] == "neutral"


def test_synthesizer_module_imports_and_builds_decision_cleanly() -> None:
    """A workflow-runtime smoke check: the synthesizer module must import
    without side effects and produce a well-formed decision when called
    directly. If the file ever regresses into a Python syntax error or
    a missing-field bug this would catch it before the shadow workflow
    ships."""
    mod = _load_module()
    decision = mod.build_error_decision()
    assert decision["decision"] == "error_fail_closed"
    assert decision["allow"] is False
    assert decision["github_check_run"]["conclusion"] == "neutral"


def test_synthesizer_output_is_pretty_sorted_json(tmp_path: Path) -> None:
    """The synthetic artifact uses canonical pretty/sorted JSON so audit
    diffs over it are stable."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main([str(output)])
    text = output.read_text(encoding="utf-8")
    assert text.endswith("\n")
    # Sorted keys: a representative key ordering check.
    assert text.index('"allow"') < text.index('"decision"')
    assert text.index('"decision"') < text.index('"findings"')
