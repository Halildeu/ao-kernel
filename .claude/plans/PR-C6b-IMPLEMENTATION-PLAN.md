# PR-C6b — Memory Write MCP Tool + Implicit Promote Refactor — Implementation Plan (2026-04-14)

## TL;DR

`ao_memory_write` MCP tool + implicit promote threshold policy refactor (CNS-010 iter-3 warning-4'ün hayata geçirilmesi). CNS-20260414-012 (2 iter adversarial consensus, `ready_for_impl=true`) onayı ile implement edilir.

- **Scope:** ~250 LOC (handler + policy refactor) + ~200 LOC test + docs batch
- **Base:** `origin/main` @ `c3fedd1` (C6a merge sonrası)
- **Test baseline:** 935 → hedef ~949 (14 yeni test)
- **Release:** v3.0.0 (C6a + C6b bundle, bu PR sonrası release PR açılabilir)
- **Consensus doc:** `.ao/consultations/CNS-20260414-012.consensus.md`

---

## Scope Özeti

### Yeni Dosyalar (1)

| Dosya | Amaç | Yaklaşık LOC |
|---|---|---|
| `tests/test_mcp_memory_write.py` | 14 yeni test + skip-effect | ~250 |

### Değişen Dosyalar (8)

| Dosya | Değişiklik | Nedeni |
|---|---|---|
| `ao_kernel/_internal/mcp/memory_tools.py` | `_SERVER_SIDE_CONFIDENCE` sabit, `_IMPLICIT_PROMOTE_SKIP` genişletme, `_load_tool_calling_policy_validated` helper, `handle_memory_write` handler | Core C6b |
| `ao_kernel/mcp_server.py` | TOOL_DEFINITIONS + TOOL_DISPATCH entry, `call_tool` implicit promote refactor (`_load_tool_calling_policy_validated` + policy threshold), docstring 6→7 | B1 + register |
| `ao_kernel/defaults/policies/policy_tool_calling.v1.json` | `implicit_canonical_promote` block eklenir | Codex iter-2 Q4 |
| `ao_kernel/defaults/schemas/policy-tool-calling.schema.v1.json` | `implicit_canonical_promote` optional property | W3 absorbe + Q3 |
| `README.md` | Tool listesi 6→7, evidence matrisi | W2 batch |
| `CLAUDE.md` | §4 tool count 6→7 + `ao_memory_write` | W2 batch |
| `tests/test_mcp_server.py` | `len(TOOL_DEFINITIONS) == 6` → `== 7` | W2 batch |
| `tests/test_tool_gateway.py` | Count 6→7 + assertion | W2 batch |
| `.claude/plans/SESSION-HANDOFF-TRANCHE-C-MID.md` | C6b merged satırı + "next = release v3.0.0" | W2 batch |

**Toplam LOC bütçesi:**
- `memory_tools.py`: mevcut ~230 + ~150 = ~380 LOC (< 800 bütçesi dahilinde)
- `mcp_server.py`: mevcut ~780 + ~15 = ~795 LOC (< 800 bütçesi dahilinde, just-in-time)

---

## Dosya Dosya Detay

### 1. `_internal/mcp/memory_tools.py` — genişletme

**Module-level değişiklikler:**

```python
_SERVER_SIDE_CONFIDENCE = 0.8  # Aligned with promote_decision default (canonical_store.py:281).
                                # Caller-supplied confidence is NOT trusted (CNS-010 iter-3 Q9).

_IMPLICIT_PROMOTE_SKIP: set[str] = {"ao_memory_read", "ao_memory_write"}
# Both tools return envelopes whose top-level scalar fields
# (api_version, tool, allowed, decision) would otherwise be
# extracted by decision_extractor.extract_from_tool_result and
# promoted as tool.ao_memory_*.{api_version,tool,allowed,decision}
# — self-referential noise. ao_memory_write also promotes
# explicitly via promote_decision(), so implicit promotion would
# double-write. Both must be denylisted.
```

**Yeni helper:**

```python
def _load_tool_calling_policy_validated(ws: Path | None) -> dict[str, Any]:
    """Load policy_tool_calling.v1.json with workspace override + schema validation.

    Note: this loader is used ONLY by the implicit-promote path in
    ``mcp_server.call_tool`` so that workspace overrides can tune
    ``implicit_canonical_promote`` per project. The gateway constructor
    in ``mcp_server.create_tool_gateway`` still uses ``load_default``
    because the gateway-level tool policy is a process-wide fallback,
    not a per-workspace override.
    """
    import jsonschema
    from ao_kernel.config import load_default, load_with_override
    policy_workspace = ws / ".ao" if (ws is not None and (ws / ".ao").is_dir()) else ws
    policy = load_with_override(
        "policies", "policy_tool_calling.v1.json",
        workspace=policy_workspace,
    )
    schema = load_default("schemas", "policy-tool-calling.schema.v1.json")
    jsonschema.validate(policy, schema)
    return policy
```

**Yeni handler** (C6a `handle_memory_read` pattern'ini takip eder):

```python
def handle_memory_write(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for the ``ao_memory_write`` MCP tool.

    Policy-gated, rate-limited, server-side fixed confidence. Caller
    -supplied ``confidence`` is IGNORED (CNS-010 iter-3 Q9); server
    uses ``_SERVER_SIDE_CONFIDENCE`` (0.8, repo default).
    """
    import json
    from ao_kernel.context.canonical_store import promote_decision
    from ao_kernel.mcp_server import _find_workspace_root

    tool = "ao_memory_write"
    ws = _resolve_workspace_for_call(params, fallback=_find_workspace_root)
    if ws is None:
        return _deny(tool, "workspace_not_found")
    try:
        policy = _load_memory_policy_validated(ws)
    except Exception as exc:  # noqa: BLE001 — fail-closed on load/validate
        return _deny(tool, "policy_load_error", error=str(exc))
    write_cfg = policy.get("write") if isinstance(policy, dict) else None
    if not isinstance(write_cfg, dict) or not bool(write_cfg.get("enabled", False)):
        return _deny(tool, "write_disabled_by_policy")

    # Param validation
    if not isinstance(params, dict):
        return _deny(tool, "invalid_params")
    key = params.get("key")
    value = params.get("value", None)
    source = params.get("source", "mcp:tool_write")
    if not isinstance(key, str) or not key.strip():
        return _deny(tool, "invalid_key")
    if value is None:
        return _deny(tool, "invalid_value")
    if not isinstance(source, str) or not source.strip():
        return _deny(tool, "invalid_source")

    # Key prefix allowlist
    key_prefixes = write_cfg.get("allowed_key_prefixes", [])
    if not isinstance(key_prefixes, list) or not key_prefixes:
        return _deny(tool, "key_prefix_not_allowed")
    if not any(isinstance(p, str) and key.startswith(p) for p in key_prefixes):
        return _deny(tool, "key_prefix_not_allowed")

    # Source prefix allowlist
    source_prefixes = write_cfg.get("allowed_source_prefixes", ["mcp:"])
    if not isinstance(source_prefixes, list) or not source_prefixes:
        return _deny(tool, "source_prefix_not_allowed")
    if not any(isinstance(p, str) and source.startswith(p) for p in source_prefixes):
        return _deny(tool, "source_prefix_not_allowed")

    # Size gate (JSON-encoded bytes)
    max_bytes = int(write_cfg.get("max_value_bytes", 4096))
    try:
        encoded = json.dumps(value).encode("utf-8")
    except (TypeError, ValueError) as exc:
        return _deny(tool, "value_not_serializable", error=str(exc))
    if len(encoded) > max_bytes:
        return _deny(tool, "oversize")

    # Rate limit — (ws, "write") tuple
    rate_cfg = policy.get("rate_limit", {}) if isinstance(policy, dict) else {}
    rpm = int(rate_cfg.get("writes_per_minute", 10)) if isinstance(rate_cfg, dict) else 10
    if rpm < 1:
        rpm = 1
    limiter = _memory_rate_limiter_for(ws, "write", rpm=rpm)
    if not limiter.try_acquire():
        return _deny(tool, "rate_limit_exceeded")

    # CAS-routed promote (promote_decision honors _mutate_with_cas internally)
    try:
        decision = promote_decision(
            ws, key=key, value=value, source=source,
            confidence=_SERVER_SIDE_CONFIDENCE,
        )
    except Exception as exc:  # noqa: BLE001 — surface as error envelope
        return _error(tool, f"promote_failure: {exc}")

    return {
        "api_version": _API_VERSION,
        "tool": tool,
        "allowed": True,
        "decision": "executed",
        "reason_codes": [],
        "data": {
            "key": decision.key,
            "confidence": decision.confidence,
            "promoted_at": decision.promoted_at,
        },
        "error": None,
    }
```

### 2. `mcp_server.py` — 4 patch noktası

**a) Module docstring (line 6-11): "Tools (6)" → "Tools (7)" + `ao_memory_write` satırı**

**b) `TOOL_DEFINITIONS` (line 530 civarı, `ao_memory_read`'dan sonra):**

```python
{
    "name": "ao_memory_write",
    "description": "Write a decision to canonical memory. Policy-gated, fail-closed, rate-limited; server-side fixed confidence.",
    "inputSchema": {
        "type": "object",
        "required": ["key", "value"],
        "properties": {
            "workspace_root": {"type": "string", "description": "Project root containing .ao/ (optional override)"},
            "key": {"type": "string", "description": "Canonical decision key (must match one of allowed_key_prefixes)"},
            "value": {"description": "Decision value (any JSON-serializable type; subject to max_value_bytes)"},
            "source": {"type": "string", "description": "Source tag (must start with an allowed_source_prefix)", "default": "mcp:tool_write"},
        },
        "additionalProperties": False,
    },
},
```

**c) `TOOL_DISPATCH` (line 577 civarı):**

