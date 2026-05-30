# AO-MA-11A — Plan Consensus + Tek Operatör Onay Kapısı

> **Statü:** 11A-1 (düşük-riskli çekirdek) implement edildi. 11A-2 (GitHub Environment wiring, yüksek-risk) follow-up.
> **Program:** [ao_ma_spm_program] 7-fazlı GitHub-native AO-MA-SPM — 3-AI tam mutabık (Claude+Codex+Mavis, 2026-05-30) + operatör onayı (tek insan kapısı) alındı.
> **Sınırlar:** `live_adapter_execution` / `support_widening` / `production_platform_claim` = FALSE. GPP-9 closed + RI-7.8c non-promotion korunur.

## 1. Amaç

Otonom multi-AI kod yazma akışının (Claude + Codex + MiniMax) **plan-zamanı consensus**'unu sistematik, schema'lı, kanıtlanabilir hale getirmek ve **tek insan onay kapısını** machine-enforced bir governance kontratına bağlamak.

İşleyiş: AI'lar bir hedefi turlar halinde plana döker → her sağlayıcı verdict verir (AGREE/REVISE/PARTIAL/RED) → `unanimous_status` **recompute** edilir → yalnız `AGREE` ise operatöre approval artifact'ı sunulabilir → operatör onayı = tek insan kapısı → gerisi otonom.

Bu, merge-zamanı per-provider kaydının (`ao-ma-10-provider-consensus.v1`) **plan-zamanı analoğudur**: aynı `provider_id` + `verdict` sözlüğünü reuse eder ama bir PR diff'ine değil, bir **plana** (`plan_digest` + base) bağlanır. Vocabulary drift önlenir.

## 2. Bu slice'ta üretilenler (11A-1)

| Artifact | Yol | Rol |
|---|---|---|
| Consensus bundle schema | `ao_kernel/defaults/schemas/ao-ma-11a-plan-consensus-bundle.schema.v1.json` | 3-AI plan verdict bundle (Draft 2020-12, additionalProperties:false) |
| Approval schema | `ao_kernel/defaults/schemas/ao-ma-11a-plan-approval.schema.v1.json` | Tek operatör onay kaydı (`unanimous_status` const `AGREE`) |
| Validator | `ao_kernel/orchestration/plan_consensus.py` | Pure-decision policy: recompute + SHA-bind + fail-closed |
| Testler | `tests/test_ao_ma_11a_plan_consensus.py` | Schema + unanimity + integrity + approval + gate state |
| Plan doc | `.claude/plans/AO-MA-11A-PLAN-CONSENSUS-APPROVAL.md` | Bu belge |

## 3. Schema kontratı

**Consensus bundle** — başlıca alanlar: `operator_goal`, `plan_digest` (sha256), `plan_binding {repo, base_ref, base_sha}`, `acceptance_criteria[]`, `required_providers` (tam olarak `[anthropic, openai, minimax]` — min/max 3 + uniqueItems + enum), `provider_verdicts[]` (uniqueItems; provider_id sadece 3-AI; her required sağlayıcı `contains`+`minContains` ile pinli; round'lar contiguous 1..max), `round_budget`/`rounds_used` (1-3; validator round_index'e bağlar), `unanimous_status` (AGREE/NOT_AGREE), `spm_anchor`, `guard_flags` (3 const false), `release_authority` const, `ai_output_release_authority`/`secrets_recorded` const false. **`risk_class` 11A-1'de YOK** — risk otoritesi `RiskClassifier` (gerçek changed-path'ler, merge-time); plan-time bundle write-set taşımadığı için self-attested risk alanı eklenmedi (bkz. §7).

**SPM anchor** (Codex tur-3 minimal anchor fields): `spm_profile_ref`, `roadmap_item_id` (`^AO-MA-...`), `quality_targets {coverage_branch_min, required_test_classes[], required_evidence_classes[]}`, `tracking_refs[]` (11E mirror; 11E gelene kadar boş).

