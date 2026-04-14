# PR-C6a — Memory Read MCP Tool — Implementation Plan (2026-04-14)

## TL;DR

`ao_memory_read` MCP tool'u — read-only, fail-closed, policy-gated, param-aware, rate-limited. CNS-20260414-011 (3 iter adversarial consensus, `ready_for_impl=true`) onayı ile implement edilir.

- **Scope:** ~230 LOC + docs (aynı PR'da batch)
- **Base:** `origin/main` @ `4e7fe34`
- **Test baseline:** 922 → hedef ~935 (13 yeni test)
- **Release:** v3.0.0 (C6b sonrası bundle)
- **Consensus doc:** `.ao/consultations/CNS-20260414-011.consensus.md`

---

## Scope Özeti

### Yeni Dosyalar (5)

| Dosya | Amaç | Yaklaşık LOC |
|---|---|---|
| `ao_kernel/_internal/mcp/__init__.py` | Package marker | 1 |
| `ao_kernel/_internal/mcp/memory_tools.py` | Tüm C6a helper'ları + handler | ~200 |
| `ao_kernel/defaults/policies/policy_mcp_memory.v1.json` | Policy (read + write + rate_limit) | ~25 |
| `ao_kernel/defaults/schemas/policy-mcp-memory.schema.v1.json` | JSON Schema | ~60 |
| `tests/test_mcp_memory_read.py` | 13 test | ~250 |

### Değişen Dosyalar (6)

| Dosya | Değişiklik | Nedeni |
|---|---|---|
| `ao_kernel/mcp_server.py` | Import + TOOL_DEFINITIONS + TOOL_DISPATCH entry + `_with_evidence` param-aware + `call_tool` denylist | Tool register + B1/B2 |
| `CLAUDE.md` | §2 evidence invariant güncelleme + §5 tool count | B3 scope pivot + W2 batch |
| `README.md` | MCP tool listesi + Evidence trail matrisi | W2 batch |
| `ao_kernel/_internal/evidence/mcp_event_log.py` | Module docstring güncelleme | B3 scope pivot |
| `.claude/plans/SESSION-HANDOFF-TRANCHE-C-MID.md` | Technical Debt satırı (manifest → Tranş D) | B3 scope pivot |
| `tests/test_mcp_server.py` | `len(TOOL_DEFINITIONS) == 5` → `== 6` | W2 batch |

**Toplam LOC bütçesi:** ~536 LOC (dosya başı < 800 bütçesine hiçbiri yaklaşmıyor)

---

## Dosya Dosya Detay

### 1. `ao_kernel/_internal/mcp/__init__.py`

```python
"""Private package for MCP server helper modules.

These modules are implementation details of `ao_kernel.mcp_server`
and are NOT part of the public API. Do not import from outside the
package.
"""
```

### 2. `ao_kernel/_internal/mcp/memory_tools.py`

Module structure:

```python
"""MCP memory tool helpers (ao_memory_read + ao_memory_write).

Private sub-module of `ao_kernel.mcp_server`. Not part of public API.

Includes:
  - _resolve_workspace_for_call(): param-aware workspace resolver
    (strict scope: only memory tools; see CNS-20260414-011 W1)
  - _IMPLICIT_PROMOTE_SKIP: tools exempted from implicit canonical promotion
  - _memory_rate_limiter_for(): per-(workspace, op) rate limiter bucket
  - _load_memory_policy_validated(): schema-validated policy loader
  - handle_memory_read(): C6a handler
  - (handle_memory_write() lands in C6b)
"""

from __future__ import annotations

import fnmatch as _fn
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ao_kernel._internal.prj_kernel_api.rate_limiter import TokenBucketRateLimiter


# ── Module-level state ──────────────────────────────────────────────

_IMPLICIT_PROMOTE_SKIP: set[str] = {"ao_memory_read"}

_memory_rate_limiters: dict[tuple[str, str], TokenBucketRateLimiter] = {}
_memory_rl_lock = threading.Lock()


# ── Param-aware workspace resolver ──────────────────────────────────

def _resolve_workspace_for_call(
    params: dict[str, Any] | None,
    *,
    fallback: Callable[[], Path | None] | None = None,
) -> Path | None:
    """Param-aware workspace resolver for MCP memory tools.

    Fallback policy: ONLY when `workspace_root` key is absent.
    Present-but-invalid → None (explicit deny path, NOT fallback).

    Validates:
      - type check (must be str)
      - non-empty after .strip()
      - resolve(strict=False) for symlink/relative normalization
      - .ao suffix → parent (project root per CLAUDE.md §3)
      - candidate must be dir AND contain .ao/ subdirectory

    Scope (CNS-20260414-011 W1): used ONLY by memory tool paths +
    their evidence/promote hooks. NOT applied to other MCP tools.
    """
    if not isinstance(params, dict):
        return fallback() if fallback else None
    if "workspace_root" not in params:
        return fallback() if fallback else None
    raw = params["workspace_root"]
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        candidate = Path(raw).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if candidate.name == ".ao":
        candidate = candidate.parent
    if not candidate.is_dir() or not (candidate / ".ao").is_dir():
        return None
    return candidate


# ── Rate limit helpers ──────────────────────────────────────────────

def _memory_rate_limiter_for(
    ws: Path,
    op: str,
    *,
    rpm: int,
) -> TokenBucketRateLimiter:
    """Get or create rate limiter for (workspace, operation) key."""
    key = (str(ws), op)
    with _memory_rl_lock:
        if key not in _memory_rate_limiters:
            _memory_rate_limiters[key] = TokenBucketRateLimiter(rps=rpm / 60.0)
        return _memory_rate_limiters[key]


def _memory_rate_limit_reset() -> None:
    """Test helper — separate from provider rate limiter reset_all()."""
    with _memory_rl_lock:
        _memory_rate_limiters.clear()


# ── Validated policy loader ─────────────────────────────────────────

def _load_memory_policy_validated(ws: Path | None) -> dict[str, Any]:
    """Load policy_mcp_memory.v1.json with schema validation.

    Workspace override: `ws/.ao/policies/policy_mcp_memory.v1.json`
    Default fallback: bundled `ao_kernel/defaults/policies/...`
    Schema: `ao_kernel/defaults/schemas/policy-mcp-memory.schema.v1.json`
    """
    from ao_kernel.config import load_default, load_with_override

    # policy_workspace bridge (CNS-011 accepted)
    policy_workspace = ws / ".ao" if (ws and (ws / ".ao").is_dir()) else ws
    policy = load_with_override(
        "policies", "policy_mcp_memory.v1.json",
        workspace=policy_workspace,
    )
    schema = load_default("schemas", "policy-mcp-memory.schema.v1.json")

    # jsonschema is the only core dep; validation always available
    import jsonschema
    jsonschema.validate(policy, schema)
    return policy


# ── Handler: ao_memory_read ─────────────────────────────────────────

def handle_memory_read(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for ao_memory_read tool.

    Policy-gated, param-aware, rate-limited, read-only canonical/memory query.
    """
    from ao_kernel.context.agent_coordination import query_memory

    # Lazy import to avoid cycle; mcp_server._find_workspace_root() fallback
    from ao_kernel.mcp_server import _find_workspace_root

    tool = "ao_memory_read"
    ws = _resolve_workspace_for_call(params, fallback=_find_workspace_root)
    if ws is None:
        return _deny(tool, "workspace_not_found")

    # Policy load + validate (fail-closed)
    try:
        policy = _load_memory_policy_validated(ws)
    except Exception as exc:  # noqa: BLE001 — fail-closed on any load/validate error
        return _deny(tool, "policy_load_error", error=str(exc))

    read_cfg = policy.get("read", {})
    if not bool(read_cfg.get("enabled", False)):
        return _deny(tool, "read_disabled_by_policy")

    # Pattern allowlist check
    user_pattern = params.get("pattern", "*")
    if not isinstance(user_pattern, str) or not user_pattern.strip():
        return _deny(tool, "invalid_pattern")
    allowed_patterns = read_cfg.get("allowed_patterns", ["*"])
    if not any(_fn.fnmatchcase(user_pattern, p) for p in allowed_patterns):
        return _deny(tool, "pattern_not_allowed")

    # Rate limit check — (ws, "read") scope
    rate_cfg = policy.get("rate_limit", {})
    rpm = int(rate_cfg.get("reads_per_minute", 60))
    limiter = _memory_rate_limiter_for(ws, "read", rpm=rpm)
    if not limiter.try_acquire():
        return _deny(tool, "rate_limit_exceeded")

    # Delegate to SDK hook
    category = params.get("category")
    if category is not None and not isinstance(category, str):
        return _deny(tool, "invalid_category")
    try:
        items = query_memory(
            workspace_root=ws,
            key_pattern=user_pattern,
            category=category,
        )
    except Exception as exc:  # noqa: BLE001 — runtime failure semantic
        return _error(tool, f"query_failure: {exc}")

    return {
        "api_version": "0.1.0",
        "tool": tool,
        "allowed": True,
        "decision": "executed",
        "reason_codes": [],
        "data": {"items": items, "count": len(items)},
        "error": None,
    }


# ── Envelope helpers (deny/error) ───────────────────────────────────

def _deny(tool: str, reason: str, *, error: str | None = None) -> dict[str, Any]:
    return {
        "api_version": "0.1.0",
        "tool": tool,
        "allowed": False,
        "decision": "deny",
        "reason_codes": [reason],
        "data": None,
        "error": error,
    }


def _error(tool: str, message: str) -> dict[str, Any]:
    return {
        "api_version": "0.1.0",
        "tool": tool,
        "allowed": True,
        "decision": "error",
        "reason_codes": ["runtime_failure"],
        "data": None,
        "error": message,
    }
```

**Tool registration:** `mcp_server.py` içinde import edilip `TOOL_DEFINITIONS` ve `TOOL_DISPATCH`'e eklenir.

### 3. `ao_kernel/defaults/policies/policy_mcp_memory.v1.json`

```json
{
  "$schema": "../schemas/policy-mcp-memory.schema.v1.json",
  "version": "v1",
  "_comment": "Fail-closed by default. Simple prefix-glob patterns recommended for allowed_patterns; pattern-on-pattern is an approximate subset check, not a proof.",
  "read": {
    "enabled": false,
    "allowed_patterns": ["*"]
  },
  "write": {
    "enabled": false,
    "allowed_key_prefixes": [],
    "max_value_bytes": 4096,
    "allowed_source_prefixes": ["mcp:"]
  },
  "rate_limit": {
    "reads_per_minute": 60,
    "writes_per_minute": 10
  }
}
```

### 4. `ao_kernel/defaults/schemas/policy-mcp-memory.schema.v1.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:ao:policy-mcp-memory:v1",
  "title": "AO Kernel MCP Memory Policy v1",
  "type": "object",
  "required": ["version", "read", "write", "rate_limit"],
  "properties": {
    "version": {"const": "v1"},
    "read": {
      "type": "object",
      "required": ["enabled"],
      "properties": {
        "enabled": {"type": "boolean"},
        "allowed_patterns": {
          "type": "array",
          "items": {"type": "string", "minLength": 1}
        }
      },
      "additionalProperties": false
    },
    "write": {
      "type": "object",
      "required": ["enabled"],
      "properties": {
        "enabled": {"type": "boolean"},
        "allowed_key_prefixes": {"type": "array", "items": {"type": "string"}},
        "max_value_bytes": {"type": "integer", "minimum": 0},
        "allowed_source_prefixes": {"type": "array", "items": {"type": "string"}}
      },
      "additionalProperties": false
    },
    "rate_limit": {
      "type": "object",
      "properties": {
        "reads_per_minute": {"type": "integer", "minimum": 1},
        "writes_per_minute": {"type": "integer", "minimum": 1}
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": true
}
```

### 5. `tests/test_mcp_memory_read.py`

13 test, 5 test grubu:

```python
"""Tests for ao_memory_read MCP handler (PR-C6a)."""
import json
from pathlib import Path

import pytest

from ao_kernel._internal.mcp.memory_tools import (
    handle_memory_read,
    _memory_rate_limit_reset,
    _resolve_workspace_for_call,
)


@pytest.fixture(autouse=True)
def reset_rl():
    _memory_rate_limit_reset()
    yield
    _memory_rate_limit_reset()


@pytest.fixture
def ws_enabled(tmp_path: Path) -> Path:
    """Workspace with memory.read.enabled=true override."""
    (tmp_path / ".ao" / "policies").mkdir(parents=True)
    (tmp_path / ".ao" / "policies" / "policy_mcp_memory.v1.json").write_text(json.dumps({
        "version": "v1",
        "read": {"enabled": True, "allowed_patterns": ["*"]},
        "write": {"enabled": False, "allowed_key_prefixes": [], "max_value_bytes": 4096, "allowed_source_prefixes": ["mcp:"]},
        "rate_limit": {"reads_per_minute": 60, "writes_per_minute": 10},
    }))
    return tmp_path


# ── 1) Happy path ──────────────────────────────────────────────────
def test_read_enabled_returns_items(ws_enabled: Path):
    result = handle_memory_read({"workspace_root": str(ws_enabled), "pattern": "*"})
    assert result["allowed"] is True
    assert result["decision"] == "executed"
    assert "items" in result["data"]
    assert "count" in result["data"]


# ── 2) Read disabled by policy ─────────────────────────────────────
def test_read_disabled_default(tmp_path: Path):
    (tmp_path / ".ao").mkdir()
    result = handle_memory_read({"workspace_root": str(tmp_path)})
    assert result["allowed"] is False
    assert "read_disabled_by_policy" in result["reason_codes"]


# ── 3-8) Resolver edge cases (B1 doğrulaması) ──────────────────────
def test_workspace_root_absent_library_mode(tmp_path, monkeypatch):
    # No _find_workspace_root found (library mode)
    monkeypatch.setattr("ao_kernel.mcp_server._find_workspace_root", lambda: None)
    result = handle_memory_read({})
    assert result["decision"] == "deny"
    assert "workspace_not_found" in result["reason_codes"]


def test_workspace_root_none_value(tmp_path):
    # KEY PRESENT, value None → deny (fallback YOK)
    result = handle_memory_read({"workspace_root": None})
    assert result["decision"] == "deny"


def test_workspace_root_int_value(tmp_path):
    result = handle_memory_read({"workspace_root": 123})
    assert result["decision"] == "deny"


def test_workspace_root_empty_string(tmp_path):
    result = handle_memory_read({"workspace_root": ""})
    assert result["decision"] == "deny"


def test_workspace_root_nonexistent(tmp_path):
    result = handle_memory_read({"workspace_root": "/nonexistent/path"})
    assert result["decision"] == "deny"


def test_workspace_root_ao_suffix_normalized(ws_enabled: Path):
    # Passing .ao directory itself → parent normalized
    result = handle_memory_read({"workspace_root": str(ws_enabled / ".ao")})
    assert result["decision"] == "executed"


# ── 9) Pattern allowlist ───────────────────────────────────────────
def test_pattern_not_allowed(tmp_path: Path):
    (tmp_path / ".ao" / "policies").mkdir(parents=True)
    (tmp_path / ".ao" / "policies" / "policy_mcp_memory.v1.json").write_text(json.dumps({
        "version": "v1",
        "read": {"enabled": True, "allowed_patterns": ["runtime.*"]},
        "write": {"enabled": False, "allowed_key_prefixes": [], "max_value_bytes": 4096, "allowed_source_prefixes": ["mcp:"]},
        "rate_limit": {"reads_per_minute": 60, "writes_per_minute": 10},
    }))
    result = handle_memory_read({"workspace_root": str(tmp_path), "pattern": "architecture.*"})
    assert result["decision"] == "deny"
    assert "pattern_not_allowed" in result["reason_codes"]


# ── 10) Rate limit ─────────────────────────────────────────────────
def test_rate_limit_triggers(ws_enabled: Path, monkeypatch):
    # Drop RPM to 1 for fast test
    policy_path = ws_enabled / ".ao" / "policies" / "policy_mcp_memory.v1.json"
    policy = json.loads(policy_path.read_text())
    policy["rate_limit"]["reads_per_minute"] = 1
    policy_path.write_text(json.dumps(policy))

    handle_memory_read({"workspace_root": str(ws_enabled)})  # acquires
    result = handle_memory_read({"workspace_root": str(ws_enabled)})
    assert result["decision"] == "deny"
    assert "rate_limit_exceeded" in result["reason_codes"]


# ── 11) Workspace RL isolation (W1 doğrulaması) ────────────────────
def test_rate_limit_isolated_per_workspace(ws_enabled: Path, tmp_path: Path):
    # Build a second workspace with same rpm=1
    ws2 = tmp_path / "ws2"
    (ws2 / ".ao" / "policies").mkdir(parents=True)
    (ws2 / ".ao" / "policies" / "policy_mcp_memory.v1.json").write_text(json.dumps({
        "version": "v1",
        "read": {"enabled": True, "allowed_patterns": ["*"]},
        "write": {"enabled": False, "allowed_key_prefixes": [], "max_value_bytes": 4096, "allowed_source_prefixes": ["mcp:"]},
        "rate_limit": {"reads_per_minute": 1, "writes_per_minute": 10},
    }))
    # Drop ws_enabled RPM to 1 too
    p1 = ws_enabled / ".ao" / "policies" / "policy_mcp_memory.v1.json"
    po = json.loads(p1.read_text())
    po["rate_limit"]["reads_per_minute"] = 1
    p1.write_text(json.dumps(po))

    handle_memory_read({"workspace_root": str(ws_enabled)})  # consume ws1 token
    # ws2 should still have a token
    r = handle_memory_read({"workspace_root": str(ws2)})
    assert r["decision"] == "executed"


# ── 12) Implicit promote skip (B2 doğrulaması) ─────────────────────
def test_implicit_promote_skip(ws_enabled: Path):
    from ao_kernel._internal.mcp.memory_tools import _IMPLICIT_PROMOTE_SKIP
    assert "ao_memory_read" in _IMPLICIT_PROMOTE_SKIP


# ── 13) Evidence JSONL append with param-aware ws ──────────────────
def test_evidence_jsonl_append(ws_enabled: Path):
    # Call through _with_evidence wrapper (full MCP path)
    from ao_kernel.mcp_server import TOOL_DISPATCH
    wrapped = TOOL_DISPATCH["ao_memory_read"]
    wrapped({"workspace_root": str(ws_enabled), "pattern": "*"})
    # Expect JSONL file in ws_enabled/.ao/evidence/mcp/{date}.jsonl
    evidence_dir = ws_enabled / ".ao" / "evidence" / "mcp"
    assert evidence_dir.is_dir()
    files = list(evidence_dir.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert any("ao_memory_read" in line for line in lines)
```

### 6. `ao_kernel/mcp_server.py` değişiklikleri

**a) `_with_evidence` wrapper (line 549 civarı):**

```python
# ÖNCE
ws = _find_workspace_root()

# SONRA
from ao_kernel._internal.mcp.memory_tools import _resolve_workspace_for_call
ws = _resolve_workspace_for_call(params, fallback=_find_workspace_root)
```

**b) `call_tool` implicit promote (line 668-683):**

```python
# ÖNCE
ws_root = _find_workspace_root()
if ws_root is not None:
    decisions = extract_from_tool_result(name, result)
    for d in decisions:
        if d.confidence >= 0.8:
            promote_decision(ws_root, ...)

# SONRA
from ao_kernel._internal.mcp.memory_tools import (
    _resolve_workspace_for_call,
    _IMPLICIT_PROMOTE_SKIP,
)
ws_root = _resolve_workspace_for_call(arguments, fallback=_find_workspace_root)
if ws_root is not None and name not in _IMPLICIT_PROMOTE_SKIP:
    decisions = extract_from_tool_result(name, result)
    for d in decisions:
        if d.confidence >= 0.8:
            promote_decision(ws_root, ...)
```

**c) `TOOL_DEFINITIONS` (line 449 civarı):**

```python
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    # ... mevcut 5 entry
    {
        "name": "ao_memory_read",
        "description": "Read canonical decisions and workspace facts (policy-gated, fail-closed, read-only).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_root": {"type": "string", "description": "Optional workspace root override"},
                "pattern": {"type": "string", "default": "*", "description": "Glob pattern for key match"},
                "category": {"type": "string", "description": "Optional category filter"},
            },
            "additionalProperties": False,
        },
    },
]
```

**d) `TOOL_DISPATCH` (line 564 civarı):**

```python
from ao_kernel._internal.mcp.memory_tools import handle_memory_read

TOOL_DISPATCH = {
    # ... mevcut 5 entry
    "ao_memory_read": _with_evidence("ao_memory_read", handle_memory_read),
}
```

**e) Docstring (line 6): "5 tools" → "6 tools"**
**f) Comment (line 576 civarı): "5 tools registered" → "6 tools registered"**

### 7. `CLAUDE.md` değişiklikleri

**§2 invariant #2 (line 15-17):**
```
2. **Evidence:** Her side-effect:
   - MCP events: JSONL append-only log (fsync'li)
   - Workspace artifacts: JSONL + SHA256 integrity manifest (tam kontrat)
```

**§4 MCP Server (line 55):**
```
6 governance tool (`ao_policy_check`, `ao_llm_route`, `ao_llm_call`, `ao_quality_gate`, `ao_workspace_status`, `ao_memory_read`)
```

### 8. `README.md` değişiklikleri

MCP tool listesi (line 126-150 civarı) + Evidence trail matrisi (line 211 civarı) — `ao_memory_read` satırı eklenir, count 5→6.

### 9. `ao_kernel/_internal/evidence/mcp_event_log.py` docstring

Module docstring güncelleme:
```python
"""MCP event log — JSONL append + fsync, no manifest.

Manifest (SHA256 integrity) is reserved for workspace artifacts
(canonical_decisions, checkpoints, evidence run_dir). MCP events
are append-only JSONL with fsync, daily-rotated.

See CLAUDE.md §2 invariant #2 for the dual-form contract.
"""
```

### 10. `.claude/plans/SESSION-HANDOFF-TRANCHE-C-MID.md` debt tablosu

"Technical Debt" tablosuna satır ekle:
```
| MCP evidence SHA256 manifest | `mcp_event_log.py` JSONL-only | Tranş D (v3.1.0+) |
```

### 11. `tests/test_mcp_server.py`

`len(TOOL_DEFINITIONS) == 5` → `== 6`

---

## Acceptance Criteria

- [ ] `pytest tests/ -x` → 935 test yeşil (922 + 13 yeni)
- [ ] `ruff check ao_kernel/ tests/` → All checks passed
- [ ] `mypy ao_kernel/ --ignore-missing-imports` → Success
- [ ] Coverage gate 70% korunuyor
- [ ] Test quality gate (AST-based) uymuyor: BLK-001, BLK-002, BLK-003 yok
- [ ] `ao_memory_read` `call_tool` içinde `_IMPLICIT_PROMOTE_SKIP`'te — canonical store'a self-referential yazmıyor (B2)
- [ ] `_with_evidence` wrapper ve `call_tool` implicit promote yolu `_resolve_workspace_for_call` kullanıyor (B1)
- [ ] Policy schema validation handler içinde explicit (`jsonschema.validate()`)
- [ ] Default policy `read.enabled=false` → fail-closed (iddia)
- [ ] Batch docs update: README, CLAUDE.md, mcp_server docstring, test count hep 6 (W2)
- [ ] `mcp_event_log.py` docstring "no manifest" netliği (B3)

---

## Key Invariants (regress etmeyelim)

| Invariant | Konum | Test |
|---|---|---|
| `_resolve_workspace_for_call` fallback = key-absent only | `memory_tools.py` | 6 test (absent/None/int/empty/nonexistent/.ao-suffix) |
| Shared `decision_extractor.py` değişmez | - | `test_memory_pipeline.py:121-132` hâlâ geçer |
| `_IMPLICIT_PROMOTE_SKIP` tool denylist | `memory_tools.py` + `mcp_server.call_tool` | `test_implicit_promote_skip` |
| `(ws, op)` tuple RL scope + ayrı registry | `memory_tools.py` | `test_rate_limit_isolated_per_workspace` |
| `TokenBucketRateLimiter` sınıf reuse, helper yok | `memory_tools.py:_memory_rate_limiter_for` | RL test'ler |
| `ToolSpec(allowed=True)` + handler-level deny envelope | `tool_gateway.py` + `memory_tools.py:handle_memory_read` | deny testleri |
| Strict resolver scope memory tool'la sınırlı | `memory_tools.py` docstring | W1 absorbe |
| MCP evidence = JSONL + fsync (no manifest) | `mcp_event_log.py` docstring + CLAUDE.md §2 | docstring assert |

---

## PR Workflow

```bash
# 1. Branch setup (iki seçenek)
#    (a) Mevcut worktree'de devam:
git status  # claude/vigorous-ptolemy, clean
#    (b) Handoff'taki ad ile yeni branch:
# git checkout -b claude/tranche-c-c6a origin/main

# 2. Dosyaları oluştur ve düzenle (yukarıdaki 11 adım)

# 3. Validation
pytest tests/ -x --tb=short
ruff check ao_kernel/ tests/
mypy ao_kernel/ --ignore-missing-imports
pytest tests/ --cov=ao_kernel --cov-fail-under=70

# 4. Commit
git add -A
git commit -m "$(cat <<'EOF'
feat(mcp): ao_memory_read tool + policy + param-aware resolver (C6a, CNS-011)

Adds fail-closed, policy-gated, rate-limited MCP read tool for
canonical decisions and workspace facts. Follows CNS-20260414-011
adversarial consensus (3 iter, AGREE, ready_for_impl=true).

Scope:
- New module ao_kernel/_internal/mcp/memory_tools.py
  - _resolve_workspace_for_call (param-aware, fallback=key-absent only)
  - _IMPLICIT_PROMOTE_SKIP = {"ao_memory_read"} (B2)
  - _memory_rate_limiter_for + _memory_rate_limit_reset
  - _load_memory_policy_validated (explicit jsonschema.validate)
  - handle_memory_read
- New policy ao_kernel/defaults/policies/policy_mcp_memory.v1.json
  - read.enabled=false (fail-closed), allowed_patterns, rate_limit
- New schema ao_kernel/defaults/schemas/policy-mcp-memory.schema.v1.json
- mcp_server.py: TOOL_DEFINITIONS + TOOL_DISPATCH entry,
  _with_evidence and call_tool param-aware resolver (B1)
- Batch docs update: README, CLAUDE.md, mcp_server docstrings,
  mcp_event_log.py docstring, handoff debt table, test count 5→6 (W2)
- 13 new tests in tests/test_mcp_memory_read.py

Invariants:
- Shared decision_extractor.py UNCHANGED (iter-2 regression fix)
- Strict resolver scope: memory tools only (iter-3 W1)
- MCP evidence = JSONL append + fsync (no manifest)

Consensus: .ao/consultations/CNS-20260414-011.consensus.md
EOF
)"

# 5. Push + PR
git push -u origin <branch>
gh pr create --title "feat(mcp): ao_memory_read tool (C6a, CNS-011)" --body "<doldur>"

# 6. CI → M2 merge pattern (protection approval=0 → merge → approval=1)
```

---

## Risk Register

| Risk | Olasılık | Etki | Mitigation |
|---|---|---|---|
| `_with_evidence` param-aware değişikliği diğer tool'ların evidence'ını bozar | Düşük | Orta | Test: mevcut 5 tool için evidence testleri yeşil kalmalı; `workspace_root` param'ı yoksa `fallback=_find_workspace_root` aynı davranışı verir |
| `call_tool` denylist mevcut tool promote davranışını değiştirir | Sıfır | - | Denylist sadece `ao_memory_read`; diğer tool'lar aynı akıştan geçer |
| Schema validation eski policy override'ları kırar | Sıfır | - | Yeni policy ilk kez tanıtılıyor, eski workspace'ler etkilenmez |
| LOC bütçesi | Sıfır | - | memory_tools.py ~200 LOC; mcp_server.py += ~20 LOC → 776 < 800 |

---

## Not Covered / Follow-up

- **C6b:** `ao_memory_write` tool + policy write surface (sonraki PR)
- **MCP manifest (B3 defer):** Tranş D / v3.1.0+
- **`read_with_revision`:** Advisory revision, C6a scope dışı; locked snapshot tasarımı sonrası ele alınır
- **C6b repo hizalaması:** `policy_mcp_tool_calling.v1.json` adı → muhtemelen mevcut `policy_tool_calling.v1.json` genişletilecek

---

**Status:** Ready for implementation. Başlangıç: branching kararı ardından 11 dosya değişikliği.
