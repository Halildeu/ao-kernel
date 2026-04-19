# v3.9 — Tool Dispatch Governance Hardening (DRAFT v1)

**Status:** DRAFT v1 — pending per-PR CNS
**Prior consensus:** Codex consult (2026-04-19) → AGREE — v3.9 = B (Tool Dispatch Governance) + opt-small C; A (External Real-Adapter Benchmark) kayar v3.10'a, E (Prompt Experiments) v3.11 koşullu.

**Depends on:** v3.8.0 LIVE (5 hardening PRs; coverage 85.03%; 2506 test pins).

**Scope optimum:** 3 PR (B1 + B2 + C1). Two-gate rule governance-critical; esnetilmez.

---

## 1. Problem statement

v3.8 sonrası ana runtime debt: `policy_tool_calling.v1.json` dormant alanlarıyla `tool_gateway.py` runtime enforcement arasındaki drift.

**Policy yüzeyi (bundled default):**
```json
{
  "max_tool_calls_per_request": 5,
  "allowed_tools": [],
  "blocked_tools": [],
  "tool_permissions": {
    "default": "read_only",
    "mutating_requires_confirmation": true
  },
  "cycle_detection": {
    "enabled": true,
    "max_identical_calls": 2
  }
}
```

**Runtime absorb (`ToolCallPolicy.from_dict()`):**
```python
return cls(
    enabled=policy.get("enabled", True),
    max_rounds=int(policy.get("max_tool_rounds", 10)),
    allow_unknown=policy.get("allow_unknown", False),
)
```

