# Support Boundary

This document is the narrative companion to [`PUBLIC-BETA.md`](PUBLIC-BETA.md).
When the two disagree, `PUBLIC-BETA.md` wins.

Use this page when you need to answer: "is this surface actually supported,
operator-only, or just contract inventory?"

## 1. Support layers

| Layer | Included surfaces | Verification |
|---|---|---|
| Shipped baseline | module entrypoints, `ao-kernel doctor`, bundled `review_ai_flow`, `examples/demo_review.py`, packaging smoke, `PRJ-KERNEL-API` `system_status` / `doc_nav_check` actions | entrypoint checks, doctor, demo review smoke, behavior tests, CI |
| Beta (operator-managed) | `claude-code-cli` helper-backed lane, `gh-cli-pr` helper-backed preflight + live-write readiness probe lane, real-adapter benchmark full mode | explicit smoke helpers and runbooks |
| Contract inventory | bundled defaults, manifests, extensions, example inventory | loader/validator and truth audit only |
| Deferred | `bug_fix_flow` release closure, live `gh-cli-pr` PR opening, roadmap/spec-only demo flow, adapter-path `cost_usd` reconcile | not a public support claim; internal benchmark/runtime wiring may exist without widening the support boundary |

### 1.1 Truth inventory to support mapping

`ao-kernel doctor` içindeki extension truth sınıfları support kararı için tek
başına yeterli değildir. Bu sınıfların support yorumu aşağıdaki gibi sabittir:

| Doctor truth tier | Support anlamı | Promotion kuralı |
|---|---|---|
| `runtime_backed` | Runtime handler + entrypoint bağlantısı vardır | Shipped/Beta claim için ek olarak behavior test + smoke + docs parity gerekir |
| `contract_only` | Manifest/contract katmanı vardır, runtime handler register değildir | Tek başına support claim üretmez; implementation tranche gerektirir |
| `quarantined` | Runtime owner/refs/entrypoint tarafında açık gap vardır | Support dışı kalır; yalnız karar/debt izleme yüzeyi olarak ele alınır |

Bu tablo, `docs/PUBLIC-BETA.md` ve status SSOT ile aynı anlamda okunur.

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
- real-adapter benchmark full-mode runbooks

`PB-6.6` closeout kararıyla `claude-code-cli` lane support-tier'i
`stay_beta_operator_managed` olarak korunur; lane shipped baseline'a yükselmez.

`gh-cli-pr` live-write probe, `PB-7.1` ile readiness amaçlı opt-in guard
katmanı kazanır. Bu probe'un varlığı tek başına live remote PR opening support
tier'ını widen etmez; public boundary satırı deferred kalır.

### Contract inventory

These may be bundled and schema-valid without being end-to-end supported:

- bundled adapter manifests
- bundled extensions and registry files
- `examples/hello-llm/`
- roadmap/spec documents

For `PRJ-KERNEL-API`, these actions remain outside the shipped support
boundary even though the extension has a minimum runtime-backed tranche:

- `project_status`
- `roadmap_follow`
- `roadmap_finish`

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

## 5. Related documents

- [`PUBLIC-BETA.md`](PUBLIC-BETA.md)
- [`OPERATIONS-RUNBOOK.md`](OPERATIONS-RUNBOOK.md)
- [`KNOWN-BUGS.md`](KNOWN-BUGS.md)
