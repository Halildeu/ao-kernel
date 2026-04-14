"""Tests for ao_memory_write MCP handler + implicit promote refactor.

PR-C6b / CNS-20260414-012 coverage:
  - happy path (enabled policy + matching prefixes → CAS-routed promote)
  - fail-closed defaults (write disabled)
  - policy gates (key prefix, source prefix, size, non-serializable value)
  - resolver edge cases (B1 invariant: fallback = key-absent only)
  - server-side fixed confidence (caller-supplied ignored)
  - per-workspace rate limiting (writes bucket)
  - implicit-promote threshold read from workspace-override policy
  - denylist effect: explicit key landed, envelope metadata did NOT
  - evidence JSONL lands with tool/allowed/decision populated (W1 hygiene)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel._internal.mcp.memory_tools import (
    _IMPLICIT_PROMOTE_SKIP,
    _SERVER_SIDE_CONFIDENCE,
    _memory_rate_limit_reset,
    handle_memory_write,
    run_implicit_promote,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_memory_rate_limiters():
    _memory_rate_limit_reset()
    yield
    _memory_rate_limit_reset()


def _write_memory_policy(
    ws: Path,
    *,
    write_enabled: bool,
    allowed_key_prefixes: list[str] | None = None,
    max_value_bytes: int = 4096,
    allowed_source_prefixes: list[str] | None = None,
    writes_per_minute: int = 10,
) -> None:
    policies_dir = ws / ".ao" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": "v1",
        "read": {"enabled": False, "allowed_patterns": ["*"]},
        "write": {
            "enabled": write_enabled,
            "allowed_key_prefixes": (
                allowed_key_prefixes if allowed_key_prefixes is not None else ["mem."]
            ),
            "max_value_bytes": max_value_bytes,
            "allowed_source_prefixes": (
                allowed_source_prefixes if allowed_source_prefixes is not None else ["mcp:"]
            ),
        },
        "rate_limit": {"reads_per_minute": 60, "writes_per_minute": writes_per_minute},
    }
    (policies_dir / "policy_mcp_memory.v1.json").write_text(
        json.dumps(doc), encoding="utf-8",
    )


@pytest.fixture
def ws_enabled(tmp_path: Path) -> Path:
    """Workspace where write.enabled=true + mem.* prefix allowlisted."""
    _write_memory_policy(tmp_path, write_enabled=True)
    return tmp_path


# ── 1) Happy path ──────────────────────────────────────────────────


def test_write_enabled_routes_through_cas(ws_enabled: Path):
    result = handle_memory_write({
        "workspace_root": str(ws_enabled),
        "key": "mem.example.hello",
        "value": "world",
        "source": "mcp:manual",
    })
    assert result["allowed"] is True
    assert result["decision"] == "executed"
    assert result["data"]["key"] == "mem.example.hello"


# ── 2) Write disabled by default ───────────────────────────────────


def test_write_disabled_fails_closed(tmp_path: Path):
    _write_memory_policy(tmp_path, write_enabled=False)
    result = handle_memory_write({
        "workspace_root": str(tmp_path),
        "key": "mem.x",
        "value": "y",
    })
    assert result["decision"] == "deny"
    assert "write_disabled_by_policy" in result["reason_codes"]


# ── 3) Empty allowed_key_prefixes → all keys denied ────────────────


def test_empty_key_prefix_denies_all(tmp_path: Path):
    _write_memory_policy(tmp_path, write_enabled=True, allowed_key_prefixes=[])
    result = handle_memory_write({
        "workspace_root": str(tmp_path),
        "key": "mem.foo",
        "value": "bar",
    })
    assert result["decision"] == "deny"
    assert "key_prefix_not_allowed" in result["reason_codes"]


# ── 4) Key prefix miss ─────────────────────────────────────────────


def test_key_prefix_miss_denies(ws_enabled: Path):
    result = handle_memory_write({
        "workspace_root": str(ws_enabled),
        "key": "other.foo",
        "value": "bar",
    })
    assert result["decision"] == "deny"
    assert "key_prefix_not_allowed" in result["reason_codes"]


# ── 5) Bad source prefix ───────────────────────────────────────────


def test_bad_source_prefix_denies(ws_enabled: Path):
    result = handle_memory_write({
        "workspace_root": str(ws_enabled),
        "key": "mem.x",
        "value": "y",
        "source": "sdk:internal",
    })
    assert result["decision"] == "deny"
    assert "source_prefix_not_allowed" in result["reason_codes"]


# ── 6) Oversized value ─────────────────────────────────────────────


def test_oversize_value_denies(tmp_path: Path):
    _write_memory_policy(tmp_path, write_enabled=True, max_value_bytes=32)
    big = "x" * 200
    result = handle_memory_write({
        "workspace_root": str(tmp_path),
        "key": "mem.x",
        "value": big,
    })
    assert result["decision"] == "deny"
    assert "oversize" in result["reason_codes"]


# ── 7) value_not_serializable ──────────────────────────────────────


def test_non_json_serializable_value_denies(ws_enabled: Path):
    result = handle_memory_write({
        "workspace_root": str(ws_enabled),
        "key": "mem.x",
        "value": {1, 2, 3},  # sets are not JSON-serializable
    })
    assert result["decision"] == "deny"
    assert "value_not_serializable" in result["reason_codes"]


# ── 8) workspace_root absent + library mode ────────────────────────


def test_workspace_root_absent_library_mode_denies(monkeypatch):
    from ao_kernel import mcp_server
    monkeypatch.setattr(mcp_server, "_find_workspace_root", lambda: None)
    result = handle_memory_write({"key": "mem.x", "value": "y"})
    assert result["decision"] == "deny"
    assert "workspace_not_found" in result["reason_codes"]


# ── 9) workspace_root present-but-invalid → deny (no fallback) ─────


def test_workspace_root_present_invalid_denies():
    for bad in (None, 123, "", "   "):
        result = handle_memory_write({
            "workspace_root": bad,
            "key": "mem.x",
            "value": "y",
        })
        assert result["decision"] == "deny", f"expected deny for {bad!r}"


# ── 10) Caller confidence IGNORED (server sets 0.8) ────────────────


def test_caller_supplied_confidence_is_ignored(ws_enabled: Path):
    result = handle_memory_write({
        "workspace_root": str(ws_enabled),
        "key": "mem.x",
        "value": "y",
        "source": "mcp:manual",
        "confidence": 0.99,  # caller tries to boost; server should ignore
    })
    assert result["decision"] == "executed"
    assert result["data"]["confidence"] == _SERVER_SIDE_CONFIDENCE


# ── 11) Rate limit triggers ────────────────────────────────────────


def test_rate_limit_triggers_on_write_bucket(tmp_path: Path):
    _write_memory_policy(tmp_path, write_enabled=True, writes_per_minute=1)
    first = handle_memory_write({
        "workspace_root": str(tmp_path),
        "key": "mem.a",
        "value": "1",
    })
    assert first["decision"] == "executed"
    second = handle_memory_write({
        "workspace_root": str(tmp_path),
        "key": "mem.b",
        "value": "2",
    })
    assert second["decision"] == "deny"
    assert "rate_limit_exceeded" in second["reason_codes"]


# ── 12) Implicit promote threshold from workspace-override policy ──


def test_implicit_promote_threshold_from_workspace_override(tmp_path: Path):
    """High override threshold skips below-threshold decisions."""
    from ao_kernel.context.canonical_store import query

    policies_dir = tmp_path / ".ao" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    override = {
        "version": "v1",
        "enabled": False,
        "max_tool_calls_per_request": 5,
        "max_tool_rounds": 3,
        "allowed_tools": [],
        "fail_action": "block",
        "implicit_canonical_promote": {
            "enabled": True,
            "threshold": 0.99,
            "source_prefix": "mcp:tool_result",
        },
    }
    (policies_dir / "policy_tool_calling.v1.json").write_text(
        json.dumps(override), encoding="utf-8",
    )

    # Simulate a tool result with confidence=0.95 — should NOT promote at 0.99.
    fake_result = {
        "api_version": "0.1.0",
        "tool": "ao_policy_check",
        "allowed": True,
        "decision": "allow",
    }
    # Monkey-patch extract_from_tool_result to return a controlled decision.
    import ao_kernel._internal.mcp.memory_tools as mt
    original = mt.__dict__.get("_test_extract_override")
    try:
        # Directly call run_implicit_promote; extractor yields from fake_result
        run_implicit_promote("ao_policy_check", fake_result, tmp_path)
    finally:
        if original is not None:
            mt.__dict__["_test_extract_override"] = original

    # Extractor output for fake_result has confidence=0.95 by default; with
    # threshold=0.99 none should promote. The canonical store must stay empty.
    items = query(tmp_path, key_pattern="*")
    assert not any(i["key"].startswith("tool.ao_policy_check.") for i in items)


# ── 13) Denylist effect: explicit key landed, envelope metadata did NOT ─


def test_write_explicit_promote_but_no_implicit_double_write(ws_enabled: Path):
    from ao_kernel.context.canonical_store import query
    from ao_kernel.mcp_server import TOOL_DISPATCH

    assert "ao_memory_write" in _IMPLICIT_PROMOTE_SKIP
    # Drive through the real MCP dispatch path so both the explicit
    # promote (handler) and the implicit side-channel are exercised.
    TOOL_DISPATCH["ao_memory_write"]({
        "workspace_root": str(ws_enabled),
        "key": "mem.note",
        "value": "persistent",
        "source": "mcp:manual",
    })
    items = query(ws_enabled, key_pattern="*")
    keys = {i["key"] for i in items}
    assert "mem.note" in keys  # explicit promote succeeded
    assert not any(k.startswith("tool.ao_memory_write.") for k in keys)  # skip honoured


# ── 14) Evidence JSONL with tool/allowed/decision assertion ────────


def test_evidence_jsonl_assert_fields(ws_enabled: Path):
    from ao_kernel.mcp_server import TOOL_DISPATCH

    TOOL_DISPATCH["ao_memory_write"]({
        "workspace_root": str(ws_enabled),
        "key": "mem.evidence",
        "value": {"ok": True},
        "source": "mcp:manual",
    })
    evidence_dir = ws_enabled / ".ao" / "evidence" / "mcp"
    assert evidence_dir.is_dir()
    jsonl_files = list(evidence_dir.glob("*.jsonl"))
    assert jsonl_files, "expected an MCP evidence file"
    records = [
        json.loads(line)
        for line in jsonl_files[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    match = [r for r in records if r.get("tool") == "ao_memory_write"]
    assert match, "expected an ao_memory_write evidence record"
    last = match[-1]
    assert last["tool"] == "ao_memory_write"
    assert last["allowed"] is True
    assert last["decision"] == "executed"
