from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from examples.demo_review import _read_intent
from scripts.gp5_read_only_rehearsal import (
    build_handoff,
    build_rehearsal_report,
    parse_demo_final_state,
    validate_report,
)


def test_handoff_records_explicit_operator_markdown_boundary() -> None:
    handoff = build_handoff()
    metadata = handoff["metadata"]

    assert "# Repo Query Context Pack" in handoff["markdown"]
    assert "## Handoff Contract" in handoff["markdown"]
    assert "No hidden injection" in handoff["markdown"]
    assert metadata["mode"] == "explicit_operator_markdown"
    assert metadata["source"] == "deterministic_contract_fixture"
    assert metadata["repo_query_command_contract"].startswith("python3 -m ao_kernel repo query ")
    assert metadata["generation_steps"] == [
        "deterministic contract fixture rendered through build_repo_query_context_pack()"
    ]
    assert metadata["hidden_injection"] is False
    assert metadata["mcp_tool_used"] is False
    assert metadata["root_export_used"] is False
    assert metadata["context_compiler_auto_feed"] is False


def test_rehearsal_report_pass_is_schema_valid_and_no_support_widening() -> None:
    handoff = build_handoff()
    report = build_rehearsal_report(
        handoff=handoff,
        workflow_result={
            "command": ["python", "examples/demo_review.py", "--cleanup"],
            "returncode": 0,
            "stdout": "[demo] final state: completed\n",
            "stderr": "",
            "final_state": "completed",
        },
    )

    validate_report(report)
    schema = load_default("schemas", "gp5-read-only-rehearsal-report.schema.v1.json")
    assert not list(Draft202012Validator(schema).iter_errors(report))
    assert report["overall_status"] == "pass"
    assert report["decision"] == "pass_read_only_rehearsal_no_support_widening"
    assert report["support_widening"] is False
    assert report["workflow_rehearsal"]["remote_side_effects"] is False


def test_rehearsal_report_blocks_failed_or_incomplete_workflow() -> None:
    report = build_rehearsal_report(
        handoff=build_handoff(),
        workflow_result={
            "command": ["python", "examples/demo_review.py", "--cleanup"],
            "returncode": 1,
            "stdout": "[demo] final state: failed\n",
            "stderr": "boom",
            "final_state": "failed",
        },
    )

    validate_report(report)
    assert report["overall_status"] == "blocked"
    assert report["decision"] == "blocked_read_only_rehearsal_no_support_widening"
    assert report["blocked_reason"] == "demo returncode=1, final_state='failed'"


def test_parse_demo_final_state_requires_demo_marker() -> None:
    assert parse_demo_final_state("[demo] final state: completed\n") == "completed"
    assert parse_demo_final_state("completed\n") is None


def test_demo_review_reads_explicit_intent_file(tmp_path: Path) -> None:
    intent_file = tmp_path / "handoff.md"
    intent_file.write_text("# Repo Query Context Pack\n", encoding="utf-8")

    assert _read_intent(intent_file) == "# Repo Query Context Pack\n"
    assert _read_intent(None) == "Inspect the workspace and emit review findings."
