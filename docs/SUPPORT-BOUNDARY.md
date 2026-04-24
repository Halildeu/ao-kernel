# Support Boundary

This document is the narrative companion to [`PUBLIC-BETA.md`](PUBLIC-BETA.md).
When the two disagree, `PUBLIC-BETA.md` wins.

Use this page when you need to answer: "is this surface actually supported,
operator-only, or just contract inventory?"

## 1. Support layers

| Layer | Included surfaces | Verification |
|---|---|---|
| Shipped baseline | module entrypoints, `ao-kernel doctor`, bundled `review_ai_flow`, `examples/demo_review.py`, packaging smoke, `PRJ-KERNEL-API` `system_status` / `doc_nav_check` actions | entrypoint checks, doctor, demo review smoke, behavior tests, CI |
| Beta (operator-managed) | `claude-code-cli` helper-backed lane, `gh-cli-pr` helper-backed preflight + live-write readiness probe lane, `PRJ-KERNEL-API` write-side actions (`project_status`, `roadmap_follow`, `roadmap_finish`) with explicit write contract, real-adapter benchmark full mode | explicit smoke helpers and runbooks |
| Contract inventory | bundled defaults, manifests, extensions, example inventory | loader/validator and truth audit only |
| Deferred | `bug_fix_flow` release closure, live `gh-cli-pr` PR opening, roadmap/spec-only demo flow, adapter-path `cost_usd` reconcile | not a public support claim; internal benchmark/runtime wiring may exist without widening the support boundary (`PB-8.3` verdict `stay_deferred`, `GP-1.3` revalidation ile teyitli) |

### 1.1 ST-2 stable boundary freeze

For `4.0.0` stable, the stable support set is the `Shipped baseline` layer
only. This freeze deliberately excludes:

- operator-managed beta lanes,
- live-write / remote side-effect flows,
- contract inventory without behavior evidence,
- roadmap/spec-only walkthroughs,
- deferred support claims.

`ST-3` real-adapter certification and `ST-4` live-write rollback rehearsal are
not blockers for a narrow stable runtime release as long as stable docs do not
claim those surfaces. They become blockers only if a future PR tries to promote
real adapters or live-write behavior into stable shipped support.

There is currently no known bug that blocks the shipped baseline. The known
bugs in [`KNOWN-BUGS.md`](KNOWN-BUGS.md) affect operator-managed beta lanes.

### 1.2 Truth inventory to support mapping

`ao-kernel doctor` içindeki extension truth sınıfları support kararı için tek
başına yeterli değildir. Bu sınıfların support yorumu aşağıdaki gibi sabittir:

| Doctor truth tier | Support anlamı | Promotion kuralı |
|---|---|---|
| `runtime_backed` | Runtime handler + entrypoint bağlantısı vardır | Shipped/Beta claim için ek olarak behavior test + smoke + docs parity gerekir |
| `contract_only` | Manifest/contract katmanı vardır, runtime handler register değildir | Tek başına support claim üretmez; implementation tranche gerektirir |
| `quarantined` | Runtime owner/refs/entrypoint tarafında açık gap vardır | Support dışı kalır; yalnız karar/debt izleme yüzeyi olarak ele alınır |

Bu tablo, `docs/PUBLIC-BETA.md` ve status SSOT ile aynı anlamda okunur.
`PB-9.2` debt sıralama kuralları için tek karar kaynağı:
`.claude/plans/PB-9.2-TRUTH-INVENTORY-DEBT-RATCHET.md`.
Bu ratchet tablosu support widening kararı vermez; yalnız debt işlem sırasını
deterministik hale getirir.
Canlı ratchet raporu `python3 scripts/truth_inventory_ratchet.py --output json`
ile tekrar üretilebilir.

## 2. Current line by line boundary

### Shipped baseline

The repo currently supports these as the default claim:

- `ao-kernel version`
- `python -m ao_kernel version`
- `python -m ao_kernel.cli version`
- `ao-kernel doctor`
- bundled `review_ai_flow` + bundled `codex-stub`
- `python3 examples/demo_review.py --cleanup`
- `PRJ-KERNEL-API` runtime-backed action: `system_status`
- `PRJ-KERNEL-API` runtime-backed action: `doc_nav_check`

### Beta (operator-managed)

These are real, testable surfaces, but they are not the default shipped demo:

- `python3 scripts/claude_code_cli_smoke.py --output text`
- `python3 scripts/gh_cli_pr_smoke.py --output text`
- `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head <branch> --base <branch>`
- `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --head <branch> --base <branch> --output json --report-path <artifact.json>`
- `python3 scripts/kernel_api_write_smoke.py --output text`
- `PRJ-KERNEL-API` write-side actions (`project_status`, `roadmap_follow`, `roadmap_finish`) with explicit `workspace_root`, default `dry_run=true`, and `confirm_write=I_UNDERSTAND_SIDE_EFFECTS` for real writes
- real-adapter benchmark full-mode runbooks

Operator prerequisite contract (PB-9.1):

1. `claude-code-cli` lane için belirleyici komut
   `python3 scripts/claude_code_cli_smoke.py --output text` olup
   `overall_status: pass` dönmelidir; bu report içinde `auth_status` ve
   `prompt_access` birlikte geçmelidir.
2. `gh-cli-pr` preflight lane için `gh` binary + aktif auth + repo context
   (`gh repo view`) çözümü gerekir; preflight side-effect-safe dry-run zinciridir.
3. `gh-cli-pr` live-write probe yalnız explicit
   `--mode live-write --allow-live-write --head ... --base ...` ile açılır.
4. Live-write probe varsayılan disposable guard keyword `sandbox` uygular;
   repo adı bu keyword'ü içermiyorsa lane bilerek `blocked` olur.
5. `--keep-live-write-pr-open` lane'i bilinçli riskli kabul ettirir ve
   support widening sinyali üretmez.

`PB-6.6` closeout kararıyla `claude-code-cli` lane support-tier'i
`stay_beta_operator_managed` olarak korunur; lane shipped baseline'a yükselmez.

`gh-cli-pr` live-write probe, `PB-8.1` ile explicit precondition (opt-in,
disposable repo, explicit `--head` + `--base`) ve create -> verify -> rollback
zincirine taşınmıştır. `--keep-live-write-pr-open` seçeneği lane'i riskli kabul
eder ve rapor `blocked` döner. Bu probe'un varlığı tek başına live remote PR
opening support tier'ını widen etmez; public boundary satırı deferred kalır.

`PB-9.4` closeout kararı `stay_beta_operator_managed` olduğu için bu satırların
support tier'i widening almadan korunur.

`PB-8.3` ile `bug_fix_flow` içindeki `open_pr` adımı ayrıca workflow-level
explicit opt-in guard (`AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1`) arkasına
alınmıştır. `GP-1.3` re-evaluation, bu durumun kararını değiştirmemiştir.
Guard accidental side-effect riskini düşürür, fakat tek başına support boundary
widening kararı üretmez; lane deferred kalır.

### Contract inventory

These may be bundled and schema-valid without being end-to-end supported:

- bundled adapter manifests
- bundled extensions and registry files
- `examples/hello-llm/`
- roadmap/spec documents

`PRJ-KERNEL-API` write-side actions runtime-backed olsa da shipped baseline
değildir; support tier yalnız Beta (operator-managed) satırı kadar genişler.
`PRJ-CONTEXT-ORCHESTRATION` için `GP-1.4` kararı `stay_contract_only` olduğu
için bu extension contract inventory katmanında kalır; support widening yoktur.
`GP-1.5` program closeout kararı da boundary'yi widen etmemiştir; genel çizgi
`stay_beta_operator_managed` olarak korunur.

## 3. What does NOT automatically widen support

The following do not, by themselves, justify a broader support claim:

- a manifest file existing in `ao_kernel/defaults/`
- a runbook describing an operator flow
- a roadmap/spec document
- a contract loader or truth-audit warning surface
- a smoke passing only in one operator environment without the support docs
  being updated

## 4. Operational rule

If a surface is not simultaneously backed by:

1. a real code path,
2. a behavior check or smoke,
3. the relevant CI or explicit operator validation path,
4. the matching support doc wording,

then treat it as not widened.

## 4.1 Stable operations rule

For the narrow stable release, operational readiness follows the same support
boundary:

- shipped baseline failure is a release blocker,
- beta/operator-managed failure is handled through smoke output and
  `KNOWN-BUGS.md`,
- deferred support claims do not become stable because a runbook exists,
- publish readiness requires the same wheel-installed smoke used by CI.

## 5. Related documents

- [`PUBLIC-BETA.md`](PUBLIC-BETA.md)
- [`OPERATIONS-RUNBOOK.md`](OPERATIONS-RUNBOOK.md)
- [`KNOWN-BUGS.md`](KNOWN-BUGS.md)
