# Support Boundary

This document is the narrative companion to [`PUBLIC-BETA.md`](PUBLIC-BETA.md).
When the two disagree, `PUBLIC-BETA.md` wins.

Use this page when you need to answer: "is this surface actually supported,
operator-only, or just contract inventory?"

## 1. Support layers

| Layer | Included surfaces | Verification |
|---|---|---|
| Shipped baseline | module entrypoints, `ao-kernel doctor`, bundled `review_ai_flow`, `examples/demo_review.py`, packaging smoke, `PRJ-KERNEL-API` `system_status` / `doc_nav_check` actions | entrypoint checks, doctor, demo review smoke, behavior tests, CI |
| Beta (operator-managed) | `claude-code-cli` helper-backed lane, `gh-cli-pr` helper-backed preflight + live-write readiness probe lane, `PRJ-KERNEL-API` write-side actions (`project_status`, `roadmap_follow`, `roadmap_finish`) with explicit write contract, real-adapter benchmark full mode, experimental read-only `repo scan` | explicit smoke helpers, runbooks, and schema-backed local artifacts |
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
- `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head <branch> --base <branch>`
- `python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head <branch> --base <branch> --output json --report-path <artifact.json>`
- `python3 scripts/kernel_api_write_smoke.py --output text`
- `PRJ-KERNEL-API` write-side actions (`project_status`, `roadmap_follow`, `roadmap_finish`) with explicit `workspace_root`, default `dry_run=true`, and `confirm_write=I_UNDERSTAND_SIDE_EFFECTS` for real writes
- real-adapter benchmark full-mode runbooks
- `python3 -m ao_kernel repo scan --project-root . --output json` for
  experimental read-only repo intelligence artifacts under `.ao/context/`,
  including Python AST-derived import graph, top-level symbol index outputs,
  deterministic chunk manifest, and a deterministic Markdown agent context pack

Operator prerequisite contract (PB-9.1):

1. `claude-code-cli` lane için belirleyici komut
   `python3 scripts/claude_code_cli_smoke.py --output text` olup
   `overall_status: pass` dönmelidir; bu report içinde `auth_status` ve
   `prompt_access` birlikte geçmelidir.
2. `gh-cli-pr` preflight lane için `gh` binary + aktif auth + repo context
   (`gh repo view`) çözümü gerekir; preflight side-effect-safe dry-run zinciridir.
3. `gh-cli-pr` live-write probe yalnız explicit
   `--mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head ... --base ...`
   ile açılır.
4. Live-write probe varsayılan disposable guard keyword `sandbox` uygular;
   repo adı bu keyword'ü içermiyorsa lane bilerek `blocked` olur.
5. `--keep-live-write-pr-open` lane'i bilinçli riskli kabul ettirir ve
   support widening sinyali üretmez.

`PB-6.6` closeout kararı, `GP-2.4d` certification verdict'i ve `GP-3.6`
program closeout ile `claude-code-cli` lane support-tier'i Beta/operator-managed
olarak korunur. `GP-3.6` final sonucu `close_keep_operator_beta` olduğundan
lane shipped baseline'a veya production-certified read-only tier'ına yükselmez.
Fresh preflight ve governed workflow smoke geçmiştir; promotion yine de
reddedilmiştir çünkü external `claude` binary/session auth operatör durumudur,
`KB-001`/`KB-002` açıktır ve live adapter gate'i CI-managed değildir.
`GP-4` bu eksik CI-managed live adapter gate'i tasarlar, fakat tasarım kaydı
tek başına support tier'ı yükseltmez.
`GP-4.1` ile eklenen `live-adapter-gate` workflow skeleton'ı da support
widening değildir: sadece manual contract artifact üretir, canlı `claude`
çağrısı yapmaz ve artifact içinde `overall_status="blocked"` /
`finding_code="live_gate_not_implemented"` beklenir.
`GP-4.2` bu gate'e schema-backed `live-adapter-gate-evidence.v1.json` artifact
contract'ını ekler. Artifact, preflight/workflow-smoke/protected-environment
kanıt slotlarını promotion blocker olarak listeler; yine canlı adapter çağrısı,
secret okuma veya support widening içermez.
`GP-4.3` ayrıca `live-adapter-gate-environment-contract.v1.json` artifact'ini
ekler. Bu contract required protected environment adını
`ao-kernel-live-adapter-gate`, required secret handle adını
`AO_CLAUDE_CODE_CLI_AUTH` olarak kaydeder; secret değeri commit etmez,
environment oluşturmaz ve artifact hâlâ `live_execution_allowed=false` /
`support_widening=false` döner.
`GP-4.4` `live-adapter-gate-rehearsal-decision.v1.json` artifact'ini ekler.
Mevcut karar `blocked_no_rehearsal`dir; protected environment ve
project-owned credential attested olmadığı için canlı rehearsal denenmez,
workflow environment'a bağlanmaz ve support widening yapılmaz.
`GP-4.5` closeout kararı `close_no_widening_keep_operator_beta` olarak
kapanmıştır. Bu karar `claude-code-cli` lane'ini `Beta (operator-managed)`
katmanında tutar; production-certified real-adapter support ve genel amaçlı
production platform claim'i verilmez.

