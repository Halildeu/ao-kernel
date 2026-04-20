"""Tests for ``ao_kernel.executor.policy_enforcer``.

Covers plan v2 CNS-20260415-022 hardening:
- B1: PATH poisoning denied (realpath + policy-derived prefix anchor).
- B2: ``inherit_from_parent=False`` strict passthrough off.
- Q4 W: ``check_http_header_exposure`` pre-flight.
- General: env allowlist, cwd escape, secret resolution.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.executor import (
    PolicyViolation,
    build_sandbox,
    check_http_header_exposure,
    resolve_allowed_secrets,
    validate_command,
    validate_cwd,
)


def _bundled_policy() -> dict[str, Any]:
    with open(
        "ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
        encoding="utf-8",
    ) as f:
        return json.load(f)


class TestBuildSandbox:
    def test_inherit_false_strict_no_parent_passthrough(
        self, tmp_path: Path
    ) -> None:
        policy = _bundled_policy()
        parent = {"PATH": "/host/bin", "HOME": "/home/user", "SECRET": "x"}
        sandbox, violations = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env=parent,
        )
        assert violations == []
        assert sandbox.inherit_from_parent is False
        # HOME should NOT be in env_vars because inherit=False and no
        # explicit_additions entry in bundled policy.
        assert "HOME" not in sandbox.env_vars
        assert "SECRET" not in sandbox.env_vars

    def test_synthesized_path_from_prefixes(self, tmp_path: Path) -> None:
        policy = _bundled_policy()
        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={"PATH": "/ignored"},
        )
        # Bundled policy has prefixes /usr/bin/, /usr/local/bin/, /opt/homebrew/bin/
        # PATH should be synthesized from those (parent not inherited).
        path = sandbox.env_vars.get("PATH", "")
        assert "/usr/bin" in path
        assert "/opt/homebrew/bin" in path

    def test_explicit_additions_override_everything(
        self, tmp_path: Path
    ) -> None:
        policy = _bundled_policy()
        # Inject explicit_additions via copy-and-modify
        policy = dict(policy)
        env_spec = dict(policy["env_allowlist"])
        env_spec["explicit_additions"] = {"FOO": "bar", "PATH": "/custom/bin"}
        policy["env_allowlist"] = env_spec

        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={"PATH": "/host/bin"},
        )
        assert sandbox.env_vars["FOO"] == "bar"
        assert sandbox.env_vars["PATH"] == "/custom/bin"

    def test_secrets_folded_when_env_exposure(self, tmp_path: Path) -> None:
        policy = _bundled_policy()
        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={"ANTHROPIC_API_KEY": "sk-test-xyz"},
            parent_env={},
        )
        assert sandbox.env_vars["ANTHROPIC_API_KEY"] == "sk-test-xyz"


class TestValidateCommand:
    def test_runtime_interpreter_not_globally_allowlisted(
        self, tmp_path: Path
    ) -> None:
        policy = _bundled_policy()
        policy = dict(policy)
        policy["command_allowlist"] = {"exact": ["git"], "prefixes": []}
        env_spec = dict(policy["env_allowlist"])
        env_spec["explicit_additions"] = {"PATH": ""}
        policy["env_allowlist"] = env_spec

        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={},
        )
        violations = validate_command(
            sys.executable,
            (),
            sandbox,
            secret_values={},
        )
        kinds = {v.kind for v in violations}
        assert "command_path_outside_policy" in kinds

    def test_runtime_override_is_localized_to_explicit_path(
        self, tmp_path: Path
    ) -> None:
        policy = _bundled_policy()
        policy = dict(policy)
        policy["command_allowlist"] = {"exact": ["git"], "prefixes": []}
        env_spec = dict(policy["env_allowlist"])
        env_spec["explicit_additions"] = {"PATH": ""}
        policy["env_allowlist"] = env_spec

        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={},
        )
        violations = validate_command(
            sys.executable,
            (),
            sandbox,
            secret_values={},
            runtime_allowed_realpaths=(Path(sys.executable).resolve(),),
        )
        assert violations == []

    def test_path_poisoning_denied(self, tmp_path: Path) -> None:
        """Plan v2 B1: fake python3 under /tmp/evil must NOT authorize
        even though 'python3' is in exact list."""
        evil_dir = tmp_path / "evil"
        evil_dir.mkdir()
        fake_python = evil_dir / "python3"
        fake_python.write_text("#!/bin/sh\necho nope\n", encoding="utf-8")
        os.chmod(fake_python, stat.S_IRWXU)

        # Build sandbox with PATH that puts evil dir first
        policy = _bundled_policy()
        policy = dict(policy)
        env_spec = dict(policy["env_allowlist"])
        env_spec["explicit_additions"] = {"PATH": f"{evil_dir}:/usr/bin"}
        policy["env_allowlist"] = env_spec

        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={},
        )
        violations = validate_command(
            "python3", (), sandbox, secret_values={}
        )
        # Must find at least one violation because evil dir is NOT under
        # policy-declared prefixes.
        kinds = {v.kind for v in violations}
        assert "command_path_outside_policy" in kinds, (
            f"path poisoning not denied: {violations}"
        )

    def test_unresolvable_command_denied(self, tmp_path: Path) -> None:
        policy = _bundled_policy()
        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={},
        )
        violations = validate_command(
            "definitely_not_a_real_command_xyz",
            (),
            sandbox,
            secret_values={},
        )
        kinds = {v.kind for v in violations}
        assert "command_not_allowlisted" in kinds

    def test_secret_in_argv_detected(self, tmp_path: Path) -> None:
        policy = _bundled_policy()
        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={"TOKEN": "super-secret-value"},
            parent_env={},
        )
        violations = validate_command(
            "git",
            ("--token", "super-secret-value"),
            sandbox,
            secret_values={"TOKEN": "super-secret-value"},
        )
        kinds = {v.kind for v in violations}
        assert "secret_exposure_denied" in kinds


class TestValidateCwd:
    def test_escape_with_parent_reference(self, tmp_path: Path) -> None:
        policy = _bundled_policy()
        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={},
        )
        violations = validate_cwd(tmp_path / ".." / "outside", sandbox)
        assert violations and violations[0].kind == "cwd_escape"

    def test_within_root_allowed(self, tmp_path: Path) -> None:
        policy = _bundled_policy()
        sandbox, _ = build_sandbox(
            policy=policy,
            worktree_root=tmp_path,
            resolved_secrets={},
            parent_env={},
        )
        sub = tmp_path / "sub"
        sub.mkdir()
        violations = validate_cwd(sub, sandbox)
        assert violations == []


class TestResolveAllowedSecrets:
    def test_happy_resolution(self) -> None:
        policy = {
            "secrets": {
                "allowlist_secret_ids": ["TOKEN_A", "TOKEN_B"],
            }
        }
        resolved, v = resolve_allowed_secrets(
            policy, {"TOKEN_A": "a-val", "TOKEN_B": "b-val", "OTHER": "x"}
        )
        assert resolved == {"TOKEN_A": "a-val", "TOKEN_B": "b-val"}
        assert v == []

    def test_missing_secret_violation(self) -> None:
        policy = {
            "secrets": {
                "allowlist_secret_ids": ["REQUIRED"],
            }
        }
        resolved, v = resolve_allowed_secrets(policy, {})
        assert resolved == {}
        assert v and v[0].kind == "secret_missing"


class TestHttpHeaderExposure:
    def test_http_without_exposure_mode_denied(self) -> None:
        policy = {
            "secrets": {
                "exposure_modes": ["env"],
                "allowlist_secret_ids": ["TOKEN"],
            }
        }
        invocation = {
            "transport": "http",
            "auth_secret_id_ref": "TOKEN",
        }
        violations = check_http_header_exposure(
            policy=policy, adapter_manifest_invocation=invocation
        )
        assert violations
        assert violations[0].kind == "http_header_exposure_unauthorized"

    def test_http_with_explicit_exposure_mode_ok(self) -> None:
        policy = {
            "secrets": {
                "exposure_modes": ["env", "http_header"],
                "allowlist_secret_ids": ["TOKEN"],
            }
        }
        invocation = {
            "transport": "http",
            "auth_secret_id_ref": "TOKEN",
        }
        violations = check_http_header_exposure(
            policy=policy, adapter_manifest_invocation=invocation
        )
        assert violations == []

    def test_cli_transport_ignored(self) -> None:
        """Non-HTTP invocations are not gated by http_header exposure."""
        policy = {"secrets": {"exposure_modes": ["env"]}}
        invocation = {"transport": "cli"}
        assert check_http_header_exposure(
            policy=policy, adapter_manifest_invocation=invocation
        ) == []

    def test_no_auth_secret_ref_ignored(self) -> None:
        policy = {"secrets": {"exposure_modes": ["env"]}}
        invocation = {"transport": "http"}
        assert check_http_header_exposure(
            policy=policy, adapter_manifest_invocation=invocation
        ) == []


class TestPolicyViolationShape:
    def test_violation_is_immutable_dataclass(self) -> None:
        v = PolicyViolation(
            kind="cwd_escape",
            detail="x",
            policy_ref="ao_kernel/defaults/policies/policy_worktree_profile.v1.json",
            field_path="cwd_confinement",
        )
        with pytest.raises(Exception):  # frozen dataclass
            v.detail = "mutated"  # type: ignore[misc]
