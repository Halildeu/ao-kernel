# AO-MA-11H-1 — Notification & Escalation: Pure Decision Core

**Faz:** AO-MA-11H (Notification & Escalation) — master plan §Faz 4.
**Dilim:** AO-MA-11H-1 (pure core, low-write / high-risk lane).
**Risk:** high (schema family + AO-MA test family RiskClassifier'da high-risk;
changed-path otoritesi plan beyanı değil).

## Amaç

Otonom run governor (AO-MA-11I) `escalation_required` / `safe_stop_required`
üretir. Bu dilim, governance **olaylarını** → **notification intent**'lerine
çeviren saf karar çekirdeğidir. Teslimatı YAPMAZ; teslimat dış side-effect
executor'un işidir (AO-MA-11H-2: Mavis CLI chat + `gh` GitHub-native). Polling'i
öldürür: sistem operatörü yalnızca gate + eskalasyonda pinglenir.

## Mimari konum (run_governor paralelizmi)

`run_governor.decide()` nasıl `safe_stop_required` üretip checkpoint yazımını
executor'a bırakıyorsa, `notifier.decide_notification()` de intent üretir ama
teslimatı executor'a bırakır:

- `delivery_authority = "external_executor_only"` (intent schema const)
- `intent_authority = "notification_decision_only"` (intent schema const)
- `receipt_authority = "delivery_observation_only"` (receipt schema const)

## Üretilenler (9 dosya)

1. **`ao_kernel/orchestration/notifier.py`** — PURE çekirdek:
   - `decide_notification(event) -> NotificationDecision` (no I/O, asla raise;
     girdi mutate edilmez)
   - `decision_to_intent_artifact(decision, *, evaluated_at)` — schema-valid dict
   - `_SEVERITY_MATRIX` — 12 governor halt_reason (birebir) + 6 lifecycle event
   - machine redaction guard (`_redact` / `_is_clean`, denylist regex)
   - `NotificationDecision` frozen dataclass
2. **`ao_kernel/defaults/schemas/ao-ma-notification-intent.schema.v1.json`** —
   Draft 2020-12, additionalProperties:false, 3 if/then (suppress / notify /
   critical-confirm), 3 guard const false + delivery/intent authority const.
3. **`ao_kernel/defaults/schemas/ao-ma-notification-receipt.schema.v1.json`** —
   contract-first (11H-2 üretir, 11H-3 okur). structured `intent_ref`
   {path, sha256, artifact_kind, schema_version}; `failure_code` enum +
   `failure_summary_redacted`; delivered/failed/skipped if/then; `attempted_at`
   executor yazar (bu dilim üretmez).
4. **`tests/test_ao_ma_11h_notifier.py`** — 59 test.
5. **`.claude/plans/AO-MA-11H-NOTIFIER.md`** — bu doküman.
6–7. **`.claude/plans/ao_ma_status.v1.json` + `AO-MA-ROADMAP-STATUS.md`** —
   tracking drift fix (11I-1 merged #762, current → 11H-1; ayrıca 11I-1
   consultation_ref'teki fabricated `019e7f3a` → gerçek `019e7d44` düzeltmesi).
8. **`local-ai-review-evidence.v1.json`** — cross-AI review kanıtı.

## Severity matrix

| event / halt_reason | severity | confirm | kanal | delivery_success_condition |
|---|---|---|---|---|
| operator_pause_flag | high | hayır | mavis+gh | none |
| wall_clock/slices/consensus_rounds/retries/total_retries/governor_steps/tokens exceeded | high | hayır | mavis+gh | none |
| clock_anomaly_negative_elapsed, usage_axis_missing, config_invalid, state_invalid | critical | evet | mavis+gh | at_least_one_required_channel_delivered |
| approval_required | critical | evet | mavis+gh | at_least_one... |
| consensus_required | high | hayır | mavis+gh | none |
| consensus_round_budget_exhausted | critical | evet | mavis+gh | at_least_one... |
| drift_detected | critical | evet | mavis+gh | at_least_one... |
| mirror_drift_detected | high | hayır | mavis+gh | none |
| slice_closeout | info | hayır | mavis | none |
| governor_continue / run_heartbeat / no_op | (suppress) | — | — | null |
| **malformed / unknown** | **critical** | evet | mavis+gh | at_least_one... |

12 governor halt_reason birebir kapsanır (kısaltma yok).

## Fail-closed davranış

- Malformed event (mapping değil / event_kind boş-eksik) → **critical, tamamen
  sanitize** notify. Raw event ASLA yansıtılmaz: sabit summary + diagnostic kod.
- Bilinmeyen event → **critical** (asla sessiz suppress); `unknown_event:` prefix.
- Suppress yalnızca explicit `_SUPPRESS_EVENTS` listesi için (no-op).

## Secret redaction (machine guard, self-attestation DEĞİL)

`no_secret_payload const true` tek başına yetmez. Her free-text alan
(`redacted_summary`, `dedupe_key`, `diagnostics`) + `evidence_refs` denylist'ten
geçer: GitHub PAT (`gh[pos]_`, `github_pat_`), `sk-`/`sk-ant-`, Slack `xox*`,
üç-parçalı JWT, `Bearer`, webhook (hooks./discord/slack), email/PII.
`decision_to_intent_artifact` artifact'ı yazmadan önce gerçekten temiz mi diye
yeniden doğrular; değilse fail-closed olarak yeniden sanitize eder + flag'ler.

`evidence_refs` yapısal: `sha256:<64hex>` veya güvenli repo-relative path
(`..`, mutlak path, URL, query string, env-var adı reddedilir).

## Cross-AI review zinciri

- Plan-time: Codex thread `019e7dd2` (REVISE → 2 blocker [tracking drift + risk
  lane] + 12 tasarım revizyonu absorbe → AGREE).
- Post-impl: Codex (aynı thread) — implementer anthropic ≠ reviewer openai.

## Test kanıtı

- 59 test PASS; notifier.py branch coverage **%90** (kalan ~%10 defensive
  redaction-iç dalları — post-impl review'da Codex'in temiz okumasıyla reachable
  olanlar tamamlanacak).
- Full suite: 4971 test / 0 fail / 0 err / 76 skip (JUnit XML).
- ruff + ruff format + mypy temiz. AST import-allowlist: yalnız
  re/dataclasses/typing/__future__ (no subprocess/os/socket/network/LLM).
- `scripts/ao_ma_next.py`: drift NONE (tracking SSOT tutarlı).

## Sonraki dilimler (high-risk, ayrı)

- **AO-MA-11H-2:** side-effect executor — intent okur, Mavis CLI + `gh` çağırır,
  receipt yazar (intent canonical SHA bind, tamper-evident).
- **AO-MA-11H-3:** governor feedback — `blocked_notification_failed` halt_reason
  (critical receipt fail + requires_confirmation → safe-stop).
