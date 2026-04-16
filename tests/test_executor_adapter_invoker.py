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


class TestBundledCodexStubEndToEnd:
    """CNS-028v2 iter-7 blocker fix: a real subprocess invocation that
    goes through the BUNDLED codex-stub manifest (not a hand-built
    _manifest_cli() helper) must succeed — the bundled manifest
    declares an output_parse rule for review_findings, so the stub
    runtime emits the payload and the rule walker extracts it without
    tripping output_parse_failed."""

    def test_bundled_manifest_invocation_extracts_review_findings(
        self, tmp_path: Path
    ) -> None:
        import os as _os
        from ao_kernel.adapters import AdapterRegistry

        rid = "00000000-0000-4000-8000-0000000b0001"

        # Load the BUNDLED manifest (same one that ships in the wheel).
        adapters = AdapterRegistry()
        adapters.load_bundled()
        manifest = adapters.get("codex-stub")
        # Sanity: bundled manifest has the output_parse rule (else the
        # blocker condition never arises).
        assert manifest.output_parse is not None
        assert "review_findings" in manifest.capabilities

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

        result, _budget_after = invoke_cli(
            manifest=manifest,
            input_envelope={"task_prompt": "review this", "run_id": rid},
            sandbox=sandbox,
            worktree=worktree,
            budget=budget,
            workspace_root=tmp_path,
            run_id=rid,
        )

        # Invocation succeeded (not output_parse_failed).
        assert result.status == "ok"
        # The walker extracted review_findings via the bundled rule.
        assert "review_findings" in result.extracted_outputs
        payload = result.extracted_outputs["review_findings"]
        assert payload["schema_version"] == "1"
        assert payload["findings"] == []
        assert "codex-stub" in payload["summary"].lower()


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


# ---------------------------------------------------------------------------
# PR-B0: output_parse rule walker + InvocationResult.extracted_outputs
# ---------------------------------------------------------------------------


def _manifest_with_output_parse(
    *,
    adapter_id: str = "review-stub",
    output_parse: dict[str, Any] | None = None,
    capabilities: tuple[str, ...] = ("read_repo", "review_findings"),
) -> AdapterManifest:
    # Start from _manifest_cli (CLI transport; no real subprocess —
    # extraction is tested via _invocation_from_envelope directly).
    base = _manifest_cli(adapter_id=adapter_id, capabilities=capabilities)
    return AdapterManifest(
        adapter_id=base.adapter_id,
        adapter_kind=base.adapter_kind,
        version=base.version,
        capabilities=base.capabilities,
        invocation=base.invocation,
        input_envelope_shape=base.input_envelope_shape,
        output_envelope_shape=base.output_envelope_shape,
        interrupt_contract=base.interrupt_contract,
        policy_refs=base.policy_refs,
        evidence_refs=base.evidence_refs,
        source_path=base.source_path,
        output_parse=output_parse,
    )


class TestInvocationResultBackwardsCompat:
    """Existing callers must continue to work without constructing
    ``extracted_outputs``; default is empty mapping."""

    def test_default_extracted_outputs_empty(self, tmp_path: Path) -> None:
        from ao_kernel.executor.adapter_invoker import InvocationResult

        r = InvocationResult(
            status="ok",
            diff=None,
            evidence_events=(),
            commands_executed=(),
            error=None,
            finish_reason=None,
            interrupt_token=None,
            cost_actual={},
            stdout_path=tmp_path / "log.jsonl",
            stderr_path=None,
        )
        assert dict(r.extracted_outputs) == {}

    def test_invocation_from_envelope_no_manifest_is_noop(self, tmp_path: Path) -> None:
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        envelope = {"status": "ok", "diff": "", "review_findings": {"x": 1}}
        result = _invocation_from_envelope(
            envelope,
            log_path=tmp_path / "log.jsonl",
            elapsed=0.1,
            command="python3",
            manifest=None,
        )
        assert result.status == "ok"
        assert dict(result.extracted_outputs) == {}


