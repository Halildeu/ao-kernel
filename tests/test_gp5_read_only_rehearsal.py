from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from examples.demo_review import _read_intent
from scripts.gp5_read_only_rehearsal import (
    build_handoff,
    build_rehearsal_report,
    parse_demo_events_path,
    parse_demo_final_state,
    parse_demo_review_artifact_path,
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
            "stdout": (
                "[demo] final state: completed\n"
                "[demo] review artifact: /tmp/demo/review-findings.json\n"
                "[demo] events: /tmp/demo/events.jsonl\n"
            ),
            "stderr": "",
            "final_state": "completed",
            "review_findings_artifact_path": "/tmp/demo/review-findings.json",
            "evidence_timeline_path": "/tmp/demo/events.jsonl",
        },
    )

    validate_report(report)
    schema = load_default("schemas", "gp5-read-only-rehearsal-report.schema.v1.json")
    assert not list(Draft202012Validator(schema).iter_errors(report))
    assert report["overall_status"] == "pass"
    assert report["decision"] == "pass_read_only_rehearsal_no_support_widening"
    assert report["support_widening"] is False
    assert report["repo_intelligence_opt_in_validation"]["status"] == "accepted"
    assert (
        report["repo_intelligence_opt_in_validation"]["source_metadata"]["vector_namespace_key_prefix"]
        == "repo_chunk::ao-kernel::space::"
    )
    assert report["workflow_rehearsal"]["remote_side_effects"] is False
    assert report["workflow_rehearsal"]["write_side_workflow_support_implied"] is False
    assert report["workflow_rehearsal"]["real_adapter_called"] is False
    assert report["workflow_rehearsal"]["review_findings_artifact_path"] == "/tmp/demo/review-findings.json"
    assert report["workflow_rehearsal"]["evidence_timeline_path"] == "/tmp/demo/events.jsonl"


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


def test_rehearsal_report_blocks_failed_opt_in_validation() -> None:
    report = build_rehearsal_report(
        handoff=build_handoff(),
        workflow_result={
            "command": [],
            "returncode": 1,
            "stdout": "",
            "stderr": "blocked",
            "final_state": None,
            "opt_in_validation": {
                "status": "blocked",
                "enabled": True,
                "decision": "blocked_repo_intelligence_workflow_opt_in",
                "findings": ["freshness_not_current_only"],
                "handoff": {"markdown_sha256": "0" * 64},
                "support_widening": False,
                "production_platform_claim": False,
            },
            "review_findings_artifact_path": None,
            "evidence_timeline_path": None,
        },
    )

    validate_report(report)
    assert report["overall_status"] == "blocked"
    assert report["blocked_reason"] == "repo_intelligence_opt_in_validation_not_accepted"
    assert report["repo_intelligence_opt_in_validation"]["findings"] == ["freshness_not_current_only"]


def test_parse_demo_final_state_requires_demo_marker() -> None:
    assert parse_demo_final_state("[demo] final state: completed\n") == "completed"
    assert parse_demo_final_state("completed\n") is None


def test_parse_demo_artifact_and_timeline_paths_require_demo_markers() -> None:
    stdout = "[demo] review artifact: /tmp/demo/review-findings.json\n[demo] events: /tmp/demo/events.jsonl\n"

    assert parse_demo_review_artifact_path(stdout) == "/tmp/demo/review-findings.json"
    assert parse_demo_events_path(stdout) == "/tmp/demo/events.jsonl"
    assert parse_demo_review_artifact_path("review-findings.json\n") is None
    assert parse_demo_events_path("events.jsonl\n") is None


def test_demo_review_reads_explicit_intent_file(tmp_path: Path) -> None:
    intent_file = tmp_path / "handoff.md"
    intent_file.write_text("# Repo Query Context Pack\n", encoding="utf-8")

    assert _read_intent(intent_file) == "# Repo Query Context Pack\n"
    assert _read_intent(None) == "Inspect the workspace and emit review findings."
