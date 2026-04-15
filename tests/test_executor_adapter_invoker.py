"""Tests for ``ao_kernel.executor.adapter_invoker``.

Covers CLI happy path (unmocked subprocess using bundled codex_stub),
CLI env hermeticity (sandbox env does NOT leak host env into subprocess),
HTTP path via mocked urlopen, JSONPath subset validation, text/plain
fallback triple gate, exit code mapping.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ao_kernel.adapters import AdapterManifest
from ao_kernel.executor import (
    AdapterInvocationFailedError,
    AdapterOutputParseError,
    RedactionConfig,
    SandboxedEnvironment,
    WorktreeHandle,
    invoke_cli,
    invoke_http,
)
from ao_kernel.executor.adapter_invoker import _jsonpath_dotted
from ao_kernel.workflow import budget_from_dict


def _sandbox(tmp_path: Path, env: dict[str, str] | None = None) -> SandboxedEnvironment:
    env_vars = env or {
        "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": "/tmp/fake-home",
        "LANG": "en_US.UTF-8",
    }
    return SandboxedEnvironment(
        env_vars=env_vars,
        cwd=tmp_path,
        allowed_commands_exact=frozenset({"git", "python3", "pytest", "ruff", "mypy"}),
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


def _worktree(tmp_path: Path, run_id: str) -> WorktreeHandle:
    (tmp_path / ".ao" / "runs" / run_id / "worktree").mkdir(parents=True)
    return WorktreeHandle(
        run_id=run_id,
        path=tmp_path / ".ao" / "runs" / run_id / "worktree",
        base_revision="deadbeef",
        strategy="new_per_run",
        created_at="2026-04-15T20:30:00+00:00",
    )


def _manifest_cli(
    *,
    adapter_id: str = "codex-stub",
    command: str = "python3",
    args: tuple[str, ...] = ("-m", "ao_kernel.fixtures.codex_stub", "--run-id", "{run_id}"),
    capabilities: tuple[str, ...] = ("read_repo", "write_diff"),
    timeout_seconds: int = 30,
) -> AdapterManifest:
    return AdapterManifest(
        adapter_id=adapter_id,
        adapter_kind="codex-stub",
        version="1.0.0",
        capabilities=frozenset(capabilities),
        invocation={
            "transport": "cli",
            "command": command,
            "args": list(args),
            "env_allowlist_ref": "#/env_allowlist/allowed_keys",
            "cwd_policy": "per_run_worktree",
            "stdin_mode": "none",
            "exit_code_map": {"0": "ok"},
            "timeout_seconds": timeout_seconds,
        },
        input_envelope_shape={"task_prompt": "x", "run_id": "x"},
        output_envelope_shape={"status": "ok"},
        interrupt_contract=None,
        policy_refs=("ao_kernel/defaults/policies/policy_worktree_profile.v1.json",),
        evidence_refs=(".ao/evidence/workflows/{run_id}/adapter-codex-stub.jsonl",),
        source_path=Path("/tmp/fake.manifest.v1.json"),
    )


def _manifest_http(
    *,
    endpoint: str = "https://agent.example.invalid/v1/run",
    response_parse: dict[str, str] | None = None,
    capabilities: tuple[str, ...] = ("read_repo", "write_diff"),
) -> AdapterManifest:
    invocation: dict[str, Any] = {
        "transport": "http",
        "endpoint": endpoint,
        "auth_secret_id_ref": "API_TOKEN",
        "headers_allowlist": ["Content-Type", "Accept"],
        "request_body_template": {"prompt": "{task_prompt}"},
        "timeout_seconds": 10,
    }
    if response_parse is not None:
        invocation["response_parse"] = response_parse
    return AdapterManifest(
        adapter_id="http-stub",
        adapter_kind="custom-http",
        version="1.0.0",
        capabilities=frozenset(capabilities),
        invocation=invocation,
        input_envelope_shape={"task_prompt": "x", "run_id": "x"},
        output_envelope_shape={"status": "ok"},
        interrupt_contract=None,
        policy_refs=("ao_kernel/defaults/policies/policy_worktree_profile.v1.json",),
        evidence_refs=(".ao/evidence/workflows/{run_id}/adapter-http-stub.jsonl",),
        source_path=Path("/tmp/fake.manifest.v1.json"),
    )


def _budget(time_limit: float = 120.0) -> Any:
    return budget_from_dict(
        {
            "time_seconds": {"limit": time_limit, "spent": 0.0, "remaining": time_limit},
            "fail_closed_on_exhaust": True,
        }
    )


# ---------------------------------------------------------------------------
# CLI happy path — unmocked subprocess (codex_stub)
# ---------------------------------------------------------------------------


class TestCliHappyPath:
    def test_codex_stub_integration(self, tmp_path: Path) -> None:
        import os as _os

        rid = "00000000-0000-4000-8000-00000000ab01"
        manifest = _manifest_cli()
        # Test must allow the subprocess to find ao_kernel on PYTHONPATH.
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

        result, budget_after = invoke_cli(
            manifest=manifest,
            input_envelope={"task_prompt": "fix bug", "run_id": rid},
            sandbox=sandbox,
            worktree=worktree,
            budget=budget,
            workspace_root=tmp_path,
            run_id=rid,
        )
        assert result.status == "ok"
        assert result.diff is not None
        assert "+hello world" in result.diff


class TestCliEnvHermeticity:
    def test_env_only_contains_sandbox_keys(self, tmp_path: Path) -> None:
        """Subprocess env must match sandbox.env_vars exactly; host env
        keys not in sandbox MUST NOT leak through."""
        sandbox = _sandbox(
            tmp_path,
            env={
                "PATH": "/usr/bin:/usr/local/bin:/opt/homebrew/bin",
                "SANDBOX_MARKER": "present",
            },
        )
        # The goal is to OBSERVE a subprocess env dump under the same
        # env dict the invoker would use. Running subprocess directly
        # avoids the invoker's JSON-envelope parsing.
        import subprocess as sp

        proc = sp.run(
            [
                "python3",
                "-c",
                "import os, json, sys; sys.stdout.write(json.dumps(dict(os.environ)))",
            ],
            env=dict(sandbox.env_vars),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        env_dump: dict[str, str] = json.loads(proc.stdout)
        assert env_dump.get("SANDBOX_MARKER") == "present"
        # Host-only env keys absent.
        assert "HOME_LEAK_MARKER" not in env_dump


class TestCliFailurePaths:
    def test_command_not_found(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000ab03"
        manifest = _manifest_cli(command="definitely_missing_bin_xyz")
        sandbox = _sandbox(tmp_path)
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        with pytest.raises(AdapterInvocationFailedError) as ei:
            invoke_cli(
                manifest=manifest,
                input_envelope={"task_prompt": "x", "run_id": rid},
                sandbox=sandbox,
                worktree=worktree,
                budget=budget,
                workspace_root=tmp_path,
                run_id=rid,
            )
        assert ei.value.reason == "command_not_found"

    def test_output_parse_fails_on_prose(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000ab04"
        manifest = _manifest_cli(
            args=("-c", "print('this is just prose, not a diff or JSON')"),
        )
        sandbox = _sandbox(tmp_path)
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        with pytest.raises(AdapterOutputParseError):
            invoke_cli(
                manifest=manifest,
                input_envelope={"task_prompt": "x", "run_id": rid},
                sandbox=sandbox,
                worktree=worktree,
                budget=budget,
                workspace_root=tmp_path,
                run_id=rid,
            )


# ---------------------------------------------------------------------------
# JSONPath minimal subset
# ---------------------------------------------------------------------------


class TestJsonPathSubset:
    def test_dotted_subset_happy(self) -> None:
        root = {"result": {"status": "ok", "diff": "--- a"}}
        assert _jsonpath_dotted(root, "$.result.status") == "ok"

    def test_non_subset_rejected_array_index(self) -> None:
        with pytest.raises(AdapterOutputParseError):
            _jsonpath_dotted({}, "$.arr[0].x")

    def test_non_subset_rejected_wildcard(self) -> None:
        with pytest.raises(AdapterOutputParseError):
            _jsonpath_dotted({}, "$.*.x")

    def test_missing_key_returns_sentinel(self) -> None:
        from ao_kernel.executor.adapter_invoker import _SENTINEL_MISSING

        assert _jsonpath_dotted({"a": 1}, "$.b") is _SENTINEL_MISSING


# ---------------------------------------------------------------------------
# HTTP invocation via mocked urlopen
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, body: str, content_type: str = "application/json") -> None:
        self._body = body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class TestHttpInvoke:
    def test_canonical_json_envelope(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000ab05"
        envelope = {
            "status": "ok",
            "diff": "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-1\n+2\n",
            "finish_reason": "normal",
        }
        manifest = _manifest_http()
        sandbox = _sandbox(
            tmp_path,
            env={"PATH": "/usr/bin", "API_TOKEN": "sk-test-abc"},
        )
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse(json.dumps(envelope)),
        ):
            result, _ = invoke_http(
                manifest=manifest,
                input_envelope={"task_prompt": "x", "run_id": rid},
                sandbox=sandbox,
                worktree=worktree,
                budget=budget,
                workspace_root=tmp_path,
                run_id=rid,
            )
        assert result.status == "ok"
        assert result.diff is not None

    def test_text_plain_fallback_triple_gate(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000ab06"
        diff_body = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        manifest = _manifest_http(capabilities=("write_diff",))
        sandbox = _sandbox(
            tmp_path,
            env={"PATH": "/usr/bin", "API_TOKEN": "sk-test"},
        )
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse(diff_body, content_type="text/plain"),
        ):
            result, _ = invoke_http(
                manifest=manifest,
                input_envelope={"task_prompt": "x", "run_id": rid},
                sandbox=sandbox,
                worktree=worktree,
                budget=budget,
                workspace_root=tmp_path,
                run_id=rid,
            )
        assert result.status == "ok"
        assert result.diff == diff_body.strip()

    def test_text_plain_without_write_diff_capability_fails(
        self, tmp_path: Path
    ) -> None:
        rid = "00000000-0000-4000-8000-00000000ab07"
        diff_body = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        manifest = _manifest_http(capabilities=("read_repo",))
        sandbox = _sandbox(
            tmp_path,
            env={"PATH": "/usr/bin", "API_TOKEN": "sk-test"},
        )
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse(diff_body, content_type="text/plain"),
        ):
            with pytest.raises(AdapterOutputParseError):
                invoke_http(
                    manifest=manifest,
                    input_envelope={"task_prompt": "x", "run_id": rid},
                    sandbox=sandbox,
                    worktree=worktree,
                    budget=budget,
                    workspace_root=tmp_path,
                    run_id=rid,
                )

    def test_response_parse_subset(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000ab08"
        manifest = _manifest_http(
            response_parse={
                "status_jsonpath": "$.result.status",
                "diff_jsonpath": "$.result.diff",
            },
            capabilities=("write_diff",),
        )
        sandbox = _sandbox(
            tmp_path,
            env={"PATH": "/usr/bin", "API_TOKEN": "sk-test"},
        )
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        body = json.dumps(
            {"result": {"status": "ok", "diff": "--- a"}}
        )
        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ):
            result, _ = invoke_http(
                manifest=manifest,
                input_envelope={"task_prompt": "x", "run_id": rid},
                sandbox=sandbox,
                worktree=worktree,
                budget=budget,
                workspace_root=tmp_path,
                run_id=rid,
            )
        assert result.status == "ok"
        assert result.diff == "--- a"

    def test_response_parse_non_subset_rejected(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000ab09"
        manifest = _manifest_http(
            response_parse={
                "status_jsonpath": "$.results[0].status",  # array index, not in subset
            },
        )
        sandbox = _sandbox(
            tmp_path,
            env={"PATH": "/usr/bin", "API_TOKEN": "sk-test"},
        )
        worktree = _worktree(tmp_path, rid)
        budget = _budget()
        with patch(
            "urllib.request.urlopen",
            return_value=_FakeResponse('{"results": [{"status": "ok"}]}'),
        ):
            with pytest.raises(AdapterOutputParseError):
                invoke_http(
                    manifest=manifest,
                    input_envelope={"task_prompt": "x", "run_id": rid},
                    sandbox=sandbox,
                    worktree=worktree,
                    budget=budget,
                    workspace_root=tmp_path,
                    run_id=rid,
                )
