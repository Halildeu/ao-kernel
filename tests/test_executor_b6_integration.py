"""Integration tests for PR-B6 driver materialization (commit 5).

End-to-end verification that the walker's `extracted_outputs` flows
through `write_capability_artifact()` and lands in the workflow run
record's `step_record.capability_output_refs` map. Covers:

- Review AI roundtrip (review_findings capability)
- Commit AI roundtrip (commit_message capability)
- Backward compat: pre-B6 records parse cleanly without the new field
- Fail-closed: artifact write failure → _StepFailed

Uses the existing `invoke_cli` + codex-stub subprocess pattern from
`test_executor_adapter_invoker.py` and composes the driver's
capability loop in-process (without standing up a full
MultiStepDriver execute() — that level lands in governed_review
benchmark in B7).
"""

from __future__ import annotations

import json
import os as _os
import uuid
from pathlib import Path

import pytest

from ao_kernel.executor.adapter_invoker import invoke_cli
from ao_kernel.executor.artifacts import write_capability_artifact


def _sandbox(tmp_path: Path, env: dict[str, str] | None = None):
    """Real SandboxedEnvironment — mirrors test_executor_adapter_invoker.py
    :_sandbox. Minimal allowlist (python3 for codex-stub subprocess)."""
    import re
    from ao_kernel.executor.policy_enforcer import (
        RedactionConfig,
        SandboxedEnvironment,
    )

    env_vars = env or {
        "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": "/tmp/fake-home",
        "LANG": "en_US.UTF-8",
    }
    return SandboxedEnvironment(
        env_vars=env_vars,
        cwd=tmp_path,
        allowed_commands_exact=frozenset({"python3", "git"}),
        allowed_command_prefixes=(
            "/usr/bin/",
            "/usr/local/bin/",
            "/opt/homebrew/bin/",
        ),
        policy_derived_path_entries=(
            Path("/usr/bin"),
            Path("/usr/local/bin"),
            Path("/opt/homebrew/bin"),
        ),
        exposure_modes=frozenset({"env"}),
        evidence_redaction=RedactionConfig(
            env_keys_matching=(re.compile(r"(?i).*(token|secret).*"),),
            stdout_patterns=(re.compile(r"sk-[A-Za-z0-9]{20,}"),),
            file_content_patterns=(),
        ),
        inherit_from_parent=False,
    )


def _worktree(tmp_path: Path, run_id: str):
    """Real WorktreeHandle — mirrors test_executor_adapter_invoker.py."""
    from ao_kernel.executor.worktree_builder import WorktreeHandle

    (tmp_path / ".ao" / "runs" / run_id / "worktree").mkdir(parents=True)
    return WorktreeHandle(
        run_id=run_id,
        path=tmp_path / ".ao" / "runs" / run_id / "worktree",
        base_revision="deadbeef",
        strategy="new_per_run",
        created_at="2026-04-17T00:00:00+00:00",
    )


def _budget():
    """Real Budget with all axes invoke_cli requires."""
    from ao_kernel.workflow.budget import Budget, BudgetAxis

    return Budget(
        tokens=BudgetAxis(limit=100_000, spent=0, remaining=100_000),
        tokens_input=None,
        tokens_output=None,
        time_seconds=BudgetAxis(limit=600.0, spent=0.0, remaining=600.0),
        cost_usd=None,
        fail_closed_on_exhaust=True,
    )


def _invoke_codex_stub(tmp_path: Path) -> tuple[object, str]:
    """Invoke codex-stub adapter via subprocess; return
    (invocation_result, run_id). Mirrors test_executor_adapter_invoker.py."""
    from ao_kernel.adapters import AdapterRegistry

    rid = str(uuid.uuid4())
    adapters = AdapterRegistry()
    adapters.load_bundled()
    manifest = adapters.get("codex-stub")

    sandbox = _sandbox(
        tmp_path,
        env={
            "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
            "PYTHONPATH": _os.getcwd(),
            "HOME": "/tmp/fake-home",
        },
    )
    worktree = _worktree(tmp_path, rid)
    budget = _budget()

    result, _ = invoke_cli(
        manifest=manifest,
        input_envelope={"task_prompt": "stubbed", "run_id": rid},
        sandbox=sandbox,
        worktree=worktree,
        budget=budget,
        workspace_root=tmp_path,
        run_id=rid,
    )
    return result, rid


class TestReviewAiRoundtrip:
    """review_findings capability flows through the walker → driver
    materialization → disk artifact."""

    def test_review_findings_extracted_then_materialized(
        self, tmp_path: Path,
    ) -> None:
        result, rid = _invoke_codex_stub(tmp_path)
        assert result.status == "ok"
        assert "review_findings" in result.extracted_outputs

        # Simulate the driver's capability loop from
        # MultiStepDriver._run_adapter_step (commit 2).
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        capability_output_refs: dict[str, str] = {}
        for capability, payload in result.extracted_outputs.items():
            cap_ref, _ = write_capability_artifact(
                run_dir=run_dir,
                step_id="step-review",
                attempt=1,
                capability=capability,
                payload=payload,
            )
            capability_output_refs[capability] = cap_ref

        assert "review_findings" in capability_output_refs
        ref = capability_output_refs["review_findings"]
        assert ref == "artifacts/step-review-review_findings-attempt1.json"
        artifact_path = run_dir / ref
        assert artifact_path.is_file()

        # Disk artifact is schema-valid review_findings payload.
        from ao_kernel.config import load_default
        from jsonschema import Draft202012Validator

        schema = load_default("schemas", "review-findings.schema.v1.json")
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == [], (
            f"review_findings artifact fails schema validation: "
            f"{[e.message for e in errors]}"
        )


