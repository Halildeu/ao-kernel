"""PR-C2.1: MultiStepDriver default bundled-policy fallback.

Regression gate for Codex retrospective `019da0b2` bulgu 1:
MultiStepDriver previously defaulted to empty ``{}`` policy, so
C2's security-split fix never engaged in benchmark/demo paths.
This file pins:

1. Default construction loads the bundled
   ``policy_worktree_profile.v1.json`` shape.
2. Explicit ``policy_config`` still wins (override semantics).
3. Downstream ``_build_sandbox`` sees the real PATH-synth
   command_allowlist prefixes, not an empty PATH.
"""

from __future__ import annotations

from pathlib import Path

from ao_kernel.adapters import AdapterRegistry
from ao_kernel.executor import Executor, MultiStepDriver
from ao_kernel.workflow.registry import WorkflowRegistry


def _build_driver(
    workspace_root: Path,
    *,
    policy_config=None,
) -> MultiStepDriver:
    wreg = WorkflowRegistry()
    wreg.load_workspace(workspace_root)
    areg = AdapterRegistry()
    areg.load_workspace(workspace_root)
    executor = Executor(
        workspace_root=workspace_root,
        workflow_registry=wreg,
        adapter_registry=areg,
    )
    return MultiStepDriver(
        workspace_root=workspace_root,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
        policy_config=policy_config,
    )


class TestDefaultPolicyLoad:
    def test_default_loads_bundled_policy(self, tmp_path: Path) -> None:
        """Default construction (no policy_config) yields the
        bundled ``policy_worktree_profile.v1.json`` — previously
        gave empty ``{}``."""
        driver = _build_driver(tmp_path)
        policy = driver._policy
        assert policy is not None
        # Bundled policy ships these top-level keys:
        for key in (
            "worktree",
            "env_allowlist",
            "secrets",
            "command_allowlist",
            "cwd_confinement",
            "evidence_redaction",
        ):
            assert key in policy, (
                f"bundled policy missing top-level {key!r}"
            )
        # Bundled default is DORMANT (enabled=false).
        assert policy.get("enabled") is False

    def test_explicit_policy_config_overrides_bundled(
        self, tmp_path: Path,
    ) -> None:
        """Non-empty ``policy_config`` kwarg still wins over the
        bundled fallback — backwards-compat invariant."""
        custom = {
            "_c2_1_sentinel": "explicit_policy_wins",
            "secrets": {"allowlist_secret_ids": ["X"]},
        }
        driver = _build_driver(tmp_path, policy_config=custom)
        assert driver._policy is custom

    def test_empty_dict_policy_config_falls_back_to_bundled(
        self, tmp_path: Path,
    ) -> None:
        """Driver/Executor parity (Codex deep-review follow-up
        note): both sides use truthiness-based fallback, so an
        explicit empty ``{}`` is treated the same as ``None`` —
        bundled policy loads. This prevents the subtle split where
        ``build_driver(policy_loader={})`` would yield empty
        driver-policy but bundled executor-policy."""
        driver = _build_driver(tmp_path, policy_config={})
        # Falsy {} → bundled (non-empty, with real scaffolding).
        assert driver._policy != {}
        assert "command_allowlist" in driver._policy
        # Executor parity check: same empty dict path there too.
        executor_policy = driver._executor._policy
        assert "command_allowlist" in executor_policy

    def test_default_policy_contains_command_prefixes(
        self, tmp_path: Path,
    ) -> None:
        """The bundled policy's ``command_allowlist.prefixes`` is
        what ``_build_sandbox`` uses to synthesise the sandbox PATH
        (policy_enforcer.py:135-141). An empty-dict default would
        leave PATH empty and break every ``ci_*`` / ``patch_*``
        sandbox call; this pins that the default now includes real
        prefixes."""
        driver = _build_driver(tmp_path)
        cmd_spec = driver._policy.get("command_allowlist", {})
        prefixes = cmd_spec.get("prefixes", [])
        assert isinstance(prefixes, list)
        assert len(prefixes) > 0, (
            "bundled command_allowlist.prefixes empty — sandbox PATH "
            "would not resolve system binaries"
        )