```python
def _handle_memory_write_lazy(params: dict[str, Any]) -> dict[str, Any]:
    from ao_kernel._internal.mcp.memory_tools import handle_memory_write
    return handle_memory_write(params)


TOOL_DISPATCH = {
    # ... mevcut 6 entry
    "ao_memory_write": _with_evidence("ao_memory_write", _handle_memory_write_lazy),
}
```

**d) `call_tool` implicit promote (line 693-716) — policy-aware refactor:**

```python
# Wire tool result into context pipeline.
# Param-aware workspace + policy-configurable implicit-promotion threshold
# protect self-writing tools (ao_memory_read, ao_memory_write) via
# _IMPLICIT_PROMOTE_SKIP while letting workspace overrides tune the
# threshold for the remaining tools (CNS-20260414-010 iter-3 warning-4
# + CNS-20260414-012 B1).
try:
    from ao_kernel.context.decision_extractor import extract_from_tool_result
    from ao_kernel.context.canonical_store import promote_decision
    from ao_kernel._internal.mcp.memory_tools import (
        _IMPLICIT_PROMOTE_SKIP,
        _resolve_workspace_for_call,
        _load_tool_calling_policy_validated,
    )
    ws_root = _resolve_workspace_for_call(
        arguments or {}, fallback=_find_workspace_root,
    )
    if ws_root is not None and name not in _IMPLICIT_PROMOTE_SKIP:
        try:
            tool_policy = _load_tool_calling_policy_validated(ws_root)
        except Exception:
            # Fail-open: revert to bundled/default implicit behavior.
            # This path is side-channel wiring; the MCP response has
            # already been delivered. Memory tool handlers still
            # fail-closed on their own policy load errors.
            tool_policy = {}
        implicit_cfg = tool_policy.get("implicit_canonical_promote") or {}
        if implicit_cfg.get("enabled", True):
            threshold = float(implicit_cfg.get("threshold", 0.8))
            source_prefix = implicit_cfg.get("source_prefix", "mcp:tool_result")
            decisions = extract_from_tool_result(name, result)
            for d in decisions:
                if d.confidence >= threshold:
                    promote_decision(
                        ws_root,
                        key=d.key, value=d.value, source=source_prefix,
                        confidence=d.confidence,
                    )
except Exception:
    pass  # Context wiring failure shouldn't block tool response
```

