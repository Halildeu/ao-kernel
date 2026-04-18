"""PR-C2: parent_env union (security-split).

Adapter path UNION ``allowlist_secret_ids ∪ env_allowlist.allowed_keys``;
sandbox (CI/patch) path env_allowlist MINUS secret_ids (least-privilege).

Security invariants pinned:
- CI sandbox MUST NOT surface GH_TOKEN/ANTHROPIC_API_KEY in env_vars.
- Adapter sandbox DOES surface allowlisted secrets (GH_TOKEN for open_pr).
- Operator misuse overlap (same key in both sets) still guarded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from ao_kernel.executor import MultiStepDriver
from ao_kernel.executor.executor import Executor
from ao_kernel.workflow.registry import WorkflowRegistry
from ao_kernel.adapters import AdapterRegistry

from tests._driver_helpers import build_driver, install_workspace


def _minimal_driver(
    tmp_path: Path,
    policy: Mapping[str, Any] | None = None,
) -> MultiStepDriver:
    install_workspace(tmp_path)
    wreg = WorkflowRegistry()
    wreg.load_workspace(tmp_path)
    areg = AdapterRegistry()
    areg.load_workspace(tmp_path)
    executor = Executor(
        workspace_root=tmp_path,
        workflow_registry=wreg,
        adapter_registry=areg,
        policy_loader=policy,
    )
    return MultiStepDriver(
        workspace_root=tmp_path,
        registry=wreg,
        adapter_registry=areg,
        executor=executor,
        policy_config=policy,
    )


# --- 1. Helper unit tests ---------------------------------------------------


class TestAdapterParentEnvUnion:
    def test_includes_allowlist_secret_ids(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AO_C2_SECRET_TOKEN", "secret-value")
        policy = {
            "secrets": {"allowlist_secret_ids": ["AO_C2_SECRET_TOKEN"]},
            "env_allowlist": {"allowed_keys": []},
        }
        result = MultiStepDriver._compute_adapter_parent_env(policy)
        assert result == {"AO_C2_SECRET_TOKEN": "secret-value"}

    def test_includes_env_allowlist_allowed_keys(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AO_C2_ENV_KEY", "env-value")
        policy = {
            "secrets": {"allowlist_secret_ids": []},
            "env_allowlist": {"allowed_keys": ["AO_C2_ENV_KEY"]},
        }
        result = MultiStepDriver._compute_adapter_parent_env(policy)
        assert result == {"AO_C2_ENV_KEY": "env-value"}

    def test_merges_both_sets(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AO_C2_TOK", "tok")
        monkeypatch.setenv("AO_C2_ENV", "env")
        policy = {
            "secrets": {"allowlist_secret_ids": ["AO_C2_TOK"]},
            "env_allowlist": {"allowed_keys": ["AO_C2_ENV"]},
        }
        result = MultiStepDriver._compute_adapter_parent_env(policy)
        assert result == {"AO_C2_TOK": "tok", "AO_C2_ENV": "env"}

    def test_omits_missing_keys(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("AO_C2_MISSING", raising=False)
        policy = {
            "secrets": {"allowlist_secret_ids": ["AO_C2_MISSING"]},
            "env_allowlist": {"allowed_keys": []},
        }
        result = MultiStepDriver._compute_adapter_parent_env(policy)
        assert result == {}


class TestSandboxParentEnvEnvOnly:
    def test_excludes_secrets(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Security: CI/patch sandbox parent_env'de secret YOK."""
        monkeypatch.setenv("AO_C2_SECRET", "leak-candidate")
        monkeypatch.setenv("AO_C2_SAFE", "env-value")
        policy = {
            "secrets": {"allowlist_secret_ids": ["AO_C2_SECRET"]},
            "env_allowlist": {"allowed_keys": ["AO_C2_SAFE"]},
        }
        result = MultiStepDriver._compute_sandbox_parent_env(policy)
        assert "AO_C2_SECRET" not in result
        assert result == {"AO_C2_SAFE": "env-value"}

    def test_excludes_operator_misuse_overlap(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """v3 HARDENING: Operator yanlışlıkla aynı key'i hem
        allowlist_secret_ids hem env_allowlist.allowed_keys'e koyarsa
        bile sandbox'a sızmaz (structural set-difference guard)."""
        monkeypatch.setenv("AO_C2_OVERLAP", "dangerous")
        monkeypatch.setenv("AO_C2_PATH", "/usr/bin")
        policy = {
            "secrets": {"allowlist_secret_ids": ["AO_C2_OVERLAP"]},
            "env_allowlist": {
                # Operator misuse: overlap with secret_ids
                "allowed_keys": ["AO_C2_OVERLAP", "AO_C2_PATH"],
            },
        }
        result = MultiStepDriver._compute_sandbox_parent_env(policy)
        assert "AO_C2_OVERLAP" not in result, (
            "operator misuse overlap leaked into sandbox env"
        )
        assert result == {"AO_C2_PATH": "/usr/bin"}


# --- 2. Integration smoke ---------------------------------------------------


class TestAdapterPathUnionIntegration:
    def test_run_adapter_step_computes_adapter_union(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify ``_run_adapter_step`` builds adapter union for
        ``executor.run_step(parent_env=...)`` call. Unit-level — we
        inspect ``_compute_adapter_parent_env`` via the driver's
        attached policy; forwarding chain pinned separately below."""
        monkeypatch.setenv("AO_C2_GH_TOKEN", "gh-token-value")
        policy = {
            "secrets": {"allowlist_secret_ids": ["AO_C2_GH_TOKEN"]},
            "env_allowlist": {"allowed_keys": []},
        }
        driver = _minimal_driver(tmp_path, policy=policy)
        result = driver._compute_adapter_parent_env(driver._policy)
        assert result == {"AO_C2_GH_TOKEN": "gh-token-value"}

    def test_build_sandbox_uses_env_only_no_secret_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify _build_sandbox does NOT invoke resolve_allowed_secrets
        (v3 hardening: resolved_secrets literal ``{}``). The resulting
        sandbox.env_vars must not contain the secret."""
        monkeypatch.setenv("AO_C2_GH_TOKEN", "gh-token-value")
        monkeypatch.setenv("AO_C2_PATH", "/usr/bin")
        policy = {
            "secrets": {
                "allowlist_secret_ids": ["AO_C2_GH_TOKEN"],
                "exposure_modes": ["env"],
            },
            "env_allowlist": {
                "allowed_keys": ["AO_C2_PATH"],
                "inherit_from_parent": True,
            },
            "command_allowlist": {
                "exact": [],
                "prefixes": [],
            },
        }
        driver = _minimal_driver(tmp_path, policy=policy)
        sandbox = driver._build_sandbox("test-run-id")
        # GH_TOKEN must NOT be in sandbox env (CI/patch least-privilege)
        assert "AO_C2_GH_TOKEN" not in sandbox.env_vars


# --- 3. Security regression -------------------------------------------------


class TestSecurityRegression:
    def test_ci_sandbox_does_not_leak_secret(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sec regression: policy allowlists GH_TOKEN as secret AND
        host env has it — _build_sandbox MUST NOT expose it."""
        monkeypatch.setenv("AO_C2_LEAK_CANDIDATE", "should-not-leak")
        policy = {
            "secrets": {
                "allowlist_secret_ids": ["AO_C2_LEAK_CANDIDATE"],
                "exposure_modes": ["env"],
            },
            "env_allowlist": {
                "allowed_keys": [],
                "inherit_from_parent": True,
            },
            "command_allowlist": {"exact": [], "prefixes": []},
        }
        driver = _minimal_driver(tmp_path, policy=policy)
        sandbox = driver._build_sandbox("test-run-id")
        assert "AO_C2_LEAK_CANDIDATE" not in sandbox.env_vars

    def test_adapter_parent_env_includes_secret(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Positive security: adapter path DOES include allowlisted
        secret (so gh-cli-pr / codex-stub can authenticate)."""
        monkeypatch.setenv("AO_C2_GH_TOKEN", "real-token")
        policy = {
            "secrets": {
                "allowlist_secret_ids": ["AO_C2_GH_TOKEN"],
                "exposure_modes": ["env"],
            },
            "env_allowlist": {"allowed_keys": []},
        }
        driver = _minimal_driver(tmp_path, policy=policy)
        adapter_env = driver._compute_adapter_parent_env(driver._policy)
        assert adapter_env == {"AO_C2_GH_TOKEN": "real-token"}


# --- 4. build_driver forwarding (B2 regression lock) -----------------------


class TestBuildDriverPolicyForward:
    def test_forwards_policy_to_both_driver_and_executor(
        self, tmp_path: Path,
    ) -> None:
        """PR-C2 B2 regression: build_driver(policy_loader=...) must
        propagate the same policy to BOTH the Executor instance AND
        the Driver instance. Previously Driver received default ``{}``
        regardless of kwarg → _build_sandbox ran against empty policy
        → union/env-only splits had no effect."""
        install_workspace(tmp_path)
        custom_policy = {
            "_c2_forward_sentinel": "both_driver_and_executor",
            "secrets": {"allowlist_secret_ids": ["X"]},
            "env_allowlist": {"allowed_keys": ["Y"]},
        }
        driver = build_driver(tmp_path, policy_loader=custom_policy)
        assert driver._policy is custom_policy, (
            "driver._policy must be the forwarded policy"
        )
        assert driver._executor._policy is custom_policy, (
            "executor._policy must be the forwarded policy"
        )
        # Contract: sandbox path uses driver._policy; adapter path
        # executes via executor (which uses executor._policy). When
        # build_driver forwards both, both sides see the same splits.
