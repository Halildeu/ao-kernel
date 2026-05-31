# AO-MA-4.6-1 — Native Worker Result Import (import-only, pure core)

**Faz:** AO-MA-4.6 (master plan §Faz 6) · **Dilim:** AO-MA-4.6-1 (pure core) · **Risk:** normal (schema + module + CLI + test; `.github`'a dokunmaz)
**Consultation:** CNS-20260601-001 · **Codex thread** `019e8000-e794-74c0-a47d-725b41da72a4` (4 tur REVISE → AGREE, ready_for_impl=true)

## Amaç

Master plan §Faz 6: "gerçek AI çıktısı (stub değil) — CLI-abonelik modeli ihlal
edilmeden". Operatör veya AI native arayüzde (claude-cli, codex-cli, mavis-cli)
worker_result.v1.json üretir; ao-kernel HİÇBİR ŞEY ÇAĞIRMAZ — sadece dosyayı
**import** eder, schema-validate eder, provenance-bind eder ve atomik kopyayı
canonical `<artifact_dir>/workers/<task_id>/worker_result.v1.json` konumuna yazar.
`live_adapter_execution=false` korunur. AO-MA-4.5 stub fixture aynen kalır.

## Mimari konum (worker_invoker / worker_runner / integrator paritesi)

`ao_kernel/orchestration/native_worker_import.py` PURE: no subprocess, no
network, no LLM, no GitHub. AST import-allowlist: hashlib, json, jsonschema,
pathlib, dataclasses, typing, re, __future__, collections + os (sadece
`os.fsync`). Bu yapısal garantidir; forbidden modül (subprocess/socket/
requests/httpx/urllib/asyncio.subprocess/os.popen/anthropic/openai/MCP/
mavis client) import edilemediği için spawn yüzeyi yoktur.

## Üretilenler (8 dosya)

- `ao_kernel/defaults/schemas/ao-ma-native-worker-import-report.schema.v1.json` — Draft 2020-12, additionalProperties:false, 3 guard const false, register_authority const "evidence_record_only", github_write_authorized const false, execution_performed_by_ao_kernel const false, ai_output_release_authority const false. `if validation_status=valid then valid=true + integrated_path != null + integrated_sha != null` ve `if invalid then valid=false + integrated_path=null + integrated_sha=null` (allOf if/then).
- `ao_kernel/orchestration/native_worker_import.py` — PURE compiler+verifier:
  - `NativeWorkerImportError` — fatal trust-boundary exception
  - `import_native_worker_result(...)` — fatal raise / reportable invalid report / valid report + atomik copy
  - `verify_import_binding(...)` — recompute-not-trust her şey
  - Helper'lar: `_compute_sha256`, `_load_json_or_fatal`, `_validate_or_fatal`, `_validate_manifest_envelope_or_fatal` (worker_runner mantığı kopya — AST allowlist daraltma), `_find_manifest_entry`, `_find_runner_entry`, `_canonical_integrated_path`, `_atomic_write_bytes`, `_check_pass`/`_check_fail`/`_finding`, `_recompute_valid`, `_redact` (notifier-grade)
- `ao_kernel/orchestration/cli_handlers.py` (genişletme) — `cmd_orchestration_native_import` + `add_orchestration_subparser` içine `native-import` subcommand
- `ao_kernel/cli.py` (genişletme) — dispatch `native-import` eklendi
- `tests/test_ao_ma_4_6_native_import_purity.py` — AST allowlist + forbidden module + os.* attribute denylist
- `tests/test_ao_ma_4_6_native_import.py` — fatal/reportable/happy path 40+ test
- `.claude/plans/AO-MA-4-6-NATIVE-IMPORT.md` (bu doc)
- `local-ai-review-evidence.v1.json`

## İki hata sınıfı (Codex iter-3/4 absorb)

### Fatal trust-boundary (NativeWorkerImportError, NO import_report, NO copy)

- source file missing/unreadable/JSON parse fail
- worker_result schema-invalid (Draft 2020-12 + worker_result.v1; guard 3 const false + no_secret_attestation.secrets_recorded const false zaten schema boundary'sinde, ihlal = schema-invalid)
- runner_report load/parse/schema-invalid
- manifest load/parse/envelope-invalid OR sha mismatch with `runner_report.manifest_sha256`
- task_graph load/parse/schema-invalid OR sha mismatch with manifest entry
- assignment load/parse/schema-invalid OR sha mismatch with manifest OR sha mismatch with `runner_entry.assignment_sha256`
- runner entry missing for task_id
- cross-id mismatch (`task_graph_id` / `task_id` / `assignment_id`)
- artifact_dir caller-supplied ≠ `runner_report_path.parent.resolve()` (kanonik derivation tek source-of-truth)
- imported_at RFC3339 değil

### Reportable policy-invalid (schema-valid import_report, valid=false, no copy)

- source_interface not in effective allowlist
- source_interface ↔ worker_provider mismatch (claude-cli↔anthropic, codex-cli↔openai, mavis-cli↔minimax, local-file↔{local,tool})
- runner_entry.status not in {prepared, skipped_existing_idempotent}
- declared_write_set mismatch across worker_result/assignment/task_graph
- actual_changed_files non-subset of declared_write_set
- actual_changed_files empty
- known_gaps non-empty (4.6-1; downstream 4.6-2'de finding)
- existing integrated file different sha (overwrite YASAK; aynı sha idempotent OK)

## Fail-closed / recompute-not-trust invariant'ları

1. **manifest anchoring kritik**: `artifact_dir = runner_report_path.parent.resolve()` kanonik tek source-of-truth; manifest envelope validate (worker_runner mantığı kopyalı); sha bind chain manifest↔runner_report↔task_graph↔assignment her seviyede.
2. **cross-id chain**: `worker_result.task_graph_id == runner_report.task_graph_id == manifest.task_graph_id == task_graph.task_graph_id == assignment.task_graph_id`; `task_id` ve `assignment_id` chain'i.
3. **cross-ref chain** (reportable; build içinde): base_ref, base_sha, head_ref, branch eşleştirme.
4. **declared_write_set set-equality** (build içinde): worker_result == assignment == task_graph_tasks[task_id].
5. **actual ⊆ declared** + **actual non-empty** + **known_gaps empty** invariant'ları.
6. **canonical_integrated_path resolve under artifact_dir** (symlink escape reject).
7. **existing integrated different hash → refuse replace** (atomic — Path.replace YOK; reportable).
8. **valid flag her zaman recompute** (`_recompute_valid(checks)`; forged valid=true verify'da reject).
9. **head_sha not_git_recomputed** her zaman warning finding (audit transparency; pure-import mode git çağırmaz).
10. **3 guard + register_authority + github_write_authorized + execution_performed_by_ao_kernel + ai_output_release_authority** const-pin schema'da + verify'da drift check.

## Atomic copy

`_atomic_write_bytes`: tmp file write + `os.fsync(fileno)` + `tmp.replace(target)`. Existing target different hash → reportable invalid, replace yapılmaz. Aynı hash → idempotent OK (path + sha report'a yazılır).

## Secret-safe (notifier-grade redaction)

`_redact` 10 pattern: ghp_/github_pat_/sk-/sk-proj-/sk-ant-/xox*/Bearer/JWT/webhook URLs/Office hooks. Check `message` + finding `message` her ikisi redact pipeline'ından geçer.

## Self-hosting (master plan §6 acceptance zinciri)

11G PR'da (sonraki/son faz) operator Claude native arayüzü ile worker_result.v1.json üretecek (worker.provider=anthropic, guard 3 const false); `ao-kernel orchestration native-import --result <path> --runner-report <path> --source-interface claude-cli --imported-at <ts> --out 11g-native-import-report.v1.json` ile import edilecek; canonical integrated path 11G evidence chain'ine girecek; Codex/OpenAI cross-provider review eder; verifier/integrator integrated path'i tüketir.

## CLI

```
ao-kernel orchestration native-import \
  --result <source_worker_result_path> \
  --runner-report <runner_report.v1.json path> \
  --source-interface {claude-cli|codex-cli|mavis-cli|local-file} \
  [--imported-at <RFC3339 UTC>] \
  [--artifact-dir <path; default runner_report.parent.resolve()>] \
  [--allow-source-interface <name> ...] \
  --out <import_report path>
```

Exit codes:
- 0 — valid=true import_report, integrated copy written
- 1 — valid=false reportable invalid OR fatal NativeWorkerImportError (no report)

CLI thin wrapper modüle call eder. RI-7.8c uyumu: `--adapter`, `--prompt`, `--model`, `--api-key`, `--url`, `--pr-write` parametreleri tanımlı DEĞİL — argparse bilinmeyen flag verilirse SystemExit verir.

## Cross-AI review

Implementer: Claude (Anthropic). Reviewer: Codex (OpenAI) thread `019e8000` —
plan-time iter-1 REVISE (3 must-close + 8 invariant) → iter-2 REVISE (6 must-close)
→ iter-3 REVISE (schema-invalid fatal vs guard-open reportable çelişkisi) →
**iter-4 AGREE** (ready_for_impl=true, 4 mekanik düzeltme absorb). Post-impl review iter ile authoritative contract verify.

## Kanıt

- **105 test PASS** (100 functional + 5 AST purity), native_worker_import.py **%86.00 branch** (gate %85+; 529 stmt, 264 branch)
- full suite 5106+/0 fail/0 error/76 skipped
- 1 yeni schema Draft 2020-12 valid; ruff + mypy strict temiz (264 src file)
- AST import-allowlist (hashlib/json/jsonschema/pathlib/dataclasses/typing/re/__future__/collections + os.fsync)
- 3 guard flag + execution_performed_by_ao_kernel + ai_output_release_authority const false
- `live_adapter_execution=false` korunur
- Cross-AI 4-tur post-impl: AGREE (`ready_for_autonomous_merge=true`, Codex thread `019e8028`)

## Sonraki (4.6-2)

- Operator runbook (claude-code-cli/codex-cli/mavis-cli native worker_result production)
- Real-world dogfooding (11G operator-produced worker_result import)
- git_diff_evidence operator artifact (ayrı slice; bu 4.6-1 input olarak alabilir)
- Live adapter execution (ayrı operator-bound GPP supersession)
