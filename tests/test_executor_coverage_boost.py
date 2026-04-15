"""Coverage-targeted tests for ``ao_kernel.executor``.

These tests cover error branches and placeholder paths that the
primary behavioural suites do not exercise directly. Keeps the ratchet
gate (85%) met without duplicating the primary-suite scenarios.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor import (
    AdapterInvocationFailedError,
    AdapterOutputParseError,
    Executor,
    ExecutorError,
    PolicyViolation,
    PolicyViolationError,
    WorktreeBuilderError,
    cleanup_worktree,
    create_worktree,
)
from ao_kernel.executor.adapter_invoker import (
    _SENTINEL_MISSING,
    _is_clear_unified_diff,
    _jsonpath_dotted,
)
from ao_kernel.workflow import WorkflowRegistry, create_run


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "t@e"], check=True
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "t"], check=True
    )
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "seed.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True
    )


# ---------------------------------------------------------------------------
# Error class branches
# ---------------------------------------------------------------------------


class TestErrorBranches:
    def test_policy_violation_error_empty_list(self) -> None:
        # Defensive branch: zero violations still produces a message.
        err = PolicyViolationError(violations=[])
        assert "0 policy violations" in str(err)

    def test_adapter_invocation_failed_str(self) -> None:
        err = AdapterInvocationFailedError(
            reason="timeout", detail="adapter ran too long"
        )
        assert "timeout" in str(err)
        assert err.reason == "timeout"

    def test_adapter_output_parse_error_excerpt(self) -> None:
        long_excerpt = "x" * 1000
        err = AdapterOutputParseError(
            raw_excerpt=long_excerpt, detail="cannot parse"
        )
        # Excerpt truncated in __str__ to 120 chars
        assert len(str(err)) < 200
        assert err.raw_excerpt == long_excerpt

    def test_worktree_builder_error_reason(self) -> None:
        err = WorktreeBuilderError(reason="disk_full", detail="out of space")
        assert err.reason == "disk_full"

    def test_executor_error_subclass_detection(self) -> None:
        assert issubclass(PolicyViolationError, ExecutorError)
        assert issubclass(AdapterInvocationFailedError, ExecutorError)


# ---------------------------------------------------------------------------
# Worktree builder unsupported / shared_readonly strategy
# ---------------------------------------------------------------------------


class TestWorktreeStrategyCoverage:
    def test_shared_readonly_strategy_creates_copy(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        rid = str(uuid.uuid4())
        handle = create_worktree(
            workspace_root=tmp_path,
            run_id=rid,
            policy={"worktree": {"strategy": "shared_readonly"}},
        )
        assert handle.strategy == "shared_readonly"
        assert handle.path.exists()
        cleanup_worktree(handle, workspace_root=tmp_path)


# ---------------------------------------------------------------------------
# Executor placeholder path (non-adapter actors)
# ---------------------------------------------------------------------------


class TestExecutorPlaceholderPath:
    def test_non_adapter_step_runs_as_placeholder(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)

        wf_reg = WorkflowRegistry()
        wf_reg.load_bundled()
        ad_reg = AdapterRegistry()

        rid = str(uuid.uuid4())
        create_run(
            tmp_path,
            run_id=rid,
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "x"},
            budget={"fail_closed_on_exhaust": True},
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[f".ao/evidence/workflows/{rid}/events.jsonl"],
        )

        # Pick a non-adapter step (e.g. ao-kernel compile_context)
        definition = wf_reg.get("bug_fix_flow")
        ao_step = next(s for s in definition.steps if s.actor == "ao-kernel")

        executor = Executor(
            tmp_path,
            workflow_registry=wf_reg,
            adapter_registry=ad_reg,
        )
        result = executor.run_step(rid, ao_step, parent_env={})
        assert result.step_state == "completed"
        assert result.invocation_result is None


# ---------------------------------------------------------------------------
# Adapter invoker small helpers
# ---------------------------------------------------------------------------


class TestAdapterInvokerHelpers:
    def test_jsonpath_missing_returns_sentinel(self) -> None:
        assert _jsonpath_dotted({"a": 1}, "$.b") is _SENTINEL_MISSING

    def test_jsonpath_empty_path_returns_sentinel(self) -> None:
        assert _jsonpath_dotted({"a": 1}, "") is _SENTINEL_MISSING

    def test_jsonpath_rejects_malformed_prefix(self) -> None:
        with pytest.raises(AdapterOutputParseError):
            _jsonpath_dotted({}, "a.b")  # no $. prefix

    def test_is_clear_unified_diff_positive(self) -> None:
        assert _is_clear_unified_diff("--- a/x\n+++ b/x\n")
        assert _is_clear_unified_diff("@@ -1 +1 @@\n")

    def test_is_clear_unified_diff_negative(self) -> None:
        assert not _is_clear_unified_diff("some prose\n--- a")
        assert not _is_clear_unified_diff("")


# ---------------------------------------------------------------------------
# PolicyViolation immutability
# ---------------------------------------------------------------------------


class TestPolicyViolationShape:
    def test_kind_and_field_path_populated(self) -> None:
        v = PolicyViolation(
            kind="secret_missing",
            detail="x",
            policy_ref="p",
            field_path="$.secrets",
        )
        assert v.kind == "secret_missing"
        assert v.field_path == "$.secrets"
