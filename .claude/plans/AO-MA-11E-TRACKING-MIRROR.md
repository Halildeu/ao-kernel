# AO-MA-11E — GitHub-Native Operator Tracking Mirror

> **Statü:** 11E-1 (derived tracking SSOT, GitHub write YOK) implement edildi. 11E-2 (gerçek GitHub Projects/Milestone/Issue sync, high-risk) follow-up.
> **Program:** [AO-MA-SPM-MASTER-PLAN.md](AO-MA-SPM-MASTER-PLAN.md) Faz 2. 3-AI mutabık (Claude+Codex thread `019e77c0` + Mavis) + operatör onaylı program.
> **Risk:** critical (schemas + program-ssot + tests-gate) → high-risk lane.
> **Değişmezler:** `support_widening`/`production_platform_claim`/`live_adapter_execution` = FALSE; risk downgrade YASAK; GitHub write YOK (11E-2).

## 1. Amaç

Operatörün "planda neredeyim + yol haritası + izlenebilirlik" sorusunu cevaplayan **makine-okur türev tracking SSOT** + insan-okur ayna + pure-read sorgu aracı + iç tutarlılık (drift) çekirdeği.

## 2. İki katman (Codex tur-4 + 019e77c0 absorbe)

- **Authority:** master plan + merged AO-MA artifact'ları + ao-release-gate. `ao_ma_status.v1.json` bunların **türevidir, otorite DEĞİL** (`status_role` + `authority_model` const ile pinli).
- **Mirror:** GitHub Projects/Milestone/Issue (11E-2). Tek-yön `ao-kernel→GitHub`; manuel GH edit override edemez (`github_mirror.manual_edit_override_allowed` const false).

## 3. Üretilenler (11E-1)

| Artifact | Yol | Rol |
|---|---|---|
| Status schema | `ao_kernel/defaults/schemas/ao-ma-status.schema.v1.json` | Draft 2020-12 strict; anchor + per-slice state machine + 3 guard const false + drift_policy |
| Status SSOT | `.claude/plans/ao_ma_status.v1.json` | Türev tracking index (7 faz, 9 slice) |
| Next-action aracı | `scripts/ao_ma_next.py` | Pure-read: load+validate+drift+next-action printer (no subprocess/network/GitHub) |
| Roadmap aynası | `.claude/plans/AO-MA-ROADMAP-STATUS.md` | İnsan-okur faz/slice tablosu |
| Testler | `tests/test_ao_ma_11e_status_tracking.py` | 56 test, ao_ma_next %99 branch |

## 4. Schema kontratı

- **status_role** const `machine_readable_derived_tracking_index`; **authority_model** const `derived_from_master_plan_and_merged_ao_ma_artifacts` — otorite olmadığını pinler.
- **master_plan_ref** `{path const, sha256, commit_sha}` zorunlu — hangi master plan sürümünden türediği SHA-bound.
- **Per-slice state machine** (Mavis enforcement notu + Codex iter-2): `consensus_ref`/`approval_ref` **required obje + state required + additionalProperties:false**; eksik obje = schema hatası (sessiz `not_started` fallback YOK). `consensus_ref.state` ∈ {not_started, agreed, not_agreed}; `approval_ref.state` ∈ {not_requested, pending, approved, rejected, expired}. **if/then kanıt zorunluluğu:** `agreed` → ya schema-bound bundle (consensus_id+artifact_path+artifact_sha256+plan_digest) ya da **tam 3-AI quorum kapsayan** `consultation_refs` ({provider_id, ref}, anthropic+openai+minimax `contains` ile zorunlu — tek/eksik provider reddedilir). `approved`/`rejected`/`expired` → ya approval artifact bağı ya da `operator_decision_ref`.
- **anchor** her slice'ta zorunlu: `ao_authority_artifact`/`artifact_sha256`/`plan_digest`/`phase_id`/`slice_id`/`last_sync_run_id` (11E-1'de null-izinli)/`mirror_projection_sha256`.
- **risk_class** ∈ {low,normal,high,critical} — RiskClassifier'dan kaydedilir; **RECORD, otorite değil** (downgrade edemez; high/critical merge-time supersession ister).
- **3 guard flag** const false + `release_authority` const + `ai_output_release_authority` const false.
- **github_mirror** {authority const false, direction const ao-kernel-to-github, manual_edit_override_allowed const false, sync_state}.
- **drift_policy** {on_status_or_mirror_drift const halt_autonomy_and_escalate, comparator const pure_local_digest_and_inventory}.

## 5. Drift comparator (`check_drift`, pure local — Codex iter-2 absorbe)

Türev index'in **iç tutarlılığını + on-disk türev bağlarını** kontrol eder (11E-1 scope; GitHub mirror karşılaştırması = 11E-2):
- **Digest bağı (pure-local hashlib):** `master_plan_ref.sha256` ↔ on-disk master plan; her slice `anchor.artifact_sha256` ↔ on-disk `ao_authority_artifact`. Dosya yoksa skip (digest check, presence değil).
- **Envanter:** guard flag flip · phase↔slice cross-ref · duplicate slice_id · anchor id eşleşmesi · current_phase varlığı + **current_slice→current_phase aidiyeti**.
- **Lifecycle:** `in_review`/`merged` → consensus=agreed · merged approved decision tutarlılığı · high/critical merged `pr_refs` · **phase done → tüm slice merged**.
- **Recompute:** slices.merged_count/total_count/**percent** + phases.done_count/total_count/**percent** yeniden hesaplanır.
Bulgu = exit≠0 (fail-closed: otonomi dur + eskalasyon).

## 6. HARD RULE pin'leri

- No GitHub write (11E-1); no subprocess/network — pure-read (import-allowlist test'le pekiştirilebilir 11E-2).
- `ao_ma_status.v1.json` release/plan otoritesi DEĞİL.
- risk downgrade YASAK; guard flag const false.

## 7. Follow-up: 11E-2 (yüksek-risk)

GitHub Projects v2 + Milestone + Issue tek-yön sync workflow (`.github/**` + `gh` API) · anchor injection (last_sync_run_id + mirror_projection_sha256 doldurma) · canlı mirror drift (`mirror_projection_sha256` ↔ GitHub state) · `sync_state` synced/mirror_drift_detected.

## 8. Sonraki fazlar

11I (Autonomous Run Governor) → 11H (Notification) → 11F (Registers) → 4.6 (Native Import) → 11G (Quality Profile). Detay: master plan §5.
