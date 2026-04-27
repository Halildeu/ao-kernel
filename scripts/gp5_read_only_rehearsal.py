#!/usr/bin/env python3
"""Generate GP-5.4a read-only workflow rehearsal evidence.

The rehearsal intentionally keeps repo intelligence as explicit operator
handoff. It builds a deterministic Markdown handoff fixture, installs the
current checkout wheel into a fresh temporary virtualenv, and runs the shipped
``review_ai_flow + codex-stub`` demo with that Markdown supplied through
``--intent-file``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ao_kernel._internal.repo_intelligence.context_pack_builder import (  # noqa: E402
    build_repo_query_context_pack,
)
from ao_kernel.repo_intelligence import validate_repo_intelligence_workflow_opt_in  # noqa: E402
from ao_kernel.config import load_default  # noqa: E402

JsonDict = dict[str, Any]

_FINAL_STATE_RE = re.compile(r"^\[demo\] final state: (?P<state>\S+)\s*$", re.MULTILINE)
_REVIEW_ARTIFACT_RE = re.compile(r"^\[demo\] review artifact: (?P<path>.+?)\s*$", re.MULTILINE)
_EVENTS_RE = re.compile(r"^\[demo\] events: (?P<path>.+?)\s*$", re.MULTILINE)
_EXPECTED_NAMESPACE = "repo_chunk::ao-kernel::space::"
_REPO_QUERY_COMMAND = (
    'python3 -m ao_kernel repo query --project-root . --workspace-root .ao '
    '--query "where is review_ai_flow invoked" --path-prefix ao_kernel/defaults/workflows/ '
    '--output markdown'
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the GP-5.4a governed read-only workflow rehearsal"
    )
    parser.add_argument(
        "--output",
        choices=("json", "text"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Timeout for the installed demo workflow command",
    )
    args = parser.parse_args(argv)

    repo_root = _REPO_ROOT
    handoff = build_handoff()
    result = run_installed_demo_with_handoff(
        repo_root=repo_root,
        handoff_markdown=handoff["markdown"],
        timeout_seconds=args.timeout_seconds,
    )
    report = build_rehearsal_report(handoff=handoff, workflow_result=result)
    validate_report(report)

    if args.output == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"overall_status: {report['overall_status']}")
        print(f"decision: {report['decision']}")
        print(f"workflow: {report['workflow_rehearsal']['final_state']}")
        print(f"handoff_sha256: {report['repo_intelligence_handoff']['markdown_sha256']}")
        if report["overall_status"] == "blocked":
            print(f"blocked_reason: {report['blocked_reason']}")
    return 0 if report["overall_status"] == "pass" else 1


def build_handoff() -> JsonDict:
    markdown = build_repo_query_context_pack(query_result=_query_result_fixture())
    encoded = markdown.encode("utf-8")
    return {
        "markdown": markdown,
        "metadata": {
            "mode": "explicit_operator_markdown",
            "source": "deterministic_contract_fixture",
            "repo_query_command_contract": _REPO_QUERY_COMMAND,
            "generation_steps": [
                "deterministic contract fixture rendered through build_repo_query_context_pack()",
            ],
            "markdown_sha256": hashlib.sha256(encoded).hexdigest(),
            "markdown_bytes": len(encoded),
            "hidden_injection": False,
            "mcp_tool_used": False,
            "root_export_used": False,
            "context_compiler_auto_feed": False,
        },
    }


def run_installed_demo_with_handoff(
    *,
    repo_root: Path,
    handoff_markdown: str,
    timeout_seconds: float,
) -> JsonDict:
    with tempfile.TemporaryDirectory(prefix="ao-kernel-gp5-rehearsal-") as tmp_dir:
        temp_root = Path(tmp_dir)
        dist_dir = temp_root / "dist"
        venv_dir = temp_root / "venv"
        smoke_cwd = temp_root / "cwd"
        smoke_cwd.mkdir()
        handoff_file = temp_root / "repo-intelligence-handoff.md"
        handoff_file.write_text(handoff_markdown, encoding="utf-8")
        opt_in_validation = validate_repo_intelligence_workflow_opt_in(
            _workflow_opt_in_config(handoff_file.name),
            project_root=temp_root,
        )
        if opt_in_validation["status"] != "accepted":
            return {
                "command": [],
                "returncode": 1,
                "stdout": "",
                "stderr": json.dumps(opt_in_validation, sort_keys=True),
                "final_state": None,
                "opt_in_validation": opt_in_validation,
                "review_findings_artifact_path": None,
                "evidence_timeline_path": None,
            }

        _run_checked([sys.executable, "-m", "build", "--outdir", str(dist_dir)], cwd=repo_root)
        _run_checked([sys.executable, "-m", "venv", str(venv_dir)], cwd=repo_root)

        venv_bin = _venv_bin_dir(venv_dir)
        venv_python = venv_bin / ("python.exe" if os.name == "nt" else "python")
        venv_pip = venv_bin / ("pip.exe" if os.name == "nt" else "pip")
        wheel_path = _single_wheel(dist_dir)

        _run_checked([str(venv_pip), "install", str(wheel_path)], cwd=smoke_cwd)
        command = [
            str(venv_python),
            str(repo_root / "examples" / "demo_review.py"),
            "--cleanup",
            "--intent-file",
            str(handoff_file),
        ]
        proc = subprocess.run(
            command,
            cwd=str(smoke_cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "final_state": parse_demo_final_state(proc.stdout),
        "opt_in_validation": opt_in_validation,
        "review_findings_artifact_path": parse_demo_review_artifact_path(proc.stdout),
        "evidence_timeline_path": parse_demo_events_path(proc.stdout),
    }


def build_rehearsal_report(*, handoff: JsonDict, workflow_result: JsonDict) -> JsonDict:
    final_state = workflow_result.get("final_state")
    returncode = int(workflow_result.get("returncode", 1))
    opt_in_validation = workflow_result.get("opt_in_validation") or _accepted_opt_in_validation_fixture(handoff)
    opt_in_accepted = opt_in_validation.get("status") == "accepted"
    passed = returncode == 0 and final_state == "completed" and opt_in_accepted
    stdout = str(workflow_result.get("stdout", ""))
    stderr = str(workflow_result.get("stderr", ""))
    report: JsonDict = {
        "schema_version": "1",
        "artifact_kind": "gp5_read_only_workflow_rehearsal_report",
        "overall_status": "pass" if passed else "blocked",
        "decision": (
            "pass_read_only_rehearsal_no_support_widening"
            if passed
            else "blocked_read_only_rehearsal_no_support_widening"
        ),
        "support_widening": False,
        "repo_intelligence_handoff": handoff["metadata"],
        "repo_intelligence_opt_in_validation": opt_in_validation,
        "workflow_rehearsal": {
            "workflow_id": "review_ai_flow",
            "adapter_id": "codex-stub",
            "execution_mode": "wheel_installed_temp_venv",
            "command": [str(item) for item in workflow_result.get("command", [])],
            "returncode": returncode,
            "final_state": final_state,
            "remote_side_effects": False,
            "write_side_workflow_support_implied": False,
            "real_adapter_called": False,
            "review_findings_artifact_path": workflow_result.get("review_findings_artifact_path"),
            "evidence_timeline_path": workflow_result.get("evidence_timeline_path"),
            "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        },
    }
    if not passed:
        if not opt_in_accepted:
            report["blocked_reason"] = "repo_intelligence_opt_in_validation_not_accepted"
        else:
            report["blocked_reason"] = (
                f"demo returncode={returncode}, final_state={final_state!r}"
            )
    return report


def parse_demo_final_state(stdout: str) -> str | None:
    match = _FINAL_STATE_RE.search(stdout)
    if match is None:
        return None
    return match.group("state")


def parse_demo_review_artifact_path(stdout: str) -> str | None:
    match = _REVIEW_ARTIFACT_RE.search(stdout)
    if match is None:
        return None
    return match.group("path")


def parse_demo_events_path(stdout: str) -> str | None:
    match = _EVENTS_RE.search(stdout)
    if match is None:
        return None
    return match.group("path")


def validate_report(report: JsonDict) -> None:
    schema = load_default("schemas", "gp5-read-only-rehearsal-report.schema.v1.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(report), key=str)
    if errors:
        messages = "; ".join(error.message for error in errors[:3])
        raise ValueError(f"invalid GP-5.4a rehearsal report: {messages}")


def _run_checked(command: list[str], *, cwd: Path) -> None:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return
    rendered = shlex.join(command)
    stderr = proc.stderr.strip()
    stdout = proc.stdout.strip()
    detail = stderr or stdout or "no output"
    raise RuntimeError(f"command failed: {rendered}: {detail}")


def _single_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("ao_kernel-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one ao-kernel wheel, found {len(wheels)}")
    return wheels[0]


def _venv_bin_dir(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts"
    return venv_dir / "bin"


def _workflow_opt_in_config(handoff_path: str) -> JsonDict:
    return {
        "enabled": True,
        "source": "explicit_handoff_file",
        "handoff_path": handoff_path,
        "require_fresh": True,
        "expected_namespace": _EXPECTED_NAMESPACE,
        "support_tier": "beta_explicit_handoff",
    }


def _accepted_opt_in_validation_fixture(handoff: JsonDict) -> JsonDict:
    return {
        "status": "accepted",
        "enabled": True,
        "decision": "accepted_repo_intelligence_workflow_opt_in",
        "handoff": {
            "path": "deterministic_contract_fixture",
            "markdown_sha256": handoff["metadata"]["markdown_sha256"],
            "mode": "explicit_operator_markdown",
            "support_tier": "beta_explicit_handoff",
        },
        "source_metadata": {
            "vector_namespace_key_prefix": _EXPECTED_NAMESPACE,
            "repo_chunks_sha256": "c" * 64,
            "repo_vector_index_manifest_sha256": "d" * 64,
            "freshness_state": "current_only",
            "stale_candidates": 0,
            "retrieved_chunks": 1,
            "source_paths": ["ao_kernel/defaults/workflows/review_ai_flow.v1.json"],
            "content_sha256": ["e" * 64],
        },
        "safety": {
            "hidden_injection": False,
            "root_export": False,
            "mcp_exposure": False,
            "context_compiler_auto_feed": False,
            "vector_writes": False,
            "artifact_writes": False,
        },
        "support_widening": False,
        "production_platform_claim": False,
    }


def _query_result_fixture() -> JsonDict:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_vector_query_result",
        "generator": {
            "name": "ao-kernel",
            "version": "4.0.0",
            "generated_at": "2026-04-24T00:00:00Z",
        },
        "project": {
            "root": ".",
            "root_name": "ao-kernel",
            "name": "ao-kernel",
            "root_identity_sha256": "a" * 64,
        },
        "retriever": {
            "name": "ao-kernel-repo-vector-retriever",
            "version": "repo-vector-retriever.v1",
            "mode": "query_vectors",
        },
        "query": {
            "text": "where is review_ai_flow invoked",
            "top_k": 5,
            "candidate_limit": 50,
            "min_similarity": 0.3,
            "max_tokens": 2000,
            "max_snippet_chars": 1200,
            "filters": {
                "source_path_prefix": "ao_kernel/defaults/workflows/",
                "language": "json",
                "symbol": "",
            },
        },
        "embedding_space": {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "dimension": 1536,
            "embedding_space_id": "b" * 64,
        },
        "vector_namespace": {
            "key_prefix": "repo_chunk::ao-kernel::space::",
            "project_root_identity_sha256": "a" * 64,
        },
        "source_artifacts": {
            "repo_chunks_sha256": "c" * 64,
            "repo_vector_index_manifest_sha256": "d" * 64,
        },
        "summary": {
            "matches": 1,
            "candidate_matches": 1,
            "filtered_candidates": 1,
            "stale_candidates": 0,
            "embedding_calls": 1,
            "estimated_tokens": 26,
            "truncated_results": 0,
        },
        "results": [
            {
                "key": "repo_chunk::ao-kernel::space::workflow-review-ai-flow",
                "similarity": 0.9876,
                "source_path": "ao_kernel/defaults/workflows/review_ai_flow.v1.json",
                "start_line": 1,
                "end_line": 28,
                "language": "json",
                "kind": "file_slice",
                "module": "",
                "symbol": "",
                "chunk_id": "workflow-review-ai-flow",
                "content_sha256": "e" * 64,
                "token_estimate": 26,
                "snippet": '"workflow_id": "review_ai_flow",\n"expected_adapter_refs": ["codex-stub"]\n',
                "snippet_truncated": False,
                "content_status": "current",
            }
        ],
        "diagnostics": [],
    }


if __name__ == "__main__":
    raise SystemExit(main())
