"""Integration tests for MCP evidence emission (B4).

Verifies that dispatching a tool through TOOL_DISPATCH writes an event
to the workspace evidence log, while direct handler imports stay silent
(tests + SDK callers don't pollute evidence).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.mcp_server import (
    TOOL_DISPATCH,
    handle_workspace_status,
    handle_policy_check,
)


def _init_workspace(path: Path) -> Path:
    (path / ".ao").mkdir()
    (path / ".ao" / "workspace.json").write_text(
        json.dumps({"version": "v2", "kind": "ao-kernel"})
    )
    return path


def _log_lines(workspace: Path) -> list[dict]:
    mcp_dir = workspace / ".ao" / "evidence" / "mcp"
    if not mcp_dir.is_dir():
        return []
    files = list(mcp_dir.glob("*.jsonl"))
    if not files:
        return []
    return [json.loads(line) for line in files[0].read_text().splitlines()]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = _init_workspace(tmp_path)
    monkeypatch.chdir(ws)
    return ws


class TestDispatchEmitsEvidence:
    def test_workspace_status_logs_event(self, workspace):
        dispatched = TOOL_DISPATCH["ao_workspace_status"]
        envelope = dispatched({"workspace_root": str(workspace)})
        assert envelope["api_version"] == "0.1.0"
        events = _log_lines(workspace)
        assert len(events) == 1
        assert events[0]["tool"] == "ao_workspace_status"
        assert events[0]["allowed"] is True
        assert "duration_ms" in events[0]

    def test_policy_check_logs_deny_envelope(self, workspace):
        dispatched = TOOL_DISPATCH["ao_policy_check"]
        envelope = dispatched({})  # missing policy_name -> deny
        assert envelope["allowed"] is False
        events = _log_lines(workspace)
        assert len(events) == 1
        assert events[0]["tool"] == "ao_policy_check"
        assert events[0]["decision"] == "deny"
        assert "MISSING_POLICY_NAME" in events[0]["reason_codes"]


class TestDirectHandlerStaysSilent:
    """Direct imports must NOT emit evidence — keeps unit tests clean."""

    def test_direct_handle_policy_check_does_not_write(self, workspace):
        handle_policy_check({})
        assert _log_lines(workspace) == []

    def test_direct_handle_workspace_status_does_not_write(self, workspace):
        handle_workspace_status({"workspace_root": str(workspace)})
        assert _log_lines(workspace) == []


class TestParamsRedactedInEvent:
    def test_params_shape_excludes_api_key_value(self, workspace):
        dispatched = TOOL_DISPATCH["ao_policy_check"]
        # Policy check will deny because the action is invalid; what we
        # care about here is that the api_key VALUE never lands in the log.
        # Construct fake token at runtime to keep the source file free of
        # pre-commit secret patterns.
        fake_key = "sk-" + ("e" * 20)
        dispatched({
            "policy_name": "policy_autonomy.v1.json",
            "action": {"intent": "x", "mode": "autonomous"},
            "workspace_root": str(workspace),
            "api_key": fake_key,
        })
        log_dir = workspace / ".ao" / "evidence" / "mcp"
        files = list(log_dir.glob("*.jsonl"))
        # Even the file should not contain the raw key string.
        assert files, "dispatch should have written a log line"
        text = files[0].read_text()
        assert fake_key not in text
        events = [json.loads(line) for line in text.splitlines()]
        # params_shape records types, not values.
        shape = events[0]["params_shape"]
        assert shape["api_key"] == "str"
        assert shape["policy_name"] == "str"