Yani **4 field + 1 nested object dormant**:
1. `max_tool_calls_per_request` (single-request cap, `max_tool_rounds`'dan farklı)
2. `allowed_tools` / `blocked_tools` (allowlist/blocklist explicit)
3. `tool_permissions.{default, mutating_requires_confirmation}`
4. `cycle_detection.{enabled, max_identical_calls}`

Bu drift operatörün policy yazdığı şeyin **çalıştığını sandığı ama çalışmadığı** sessiz-misconfigured durumu yaratıyor. v3.9 kapatıyor.

---

## 2. Non-goals

- **No new policy surface.** v3.9 sadece mevcut dormant alanları canlandırır. Yeni alan eklemez.
- **No `implicit_canonical_promote` revision.** O flag zaten farklı pathway'de (`handler_promote`) kullanılıyor; out-of-scope.
- **No tool registry schema change.** `ToolSpec` / `register_handler()` signature'ları aynen kalır.
- **No MCP protocol extension.** MCP `ao_tool_call` (varsa) veya external tool dispatch protokolü dokunulmaz.
- **No LLM-side tool-use orchestration change.** `client.py`'nin manual tool loop contract'ı pre-v3.9 gibi kalır.

---

## 3. PR split (3 PRs)

### PR-B1 — `ToolCallPolicy` contract absorb + parser tests (MUST)

**Amaç:** policy schema'daki dormant alanları `ToolCallPolicy` dataclass'ına parse et. Runtime enforcement henüz yok — sadece contract absorb + validation.

**Kontrat:**
- `ToolCallPolicy` dataclass yeni alanlar:
  - `max_calls_per_request: int = 5`
  - `allowed_tools: tuple[str, ...] = ()`
  - `blocked_tools: tuple[str, ...] = ()`
  - `default_permission: Literal["read_only", "mutating"] = "read_only"`
  - `mutating_requires_confirmation: bool = True`
  - `cycle_detection_enabled: bool = True`
  - `cycle_max_identical_calls: int = 2`
- `ToolCallPolicy.from_dict()` tüm bu alanları absorb eder
- Input validation: `max_calls_per_request >= 1`, `cycle_max_identical_calls >= 1`, `default_permission in {"read_only", "mutating"}`; invalid → `ValueError`
- Parser tests (~8 pin): happy path absorb, eksik alan default, invalid type, invalid enum, negative ints

**Ship class:** MUST.
**Risk:** düşük (no runtime behavior change; sadece parsing).
**Test pin:** ~8.

### PR-B2 — Runtime enforcement + denial reasons + MCP integration (MUST)

**Amaç:** B1'deki absorb edilmiş alanları `ToolGateway.dispatch()` runtime'ında enforce et.

**Kontrat:**
- `ToolGateway.dispatch()`:
  - `max_calls_per_request` — per-request call counter; aşılırsa `status="DENIED", reason="max_calls_per_request exceeded"`
  - `allowed_tools` non-empty ise: çağrılan tool listede değilse `DENIED, reason="not_in_allowlist"`
  - `blocked_tools` non-empty ise: çağrılan tool listede varsa `DENIED, reason="blocked_by_policy"`
  - `cycle_detection_enabled=True` ise: son N çağrıyı takip, aynı tool+params > max_identical_calls → `DENIED, reason="cycle_detected"`
  - `default_permission="read_only"` + mutating tool + `mutating_requires_confirmation=True` → `DENIED, reason="mutating_requires_confirmation"` (tools kendi shape'inde `is_mutating` işareti taşıyacak; `ToolSpec` + `register_handler` additive opt-in param)
- `ToolCallResult.reason_code` (yeni): machine-readable denial key
- MCP server'daki tool dispatch path'i (varsa) aynı enforcement'ı kullanır
- Fail-closed: bilinmeyen permission değeri → `DENIED`
- Audit: her denial `evidence_emitter` üzerinden `policy_denied` event'i yazar

**Ship class:** MUST.
**Risk:** ORTA (runtime behavior change; eski davranışta kabul edilen tool call'lar artık DENIED dönebilir).
**Mitigation:** bundled policy `enabled=false` kalır (opt-in). Operatörler flag çevirene kadar pre-v3.9 davranışı aynen. Changelog açıkça documented.
**Test pin:** ~10-12.

### PR-C1 — `_internal/*` coverage tranche 2 (opt-small, MUST if capacity)

**Amaç:** v3.8 H1'deki pattern'i devam ettir; bu sefer `_internal/utils/*` veya `_internal/providers/*` ekle.

**Kontrat:**
- `pyproject.toml::coverage.run.omit`: seçilen tree'yi çıkar
- Gap pin'leri ekle (H1 pattern: vault_stub, api_key_resolver branches gibi)
- Gate: `fail_under=85` korunur (85.03% → ≥85%)

**Ship class:** MUST (kapasite varsa). Atlanabilir; H1 zaten tranche pattern'i kurdu.
**Risk:** düşük (mekanik).
**Test pin:** ~5-15 (tranche'a bağlı).

---

## 4. Rollout

```
B1 (parser absorb) ──→ B2 (runtime enforce)
                             ↓
                        C1 (coverage tranche 2; parallel-safe)
                             ↓
                        release(v3.9.0)
```

B1 → B2 seri (B2 B1'e bağlı). C1 B1 merge sonrası parallel lane. Codex iter-1: "B ve A için two-gate kesinlikle esnetmem" — her 3 PR için plan-time + post-impl CNS.

**v3.9.0 total estimate:**
- +23-35 test pin (B1 8 + B2 10-12 + C1 5-15)
- Runtime enforcement değişimi — opt-in via `enabled=true`
- Bundled policy aynen kalır; operatörler elle aktifleştirir

---

## 5. Codex AGREE — absorbed decisions

1. **v3.9 = B** (Tool Dispatch Governance), A (External Adapter Benchmark) kayar v3.10.
2. **E (Prompt Experiments) conditional** — "trustworthy metrics" koşulu hâlâ tam karşılanmıyor; codex-stub event-backed realism var ama external vendor adapter realism (A scope) lazım. A → E sıralaması.
3. **3 PR ritmi** (B1 + B2 + C1); 4. PR ancak A prep/doc olarak eklenirse mantıklı.
4. **Two-gate pattern korunacak** — governance + policy + external dependency PR'larında esnetilmeyecek.
5. **v4.0 ≥ v3.11**; async ayrı tutulursa daha geç. save_store cleanup zaten v4.0 kilidi.

---

## 6. v3.10 forward reference (External Real-Adapter Benchmark)

v3.9 B shipped olduktan sonra A (F2.1+):
- Yeni bench workflow variant (`governed_review_real_adapter.v1.json`)
- `claude-code-cli.manifest.v1.json` `review_findings` capability advertise
- `policy_worktree_profile.enabled=true` workspace override + secret flow
- Disposable sandbox repo runbook docs

v3.10 planı kendi CNS'inde daraltılır; burada forward reference olarak kayıtlı.

---

## 7. Explicit non-contracts

- v3.9 MCP protokolünü extend etmez.
- `implicit_canonical_promote` field'ı dokunulmaz (v4.0+ koşullu).
- Tool registry schema aynen kalır.
- v3.9 runtime default behavior değişmez (policy `enabled=false`); flag-gated enforcement.