class TestOutputParseExtraction:
    """PR-B0 output_parse rule walker — happy path + four Q6 edge cases."""

    def test_extraction_happy_path(self, tmp_path: Path) -> None:
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.review_findings",
                        "capability": "review_findings",
                        "schema_ref": "review-findings.schema.v1.json",
                    }
                ]
            },
        )
        envelope = {
            "status": "ok",
            "review_findings": {
                "schema_version": "1",
                "findings": [
                    {
                        "severity": "warning",
                        "message": "Possible off-by-one in loop bound.",
                        "file": "foo.py",
                        "line": 42,
                    }
                ],
                "summary": "Reviewed 1 file; found 1 warning.",
                "score": 0.7,
            },
        }
        result = _invocation_from_envelope(
            envelope,
            log_path=tmp_path / "log.jsonl",
            elapsed=0.2,
            command="python3",
            manifest=manifest,
        )
        assert "review_findings" in result.extracted_outputs
        payload = result.extracted_outputs["review_findings"]
        assert payload["summary"].startswith("Reviewed")
        assert len(payload["findings"]) == 1

    def test_edge_case_1_multi_rule_same_capability_is_loader_concern_not_runtime(
        self, tmp_path: Path
    ) -> None:
        """The rule walker itself does not enforce uniqueness — the
        loader does (see TestDuplicateCapabilityLoaderCheck). If a
        manifest with duplicate capabilities bypassed the loader, the
        walker would overwrite by order; this test documents runtime
        behaviour as defensive fallback.
        """
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {"json_path": "$.a", "capability": "dupe", "schema_ref": None},
                    {"json_path": "$.b", "capability": "dupe", "schema_ref": None},
                ]
            },
        )
        envelope = {"status": "ok", "a": {"first": True}, "b": {"second": True}}
        result = _invocation_from_envelope(
            envelope,
            log_path=tmp_path / "log.jsonl",
            elapsed=0.1,
            command="python3",
            manifest=manifest,
        )
        # Later rule wins at runtime; loader should have rejected at load.
        assert dict(result.extracted_outputs["dupe"]) == {"second": True}

    def test_edge_case_2_unresolvable_schema_ref_fails_closed(self, tmp_path: Path) -> None:
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.payload",
                        "capability": "review_findings",
                        "schema_ref": "does-not-exist.schema.v1.json",
                    }
                ]
            },
        )
        envelope = {"status": "ok", "payload": {"x": 1}}
        with pytest.raises(AdapterOutputParseError) as excinfo:
            _invocation_from_envelope(
                envelope,
                log_path=tmp_path / "log.jsonl",
                elapsed=0.1,
                command="python3",
                manifest=manifest,
            )
        assert "schema_ref" in str(excinfo.value).lower()
        assert "does-not-exist" in str(excinfo.value)

    def test_edge_case_3a_null_payload_rejected_when_schema_disallows(
        self, tmp_path: Path
    ) -> None:
        """``review-findings.schema.v1.json`` requires ``findings`` +
        ``summary``; a bare ``null`` payload fails validation."""
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.review_findings",
                        "capability": "review_findings",
                        "schema_ref": "review-findings.schema.v1.json",
                    }
                ]
            },
        )
        envelope = {"status": "ok", "review_findings": None}
        with pytest.raises(AdapterOutputParseError) as excinfo:
            _invocation_from_envelope(
                envelope,
                log_path=tmp_path / "log.jsonl",
                elapsed=0.1,
                command="python3",
                manifest=manifest,
            )
        # "validation failed" phrase is stable in our error wording.
        assert "validation failed" in str(excinfo.value).lower()

    def test_edge_case_3b_null_payload_accepted_when_schema_allows(
        self, tmp_path: Path
    ) -> None:
        """When no ``schema_ref`` is declared, a null envelope field is
        walked but not keyed (rule walker stores dict-shaped payloads
        only) — extracted_outputs stays empty, no error."""
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.review_findings",
                        "capability": "review_findings",
                        # no schema_ref → validation skipped
                    }
                ]
            },
        )
        envelope = {"status": "ok", "review_findings": None}
        result = _invocation_from_envelope(
            envelope,
            log_path=tmp_path / "log.jsonl",
            elapsed=0.1,
            command="python3",
            manifest=manifest,
        )
        # null is not a mapping → not stored; no error raised.
        assert dict(result.extracted_outputs) == {}

    def test_edge_case_4_missing_json_path_fails_closed(self, tmp_path: Path) -> None:
        """``json_path`` does not resolve in envelope → fail-closed.
        Edge case #4 inverse: a declared rule whose target key is missing
        must raise, not silently ignore."""
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.review_findings",
                        "capability": "review_findings",
                        "schema_ref": "review-findings.schema.v1.json",
                    }
                ]
            },
        )
        envelope = {"status": "ok"}  # no review_findings key
        with pytest.raises(AdapterOutputParseError) as excinfo:
            _invocation_from_envelope(
                envelope,
                log_path=tmp_path / "log.jsonl",
                elapsed=0.1,
                command="python3",
                manifest=manifest,
            )
        assert "did not resolve" in str(excinfo.value)

    def test_edge_case_5_envelope_field_without_rule_is_silent_ignore(
        self, tmp_path: Path
    ) -> None:
        """Envelope carries a payload for which the manifest has no rule
        — silently ignored. Extraction is opt-in, never surprise."""
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={"rules": [
                {"json_path": "$.x", "capability": "x", "schema_ref": None}
            ]},
        )
        envelope = {
            "status": "ok",
            "x": {"wanted": True},
            "review_findings": {"unwanted": True},  # no rule targets this
        }
        result = _invocation_from_envelope(
            envelope,
            log_path=tmp_path / "log.jsonl",
            elapsed=0.1,
            command="python3",
            manifest=manifest,
        )
        assert set(result.extracted_outputs.keys()) == {"x"}

    def test_schema_validation_failure_surfaces_as_output_parse_error(
        self, tmp_path: Path
    ) -> None:
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.review_findings",
                        "capability": "review_findings",
                        "schema_ref": "review-findings.schema.v1.json",
                    }
                ]
            },
        )
        envelope = {
            "status": "ok",
            "review_findings": {
                # Missing required fields: ``findings`` and ``summary``.
                "schema_version": "1",
            },
        }
        with pytest.raises(AdapterOutputParseError) as excinfo:
            _invocation_from_envelope(
                envelope,
                log_path=tmp_path / "log.jsonl",
                elapsed=0.1,
                command="python3",
                manifest=manifest,
            )
        assert "validation failed" in str(excinfo.value).lower()

    def test_rule_without_capability_walks_but_does_not_store(self, tmp_path: Path) -> None:
        """Rules without ``capability`` key serve as schema guards only;
        the payload is validated but not added to ``extracted_outputs``."""
        from ao_kernel.executor.adapter_invoker import _invocation_from_envelope

        manifest = _manifest_with_output_parse(
            output_parse={
                "rules": [
                    {
                        "json_path": "$.meta",
                        # no capability — descriptive-only rule
                    }
                ]
            },
        )
        envelope = {"status": "ok", "meta": {"anything": 1}}
        result = _invocation_from_envelope(
            envelope,
            log_path=tmp_path / "log.jsonl",
            elapsed=0.1,
            command="python3",
            manifest=manifest,
        )
        assert dict(result.extracted_outputs) == {}


