"""Tests for the ao-release-gate error synthesizer (GPP-2D-3).

The GPP-2D-2c shadow synthesizer was fail-OPEN: it produced an artifact
AND let the shadow advisory job exit 0. GPP-2D-3 retires that contract
and rewrites the synthesizer as an enforce-aware audit safety net:

- the default conclusion mode is now ``enforce``;
- the artifact's ``github_check_run.conclusion`` mirrors the conclusion
  mode (shadow -> neutral, enforce -> failure);
- the script never alters the calling step's exit code; the invoking
  workflow step is responsible for the job conclusion.

These tests pin the new contract.
"""

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


def test_synthesizer_defaults_to_enforce_conclusion_mode(tmp_path: Path) -> None:
    """The default conclusion mode is now ``enforce`` (it was ``shadow``
    in the retired GPP-2D-2c synthesizer). When invoked without
    --conclusion-mode the artifact reflects enforce semantics."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    rc = mod.main([str(output)])
    assert rc == 0
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert decision["conclusion_mode"] == "enforce"
    assert decision["decision"] == "error_fail_closed"
    assert decision["allow"] is False
    # Under enforce, deny/error maps to conclusion=failure.
    assert decision["github_check_run"]["conclusion"] == "failure"


def test_synthesizer_supports_shadow_conclusion_mode(tmp_path: Path) -> None:
    """For audit / debugging the shadow mode is still selectable; the
    artifact's check-run conclusion then maps to neutral."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main([str(output), "--conclusion-mode", "shadow"])
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert decision["conclusion_mode"] == "shadow"
    assert decision["github_check_run"]["conclusion"] == "neutral"


def test_synthesizer_emits_default_pre_decision_finding(tmp_path: Path) -> None:
    """The default finding code records the pre-decision crash path
    distinctly from any decision-core-emitted finding code."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main([str(output)])
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert "ao_release_gate_pre_decision_step_failed" in decision["findings"]


def test_synthesizer_accepts_custom_reason_and_finding(tmp_path: Path) -> None:
    """The enforce job uses --reason / --finding-code to record the
    fail-closed needs-short-circuit reason distinctly from the
    pre-decision crash reason."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main(
        [
            str(output),
            "--reason",
            "an upstream required CI job did not succeed",
            "--finding-code",
            "ao_release_gate_upstream_required_check_failed",
        ]
    )
    decision = json.loads(output.read_text(encoding="utf-8"))
    assert decision["reason"] == "an upstream required CI job did not succeed"
    assert "ao_release_gate_upstream_required_check_failed" in decision["findings"]
    assert "ao_release_gate_upstream_required_check_failed" in decision["github_check_run"]["text"]


def test_synthesizer_module_imports_and_builds_decision_cleanly() -> None:
    """A workflow-runtime smoke check: the synthesizer module must
    import without side effects and produce a well-formed decision when
    called directly."""
    mod = _load_module()
    decision = mod.build_error_decision(
        conclusion_mode="enforce",
        reason="pre-decision crash",
        finding_code="ao_release_gate_pre_decision_step_failed",
    )
    assert decision["decision"] == "error_fail_closed"
    assert decision["allow"] is False
    assert decision["conclusion_mode"] == "enforce"
    assert decision["github_check_run"]["conclusion"] == "failure"


def test_synthesizer_output_is_pretty_sorted_json(tmp_path: Path) -> None:
    """The synthetic artifact uses canonical pretty/sorted JSON so audit
    diffs over it are stable."""
    mod = _load_module()
    output = tmp_path / "decision.json"
    mod.main([str(output)])
    text = output.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"allow"') < text.index('"decision"')
    assert text.index('"decision"') < text.index('"findings"')