`gh-cli-pr` live-write probe, `PB-8.1` ile explicit precondition (opt-in,
disposable repo, explicit `--repo` + `--head` + `--base`) ve create -> verify
-> rollback zincirine taşınmıştır. `GP-2.5a` disposable sandbox rehearsal
geçmiştir; created PR verify edildikten sonra rollback ile kapatılmış ve head
branch cleanup doğrulanmıştır. `--keep-live-write-pr-open` seçeneği lane'i
riskli kabul eder ve rapor `blocked` döner. Bu probe'un varlığı tek başına live
remote PR opening support tier'ını widen etmez; public boundary satırı deferred
kalır.

`PB-9.4` closeout kararı `stay_beta_operator_managed` olduğu için bu satırların
support tier'i widening almadan korunur.

The `repo scan` surface is Beta / experimental and read-only. It may write only
schema-backed local artifacts under `.ao/context/`: `repo_map.json`,
`import_graph.json`, `symbol_index.json`, `repo_chunks.json`, `agent_pack.md`,
and `repo_index_manifest.json`. It does not create root authority files such as
`CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, or `CODEX_CONTEXT.md`, and does not
include embedding calls, vector writes, LLM summaries, MCP tools,
target-specific exports, or root context-pack export.

The `repo index --dry-run` surface is Beta / experimental dry-run only. It reads
`.ao/context/repo_chunks.json` and may write only
`.ao/context/repo_vector_write_plan.json`. The write-plan records deterministic
repo chunk vector keys, planned upserts, planned stale-key deletes, and embedding
space identity. It does not call an embedding provider, connect to a vector
backend, write vectors, use network access, expose an MCP tool, or write root
authority files.

The `repo index --write-vectors` surface is Beta / experimental explicit-write
only. It requires
`--confirm-vector-index I_UNDERSTAND_REPO_VECTOR_WRITES`, a configured vector
backend, and an embedding API key. It may write only
`.ao/context/repo_vector_write_plan.json` and
`.ao/context/repo_vector_index_manifest.json`, plus records in the configured
vector backend under the `repo_chunk::<project_identity>::<embedding_space>::`
namespace. It deletes stale keys only inside the same recorded project identity
and embedding space. It does not write root authority files, expose MCP tools,
or provide retrieval integration.

The `repo query` surface is Beta / experimental read-only retrieval. It reads
`.ao/context/repo_vector_index_manifest.json` and the configured vector backend,
requires an embedding API key to embed the query, and returns only candidates
that match the recorded `repo_chunk::<project_identity>::<embedding_space>::`
namespace plus repo chunk metadata. It validates current source line ranges and
content hashes before returning snippets, and excludes stale candidates by
default. The optional Markdown output is a stdout-only, agent-readable preview
of the same query result and carries an explicit handoff contract: operators
must copy or supply it as visible agent input. It does not write root authority
files, `.ao/context` artifacts, vector backend records, expose MCP tools, or
feed `context_compiler` automatically.

`GP-5.3d` pins this negative boundary with regression tests: no
repo-intelligence MCP tool is registered, the `repo` CLI surface remains
limited to `scan`, `index`, and `query`, and `repo query` does not create root
authority exports, MCP config exports, or `.ao/context/repo_export_plan.json`.

`GP-5.3e` promotes this surface only to a beta explicit-handoff workflow
building block: a future GP-5 read-only workflow rehearsal may use
`repo query --output markdown` when the operator supplies that Markdown as
visible input. This is not production workflow integration and does not add
automatic prompt injection, MCP tools, root exports, workflow runtime wiring,
`context_compiler` auto-feed, or real-adapter support widening.

`GP-5.4a` adds a deterministic read-only rehearsal command,
`python3 scripts/gp5_read_only_rehearsal.py --output json`. It builds a
schema-backed report, installs the current wheel in a temporary virtualenv, and
runs `review_ai_flow + codex-stub` with explicit repo-intelligence Markdown
supplied through `--intent-file`. This is still beta rehearsal evidence only:
`support_widening=false`, no live real adapter, no MCP/root export, no
`context_compiler` auto-feed, and no write-side support.

`GP-5.5a` adds only the controlled patch/test design contract,
`gp5-controlled-patch-test-contract.schema.v1.json`. The contract requires a
disposable or dedicated worktree, path-scoped ownership, diff preview, explicit
apply decision, explainable targeted tests with full-gate fallback, rollback
verification, cleanup evidence, and an incident/runbook reference. It records
`support_widening=false`, `runtime_patch_application_enabled=false`,
`remote_side_effects_allowed=false`, and `active_main_worktree_allowed=false`.
This is not runtime write support widening and does not promote live remote PR
creation or real-adapter live-write support.

`GP-5.5b` adds the first controlled local patch/test rehearsal command,
`python3 scripts/gp5_controlled_patch_test_rehearsal.py --approve-apply --output json`.
It creates a disposable detached worktree, previews a deterministic patch,
requires explicit apply approval, acquires path-scoped apply and rollback
claims, runs a targeted verification command, rolls back through the reverse
diff, verifies rollback idempotency, and removes the worktree. The report is
validated by `gp5-controlled-patch-test-rehearsal-report.schema.v1.json` and
records `support_widening=false`, `runtime_patch_support_widening=false`,
`remote_side_effects_allowed=false`, and `active_main_worktree_touched=false`.
This is rehearsal evidence only. It does not make arbitrary patch generation,
live remote PR creation, real-adapter live-write, or production write-side
support shipped.

`GP-5.6a` adds the first disposable PR write rehearsal wrapper,
`python3 scripts/gp5_disposable_pr_write_rehearsal.py`. It requires a passing
GP-5.5b local rehearsal report before any remote write and only runs live with
explicit `--allow-live-write` against a `sandbox`-guarded repo. Its report is
validated by `gp5-disposable-pr-write-rehearsal-report.schema.v1.json` and
records `support_widening=false`, `production_remote_pr_support=false`, and
`arbitrary_repo_support=false`. This does not make full remote PR opening a
stable shipped support surface.

`GP-5.7a` adds the full production rehearsal contract
`gp5-full-production-rehearsal-contract.schema.v1.json`. It requires the future
execution slice to prove the complete issue/task -> repo intelligence ->
explicit context handoff -> adapter reasoning -> patch plan -> controlled
patch/test -> disposable PR rehearsal -> rollback/closeout chain with at least
three clean rehearsals and one fail-closed rehearsal. The contract records
`support_widening=false` and `production_platform_claim=false`; it is not the
execution itself and does not make `ao-kernel` a general-purpose production
coding automation platform.

The bundled
`repo-intelligence-workflow-context-opt-in.schema.v1.json` is a contract-only
future opt-in shape. It is not wired into workflow definitions, executor
runtime, MCP, root exports, or `context_compiler` in the shipped runtime.

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
- a CI/live-gate design document without a protected implementation and
  recorded evidence artifacts
- a CI-safe live-gate skeleton that emits a blocked contract artifact without
  executing a protected live adapter identity
- a schema-valid live-gate evidence artifact that still marks required live
  evidence slots as blocked and `support_widening=false`
- a support-boundary closeout decision that explicitly records blocked live
  rehearsal evidence and keeps support unchanged
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
