# AO-MA-11F-1 — Test/Suggestion/Update Evidence Registers (pure core)

**Faz:** AO-MA-11F (master plan §Faz 5) · **Dilim:** AO-MA-11F-1 (pure core) · **Risk:** normal (schema + test; `.github`'a dokunmaz)
**Consultation:** CNS-20260531-002 · **Codex thread** `019e7fce` (3 tur REVISE → AGREE, ready_for_autonomous_merge=true)

## Amaç

Master plan §Faz 5: "testler/öneriler/güncellemeler hepsini takip". Her AO-MA slice için
test sonuçlarını, cross-AI itiraz dispozisyonlarını (accept/reject/partial + gerekçe,
CLAUDE.md §15), değişiklik günlüğünü ve SHA-bound bir kapanış zincirini makine-üretilebilir,
tamper-evident evidence artifact'larına döker.

## Mimari konum (run_governor / notifier / plan_consensus paritesi)

`ao_kernel/orchestration/slice_evidence_registers.py` PURE compiler: no I/O, no subprocess,
no network, no LLM, no GitHub. Verilen girdilerden (suite sayıları, objection kayıtları,
ledger satırları) schema-valid artifact üretir. GitHub PR-review-thread harvest + CI test
artifact okuma = AO-MA-11F-2 (side-effect, ayrı dilim).

## Üretilenler (9 dosya)

5 schema (Draft 2020-12, additionalProperties:false, 3 guard const false, register_authority=evidence_record_only):
- `ao-ma-slice-test-report.schema.v1.json` — sayılar + `required_tests_present` + `all_passed` (if/then: all_passed→0 fail/err)
- `ao-ma-ai-suggestion-register.schema.v1.json` — objections[{provider, source_kind, source_id, iteration, objection_digest, summary_redacted, disposition, rationale, applied_ref}] + harvest_mode + expected_objections_count + no_secret_payload; if/then reject/partial→rationale, no_objections→empty
- `ao-ma-slice-update-ledger-line.schema.v1.json` — append-only jsonl satır şeması
- `ao-ma-slice-closeout.schema.v1.json` — 3 sibling'i `bound_artifacts` ile SHA-bind eder
- `ao-ma-slice-evidence-bundle-manifest.schema.v1.json` — 4 üyeyi (closeout dahil) listeler (minItems=maxItems=4, uniqueItems)

`slice_evidence_registers.py` (PURE): build_test_report, build_suggestion_register,
build_update_ledger, build_closeout, verify_closeout_binding, build_bundle_manifest,
verify_bundle_manifest + canonical_bytes/sha256_of/_redact/_digest_text helper'ları.

`tests/test_ao_ma_11f_slice_evidence_registers.py` — 41 test, %100 branch.

## Fail-closed / recompute-not-trust invariant'lar (Codex CNS-20260531-002, 3 tur)

1. **Green by totals:** test report `all_passed` totals'tan türetilir; closeout `slice_passed=True`
   `_report_is_green` (required_tests_present + 0 fail/err + flag-totals tutarlılığı) şart. Forged
   `all_passed=true`+`failed=2` hem build hem verify'da reddedilir.
2. **Register closed:** `slice_passed=True` → suggestion register `complete` (expected==len coverage)
   veya `no_objections` (boş + expected 0). `in_progress` register pass'i destekleyemez.
3. **Cross-artifact slice_id:** test_report + suggestion_register + her ledger satırı closeout
   slice_id'sini taşımalı (build + verify). Farklı slice'tan sibling bind edilemez.
4. **Manifest exact-set semantic:** verify role + artifact_kind + schema_version + sha256 +
   line_count beklenen değerlerle eşleşmeli; doğru-sha+yanlış-kind, eksik/duplicate üye reddedilir.
5. **Empty-register explicit provenance:** boş register `expected_objections_count=0` explicit ister;
   implicit "kayıt yok = itiraz yok" reddedilir.
6. **Skipped ≠ pass:** `required_tests_present = (tests-skipped)>0`; all-skipped run pass DEĞİL.
7. **Rationale:** reject/partial → rationale required; accept → applied_ref veya no-op rationale.
8. **Secret-safe:** tüm free-text (objection, rationale, ledger summary, suite name) notifier-grade
   denylist'ten geçer; `no_secret_payload` const true. Tamper-evident: verify_* machine-recompute.
9. **Ledger monotonik seq + tek slice_id.** **Closeout dairesel değil:** manifest closeout'a referans
   verir, closeout manifest'e vermez.

## Cross-AI review

Implementer: Claude (Anthropic). Reviewer: Codex (OpenAI) thread `019e7fce` —
plan-time REVISE (7 invariant) → post-impl REVISE (closeout flag-trust) → post-impl
REVISE (register-closed + cross-slice_id + manifest semantic + empty-explicit) → **AGREE**
(ready_for_autonomous_merge=true). Her itiraz suggestion register'ın temsil ettiği tam modelle
kaydedilebilir (self-hosting: bu dilim kendi review geçmişini temsil edebilen şemayı üretir).

## Kanıt

- 41 test PASS, slice_evidence_registers.py **%100 branch** (244 stmt, 94 branch, 0 miss)
- full suite **5059 / 0 fail** (JUnit XML)
- 5 schema Draft 2020-12 valid; ruff + mypy temiz; AST import-allowlist (hashlib/json/re/dataclasses/typing)
- 3 guard flag const false; `live_adapter_execution=false` korunur

## Sonraki (ayrı dilim)

- **AO-MA-11F-2** (side-effect, high-risk): `gh` ile PR review thread harvest → suggestion register;
  CI test artifact okuma → test report; manifest'in fiziksel dosya yollarına bağlanması; secret
  redaction'ın canlı PR yorumlarındaki davranışı.