class TestCommitAiRoundtrip:
    """commit_message capability flows through the walker → driver
    materialization → disk artifact."""

    def test_commit_message_extracted_then_materialized(
        self, tmp_path: Path,
    ) -> None:
        result, rid = _invoke_codex_stub(tmp_path)
        assert result.status == "ok"
        assert "commit_message" in result.extracted_outputs

        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        capability_output_refs: dict[str, str] = {}
        for capability, payload in result.extracted_outputs.items():
            cap_ref, _ = write_capability_artifact(
                run_dir=run_dir,
                step_id="step-commit",
                attempt=1,
                capability=capability,
                payload=payload,
            )
            capability_output_refs[capability] = cap_ref

        assert "commit_message" in capability_output_refs
        ref = capability_output_refs["commit_message"]
        assert ref == "artifacts/step-commit-commit_message-attempt1.json"
        artifact_path = run_dir / ref
        assert artifact_path.is_file()

        # Disk artifact is schema-valid commit_message payload.
        from ao_kernel.config import load_default
        from jsonschema import Draft202012Validator

        schema = load_default("schemas", "commit-message.schema.v1.json")
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == []

    def test_two_capabilities_yield_two_distinct_artifacts(
        self, tmp_path: Path,
    ) -> None:
        """Codex-stub fixture emits BOTH review_findings AND
        commit_message — driver materialization writes two separate
        capability artifacts under the same step_id."""
        result, rid = _invoke_codex_stub(tmp_path)

        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        refs: dict[str, str] = {}
        for capability, payload in result.extracted_outputs.items():
            cap_ref, _ = write_capability_artifact(
                run_dir=run_dir,
                step_id="step-both",
                attempt=1,
                capability=capability,
                payload=payload,
            )
            refs[capability] = cap_ref

        assert {"review_findings", "commit_message"} <= refs.keys()
        assert refs["review_findings"] != refs["commit_message"]
        assert (run_dir / refs["review_findings"]).is_file()
        assert (run_dir / refs["commit_message"]).is_file()


class TestBackwardCompatPreB6:
    """Pre-B6 workflow-run records lack `capability_output_refs`; the
    schema additive widen must keep those records loadable."""

    def test_pre_b6_record_schema_valid(self) -> None:
        from ao_kernel.config import load_default
        from jsonschema import Draft202012Validator

        schema = load_default("schemas", "workflow-run.schema.v1.json")
        step_schema = schema["$defs"]["step_record"]

        # Pre-B6 shape: no capability_output_refs key
        record = {
            "step_id": "sample-step-1",
            "step_name": "sample",
            "state": "completed",
            "actor": "adapter",
            "started_at": "2026-04-17T00:00:00+00:00",
            "completed_at": "2026-04-17T00:00:01+00:00",
            "attempt": 1,
            "output_ref": "artifacts/step-sample-attempt1.json",
        }
        errors = list(Draft202012Validator(step_schema).iter_errors(record))
        assert errors == [], (
            f"pre-B6 step_record should validate (additive widen): "
            f"{[e.message for e in errors]}"
        )

    def test_b6_record_with_capability_output_refs_schema_valid(self) -> None:
        from ao_kernel.config import load_default
        from jsonschema import Draft202012Validator

        schema = load_default("schemas", "workflow-run.schema.v1.json")
        step_schema = schema["$defs"]["step_record"]

        record = {
            "step_id": "sample-step-1",
            "step_name": "sample",
            "state": "completed",
            "actor": "adapter",
            "started_at": "2026-04-17T00:00:00+00:00",
            "completed_at": "2026-04-17T00:00:01+00:00",
            "attempt": 1,
            "output_ref": "artifacts/step-sample-attempt1.json",
            "capability_output_refs": {
                "review_findings": "artifacts/step-sample-review_findings-attempt1.json",
                "commit_message": "artifacts/step-sample-commit_message-attempt1.json",
            },
        }
        errors = list(Draft202012Validator(step_schema).iter_errors(record))
        assert errors == []

    def test_invalid_capability_key_rejected(self) -> None:
        """Schema pattern `^[a-z][a-z0-9_]{0,63}$` rejects uppercase
        capability keys in the map."""
        from ao_kernel.config import load_default
        from jsonschema import Draft202012Validator

        schema = load_default("schemas", "workflow-run.schema.v1.json")
        step_schema = schema["$defs"]["step_record"]

        record = {
            "step_id": "sample-step-1",
            "step_name": "sample",
            "state": "completed",
            "actor": "adapter",
            "started_at": "2026-04-17T00:00:00+00:00",
            "completed_at": "2026-04-17T00:00:01+00:00",
            "attempt": 1,
            "capability_output_refs": {
                "InvalidCap": "artifacts/x.json",  # uppercase — pattern violation
            },
        }
        errors = list(Draft202012Validator(step_schema).iter_errors(record))
        assert errors != [], "uppercase capability key should be rejected"


class TestArtifactWriteFailClosed:
    """Artifact write failure maps to output_parse_failed (plan §2.3
    error plumbing)."""

    def test_invalid_capability_name_raises(self, tmp_path: Path) -> None:
        """Helper-level guard: write_capability_artifact raises
        ValueError on invalid capability. The driver catches this in
        _run_adapter_step and translates to _StepFailed."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        with pytest.raises(ValueError, match="capability must match"):
            write_capability_artifact(
                run_dir=run_dir,
                step_id="s1",
                attempt=1,
                capability="Upper-Case-Invalid",
                payload={"ok": True},
            )
