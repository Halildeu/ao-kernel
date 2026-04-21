"""v3.11 P2 — Executor activation + rollout semantics honoring.

Pins the three-tier contract from `policy_worktree_profile.v1.json`:

1. ``enabled=false`` → policy layer dormant (no ``policy_checked`` /
   ``policy_denied`` events, no fail; sandbox still built so the
   adapter has a runnable env).
2. ``enabled=true`` + ``mode_default="report_only"`` → violations
   emit ``policy_checked`` with additive payload fields (``mode``,
   ``would_block``, ``violation_kinds``, ``promoted_to_block``); step
   continues even with violations present. ``promote_to_block_on``
   escalation: if any violation.kind matches an entry, escalation
   overrides report_only and the step is blocked.
3. ``enabled=true`` + ``mode_default="block"`` → current fail-closed
   behaviour: ``policy_checked`` + (on violations) ``policy_denied``
   + ``PolicyViolationError``.

Unknown ``mode_default`` → ``block`` fallback (fail-closed).

Also pins dry_run_step parity: a report-only violation MUST NOT raise
``PolicyViolationError`` from inside ``dry_run_step``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor import Executor
from ao_kernel.executor.errors import PolicyViolationError
from ao_kernel.workflow import WorkflowRegistry, create_run, load_run, update_run


_FIXTURE_SRC = Path(__file__).parent / "fixtures" / "adapter_manifests"


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@e"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True)


def _copy_adapter(workspace_root: Path, fixture_name: str) -> None:
    adapters_dir = workspace_root / ".ao" / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_FIXTURE_SRC / fixture_name, adapters_dir / fixture_name)


def _create_run_record(workspace_root: Path, run_id: str) -> None:
    create_run(
        workspace_root,
        run_id=run_id,
        workflow_id="bug_fix_flow",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "fix the crash"},
        budget={
            "time_seconds": {"limit": 120.0, "spent": 0.0, "remaining": 120.0},
            "fail_closed_on_exhaust": True,
        },
        policy_refs=["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
        evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
        adapter_refs=["codex-stub"],
    )


def _transition_run_to_running(workspace_root: Path, run_id: str) -> None:
    """Transition run state from 'created' → 'running'.

    The executor's ``_fail_run`` expects the run to already be in a
    state that can legally transition to 'failed' ('created' → 'failed'
    is blocked by the workflow state machine; 'running' → 'failed' is
    allowed). In production this transition happens inside the
    ``MultiStepDriver`` before it dispatches to ``Executor.run_step``.
    For these unit-level P2 tests we do it by hand so the fail-path
    assertions actually exercise the activation / rollout branches
    rather than tripping over the state machine.
    """

    def _mutator(current: dict[str, Any]) -> dict[str, Any]:
        current["state"] = "running"
        return current

    update_run(workspace_root, run_id, mutator=_mutator)


def _bundled_policy() -> dict[str, Any]:
    with open(
        "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        encoding="utf-8",
    ) as f:
        return dict(json.load(f))


def _permissive_policy(**overrides: Any) -> dict[str, Any]:
    """Bundled policy tuned so codex-stub can actually run."""
    p = _bundled_policy()
    p["enabled"] = True
    env_spec = dict(p["env_allowlist"])
    env_spec["explicit_additions"] = {
        "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        "PYTHONPATH": os.getcwd(),
    }
    p["env_allowlist"] = env_spec
    for k, v in overrides.items():
        p[k] = v
    return p


def _policy_with_secret_missing_violation(
    enabled: bool = True, mode_default: str = "block", promote_to_block_on=None
) -> dict[str, Any]:
    """Builds a policy that WILL produce a ``secret_missing`` violation.

    Uses the ``secret_missing`` kind (declared in
    ``ao_kernel/executor/errors.py`` and actively emitted by
    ``resolve_allowed_secrets`` when a secret_id is in the allowlist
    but has no env value). Callers pass a ``parent_env`` that omits
    the required secret id; the violation fires deterministically
    regardless of the real shell env because ``resolve_allowed_secrets``
    only reads from ``parent_env``.
    """
    p = _permissive_policy()
    p["enabled"] = enabled
    secrets_spec = dict(p["secrets"])
    secrets_spec["allowlist_secret_ids"] = ["REQUIRED_TEST_TOKEN_V311_P2"]
    p["secrets"] = secrets_spec
    p["rollout"] = {
        "mode_default": mode_default,
        "promote_to_block_on": list(promote_to_block_on or []),
    }
    return p


def _policy_with_command_violation(
    *,
    enabled: bool = True,
    mode_default: str = "block",
    promote_to_block_on=None,
) -> dict[str, Any]:
    """Build a policy that denies the fixture codex-stub CLI command."""

    p = _permissive_policy()
    p["enabled"] = enabled
    p["command_allowlist"] = {"exact": ["git"], "prefixes": []}
    p["rollout"] = {
        "mode_default": mode_default,
        "promote_to_block_on": list(promote_to_block_on or []),
    }
    return p


def _build_executor(tmp_path: Path, policy: dict[str, Any]) -> tuple[Executor, Any]:
    _init_git_repo(tmp_path)
    _copy_adapter(tmp_path, "codex-stub.manifest.v1.json")
    _copy_adapter(tmp_path, "gh-cli-pr.manifest.v1.json")
    wf_reg = WorkflowRegistry()
    wf_reg.load_bundled()
    ad_reg = AdapterRegistry()
    ad_reg.load_workspace(tmp_path)
    ex = Executor(
        tmp_path,
        workflow_registry=wf_reg,
        adapter_registry=ad_reg,
        policy_loader=policy,
    )
    definition = wf_reg.get("bug_fix_flow")
    adapter_step = next(s for s in definition.steps if s.actor == "adapter")
    return ex, adapter_step


def _read_events(workspace_root: Path, run_id: str) -> list[dict[str, Any]]:
    path = workspace_root / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _event_kinds(events: list[dict[str, Any]]) -> list[str]:
    return [e.get("kind") for e in events]


class TestTierDormant:
    """`enabled=false` → policy layer bypassed entirely."""

    def test_disabled_policy_emits_no_policy_events(self, tmp_path: Path) -> None:
        policy = _permissive_policy(enabled=False)
        # Also add rollout so the unknown-mode fallback isn't what we're testing.
        policy["rollout"] = {"mode_default": "block", "promote_to_block_on": []}
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        result = ex.run_step(rid, step, parent_env={"OTHER_KEY": "would_violate"})
        assert result.step_state == "completed"

        events = _read_events(tmp_path, rid)
        kinds = [e.get("kind") for e in events]
        assert "policy_checked" not in kinds, f"dormant mode must not emit policy_checked; got {kinds!r}"
        assert "policy_denied" not in kinds

    def test_disabled_policy_skips_command_validation(self, tmp_path: Path) -> None:
        policy = _policy_with_command_violation(enabled=False, mode_default="block")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        result = ex.run_step(rid, step, parent_env={})
        assert result.step_state == "completed"
        assert result.invocation_result is not None
        assert result.invocation_result.status == "ok"

        kinds = [e.get("kind") for e in _read_events(tmp_path, rid)]
        assert "policy_checked" not in kinds
        assert "policy_denied" not in kinds


class TestTierReportOnly:
    """`enabled=true` + `mode_default="report_only"` — log, no block."""

    def test_report_only_with_violation_continues(self, tmp_path: Path) -> None:
        policy = _policy_with_secret_missing_violation(enabled=True, mode_default="report_only")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        placeholder_step_id = "invoke_agent-a2-report0001"
        _create_run_record(tmp_path, rid)

        result = ex.run_step(
            rid,
            step,
            parent_env={"OTHER_KEY": "triggers_secret_missing"},
            attempt=2,
            step_id=placeholder_step_id,
        )
        assert result.step_state == "completed"
        assert result.invocation_result is not None
        assert result.invocation_result.status == "ok"

        events = _read_events(tmp_path, rid)
        kinds = _event_kinds(events)
        assert kinds[:5] == [
            "step_started",
            "policy_checked",
            "adapter_invoked",
            "adapter_returned",
            "step_completed",
        ]
        checked = next((e for e in events if e.get("kind") == "policy_checked"), None)
        assert checked is not None, "policy_checked must be emitted"
        payload = checked.get("payload", {})
        assert payload.get("mode") == "report_only"
        assert payload.get("violations_count") == 1
        assert payload.get("would_block") is True
        assert payload.get("violation_kinds") == ["secret_missing"]
        assert payload.get("promoted_to_block") is False
        assert {e.get("step_id") for e in events[:5]} == {placeholder_step_id}

        # policy_denied NOT emitted in report_only + no escalation.
        denied = [e for e in events if e.get("kind") == "policy_denied"]
        assert denied == [], f"policy_denied must not fire in report_only without escalation; got {denied!r}"
        record, _ = load_run(tmp_path, rid)
        assert record["steps"][-1]["step_id"] == placeholder_step_id
        assert record["steps"][-1]["attempt"] == 2

    def test_report_only_command_violation_emits_checked_and_continues(
        self, tmp_path: Path
    ) -> None:
        policy = _policy_with_command_violation(
            enabled=True,
            mode_default="report_only",
        )
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        placeholder_step_id = "invoke_agent-a2-retry0001"
        _create_run_record(tmp_path, rid)

        result = ex.run_step(rid, step, parent_env={}, attempt=2, step_id=placeholder_step_id)
        assert result.step_state == "completed"
        assert result.invocation_result is not None
        assert result.invocation_result.status == "ok"

        events = _read_events(tmp_path, rid)
        kinds = [e.get("kind") for e in events]
        assert kinds[:5] == [
            "step_started",
            "policy_checked",
            "adapter_invoked",
            "adapter_returned",
            "step_completed",
        ]
        checked = events[1]
        payload = checked.get("payload", {})
        assert payload.get("mode") == "report_only"
        assert payload.get("violations_count") == 1
        assert payload.get("violation_kinds") == ["command_path_outside_policy"]
        assert payload.get("would_block") is True
        assert payload.get("promoted_to_block") is False
        assert "policy_denied" not in kinds
        assert {e.get("step_id") for e in events[:5]} == {placeholder_step_id}

        record, _ = load_run(tmp_path, rid)
        assert record["steps"][-1]["step_id"] == placeholder_step_id
        assert record["steps"][-1]["attempt"] == 2

    def test_report_only_escalates_via_promote_to_block(self, tmp_path: Path) -> None:
        # secret_missing in promote_to_block_on → escalation overrides
        # report_only, step must block (policy_denied + PolicyViolationError).
        policy = _policy_with_secret_missing_violation(
            enabled=True,
            mode_default="report_only",
            promote_to_block_on=["secret_missing"],
        )
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        placeholder_step_id = "invoke_agent-a2-escalate0001"
        _create_run_record(tmp_path, rid)
        _transition_run_to_running(tmp_path, rid)

        with pytest.raises(PolicyViolationError):
            ex.run_step(
                rid,
                step,
                parent_env={"OTHER_KEY": "escalates"},
                attempt=2,
                step_id=placeholder_step_id,
            )

        events = _read_events(tmp_path, rid)
        kinds = _event_kinds(events)
        assert kinds[:4] == [
            "step_started",
            "policy_checked",
            "policy_denied",
            "step_failed",
        ]
        checked = next((e for e in events if e.get("kind") == "policy_checked"), None)
        assert checked is not None
        assert checked.get("payload", {}).get("promoted_to_block") is True
        # Effective mode in the emitted payload is now block.
        payload = checked.get("payload", {})
        assert payload.get("mode") == "block"
        assert payload.get("violations_count") == 1
        assert payload.get("violation_kinds") == ["secret_missing"]
        assert payload.get("would_block") is True

        denied = next((e for e in events if e.get("kind") == "policy_denied"), None)
        assert denied is not None, "escalation must emit policy_denied"
        assert "adapter_invoked" not in kinds
        assert {e.get("step_id") for e in events[:4]} == {placeholder_step_id}

        record, _ = load_run(tmp_path, rid)
        assert record["steps"][-1]["step_id"] == placeholder_step_id
        assert record["steps"][-1]["state"] == "failed"


class TestTierBlock:
    """`enabled=true` + `mode_default="block"` — fail-closed (pre-P2)."""

    def test_block_with_violation_fails_closed(self, tmp_path: Path) -> None:
        policy = _policy_with_secret_missing_violation(enabled=True, mode_default="block")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        placeholder_step_id = "invoke_agent-a2-secretblock0001"
        _create_run_record(tmp_path, rid)
        _transition_run_to_running(tmp_path, rid)

        with pytest.raises(PolicyViolationError):
            ex.run_step(
                rid,
                step,
                parent_env={"OTHER_KEY": "triggers_block"},
                attempt=2,
                step_id=placeholder_step_id,
            )

        events = _read_events(tmp_path, rid)
        kinds = _event_kinds(events)
        assert kinds[:4] == [
            "step_started",
            "policy_checked",
            "policy_denied",
            "step_failed",
        ]
        checked = events[1]
        payload = checked.get("payload", {})
        assert payload.get("mode") == "block"
        assert payload.get("violations_count") == 1
        assert payload.get("violation_kinds") == ["secret_missing"]
        assert payload.get("would_block") is True
        assert payload.get("promoted_to_block") is False
        assert "adapter_invoked" not in kinds
        assert {e.get("step_id") for e in events[:4]} == {placeholder_step_id}

        record, _ = load_run(tmp_path, rid)
        assert record["steps"][-1]["step_id"] == placeholder_step_id
        assert record["steps"][-1]["state"] == "failed"

    def test_block_command_violation_fails_before_adapter_invocation(
        self, tmp_path: Path
    ) -> None:
        policy = _policy_with_command_violation(enabled=True, mode_default="block")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        placeholder_step_id = "invoke_agent-a2-block0001"
        _create_run_record(tmp_path, rid)
        _transition_run_to_running(tmp_path, rid)

        with pytest.raises(PolicyViolationError):
            ex.run_step(rid, step, parent_env={}, attempt=2, step_id=placeholder_step_id)

        events = _read_events(tmp_path, rid)
        kinds = [e.get("kind") for e in events]
        assert kinds[:4] == [
            "step_started",
            "policy_checked",
            "policy_denied",
            "step_failed",
        ]
        checked = events[1]
        payload = checked.get("payload", {})
        assert payload.get("violations_count") == 1
        assert payload.get("violation_kinds") == ["command_path_outside_policy"]
        assert "adapter_invoked" not in kinds
        assert {e.get("step_id") for e in events[:4]} == {placeholder_step_id}

        record, _ = load_run(tmp_path, rid)
        assert record["steps"][-1]["step_id"] == placeholder_step_id


class TestUnknownModeFallback:
    """Unknown `mode_default` value → `block` fail-closed fallback."""

    def test_unknown_mode_defaults_to_block(self, tmp_path: Path) -> None:
        policy = _policy_with_secret_missing_violation(enabled=True, mode_default="audit_only_v7")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        placeholder_step_id = "invoke_agent-a2-fallback0001"
        _create_run_record(tmp_path, rid)
        _transition_run_to_running(tmp_path, rid)

        with pytest.raises(PolicyViolationError):
            ex.run_step(
                rid,
                step,
                parent_env={"OTHER_KEY": "triggers_fallback"},
                attempt=2,
                step_id=placeholder_step_id,
            )

        events = _read_events(tmp_path, rid)
        kinds = _event_kinds(events)
        assert kinds[:4] == [
            "step_started",
            "policy_checked",
            "policy_denied",
            "step_failed",
        ]
        payload = events[1].get("payload", {})
        assert payload.get("mode") == "block"
        assert payload.get("violations_count") == 1
        assert payload.get("violation_kinds") == ["secret_missing"]
        assert payload.get("promoted_to_block") is False
        assert "adapter_invoked" not in kinds
        assert {e.get("step_id") for e in events[:4]} == {placeholder_step_id}


class TestDryRunParityReportOnly:
    """Report-only + dry_run_step must NOT raise PolicyViolationError —
    violations surface in the DryRunResult instead (Codex-requested parity)."""

    def test_dry_run_report_only_does_not_raise(self, tmp_path: Path) -> None:
        policy = _policy_with_secret_missing_violation(enabled=True, mode_default="report_only")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        result = ex.dry_run_step(rid, step, parent_env={"OTHER_KEY": "parity_check"})
        kinds = [kind for kind, _payload in result.predicted_events]
        assert kinds == [
            "step_started",
            "policy_checked",
            "adapter_invoked",
            "adapter_returned",
            "step_completed",
        ]
        checked_payload = result.predicted_events[1][1]
        assert checked_payload["mode"] == "report_only"
        assert checked_payload["violations_count"] == 1
        assert checked_payload["would_block"] is True
        assert checked_payload["violation_kinds"] == ["secret_missing"]
        assert checked_payload["promoted_to_block"] is False
        assert result.policy_violations == ()


class TestDryRunParityBlock:
    """Block-mode dry-run should predict denial order and surface violation details."""

    def test_dry_run_block_command_violation_predicts_denial(self, tmp_path: Path) -> None:
        policy = _policy_with_command_violation(enabled=True, mode_default="block")
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        result = ex.dry_run_step(rid, step, parent_env={})
        kinds = [kind for kind, _payload in result.predicted_events]
        assert kinds == [
            "step_started",
            "policy_checked",
            "policy_denied",
            "step_failed",
        ]
        checked_payload = result.predicted_events[1][1]
        assert checked_payload["mode"] == "block"
        assert checked_payload["violations_count"] == 1
        assert checked_payload["violation_kinds"] == ["command_path_outside_policy"]
        assert checked_payload["would_block"] is True
        assert checked_payload["promoted_to_block"] is False
        assert len(result.policy_violations) == 1
        assert "command_path_outside_policy" in result.policy_violations[0]


class TestPolicyCheckedAdditivePayload:
    """Additive fields on `policy_checked.payload` stay backward-compat."""

    def test_block_no_violation_payload_shape(self, tmp_path: Path) -> None:
        policy = _permissive_policy()
        policy["rollout"] = {"mode_default": "block", "promote_to_block_on": []}
        ex, step = _build_executor(tmp_path, policy)
        rid = str(uuid.uuid4())
        _create_run_record(tmp_path, rid)

        # No violation under permissive policy → step completes.
        ex.run_step(rid, step, parent_env={})
        events = _read_events(tmp_path, rid)
        checked = next((e for e in events if e.get("kind") == "policy_checked"), None)
        assert checked is not None
        payload = checked.get("payload", {})
        # Additive fields present with expected shapes.
        assert payload.get("mode") == "block"
        assert payload.get("would_block") is False
        assert payload.get("violation_kinds") == []
        assert payload.get("promoted_to_block") is False
        # Legacy field still present for BC.
        assert payload.get("violations_count") == 0
