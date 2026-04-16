# PR-A5 Implementation Plan v2 — Evidence Timeline CLI + SHA-256 Manifest + Replay

**Tranche A PR 6/8** — post CNS-025 iter-1 PARTIAL (5B + 5W absorbed). Target iter-2 AGREE via MCP reply (thread `019d93d3-054f-7743-b166-e892d712ff88`).

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-16 | Initial draft; CNS-025 iter-1 submission. |
| **v2** | **2026-04-16** | **5 blocker absorbed: B1 manifest canonical shape (`manifest.json` + `{version,run_id,generated_at,files:[{path,sha256,bytes}]}`), B2 replay_safe=False fix (5 event call site), B3 replay → "inferred state trace" (not exact recorded state), B4 manifest scope += `patches/*.revdiff`, B5 `_internal/evidence/` layout (no public evidence_cli.py). 5 warning noted (W1-W5).** |

---

## 1. Amaç

FAZ-A'nın evidence tarafını kapatır. PR-A3 `EvidenceEmitter` JSONL append-only yazıyor (18-kind taxonomy, per-run lock + monotonic seq). PR-A5 **okuma + doğrulama + replay** katmanını ekler:

- `ao-kernel evidence timeline --run <run_id>` — JSONL → kronolojik tablo (human-readable veya `--format json`)
- `ao-kernel evidence replay --run <run_id> --mode inspect|dry-run` — deterministic replay via `replay_safe` flag
- `ao-kernel evidence verify-manifest --run <run_id>` — SHA-256 manifest on-demand generation + verification
- `ao-kernel evidence generate-manifest --run <run_id>` — manifest.json üretir (on-demand, PR-A3 invariant: emit sırasında manifest güncellenmez)

FAZ-A release gate: "`ao-kernel evidence timeline` CLI works" (§10).

### Kapsam özeti

| Katman | Modül / Dosya | Yaklaşık LOC |
|---|---|---|
| CLI dispatcher | `ao_kernel/cli.py` delta (evidence subcommand) | ~40 |
| Timeline handler | `ao_kernel/_internal/evidence/timeline.py` (yeni, B5 absorb) | ~200 |
| Replay handler | `ao_kernel/_internal/evidence/replay.py` (yeni, B3 absorb) | ~200 |
| Manifest generator | `ao_kernel/_internal/evidence/manifest.py` (yeni, B1+B4 absorb) | ~150 |
| CLI handlers | `ao_kernel/_internal/evidence/cli_handlers.py` (yeni) | ~80 |
| Tests | `tests/test_evidence_cli.py` (yeni) | ~400 |
| Docs update | `docs/EVIDENCE-TIMELINE.md` §7/§8 CLI reference | ~30 delta |
| CHANGELOG | `[Unreleased]` → FAZ-A PR-A5 entry | ~40 |
| **Toplam** | 4 yeni _internal modül + 2 delta (cli.py + evidence_emitter.py) + 1 test | **~1130** |

- Yeni schema: **0** (manifest.json layout defined in docs, not a versioned schema).
- Yeni policy: **0**.
- Yeni core dep: **0** (stdlib: `hashlib`, `json`, `argparse`, `pathlib`).
- Evidence kind delta: **0** (18-kind whitelist intact).
- Tahmini yeni test: **≥ 25** (target 1510+).

---

## 2. Scope Fences

### Scope İçi

- **`ao-kernel evidence timeline --run <run_id>`**
  - Reads `{workspace}/.ao/evidence/workflows/{run_id}/events.jsonl`
  - Default output: kronolojik tablo (`seq | ts | kind | actor | step_id | payload_summary`)
  - `--format json` → newline-delimited JSON (passthrough with validation)
  - `--filter-kind step_started,step_completed` → whitelist filter
  - `--filter-actor adapter` → actor filter
  - `--limit N` → son N event
  - Default output tablo: `seq | ts | kind | actor | step_id | payload_summary` (payload_summary = canonical compact JSON, 96 char üstünde `93...` truncate; Q1 resolved)
  - `--format json` → full event NDJSON (filtrelenmiş tam event objeleri, envelope-only değil; Q1 resolved)
  - Graceful handling: missing run_id → error (exit 1); empty JSONL → "no events" (exit 0); malformed JSONL → error (exit 1)