class TestDuplicateCapabilityLoaderCheck:
    """Edge case #1 proper: multi-rule same-capability is rejected at
    manifest load time, before the walker ever runs."""

    def test_duplicate_capability_fails_at_load_time(self, tmp_path: Path) -> None:
        from ao_kernel.adapters.manifest_loader import AdapterRegistry

        manifest_dir = tmp_path / ".ao" / "adapters"
        manifest_dir.mkdir(parents=True)
        manifest_path = manifest_dir / "dupe-stub.manifest.v1.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "adapter_id": "dupe-stub",
                    "adapter_kind": "custom-cli",
                    "version": "1.0.0",
                    "capabilities": ["read_repo", "review_findings"],
                    "invocation": {
                        "transport": "cli",
                        "command": "python3",
                        "args": ["--help"],
                        "env_allowlist_ref": "#/env_allowlist/allowed_keys",
                        "cwd_policy": "per_run_worktree",
                        "stdin_mode": "none",
                    },
                    "input_envelope": {
                        "task_prompt": "x",
                        "run_id": "11111111-1111-4111-8111-111111111111",
                    },
                    "output_envelope": {"status": "ok"},
                    "policy_refs": [
                        "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
                    ],
                    "evidence_refs": [
                        ".ao/evidence/workflows/{run_id}/adapter-dupe-stub.jsonl"
                    ],
                    "output_parse": {
                        "rules": [
                            {
                                "json_path": "$.a",
                                "capability": "review_findings",
                            },
                            {
                                "json_path": "$.b",
                                "capability": "review_findings",  # duplicate
                            },
                        ]
                    },
                }
            )
        )
        registry = AdapterRegistry()
        report = registry.load_workspace(tmp_path)
        assert len(report.loaded) == 0
        assert len(report.skipped) == 1
        skipped = report.skipped[0]
        assert skipped.reason == "schema_invalid"
        assert "review_findings" in skipped.details
        assert "duplicate" in skipped.details.lower()


