# AO-MA-11I — Autonomous Run Governor

> **Statü:** 11I-1 (pure-decision governor + budget config + PAUSE kill-switch + decision artifact) implement edildi. Tek slice (Codex+Mavis: GitHub write yok, bölmeye gerek yok).
> **Program:** [AO-MA-SPM-MASTER-PLAN.md](AO-MA-SPM-MASTER-PLAN.md) Faz 3. 3-AI mutabık (Claude + Codex plan-time `019e7d41`/`019e7d44` + Mavis; post-impl Codex `019e7d6d`→`019e7d7b`). **4.6 native-import'tan ÖNCE zorunlu güvenlik kemeri.**
> **Değişmezler:** `support_widening`/`production_platform_claim`/`live_adapter_execution` = FALSE; governor RELEASE otoritesi DEĞİL (`governor_authority` const `run_continuation_only`).

## 1. Amaç

Otonom AO-MA run'ı sırasında **runaway koruması + operatör kill-switch**. Her adımdan önce governor'a "devam edebilir miyim?" sorulur; budget/PAUSE/anomali kontrolüyle `continue` veya `halt` döner. Sen uzaktayken sistem güvenle koşar; limit aşımı veya PAUSE → durur + eskalasyon.

## 2. Mimari (Codex + Mavis absorbe)

- **Pure-decision** (`run_governor.decide`): girdi = budget + state + `now_epoch` + `pause_present`; çıktı = `GovernorDecision`. **Yan etki YOK** (checkpoint yazmaz, network/LLM/subprocess yok). `now` enjekte edilir (deterministik test; wall-clock okumaz).
- **`is_paused(workspace_root)`**: tek-satır ince I/O wrapper (decide saf kalsın).
- **Side-effect ayrımı (Codex):** halt'ta governor sadece `safe_stop_required=True` der; checkpoint'i **executor** yazar. `escalation_required=True` → **AO-MA-11H** tüketir.
- **PAUSE en yüksek öncelik (Codex+Mavis):** `.ao/autonomous/PAUSE` varsa başka hiçbir kontrole bakmadan halt. Lokal-otoriter; GitHub status pause sayılmaz (network bağımlılığı/gecikme yok).
- **Fail-closed (Codex):** geçersiz budget → `config_invalid` halt; bozuk state → `state_invalid` halt; `now < started_at` (saat anomalisi) → `clock_anomaly_negative_elapsed` halt. Sessizce continue YOK.

## 3. Üretilenler

| Artifact | Yol | Rol |
|---|---|---|
| Budget schema | `ao_kernel/defaults/schemas/ao-ma-run-budget.schema.v1.json` | Hard cap config; her limit explicit required (null=unlimited YOK) |
| Decision schema | `ao_kernel/defaults/schemas/ao-ma-governor-decision.schema.v1.json` | continue/halt + if/then (continue→temiz, halt→safe_stop+escalation) |
| Governor | `ao_kernel/orchestration/run_governor.py` | pure `decide()` + `is_paused()` + `decision_to_artifact()` |
| Testler | `tests/test_ao_ma_11i_run_governor.py` | 42 test, run_governor %100 branch |

## 4. Budget kontratı (her limit zorunlu — fail-closed)

`max_slices` · `max_consensus_rounds` (≤3, merge-lane ile hizalı; PER consensus cycle — `current_consensus_rounds_used`) · `max_retries_per_slice` · `max_total_retries` (global retry tavanı) · `max_governor_steps` (master plan "iteration cap"; **global run-length tavanı**) · `max_wall_clock_seconds` · `max_total_output_tokens` (Codex: AI run'da asıl runaway riski token — primary guard). **Null=unlimited YOK** (Codex fail-open uyarısı): meaningful cap için bilinçli yüksek explicit değer (auditable). `cost_tracking.available` const false + `max_cost_usd` null (RI-7.8c: CLI-abonelik, cost API yok → cost dormant). 3 guard flag const false + `release_authority` pin + `governor_authority` const `run_continuation_only` + `github_write_authorized` const false + `side_effect_authority` const `none`. **Counter semantiği `used >= cap`** ("sıradaki action başlatılabilir mi"; `>` off-by-one düzeltildi).

## 5. Decision kontratı

`action` ∈ {continue, halt}; `halt_reason` (12 kod: operator_pause_flag, wall_clock_exceeded, max_slices_exceeded, max_consensus_rounds_exceeded, max_retries_exceeded, max_total_retries_exceeded, max_governor_steps_exceeded, max_total_output_tokens_exceeded, clock_anomaly_negative_elapsed, usage_axis_missing, config_invalid, state_invalid); `breached_limits[]`; `safe_stop_required`; `escalation_required`; `pause_present`. Schema if/then: **continue** → halt_reason null + breached boş + safe_stop/escalation false; **halt** → halt_reason string + safe_stop + escalation true. Guard pin'leri artifact + schema'da: `governor_authority`/`github_write_authorized`/`side_effect_authority` + **3 standart guard flag** (support_widening/production_platform_claim/live_adapter_execution) const false + `ai_output_release_authority` false.

## 6. Karar sırası (fail-closed, en yüksek öncelik önce)

1. PAUSE present → halt (`operator_pause_flag`)
2. budget schema-invalid VEYA schema yüklenemez → halt (`config_invalid`) — `decide()` ASLA raise etmez; schema-load hatası bile fail-closed halt'a döner
3. state axis absent → halt (`usage_axis_missing`); state malformed (non-int/bool/negatif) → halt (`state_invalid`)
4. `now < started_at` → halt (`clock_anomaly_negative_elapsed`)
5. budget breach(ler) `used >= cap` → halt + `breached_limits` (hepsi toplanır; ilk breach reason)
6. aksi halde → continue

Schema'lar bir kez okunup modül-seviye cache'lenir; warm-up sonrası `decide()` per-call filesystem read yapmaz (bundled resource, mutable state değil).

## 7. HARD RULE pin'leri

- Pure-decision: no subprocess/network/LLM (AST import-allowlist test'le pekiştirildi: yalnız json/dataclasses/pathlib/typing/jsonschema).
- governor RELEASE otoritesi DEĞİL (`governor_authority` const); 3 guard false.
- `now` enjekte (wall-clock okumaz) → deterministik.

## 8. Sonraki

11H (Notification — `escalation_required` tüketir) → 11F (Registers) → 4.6 (Native Import; governor artık koruyor) → 11G. Detay: master plan §5.