- **`ao-kernel evidence replay --run <run_id> --mode inspect|dry-run`**
  - `inspect`: print each event with `replay_safe` annotation + **inferred** state trace (B3 absorb: "inferred/synthetic state trace validates observable event order", not "exact recorded state")
  - `dry-run`: walk the 9-state machine from `created` → terminal using **inferred transitions**; report:
    - `state_source: event` (explicit event like `workflow_started → running`)
    - `state_source: inferred` (e.g., `diff_applied → applying`)
    - `state_source: synthetic` (driver's CAS chain like `running → applying → verifying → completed` without matching events)
    - Illegal/unexpected transition → warning, not hard failure (evidence stream is a projection of state, not the state itself)
  - Evidence taxonomy: 18 kind'dan `replay_safe=True` olanlar deterministic; `replay_safe=False` olanlar non-deterministic (adapter invocations, approval responses, external API calls) (B2 absorb: 5 call site fix'i PR-A5'te yapılır)
  - No actual re-execution — read-only analysis

- **`ao-kernel evidence generate-manifest --run <run_id>`**
  - Scans `{run_dir}/events.jsonl` + `{run_dir}/adapter-*.jsonl` + `{run_dir}/artifacts/**/*.json` + `{run_dir}/patches/*.revdiff` (B4 absorb)
  - Computes SHA-256 for each file
  - Writes `{run_dir}/manifest.json` atomically (tempfile + fsync + rename)
  - Manifest shape (B1 absorb — canonical, docs §5 güncellenir): `{"version": "1", "run_id": str, "generated_at": ISO-8601, "files": [{"path": relative, "sha256": hex, "bytes": int}]}`
  - Overwrites existing manifest (idempotent)

- **`ao-kernel evidence verify-manifest --run <run_id>`**
  - Reads `{run_dir}/manifest.json`
  - Recomputes SHA-256 for each listed file
  - Reports match/mismatch per file
  - Exit codes (W3 + W5 absorb): `0` = all match; `1` = hash mismatch or missing listed file; `2` = manifest outdated (new in-scope file not in manifest); `3` = manifest.json itself missing (use `--generate-if-missing`)
  - Outdated detection: scans run_dir for in-scope files not listed in manifest → `manifest_outdated=true` → exit 2
  - `--generate-if-missing` flag: if manifest absent, generate first then verify (convenience)

- **`ao_kernel/_internal/evidence/timeline.py`** — JSONL reader + formatter + filter (B5 absorb: _internal, not public facade)
- **`ao_kernel/_internal/evidence/replay.py`** — inferred state trace walker (B3 absorb: "inferred/synthetic", not "exact recorded state"); annotates `replay_safe` per event; reports `state_source: inferred|synthetic|event`
- **`ao_kernel/_internal/evidence/manifest.py`** — manifest generator + verifier; canonical shape `manifest.json`: `{version: "1", run_id, generated_at, files: [{path, sha256, bytes}]}` (B1 absorb); scope: `events.jsonl` + `adapter-*.jsonl` + `artifacts/**/*.json` + `patches/*.revdiff` (B4 absorb); excludes `manifest.json`, `*.lock`, `*.tmp`
- **`ao_kernel/_internal/evidence/cli_handlers.py`** — argparse handler delegates to timeline/replay/manifest

- **`ao_kernel/executor/evidence_emitter.py` delta (B2 absorb):** 5 call site'ta `replay_safe=False` fix:
  - `Executor._run_adapter_step` → `adapter_invoked(replay_safe=False)`, `adapter_returned(replay_safe=False)`
  - `MultiStepDriver._emit` → `approval_granted(replay_safe=False)`, `approval_denied(replay_safe=False)`
  - `pr_opened` → `replay_safe=False` (PR-A6'da wiring; PR-A5 emitter default korunur ama docs + replay tool "effective replay_safe" taxonomy'si hazırlanır)

- **Tests:** ≥25 across `test_evidence_cli.py`:
  - timeline happy path (seeded events.jsonl → table output)
  - timeline with filters (kind, actor, limit)
  - timeline empty run → "no events"
  - timeline missing run → error
  - timeline --format json
  - replay inspect annotates replay_safe
  - replay dry-run walks state machine, reports illegal transition
  - generate-manifest creates manifest.json
  - verify-manifest all-match → exit 0
  - verify-manifest mismatch → exit non-zero
  - verify-manifest missing file → exit non-zero
  - generate-if-missing convenience
  - manifest idempotent overwrite

### Scope Dışı

| Alan | Nereye | Neden |
|---|---|---|
| Demo `.demo/` runnable script | PR-A6 | Release gate sonlayıcı |
| Production adapter fixtures | PR-A6 | Adapter manifests |
| Tutorial docs | PR-A6 | Adoption gate |
| `[coding]` meta-extra | PR-A6 | pyproject.toml extras |
| `[llm]` fallback intent classifier | PR-A6 | IntentRouter stub |
| Replay `full` mode (re-execution) | FAZ-B+ | Requires sandbox + budget + adapter re-invocation |
| Evidence streaming / watch mode | FAZ-B+ | Ops hardening scope |
| Evidence retention / cleanup | FAZ-B+ | Ops policy |
| Evidence export (Prometheus / OTEL) | FAZ-B | Metrics export scope |

### Bozulmaz İlkeler (korunur)

1. **Evidence append-only** — PR-A5 CLI **yalnızca okur**; JSONL'a yazmaz (manifest.json ayrı dosya, events.jsonl dokunulmaz).
2. **Per-run lock** — manifest generation sırasında `events.jsonl.lock` acquire edilir (concurrent emit ile çakışma önlenir); verify sırasında lock gereksiz (read-only).
3. **Manifest on-demand** — PR-A3 invariant korunur: emit sırasında manifest güncellenmez; CLI `generate-manifest` explicit çağrılır.
4. **18-kind taxonomy** — CLI yeni kind eklemez; timeline filter sadece mevcut kind'ları kabul eder.
5. **Opaque event_id** — CLI `seq` ile sıralar, event_id'yi opaque gösterir (sort by seq, not event_id).
6. **Redacted payloads** — CLI, evidence_emitter tarafından zaten redact edilmiş payload'ları okur; ek redaction yapmaz (double-redaction riski yok).
7. **POSIX-only** — manifest lock + atomic write POSIX (A3 invariant).
8. **Canonical JSON** — manifest.json `sort_keys=True, ensure_ascii=False, separators=(",",":")` (replay determinism).

---

## 3. Write Order

```
Layer 0 — Manifest generator (_internal)
  1. ao_kernel/_internal/evidence/manifest.py
     - generate_manifest(workspace_root, run_id) -> ManifestResult
     - verify_manifest(workspace_root, run_id) -> VerifyResult
     - ManifestResult dataclass (files, generated_at)
     - VerifyResult dataclass (files, all_match, mismatches)

Layer 1 — Evidence handlers (_internal, B5 absorb)
  2. ao_kernel/_internal/evidence/timeline.py
     - timeline(workspace_root, run_id, *, format, filter_kinds, filter_actor, limit) -> str
  3. ao_kernel/_internal/evidence/replay.py
     - replay(workspace_root, run_id, *, mode) -> ReplayReport
  4. ao_kernel/_internal/evidence/cli_handlers.py
     - cmd_timeline(args) / cmd_replay(args) / cmd_generate_manifest(args) / cmd_verify_manifest(args)

Layer 2 — CLI dispatcher delta
  5. ao_kernel/cli.py
     - `evidence` subcommand group: timeline, replay, generate-manifest, verify-manifest
     - argparse subparser registration

Layer 3 — Tests
  4. tests/test_evidence_cli.py (~25 tests)
  5. tests/fixtures/evidence/ (seeded events.jsonl + adapter log + artifact)

Layer 4 — Docs + CHANGELOG
  6. docs/EVIDENCE-TIMELINE.md §7/§8 CLI reference
  7. CHANGELOG.md [Unreleased] → FAZ-A PR-A5
```

---

## 4. CNS-025 Question Candidates

6 spec-level soru:

**Q1 — Timeline output format.** Default tablo `seq | ts | kind | actor | step_id | payload_summary` mi? payload_summary max kaç karakter (truncation)? `--format json` full event mi yoksa envelope-only mi?

**Q2 — Replay dry-run state machine walk.** 9-state machine transition'larını event stream'den nasıl reconstruct ediyoruz? `workflow_started` → state=running; `step_started/completed/failed` → step-level; `approval_requested/granted/denied` → waiting_approval/running/cancelled; `workflow_completed/failed` → terminal. Evidence'de explicit state transition event yok — state INFERRED mi?

**Q3 — Manifest scope.** `events.jsonl` + `adapter-*.jsonl` + `artifacts/*.json` — başka dosya var mı? `patches/*.revdiff` manifest kapsamında mı? (reverse-diff dosyaları evidence integrity scope'u mu yoksa workspace artifact scope'u mu?)

**Q4 — Verify-manifest concurrent write tolerance.** verify sırasında yeni event emit olursa (running workflow), manifest stale olur. Verify sadece manifest snapshot'taki dosyaları kontrol edip, post-manifest event'leri ignore mu? Yoksa "manifest outdated" uyarısı mı?

**Q5 — `evidence_cli.py` public module vs _internal.** Planın evidence_cli'yi public yapması doğru mu? Caller (non-CLI) programmatic kullanım: `from ao_kernel.evidence_cli import timeline, replay`. Yoksa `ao_kernel._internal/evidence/cli_handlers.py` + public yüzey sadece `ao_kernel.cli` mi?

**Q6 — PR-A5 test fixture strategy.** Integration test'ler seeded `events.jsonl` ile mi çalışır (deterministic fixture) yoksa real `EvidenceEmitter.emit_event` + real `MultiStepDriver.run_workflow` ile mi? Seeded fixture → hızlı + stable; real flow → gerçek end-to-end ama yavaş. Hangisi?

---

## 5. Audit Trail

| Field | Value |
|---|---|
| Plan version | **v2 (post CNS-025 iter-1 absorption)** |
| Head SHA | `0dfd742` |
| Base branch | `main` |
| Target branch | `claude/tranche-a-pr-a5` |
| CNS-025 thread | NEW (fresh MCP thread) |
| Total test target | 1510+ (1485 + ≥25) |
| Coverage gate | 85% |
| Core dep | `jsonschema>=4.23.0` unchanged |

| CNS-025 thread | `019d93d3-054f-7743-b166-e892d712ff88` |

**Status:** Plan v2 complete. Submit iter-2 via `mcp__codex__codex-reply`.