**Approval** — `consensus_bundle_sha256` + `approval_request_sha256` + `plan_digest` (üçlü SHA-bind; üçü de `validate_approval`'da byte-byte doğrulanır — `approval_request_path` zorunlu parametre), `unanimous_status` const `AGREE`, `decision` (approved/rejected/expired), `environment_ref` const `ao-ma-plan-approval`, `bypass_detected` const false (admin bypass invalid), `approved_by`/`approved_at`/`audit_url`.

## 4. Validator garantileri (machine-enforced, self-attestation YOK)

- **Unanimity recompute:** `unanimous_status` her zaman `provider_verdicts`'ten (her sağlayıcının **son tur** verdict'i) yeniden hesaplanır; bundle'ın yazdığı değer uyuşmazsa **fail-closed** (`PlanConsensusError`).
- **Quorum tamper guard:** `required_providers` tam olarak `{anthropic, openai, minimax}` olmalı.
- **Duplicate `(provider, round)` guard:** ambiguous truth → reddedilir.
- **Round-budget binding:** verdict round'ları contiguous `1..max` olmalı; `rounds_used == max(round_index)`; `max(round_index) <= round_budget <= 3` (round_index üzerinden budget bypass engellenir).
- **Conservative dissent:** kayıtlı herhangi bir sağlayıcının son-tur verdict'i AGREE değilse (required dışı dahil) → NOT_AGREE.
- **Approval triple SHA-bind:** `consensus_bundle_sha256 == sha256_of(bundle)`, `approval_request_sha256 == sha256_of(request)`, `plan_digest == bundle.plan_digest`, `consensus_id` eşleşmesi; aksi halde tamper → reddedilir.
- **AGREE-only approval:** approval yalnız `unanimous_status == AGREE` bundle için geçerli; NOT_AGREE'ye bağlı approval reddedilir.
- **No bypass:** `bypass_detected` false zorunlu.
- **Pure-policy guard:** AST import-allowlist testi (`{__future__, hashlib, json, dataclasses, pathlib, typing, jsonschema}`) — subprocess/os/LLM importu yok ⟹ shell-out / GitHub-write / LLM çağrısı imkânsız.

## 5. Tek gate state'leri (`gate_status`)

| State | Koşul | proceed |
|---|---|---|
| `consensus_not_reached` | unanimity NOT_AGREE | false |
| `awaiting_operator_approval` | AGREE, approval yok | false |
| `approved_autonomous_run_may_start` | AGREE + approval approved | **true** |
| `halted_operator_rejected` | AGREE + approval rejected/expired | false |

## 6. HARD RULE pin'leri

- No LLM call / no agent execution — pure deterministic policy.
- No GitHub write (no `git push` / `gh pr create` / `gh api`) — `subprocess` import YOK (static-test enforced).
- `release_authority` const `ao-release-gate+github-ruleset` — plan consensus/approval **release otoritesi DEĞİL**; gate bir **otonom run-start** yetkilendirir, merge/release değil.

## 7. Follow-up: 11A-2 (yüksek-risk)

GitHub Environment `ao-ma-plan-approval` (required-reviewer) + onay-akışı workflow'u (`.github/**` = high-risk lane). Gated job, bu validator'ı çağırıp `plan_digest` + `consensus_bundle_sha256` + `approval_request_sha256` üçlüsünü re-verify eder; gate açılmadan önce `unanimous_status == AGREE` zorunlu (REVISE/RED/missing → job hiç açılmaz). High-risk consensus lane (cross-provider supersession veya non-author human approval) ile merge edilir.

## 8. Sonraki fazlar (program)

11E (GitHub-Native Tracking Mirror) → 11I (Autonomous Run Governor) → 11H (Notification) → 11F (Test/Öneri/Güncelleme Register) → 4.6 (Native Worker Import) → 11G (SPM Quality Profile). Detay: [ao_ma_spm_program].