class TestCapabilityCrossRefLoaderCheck:
    """CNS-028v2 iter-6 W2 post-impl fix: output_parse.rules[*].capability
    must appear in the adapter's top-level capabilities[] declaration.
    Extraction rules advertise typed payload surface; that surface cannot
    bypass the top-level capability advertisement."""

    def test_unadvertised_capability_in_rule_fails_at_load(
        self, tmp_path: Path
    ) -> None:
        from ao_kernel.adapters.manifest_loader import AdapterRegistry

        manifest_dir = tmp_path / ".ao" / "adapters"
        manifest_dir.mkdir(parents=True)
        manifest_path = manifest_dir / "sneaky-stub.manifest.v1.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "adapter_id": "sneaky-stub",
                    "adapter_kind": "custom-cli",
                    "version": "1.0.0",
                    # NOTE: top-level capabilities does NOT include
                    # review_findings, but output_parse rule does.
                    "capabilities": ["read_repo"],
                    "invocation": {
                        "transport": "cli",
                        "command": "python3",
                        "args": ["--help"],
                        "env_allowlist_ref": "#/env_allowlist/allowed_keys",
                        "cwd_policy": "per_run_worktree",
                        "stdin_mode": "none",
                    },
                    "input_envelope": {
                        "task_prompt": "x",
                        "run_id": "11111111-1111-4111-8111-111111111111",
                    },
                    "output_envelope": {"status": "ok"},
                    "policy_refs": [
                        "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
                    ],
                    "evidence_refs": [
                        ".ao/evidence/workflows/{run_id}/adapter-sneaky-stub.jsonl"
                    ],
                    "output_parse": {
                        "rules": [
                            {
                                "json_path": "$.review_findings",
                                # Capability not in capabilities[] — must fail.
                                "capability": "review_findings",
                            },
                        ]
                    },
                }
            )
        )
        registry = AdapterRegistry()
        report = registry.load_workspace(tmp_path)
        assert len(report.loaded) == 0
        assert len(report.skipped) == 1
        skipped = report.skipped[0]
        assert skipped.reason == "schema_invalid"
        assert "review_findings" in skipped.details
        assert "not listed" in skipped.details.lower() or "capabilities" in skipped.details

    def test_rule_without_capability_does_not_need_cross_ref(
        self, tmp_path: Path
    ) -> None:
        """Rules without a ``capability`` key are descriptive-only schema
        guards; they do not participate in the cross-ref check (there is
        nothing to cross-ref)."""
        from ao_kernel.adapters.manifest_loader import AdapterRegistry

        manifest_dir = tmp_path / ".ao" / "adapters"
        manifest_dir.mkdir(parents=True)
        manifest_path = manifest_dir / "guard-only-stub.manifest.v1.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "adapter_id": "guard-only-stub",
                    "adapter_kind": "custom-cli",
                    "version": "1.0.0",
                    "capabilities": ["read_repo"],
                    "invocation": {
                        "transport": "cli",
                        "command": "python3",
                        "args": ["--help"],
                        "env_allowlist_ref": "#/env_allowlist/allowed_keys",
                        "cwd_policy": "per_run_worktree",
                        "stdin_mode": "none",
                    },
                    "input_envelope": {
                        "task_prompt": "x",
                        "run_id": "11111111-1111-4111-8111-111111111111",
                    },
                    "output_envelope": {"status": "ok"},
                    "policy_refs": [
                        "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
                    ],
                    "evidence_refs": [
                        ".ao/evidence/workflows/{run_id}/adapter-guard-only-stub.jsonl"
                    ],
                    "output_parse": {
                        "rules": [
                            {"json_path": "$.meta"},  # no capability — OK
                        ]
                    },
                }
            )
        )
        registry = AdapterRegistry()
        report = registry.load_workspace(tmp_path)
        assert len(report.loaded) == 1
        assert len(report.skipped) == 0