**e) `create_tool_gateway` docstring (line 601): "6 tools" → "7 tools"**

### 3. `policy_tool_calling.v1.json` — genişletme

```json
{
  "version": "v1",
  "enabled": false,
  "max_tool_calls_per_request": 5,
  "max_tool_rounds": 3,
  "allowed_tools": [],
  "blocked_tools": [],
  "tool_permissions": {
    "default": "read_only",
    "mutating_requires_confirmation": true
  },
  "cycle_detection": {
    "enabled": true,
    "max_identical_calls": 2
  },
  "fail_action": "block",
  "implicit_canonical_promote": {
    "enabled": true,
    "threshold": 0.8,
    "source_prefix": "mcp:tool_result"
  }
}
```

### 4. `policy-tool-calling.schema.v1.json` — genişletme

Mevcut schema'ya `properties` altına eklenir (required DEĞİL — CNS-012 iter-2 Q3):

```json
"implicit_canonical_promote": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "enabled": {"type": "boolean"},
    "threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "source_prefix": {"type": "string", "minLength": 1}
  }
}
```

### 5. `tests/test_mcp_memory_write.py` — 14 yeni test

Test kategorileri (C6a pattern):

**Happy path (1):**
1. Write enabled + matching key/source prefix → executed via CAS

**Policy gates (6):**
2. Write disabled (default) → deny `write_disabled_by_policy`
3. Empty `allowed_key_prefixes` → deny `key_prefix_not_allowed`
4. Key prefix miss → deny
5. Bad source prefix → deny `source_prefix_not_allowed`
6. Oversized value (>4096 bytes) → deny `oversize`
7. `value_not_serializable` (ör. `value={1, 2}` set) → deny `value_not_serializable`

