"""PR-C1a: tests/_driver_helpers.build_driver(policy_loader=...) forward.

Default call (no policy_loader) must preserve the pre-C1a behavior;
explicit override must reach the Executor's effective policy surface.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests._driver_helpers import build_driver


def _install_workflow(root: Path) -> None:
    """Minimal bundled workflow for driver smoke (mirrors fixture
    ``simple_aokernel_flow`` shape used across A4+ tests)."""
    workflows_dir = root / ".ao" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    # Build a tiny ao-kernel-only workflow so no adapter is required.
    wf = {
        "workflow_id": "smoke_flow",
        "workflow_version": "1.0.0",
        "initial_state": "created",
        "steps": [
            {
                "step_name": "noop",
                "actor": "ao-kernel",
                "operation": "context_compile",
            }
        ],
        "states": ["created", "running", "completed", "failed", "cancelled"],
        "transitions": [
            ["created", "running"],
            ["running", "completed"],
        ],
    }
    (workflows_dir / "smoke_flow.workflow.v1.json").write_text(
        json.dumps(wf, indent=2), encoding="utf-8",
    )


class TestBuildDriverPolicyLoaderForward:
    def test_default_call_no_override_baseline(self, tmp_path: Path) -> None:
        """Default build_driver(root) signature unchanged: no kwarg
        required, executor constructed with bundled policy defaults."""
        _install_workflow(tmp_path)
        driver = build_driver(tmp_path)
        assert driver is not None
        # Executor is available via driver internals
        executor = driver._executor
        assert executor is not None

    def test_explicit_override_reaches_executor(self, tmp_path: Path) -> None:
        """policy_loader kwarg forwards to Executor; custom policy
        visible on the executor's effective policy surface."""
        _install_workflow(tmp_path)
        custom_policy = {
            "_pr_c1a_sentinel": "policy_loader_forward_test",
        }
        driver = build_driver(tmp_path, policy_loader=custom_policy)
        executor = driver._executor
        # Executor stores policy on ``_policy`` attribute
        assert executor._policy.get("_pr_c1a_sentinel") == (
            "policy_loader_forward_test"
        )

    def test_none_kwarg_matches_default_behavior(self, tmp_path: Path) -> None:
        """Passing policy_loader=None is identical to omitting it —
        Executor falls back to bundled defaults."""
        _install_workflow(tmp_path)
        driver_default = build_driver(tmp_path)
        driver_none = build_driver(tmp_path, policy_loader=None)
        # Both executors share bundled-default policy keys
        assert "_pr_c1a_sentinel" not in driver_default._executor._policy
        assert "_pr_c1a_sentinel" not in driver_none._executor._policy
