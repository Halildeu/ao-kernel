"""Tests for the ao_memory_read MCP handler (PR-C6a / CNS-20260414-011).

Covers:
  - happy path (enabled policy + matching pattern → items)
  - fail-closed defaults (read disabled)
  - resolver edge cases (B1 invariant: fallback = key-absent only)
  - pattern allowlist (W1-iter2 / fnmatch direction)
  - per-workspace rate limiting (W1-iter1 isolation)
  - implicit-promote denylist (B2)
  - evidence JSONL append with param-aware workspace (B1)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel._internal.mcp.memory_tools import (
    _IMPLICIT_PROMOTE_SKIP,
    _memory_rate_limit_reset,
    handle_memory_read,
)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_memory_rate_limiters():
    _memory_rate_limit_reset()
    yield
    _memory_rate_limit_reset()


def _write_policy(
    ws: Path,
    *,
    read_enabled: bool = True,
    allowed_patterns: list[str] | None = None,
    reads_per_minute: int = 60,
    writes_per_minute: int = 10,
) -> None:
    policies_dir = ws / ".ao" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": "v1",
        "read": {
            "enabled": read_enabled,
            "allowed_patterns": allowed_patterns or ["*"],
        },
        "write": {
            "enabled": False,
            "allowed_key_prefixes": [],
            "max_value_bytes": 4096,
            "allowed_source_prefixes": ["mcp:"],
        },
        "rate_limit": {
            "reads_per_minute": reads_per_minute,
            "writes_per_minute": writes_per_minute,
        },
    }
    (policies_dir / "policy_mcp_memory.v1.json").write_text(
        json.dumps(doc), encoding="utf-8",
    )


@pytest.fixture
def ws_enabled(tmp_path: Path) -> Path:
    """Workspace with memory.read.enabled=true + allowed_patterns=['*']."""
    _write_policy(tmp_path, read_enabled=True)
    return tmp_path


# ── 1) Happy path ──────────────────────────────────────────────────


def test_read_enabled_returns_items_envelope(ws_enabled: Path):
    result = handle_memory_read(
        {"workspace_root": str(ws_enabled), "pattern": "*"},
    )
    assert result["allowed"] is True
    assert result["decision"] == "executed"
    assert isinstance(result["data"]["items"], list)
    assert result["data"]["count"] == len(result["data"]["items"])
    assert result["tool"] == "ao_memory_read"


# ── 2) Read disabled by default ────────────────────────────────────


def test_read_disabled_by_default_fails_closed(tmp_path: Path):
    _write_policy(tmp_path, read_enabled=False)
    result = handle_memory_read({"workspace_root": str(tmp_path)})
    assert result["allowed"] is False
    assert result["decision"] == "deny"
    assert "read_disabled_by_policy" in result["reason_codes"]


# ── 3) workspace_root absent → fallback (library mode → deny) ──────


def test_workspace_root_absent_library_mode_denies(monkeypatch):
    from ao_kernel import mcp_server
    monkeypatch.setattr(mcp_server, "_find_workspace_root", lambda: None)
    result = handle_memory_read({})
    assert result["decision"] == "deny"
    assert "workspace_not_found" in result["reason_codes"]


# ── 4) workspace_root key present but None → deny (fallback NOT used) ─


def test_workspace_root_none_value_explicit_deny():
    result = handle_memory_read({"workspace_root": None})
    assert result["decision"] == "deny"
    assert "workspace_not_found" in result["reason_codes"]


# ── 5) workspace_root key present but int → deny ───────────────────


def test_workspace_root_int_value_explicit_deny():
    result = handle_memory_read({"workspace_root": 123})
    assert result["decision"] == "deny"
    assert "workspace_not_found" in result["reason_codes"]


# ── 6) workspace_root key present but empty → deny ─────────────────


def test_workspace_root_empty_string_explicit_deny():
    result = handle_memory_read({"workspace_root": "   "})
    assert result["decision"] == "deny"


# ── 7) workspace_root points to nonexistent path → deny ────────────


def test_workspace_root_nonexistent_explicit_deny(tmp_path: Path):
    bogus = tmp_path / "does_not_exist"
    result = handle_memory_read({"workspace_root": str(bogus)})
    assert result["decision"] == "deny"


# ── 8) workspace_root points at .ao suffix → parent normalized ─────


def test_workspace_root_ao_suffix_is_normalized_to_parent(ws_enabled: Path):
    result = handle_memory_read(
        {"workspace_root": str(ws_enabled / ".ao")},
    )
    assert result["decision"] == "executed"


# ── 9) Pattern not in allowed_patterns → deny ──────────────────────


def test_pattern_not_allowed_denies(tmp_path: Path):
    _write_policy(tmp_path, read_enabled=True, allowed_patterns=["runtime.*"])
    result = handle_memory_read(
        {"workspace_root": str(tmp_path), "pattern": "architecture.*"},
    )
    assert result["decision"] == "deny"
    assert "pattern_not_allowed" in result["reason_codes"]


# ── 10) Rate limit triggers after the bucket drains ────────────────


def test_rate_limit_triggers_when_budget_exhausted(tmp_path: Path):
    _write_policy(tmp_path, read_enabled=True, reads_per_minute=1)
    first = handle_memory_read({"workspace_root": str(tmp_path)})
    assert first["decision"] == "executed"
    second = handle_memory_read({"workspace_root": str(tmp_path)})
    assert second["decision"] == "deny"
    assert "rate_limit_exceeded" in second["reason_codes"]


# ── 11) Rate limit isolated per workspace (W1-iter1) ───────────────


def test_rate_limit_isolated_per_workspace(tmp_path: Path):
    ws_a = tmp_path / "ws_a"
    ws_b = tmp_path / "ws_b"
    ws_a.mkdir()
    ws_b.mkdir()
    _write_policy(ws_a, read_enabled=True, reads_per_minute=1)
    _write_policy(ws_b, read_enabled=True, reads_per_minute=1)

    # Drain ws_a's bucket
    handle_memory_read({"workspace_root": str(ws_a)})
    drained = handle_memory_read({"workspace_root": str(ws_a)})
    assert drained["decision"] == "deny"

    # ws_b should still have its own token
    other = handle_memory_read({"workspace_root": str(ws_b)})
    assert other["decision"] == "executed"


# ── 12) Implicit-promote denylist (B2) ─────────────────────────────


def test_ao_memory_read_is_exempt_from_implicit_promotion():
    assert "ao_memory_read" in _IMPLICIT_PROMOTE_SKIP


# ── 13) Evidence JSONL append with param-aware workspace (B1) ──────


def test_evidence_jsonl_lands_in_param_workspace(ws_enabled: Path):
    from ao_kernel.mcp_server import TOOL_DISPATCH

    wrapped = TOOL_DISPATCH["ao_memory_read"]
    wrapped({"workspace_root": str(ws_enabled), "pattern": "*"})

    evidence_dir = ws_enabled / ".ao" / "evidence" / "mcp"
    assert evidence_dir.is_dir()
    jsonl_files = list(evidence_dir.glob("*.jsonl"))
    assert jsonl_files, "Expected an MCP evidence JSONL file"
    lines = jsonl_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert lines, "Expected at least one evidence record"
    recorded = [json.loads(line) for line in lines]
    assert any(rec.get("tool") == "ao_memory_read" for rec in recorded)