**Resolver edge cases — B1 invariant (2):**
8. `workspace_root` absent + library mode → deny `workspace_not_found`
9. `workspace_root` present-but-invalid (None/int/empty) → deny

**Semantic guarantees (3):**
10. Caller-supplied `confidence=0.99` IGNORED (server sets 0.8) — verify `decision.confidence == 0.8`
11. Rate limit triggers after N+1 writes
12. Implicit promote threshold from workspace-override policy (set threshold=0.99 → 0.95-confidence extract skipped)

**Skip-effect doğrulaması — B2 invariant (1):**
13. `ao_memory_write in _IMPLICIT_PROMOTE_SKIP` AND canonical store'da explicit `mem.foo` var, `tool.ao_memory_write.*` YOK

**Evidence — W1 hygiene (1):**
14. Evidence JSONL lands in param-aware workspace + assert `tool="ao_memory_write"`, `allowed=True`, `decision="executed"`

### 6. Docs batch (C6a pattern)

| Dosya | Değişiklik |
|---|---|
| `README.md` MCP tools listesi | 6→7: `ao_memory_write` satırı |
| `README.md` architecture | `mcp_server.py (6 tools, 3 resources)` → `(7 tools, 3 resources)` |
| `CLAUDE.md` §4 | 6 governance tool → 7 + `ao_memory_write` |
| `ao_kernel/mcp_server.py` docstring | line 6 `Tools (6)` → `Tools (7)`, line 601 `all 6 tools` → `all 7 tools` |
| `tests/test_mcp_server.py` | `assert len(TOOL_DEFINITIONS) == 6` → `== 7`, ao_memory_write added to assert |
| `tests/test_tool_gateway.py` | `test_create_tool_gateway_has_6_tools` → `..has_7..` + assertion |
| `.claude/plans/SESSION-HANDOFF-TRANCHE-C-MID.md` | Merged table satırı (#71 C6b), "Still open" listesinden C6b sil, next = release v3.0.0 |

---

## Acceptance Criteria

- [ ] `pytest tests/ -x` → ~949 test yeşil (935 + 14 yeni)
- [ ] `ruff check ao_kernel/ tests/` → All checks passed
- [ ] `mypy ao_kernel/ --ignore-missing-imports` → Success
- [ ] Coverage gate 70% korunuyor
- [ ] Test quality gate (AST-based): BLK-001, BLK-002, BLK-003 yok
- [ ] `ao_memory_write` explicit promote çalışıyor (canonical store'da `mem.*` key var)
- [ ] Implicit promote threshold workspace override ile değiştirilebiliyor (test 12)
- [ ] `ao_memory_write in _IMPLICIT_PROMOTE_SKIP` ve canonical store'da `tool.ao_memory_write.*` YOK (test 13)
- [ ] Evidence JSONL `tool/allowed/decision` alanları doğru (test 14)
- [ ] `_SERVER_SIDE_CONFIDENCE = 0.8` ve caller `confidence` param'ı yok sayılıyor (test 10)
- [ ] Batch docs update: 7 tool count hep tutarlı

---

## Key Invariants (regress etmeyelim)

| Invariant | Konum | Test |
|---|---|---|
| `_resolve_workspace_for_call` fallback = key-absent only | `memory_tools.py` | Test 8-9 (ws absent + present-invalid) |
| Shared `decision_extractor.py` DEĞİŞMEZ | — | `test_memory_pipeline.py:121-132` hâlâ geçer |
| `_IMPLICIT_PROMOTE_SKIP` = {ao_memory_read, ao_memory_write} | `memory_tools.py` module-level | Test 13 |
| Server-side confidence = 0.8 (caller ignored) | `memory_tools.py` | Test 10 |
| `promote_decision` CAS path korunur (`allow_overwrite=True` default) | Explicit handler call | Write happy path |
| Policy load fail-closed (memory), fail-open (implicit promote) | Handler + `call_tool` | Policy corrupt testi (memory deny; implicit default) |
| Bundled `policy_tool_calling.v1.json` default `enabled=true, threshold=0.8, source_prefix="mcp:tool_result"` | JSON dosyası | Schema + smoke test |
| Schema `implicit_canonical_promote` optional (legacy override güvenliği) | Schema JSON | Schema validation testi legacy override ile çalışmalı |
| `mcp_server.py < 800 LOC` | Dosya boyutu | `wc -l ao_kernel/mcp_server.py` |

---

## PR Workflow

```bash
# 1. Branch (mevcut worktree'de devam)
git status  # claude/vigorous-ptolemy, clean
git fetch origin --quiet
git pull --ff-only origin main 2>/dev/null || true  # optional sync (worktree branch, main cannot be checked out here)

# 2. Implementation
#    - memory_tools.py genişletme
#    - mcp_server.py patch (4 nokta)
#    - policy + schema genişletme
#    - test_mcp_memory_write.py (14 test)
#    - docs batch

# 3. Validation
pytest tests/ -x --tb=short
ruff check ao_kernel/ tests/
mypy ao_kernel/ --ignore-missing-imports
pytest tests/ --cov=ao_kernel --cov-fail-under=70

# 4. Commit
git add <files>
git commit -m "feat(mcp): ao_memory_write tool + implicit promote policy refactor (C6b, CNS-012)"

# 5. Push + PR
git push -u origin claude/vigorous-ptolemy  # branch zaten silinmişti, re-push
gh pr create --title "feat(mcp): ao_memory_write tool (C6b, CNS-012)" --body "..."

# 6. CI 7/7 → M2 merge pattern (approval=0 → merge → approval=1)
```

---

## Risk Register

| Risk | Olasılık | Etki | Mitigation |
|---|---|---|---|
| `call_tool` implicit promote refactor mevcut 5 tool'ın promote davranışını değiştirir | Düşük | Orta | Test: mevcut promote test'leri (ör. `test_mcp_server.py::TestImplicitPromote`) yeşil kalmalı; default policy `enabled=true, threshold=0.8` mevcut davranışı korur |
| Workspace override legacy policy (implicit_canonical_promote bloğu olmadan) kırılır | Düşük | Orta | Schema optional + runtime default kombinasyonu; Codex iter-2 Q3 onayı |
| `ToolCallPolicy.from_dict` yeni block'u parse ederken patlar | Sıfır | - | Codex iter-2 Q4: parser sadece mevcut alanları tüketir, yeni alan ignore edilir |
| `mcp_server.py` 800 LOC bütçesi patlar | Düşük | Orta | Mevcut ~780 + ~15 = ~795, tampon 5 LOC. Riskli ise TOOL_DEFINITIONS entry kısaltılır |
| `json.dumps(value)` her write'ta double serializasyon (promote_decision tekrar yazar) | Sıfır | Düşük | Codex iter-2 kabul: 4KB / 10rpm ölçeğinde ihmal edilebilir |

---

## Not Covered / Follow-up

- **Release v3.0.0:** C6b sonrası bundle tag (CHANGELOG + `__init__.py` version + `pyproject.toml` version → `3.0.0`)
- **MCP manifest:** Tranş D (CNS-011 B3 scope pivot)
- **`read_with_revision` response:** C6c'ye ertelendi (`CanonicalDecision` revision taşımıyor, ayrı API gerek)
- **Inverse allowlist (denylist yerine):** Codex iter-1 over-engineering kararı, üçüncü self-mutating tool geldiğinde yeniden değerlendirilir
- **`source` string grep (`mcp_tool` vs `mcp:tool_result`):** Batch'te tüm referanslar doğrulanmalı — commit öncesi grep check

---

**Status:** Ready for implementation. Başlangıç: `_internal/mcp/memory_tools.py` genişletmesi.
