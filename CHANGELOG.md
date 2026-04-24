# Changelog

All notable changes to ao-kernel are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `gh-cli-pr` smoke helper now passes repo overrides to `gh repo view` as the
  positional repository argument supported by current GitHub CLI versions. The
  regression is pinned by `tests/test_gh_cli_pr_smoke.py`.

### Changed

- Added agent-readable Markdown output for the RI-4 repo query boundary via
  `repo query --output markdown`. The output is stdout-only and keeps the same
  read-only support boundary: no root exports, `.ao/context` artifact writes,
  vector writes, MCP exposure, or `context_compiler` auto-injection.
- Added the RI-4d read-only `repo query` boundary over explicit repo vector
  indexes. The new surface requires an existing vector index manifest,
  configured vector backend, and embedding API key; it returns schema-backed
  repo chunk candidates without vector writes, `.ao/context` artifact writes,
  MCP exposure, root exports, or `context_compiler` auto-injection.
- Recorded the `GP-2.5a` disposable sandbox live-write rehearsal evidence:
  `gh-cli-pr` created, verified, closed, and cleaned up a draft PR in
  `Halildeu/ao-kernel-sandbox`. This does not widen the stable support
  boundary; full remote PR opening remains outside the shipped baseline.
- Added the `GP-2` parent closeout decision record. The deferred support-lane
  reprioritization program is complete, with no automatic stable support
  widening for `claude-code-cli`, `gh-cli-pr`, `bug_fix_flow`, or adapter-path
  `cost_usd`.
- Added the `SM-1` stable maintenance baseline decision record and aligned the
  operator-facing `gh-cli-pr` live-write prerequisite prose with the explicit
  sandbox `--repo` requirement.
- Added the `SM-2` stable baseline evidence refresh, recording entrypoint,
  doctor, truth inventory, wheel-installed packaging smoke, and targeted test
  results without runtime changes or support widening.
- Added the `SM-3` program-status cleanup, removing stale historical `ST-2`
  wording from the living status board while keeping stable maintenance / no
  active widening as the current mode.
- Added the `SM-4` historical beta pin wording cleanup, clarifying that
  `4.0.0b2` is an intentional historical Public Beta pre-release path while
  stable `4.0.0` remains the default user and rollback path.
- Opened the `GP-3` production-certified adapter promotion roadmap. The first
  candidate lane is `claude-code-cli` read-only governed workflow, but this
  roadmap does not widen support without later evidence gates.
- Recorded the `GP-3.1` `claude-code-cli` prerequisite truth refresh. Live
  preflight and governed workflow smoke both passed, but the lane remains
  `Beta (operator-managed)` until repeatability, failure-mode, evidence,
  runbook, docs, and support-boundary gates close.
- Recorded the `GP-3.2` `claude-code-cli` governed workflow repeatability
  evidence: three independent read-only workflow smoke runs passed with
  `completed` final state, required evidence events, `review_findings`
  artifact, redacted adapter log, and schema validation. This does not widen
  support; failure-mode classification remains next.
- Recorded the `GP-3.3` `claude-code-cli` failure-mode matrix. The helper and
  governed workflow smoke now explicitly pin malformed auth status JSON,
  malformed manifest JSON missing `status`, and workflow adapter timeout as
  fail-closed promotion blockers, with operator-facing failure codes aligned in
  the real-adapter runbook.
- Recorded the `GP-3.4` `claude-code-cli` evidence completeness gate. The
  governed workflow smoke now checks canonical event order and semantic
  `review_findings` contents, pins adapter-log secret-like leaks as failures,
  and keeps adapter-path `cost_usd` / token usage as an explicit non-claim.
- Recorded the `GP-3.5` `claude-code-cli` support-boundary decision. Fresh
  preflight and governed workflow smoke passed, but the final verdict remains
  `keep_operator_beta`; no stable support widening, version bump, tag, or
  publish is included.
- Closed the `GP-3` production-certified adapter promotion program with final
  verdict `close_keep_operator_beta`. The first real-adapter lane remains
  evidence-backed operator-managed beta, but no production-certified
  real-adapter support claim or general-purpose production platform claim is
  granted.
- Opened the `GP-4` CI-managed live adapter gate design program. This records
  the missing gate required before future real-adapter production support can
  be reconsidered; it adds no secrets, live default CI calls, runtime changes,
  version bump, tag, publish, or support widening.
- Added the `GP-4.1` CI-safe live adapter gate skeleton. The new manual
  `live-adapter-gate` workflow emits a blocked
  `live-adapter-gate-contract.v1.json` artifact and deliberately performs no
  secret access, live adapter execution, version bump, tag, publish, or support
  widening.
- Added the `GP-4.2` live adapter evidence artifact contract. The manual
  `live-adapter-gate` workflow now also emits schema-backed
  `live-adapter-gate-evidence.v1.json`, with required live preflight,
  governed workflow-smoke, and protected-environment evidence slots recorded as
  blocked promotion gates. This still performs no secret access, live adapter
  execution, version bump, tag, publish, or support widening.
- Added the `GP-4.3` protected environment / secret contract. The manual
  `live-adapter-gate` workflow now also emits schema-backed
  `live-adapter-gate-environment-contract.v1.json`, naming the required
  `ao-kernel-live-adapter-gate` protected environment and
  `AO_CLAUDE_CODE_CLI_AUTH` secret handle without committing secret values,
  binding a live environment, calling `claude`, or widening support.
- Added the `GP-4.4` protected live rehearsal blocked decision. The manual
  `live-adapter-gate` workflow now also emits schema-backed
  `live-adapter-gate-rehearsal-decision.v1.json` with
  `decision="blocked_no_rehearsal"` because the protected environment and
  project-owned credential are not attested; it still does not bind a live
  environment, call `claude`, or widen support.
- Closed the `GP-4` CI-managed live adapter gate design program with
  `GP-4.5` verdict `close_no_widening_keep_operator_beta`. `claude-code-cli`
  remains `Beta (operator-managed)`; production-certified real-adapter support,
  stable support widening, general-purpose production platform claims, version
  bump, tag, publish, secret access, workflow environment binding, and live
  `claude` invocation are all explicitly not included.

## [4.0.0] - 2026-04-24

### Changed — Stable release candidate

`v4.0.0` prepares the narrow stable runtime line from the proven `4.0.0b2`
Public Beta baseline. This release candidate does **not** claim that
ao-kernel is a general-purpose production coding automation platform. It makes
the governed runtime baseline stable while keeping beta and deferred lanes
outside the stable support boundary.

- Stable shipped baseline remains narrow:
  - CLI/module entrypoints
  - `ao-kernel doctor`
  - bundled `review_ai_flow` + bundled `codex-stub`
  - `examples/demo_review.py`
  - policy command enforcement
  - wheel-installed packaging smoke
  - documented read-only `PRJ-KERNEL-API` actions
- Added and closed the stable gate sequence:
  - `ST-2` stable support boundary freeze
  - `ST-5` deferred correctness closure
  - `ST-6` operations readiness
  - `ST-7` stable release candidate contract
- Clarified upgrade, rollback, known-bugs, and operations docs so stable
  checks do not fall back to beta/operator-managed lanes.
- Operator-managed lanes remain outside stable support:
  - `claude-code-cli`
  - `gh-cli-pr`
  - `PRJ-KERNEL-API` write-side actions
  - real-adapter benchmark full mode
- Deferred lanes remain deferred:
  - `bug_fix_flow` release closure
  - full remote PR opening
  - roadmap/spec demo widening
  - adapter-path `cost_usd` as a public support claim
- Known bugs currently affect operator-managed beta lanes only; there is no
  known shipped-baseline blocker.
- Legacy `save_store()` and `allow_overwrite=True` compatibility is retained
  for this narrow stable line. Their deprecation text now targets a future
  major release instead of promising removal/default flip inside `4.0.0`.
- Version bump `4.0.0b2 -> 4.0.0` (git tag target: `v4.0.0`).

### Migration note

- Until the stable tag is pushed and the publish workflow succeeds,
  `pip install ao-kernel` may still resolve to the previous stable package.
- After publish verification, `pip install ao-kernel` and
  `pip install ao-kernel==4.0.0` are the intended stable install paths.
- Public Beta users who need the prior pre-release line can still pin
  `ao-kernel==4.0.0b2`.

## [4.0.0b2] - 2026-04-24

### Changed — Post-beta closeout + stable-release gate preparation

`v4.0.0b2` refreshes the Public Beta pre-release line from current `main`
after the post-beta correctness and productionization program work. It does
not widen the public support boundary to a general-purpose production coding
automation platform; it packages the current governed runtime baseline with
clearer release gates and closeout records.

- Added the production stable live roadmap and ST-1 pre-release gate contract:
  - `.claude/plans/PRODUCTION-STABLE-LIVE-ROADMAP.md`
  - `.claude/plans/ST-1-RELEASABLE-PRE-RELEASE-GATE.md`
- Closed the GP-2.2 adapter-path `cost_usd` reconcile completeness tranche:
  - deterministic assertions now pin the fast-mode negative path and
    full-mode `llm_spend_recorded(source="adapter_path")` payload fields
  - no additional runtime patch was required
  - adapter-path `cost_usd` reconcile remains deferred as a public support
    claim
- Public Beta docs no longer hard-code the exact stable channel version; they
  document the install rule instead.
- Support boundary remains intentionally narrow:
  - shipped baseline: module/CLI entrypoints, doctor, `review_ai_flow` +
    `codex-stub`, `examples/demo_review.py`, policy command enforcement,
    packaging smoke, and documented read-only kernel API actions
  - operator-managed beta: `claude-code-cli`, `gh-cli-pr` preflight/live-write
    readiness probe, kernel API write-side actions, and real-adapter benchmark
    full mode
  - deferred: `bug_fix_flow` release closure, full remote PR opening,
    roadmap/spec demo widening, and adapter-path `cost_usd` as a public
    support claim
- Version bump `4.0.0b1 -> 4.0.0b2` (git tag target:
  `v4.0.0-beta.2`).

### Migration note

- `pip install ao-kernel` still stays on the stable channel until a
  pre-release is requested explicitly.
- Public Beta users should pin `ao-kernel==4.0.0b2` or use
  `pip install --pre ao-kernel`.
- No stable `4.0.0` claim is made by this release.

## [4.0.0b1] - 2026-04-20

### Changed — Runtime command enforcement + packaging smoke gate

**Context.** `v3.13.3` deliberately stopped at docs/test parity: operator docs became honest again, but adapter-path command enforcement was still deferred. The remaining review findings were all on the same seam: command violations were not wired into executor rollout semantics, `{python_executable}` needed a localized exception rather than a global sandbox hole, and wheel-install smoke still was not a release gate.

`v4.0.0b1` closes that seam.

- `Executor._run_adapter_step()` now resolves CLI invocations before execution and validates the resolved command in canonical order:
  - `step_started`
  - `policy_checked`
  - `policy_denied` on effective block
  - `adapter_invoked` only after the command passes
- `policy_checked.violations_count` / `violation_kinds` now include command-level violations, so evidence/audit output no longer reports a false zero immediately before a command deny.
- `build_sandbox()` stays policy-only. The runtime interpreter is **not** injected into sandbox-wide allowlists or path anchors.
- `{python_executable}` is now a localized command-resolution exception only:
  - only when the manifest command field explicitly uses the reserved token
  - only for the resolved `sys.executable` realpath
  - never for args, unrelated commands, PATH resolution, or sandbox mutation
- `invoke_cli()` and the executor now share one resolver (`ResolvedCliInvocation`) for command/args/stdin substitution, removing duplicated placeholder logic and preserving a single source of truth for reserved-token metadata.
- Command rollout semantics are live:
  - `enabled=false` keeps the policy layer dormant
  - `report_only` emits `policy_checked` and continues
  - `promote_to_block_on` escalation applies to command violations too
  - `block` fails closed before adapter execution
- Full-suite verification also surfaced a pre-existing deterministic test hygiene issue in `context.memory_tiers`: the optional `now` parameter was ignored and tier tests were pinned to wall-clock-sensitive dates. `v4.0.0b1` now honors the explicit `now` override and pins the tests to a fixed reference time so CI does not drift with the calendar.
- New release gate: `scripts/packaging_smoke.py` builds sdist+wheel, creates a fresh venv, installs the wheel only, runs the three CLI entrypoint checks, then executes `examples/demo_review.py --cleanup` from a temp cwd outside the repo.
- `.github/workflows/test.yml` now runs the packaging smoke as a blocking job, and `.github/workflows/publish.yml` reruns the same smoke before `twine check` / PyPI publish.
- Operator docs and the bundled policy comments now describe command enforcement as live in `v4.0.0b1`, including the localized `{python_executable}` exception.
- Version bump `3.13.3 -> 4.0.0b1` (git tag target: `v4.0.0-beta.1`).

### Migration note

- Workspaces with `policy_worktree_profile.enabled=true` and restrictive `command_allowlist` settings now get real adapter CLI blocking via `command_not_allowlisted` / `command_path_outside_policy`.
- Bundled `codex-stub` remains runnable under enabled policy because its manifest explicitly uses `{python_executable}`; that exception does not generalize to other commands.
- `pip install ao-kernel` stays on the stable channel until a pre-release is explicitly requested (`pip install ao-kernel==4.0.0b1` or `pip install --pre ao-kernel`).

## [3.13.3] - 2026-04-20

### Fixed — Policy docs/test parity patch

**Context.** `v3.13.2` deliberately left adapter-path command validation out of the patch release after Codex iter-2 blocked the first wiring attempt. That left one honest but awkward state: the runtime behavior was intentional, yet several operator-facing docs still described command-allowlist enforcement as if it were already live, and one rollout test still pinned parity with `assert result is not None`.

`v3.13.3` is the truth-and-tests patch for that gap. It does **not** change runtime semantics. The shipped executor still performs sandbox shaping, secret resolution / secret-in-argv checks, and HTTP-header exposure checks; adapter CLI command preflight remains a `v4.0.0b1` lane item.

- Docs aligned to the real shipped scope:
  - `docs/WORKTREE-PROFILE.md`
  - `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md`
  - `docs/ADAPTERS.md`
  - `docs/EVIDENCE-TIMELINE.md`
  - `docs/METRICS.md`
  - `ao_kernel/defaults/policies/policy_worktree_profile.v1.json`
- `docs/PUBLIC-BETA.md` stable banner and shipped section updated from `v3.13.2` to `v3.13.3`; the document keeps the same honest caveat that adapter CLI command preflight is not yet live.
- `tests/test_executor_policy_rollout_v311_p2.py` hardened:
  - report-only run now pins deterministic success (`step_state == "completed"` + `InvocationResult.status == "ok"`)
  - dry-run parity now asserts `predicted_events` order plus `policy_checked` payload fields instead of a tautological non-`None` result
- Version bump `3.13.2 -> 3.13.3`.

### Migration note

- No runtime behavior change.
- Operators should read `command_allowlist` in `v3.13.3` as a declared policy boundary plus sandbox PATH-shaping input. Adapter CLI hard enforcement becomes live in `v4.0.0b1`.

## [3.13.2] - 2026-04-20

### Fixed — v3.13.2 Correctness Patch (F1–F5, single PR)

**Context.** v3.13.1 ship'ten sonra iki dış AI değerlendirmesi art arda geldi. İlkinde README quick demo'nun çalışmadığı + `workspace_root` path semantic drift keşfedildi (absorb edildi v3.13.1'de). İkincisinde v3.13.1 sonrası kalan 5 bulgu ortaya çıktı:

1. **P1 demo bozuk**: README:79 hâlâ `examples/demo_bugfix.py`'ı öneriyor, ancak script `wreg.load_bundled()` çağırmıyor → `WorkflowDefinitionNotFoundError`. Yani README'yi izleyen kullanıcı ilk demoda duvara çarpıyor.
2. **P2 CI coverage gate drift**: `pyproject.toml::fail_under = 85` ama `.github/workflows/test.yml::coverage report --fail-under=70` — 15 puan boşluk. v3.13.0'daki coverage ratchet work'ü CI-level gate altında değildi.
3. **P2 DEMO-SCRIPT.md aspirational**: `intent classify`, `workflow start`, `diff preview` vb. canlı CLI'de olmayan komutları live runbook gibi anlatıyor.
4. **P3 `python -m ao_kernel` çalışmıyor**: `ao_kernel/__main__.py` eksik, `ModuleNotFoundError: No module named ao_kernel.__main__`.
5. **P1 `bug_fix_flow + codex-stub` patch_preview fail**: Ayrı bug — demo değiştirildiğinde user-facing değil ama gerçek runtime problemi. v3.13.3+'e ertelendi.

v3.13.2 F1–F5'i tek PR'da kapatır; F6 (bug_fix_flow patch_preview) ayrı correctness lane'e bırakılır.

**F1 — CI coverage gate 70 → 85**
- `.github/workflows/test.yml:59`: `coverage report --fail-under=70` → `--fail-under=85`
- `pyproject.toml::fail_under=85` ile hizalı. v3.13.0 coverage ratchet artık CI-level enforced.

**F2 — Public demo pivotu (`bug_fix_flow` → `review_ai_flow`)**
- `examples/demo_bugfix.py` **silindi** — never worked end-to-end on a fresh workspace (registry + git init + adapter subprocess cascade of bugs). `bug_fix_flow` patch_preview bug'ı (F6) ayrı lane'e.
- **`examples/demo_review.py` yeni** — `review_ai_flow + codex-stub` disposable git workspace + auto-approve + `review_findings` artifact validation + evidence timeline verify. Canlı smoke `final state: completed`.
- `README.md` quick-start: `demo_bugfix.py --workspace-root .` → `demo_review.py --cleanup`
- `docs/PUBLIC-BETA.md` **yeni** — Shipped / Beta / Deferred / Known Bugs SSOT tablosu (Codex Public Beta planından port).
- `docs/DEMO-SCRIPT.md` → compat pointer stub (canlı runbook değil, spec reference)
- `docs/roadmap/DEMO-SCRIPT-SPEC.md` **yeni** — 11 adımlı `bug_fix_flow` anlatımı roadmap/spec olarak taşındı; release-closure hedefi olarak korunur.

**F3 — Doc/CLI parity** (F2 içinde)
- DEMO-SCRIPT.md aspirational content roadmap/'a taşındı, canlı yüzey `bug_fix_flow` demo vaadini geri çekiyor.

**F4 — Module entry point: `python -m ao_kernel`**
- `ao_kernel/__main__.py` **yeni**: 9 satır, `from ao_kernel.cli import main; raise SystemExit(main())`. Codex Public Beta planından port.
- Contract: `ao-kernel version`, `python -m ao_kernel version`, `python -m ao_kernel.cli version` — üçü de `4.0.0b1` (sonraki major) veya `3.13.2` dönecek.

**F5 — Ergonomic pins** (F4 contract'ını pinliyor)
- `tests/test_cli_entrypoints.py` **yeni**: 3 entry kontratı subprocess ile pinleniyor:
  - `python -m ao_kernel version` (module entrypoint)
  - `python -m ao_kernel.cli version` (cli module entrypoint)
  - `ao-kernel version` (console script; `shutil.which` kontrolüyle skip-if-not-installed)
- Not: `ao-kernel --version` flag'i YOKTUR; cli.py parser sadece `version` subcommand'ını destekler.

**Codex iter-1 REVISE absorb (post-impl review):**
- **M2**: `test_cli_entrypoints.py` konsol script test'i eklendi + CHANGELOG'da `ao-kernel --version` yanlış ifadesi düzeltildi (parser sadece subcommand destekliyor).
- **L1**: `docs/PUBLIC-BETA.md` sürüm durumu banner'ı eklendi — v3.13.2 Shipped satırları ile v4.0.0b1 plan satırları ayrıldı; "Wheel-install smoke CI shipped" iddiası "Beta (plan)"a çevrildi (gerçek CI job v4.0.0b1 scope'unda).

**Codex iter-2 BLOCKER verdict — M1 reverted:**
- İlk iter-1'de `executor.py` adapter CLI adımına `validate_command()` preflight wiring'i eklenmişti. Codex iter-2 review'unda 3 substantive bulgu: (1) event ordering bozuluyor — `adapter_invoked` ÖNCE emit ediliyor, sonra validate_command; canonical order `step_started → policy_checked → adapter_invoked` bozuluyor; (2) rollout semantics bypass — `enabled=false` dormant policy'de bile blokluyor (executor.py:408-424 `enabled=false → no check/emit/fail` kontratı dışında); (3) `build_sandbox()` runtime interpreter path'ini anchor olarak eklemiyor → `sys.executable` venv/Homebrew/python.org kurulumlarda `command_path_outside_policy` violation atabilir.
- Codex iter-2 hüküm: "Böyle bir şeyi patch release'te 'iyileştirme' diye ship etmek, hiç ship etmemekten daha kötü."
- **Karar**: M1 wiring tamamen revert edildi. `{python_executable}` token + `codex-stub` manifest değişikliği sadece demo/packaging compatibility fix olarak tutuldu (`adapter_invoker.py` substitution only). Executor sandbox enforcement v3.13.1'deki gibi policy command preflight YAPMIYOR.
- **Semantic not** (Codex iter-3 absorb): `codex-stub.manifest` artık `command: "{python_executable}"` kullandığı için invocation aktif Python interpreter'ının **mutlak yoluyla** (`sys.executable`) çalıştırılır. Önceki `"python3"` sandbox PATH çözümüne tabiydi; yeni wiring PATH resolution'dan bağımsız. Enabled policy + command_allowlist tanımlayan operator'lar için interpreter seçimi semantiği v3.13.1'e göre değişmiş olabilir.
- **Defer**: `enabled policy + command validation integration` (rollout-aware, event-order-preserving, runtime-anchor sandbox) → v4.0.0b1 lane, Codex implementation.

### Migration note

- **Operator breaking** yok (non-breaking patch release).
- **README quick-start komutu** değişti: `examples/demo_bugfix.py` YOK. Yerine `python3 examples/demo_review.py --cleanup`. Eski script'e referans veren harici doc/script varsa güncelleyin.
- **CI coverage gate** 70 → 85 yükseldi. Fork ederek PR açan contributor'lar: `pytest --cov` sonucu 85'in altındaysa CI fail eder. Önceden geçiyor olan (70-85 arası) PR'lar artık geçmez — ratchet disiplini CI'de aktif.
- **`python -m ao_kernel`** contract'ı artık garantili. Mevcut `ao-kernel` console script davranışı değişmedi.

### Deferred (v3.13.3+)

- **F6 `bug_fix_flow + codex-stub` patch_preview**: `codex-stub` sabit `hello.txt` diff'i üretiyor, `patch_preview` adımı `PATCH_ERROR / patch_patch_preview_PatchPreviewError` atıyor. `bug_fix_flow` tam hattı için: ya `codex-stub` akıllı diff üretsin (workflow intent'ine göre), ya workflow adapter-ref'i fallback variant alsın, ya `bug_fix_flow_real_adapter` opt-in variant olsun (review_ai_flow pattern'ı).
- `init_cmd.run(override)` WRITE-side asymmetry — v3.14+ contract-break Codex consultation.
- `sanitize.py:39` EMAIL regex raw-string bug.
- `compiler.py:139` no-id dict KeyError.

### v4.0 gates (tracked)

- `save_store()` removal (deprecated since v3.0.0).
- `allow_overwrite` default flip `True → False`.
- FAZ-C feature surface: streaming cost, patch primitive, `governed_bugfix` full, retry/chaos bench, Windows platform.

## [3.13.1] - 2026-04-20

### Fixed — v3.13.1 Drift Patch (2 PRs)

**Context.** v3.13.0 shipped pure coverage lane (H2b1 + H2b-compiler + H3c). External AI UX review flagged three drift signals that accumulated during the v3.8 → v3.13 release cadence: (1) README policy/JSON counts outdated, (2) `CLAUDE.md` CLI reference listed a non-existent `ao-kernel system-status` command, (3) `workspace_root(override=...)` ↔ `load_workspace_json()` contract asymmetry made `doctor --workspace-root .` fail while `doctor --workspace-root .ao` passed. Codex plan-time REVISE absorbed into two-PR patch (read-side non-breaking).

**PR-D1 (#177) — docs + examples drift fix.**
- `README.md`: `96 policies` → `100+ policy files` with live breakdown footnote (377 bundled JSON = 106 policies + 231 schemas + 19 extensions + 9 registry + 4 workflows + 3 operations + 3 adapters + 1 catalogs + 1 intent_rules). Architecture tree `338 bundled JSON` → `377` with category list.
- `CLAUDE.md`: stale `ao-kernel system-status` line removed (no handler in `cli.py`); `evidence` / `metrics` / `policy-sim` entries added to match live CLI surface. Architecture tree `defaults/` category list synchronized with README (9 kinds) per Codex iter-1 REVISE absorb.
- `examples/hello-llm/main.py`: fixed misleading "`AoKernelClient` creates `.ao/` on demand" claim. Default `auto_init=False` is intentional; the example now explicitly opts in with `auto_init=True`.
- `examples/hello-llm/README.md`:85 troubleshooting narrative updated with the `auto_init` contract.
- `examples/demo_bugfix.py`: side-stepped `init --workspace-root X` asymmetric write-side bug (tracked for v3.14+) by `chdir` into target + `init` with no override.

**PR-P1 (#178) — `resolve_workspace_dir` normalizer + `load_workspace_json` fallback.**
- New public helper `ao_kernel.config.resolve_workspace_dir(path)` — tolerant normalization between project root (with `.ao/` inside) and the workspace dir itself (`.ao/`). Accepts `Path | str`. Returns input unchanged when neither shape matches so downstream callers produce clear fail-closed errors with the user-supplied path.
- `load_workspace_json()` now calls the helper first. `doctor`, `migrate`, `workspace.load_config`, and MCP `ao_workspace_status` all benefit transparently — `doctor --workspace-root .` returns **8/8 OK** (previously 7/1 FAIL on `workspace.json valid`).
- Codex iter-1 BLOCKER absorb: `migrate_cmd.run()` widened to normalize via `resolve_workspace_dir(ws)` once and use the resolved directory for every downstream write path (mutation file, `report.workspace_path`, `backup_dir`, legacy comparison). Without this, `migrate --workspace-root <project_root>` would silently mutate a stray `workspace.json` at the project root rather than `.ao/workspace.json`.
- +12 pins in `tests/test_resolve_workspace_dir_v3131_p1.py`: helper shape (project root / `.ao/` / neither / string / precedence edge case), `load_workspace_json` integration + malformed JSON + fail-closed error message, `doctor_cmd._check_workspace_json(project_root)` real path, `migrate` dry-run mutation file targets `.ao/`, `migrate` non-dry-run writes to `.ao/workspace.json` + backup under `.ao/.backup/`.
- Coverage 85.8% → 86.10%.

### Migration note

- **No breaking change.** Both PRs are read-side normalization + doc alignment. Operators who explicitly point `--workspace-root` at their `.ao/` directory keep working (backward compat). Operators who pass the project root (the intuitive interpretation of "workspace root") now work correctly where they previously failed.
- **`AoKernelClient` ergonomic detail** — the default remains `auto_init=False`. If you want the client to scaffold `.ao/` when missing, pass `auto_init=True` explicitly (as `examples/hello-llm/main.py` now does).

### Deferred follow-ups

- **`init_cmd.run(override)` WRITE-side asymmetry** — `init --workspace-root X` writes directly to `X/workspace.json` rather than `X/.ao/workspace.json`. Fixing this is a contract break for operators who intentionally pass `.ao/` as override. Scheduled for v3.14+ with a Codex plan-time consultation and a migration note.
- **`system-status` CLI alias** — Codex rejected adding a new command (name collision with `tool_registry` and `policy_intent_runbook_registry` concepts). Docs-only fix shipped in PR-D1.
- **`sanitize.py:39` EMAIL regex raw-string bug** — tracked separately (spawn_task); fix will also flip the paired regression pin in `tests/test_internal_roadmap_small_trio_coverage.py`.
- **`compiler.py:139` no-id dict KeyError** — tracked separately (spawn_task).

### v4.0 gates (tracked)

- `save_store()` removal (deprecated since v3.0.0; `canonical_store.py:132`).
- `allow_overwrite` default flip `True → False` on `promote_decision` + `forget` (CAS-first contract).
- FAZ-C feature surface: streaming cost tracking, Aider-style patch primitive, `governed_bugfix` full flow, retry/chaos benchmark variants, Windows platform.

## [3.13.0] - 2026-04-20

### Added — v3.13.0 Coverage Ratchet Final (3 PRs)

**Context.** v3.12.0 shipped seven PRs (H1+H3+H2a+E1+E2+E3+P5) covering a mix of hygiene, Prompt Experiments, and polish. Two coverage-tranche follow-ups stayed open: deeper roadmap files (H2a deferred `compiler.py` + 7 remaining omits) and the session module's stateful members. v3.13 closes three of them in a focused coverage lane and picks up two absorbed Codex-review iteration BLOCKERs.

**Scope:** 3 coverage PRs. v4.0 breaking prep (save_store removal + allow_overwrite flip) intentionally deferred — per Codex plan-time AGREE, v3.13 stays a pure hygiene release.

**PR-H2b1 (#173) — roadmap small-trio coverage tranche 5B.**
- `pyproject.toml::coverage.run.omit`: `_internal/roadmap/{change_proposals, sanitize, evidence}.py` pulled in.
- `tests/test_internal_roadmap_small_trio_coverage.py` (new, 44 pins total): 40 first-pass + 4 Codex iter-1 absorb.
- **Real API pins per Codex plan-time guardrail:** `change_proposals` exercises `validate_change()` + `apply_change_to_roadmap_obj()` with all 4 patch ops (`append_milestone_note`, `replace_milestone_notes`, `replace_milestone_steps`, `replace_milestone_title`) + fail-closed guards (`CHANGE_INVALID` / `CHANGE_TYPE_UNSUPPORTED` / `PATCH_OP_UNSUPPORTED`); `sanitize` pins the `scan_directory()` rule matrix (`FORBIDDEN_TOKEN` / `PRIVATE_KEY_MARKER` / `TOKEN_PREFIX_DETECTED`) + `findings_fingerprint()` determinism; `evidence` covers `init_evidence_dir()` + `write_step_evidence()` + `write_integrity_manifest()` SHA-256 envelope.
- Codex iter-1 REVISE absorb: two missing `change_proposals` fail-closed guards (`patch entry must be an object`, `patch.milestone_id missing`) + `EMAIL_DETECTED` branch in `sanitize` now directly exercised via `scan_directory()`. Paired regression pin documents a raw-string regex bug (literal `\\.` instead of `\.` in `sanitize.py:39`): current behaviour matches only `user@example\.com`, not normal emails — follow-up bug fix tracked separately.
- Coverage 85.42% → +0.39% delta.

**PR-H2b-compiler (#174) — `compiler.py` real-API coverage + drop stale DEFER.**
- `tests/test_internal_roadmap_compiler_coverage.py` (new, 18 pins) writes fresh pins directly against the live `compile_roadmap(roadmap_path=..., schema_path=..., cache_root=...)` surface.
- `tests/test_internal_roadmap_small_coverage.py`: `_TestCompilerInvariantGuards_DEFER` class removed — it targeted a stale `plan_path=` kwarg and `"id"` roadmap field that don't exist in the live API (real roadmap shape uses `roadmap_id` + `version` + `milestones`). Per Codex plan-time directive, deferred pins were rewritten from scratch rather than revived.
- Covers all missing branches from the 83% transitive baseline: `validate_roadmap` json_path error anchor, `ROADMAP_SCHEMA_INVALID` / `ROADMAP_INVALID` / `ROADMAP_MILESTONE_NOT_FOUND` raises, non-dict milestone skip, no-filter string-id tracking, `iso_core_required` preflight injection, `global_gates` → `GLOBAL:G:NNN` IDs, `deliverables` fallback paths (`steps` primary + `deliverables` elif), `out_path` additional-copy write, plan fingerprint differs on milestone filter.
- Compiler transitive coverage: 83% → ~100%.
- Follow-up flagged: `compiler.py:139` accesses `ms["id"]` unguarded — no-id dict crashes with `KeyError`. Pre-existing bug; test fixture intentionally excludes the no-id case.

**PR-H3c (#175) — `_internal/session/provider_memory.py` coverage tranche 6B.**
- `pyproject.toml::coverage.run.omit`: `provider_memory.py` pulled in. `cross_session_context.py` intentionally stays omitted (multi-session aggregation + prune/save + hierarchical merge deferred to a v3.14+ tranche per Codex plan-time split).
- `tests/test_internal_session_provider_memory_coverage.py` (new, 30 pins) uses a **real** schema-valid session-context harness (`new_context()` + `save_context_atomic()`) rather than mocking `load_context` — schema round-trip + hash computation are exercised alongside the tested logic.
- Covered surfaces: `_safe_slug` regex normalization + fallback, `resolve_auto_compact_token_limit` codex-config guards (exception / non-dict / missing effective / non-numeric), `read_provider_session_state` memory_strategy branches + provider match/mismatch + `compaction_summary_ref` on completed vs idle, `maybe_auto_compact_markdown` threshold guards + archive + summary + session update, `persist_provider_result` missing/happy/invalid, `_render_compaction_summary` structured + fallback + CRLF normalization.
- Coverage 85.42% → +0.33% delta (H3c-only; cumulative with H2b1 + H2b-compiler lands at ~85.8%).

### Changed

- `tests/test_internal_roadmap_small_coverage.py`: docstring rewritten to cross-ref the new H2b1 + H2b-compiler companion files. Unused `import pytest` removed after deferred-class deletion.

### Fixed (follow-up fixes folded from v3.12)

- CHANGELOG v3.12 follow-up block had stale session-module filenames (`compaction.py` + `distillation.py` — those files don't exist; actual members are `compaction_engine.py` and `memory_distiller.py`, and the true omitted pair was `cross_session_context.py` + `provider_memory.py`). The stale names were correct at plan-time but drifted away from the omit list during H3 rewording. v3.13 H3c closed the `provider_memory.py` half; remaining omit is just `cross_session_context.py`.

### Migration note

- No runtime behaviour change. All three PRs are pure test + coverage-gate surface changes. Operators using `compile_roadmap` continue to pass `roadmap_path` + `schema_path` + `cache_root` — no signature drift.
- Consumers subclassing or importing from `_internal/*` (not supported per D1) may want to note that `provider_memory.py` and the roadmap small-trio are now under the 85% coverage ratchet; behaviour isn't affected, but new pins will flag regressions more aggressively.

### Known follow-ups (post-v3.13)

- `sanitize.py:39` email regex raw-string bug (`r"...\\.[A-Z]{2,}"` should be `r"...\.[A-Z]{2,}"`) — `EMAIL_DETECTED` branch currently only fires on weird backslash-dot inputs. Two paired pins in `test_internal_roadmap_small_trio_coverage.py` (positive + negative) document current behaviour; the regex fix will flip the negative pin and the pair collapses to a single real-world positive pin.
- `compiler.py:139` `ms_id = str(ms["id"])` accesses the key unguarded — dicts in the no-filter path that lack `"id"` crash with `KeyError`. Skip the dict in the filter's append loop or use `.get("id", "")` with a guard.
- `_internal/roadmap/` remaining omits (`change_proposals` now in scope) still leave `step_templates`, `exec_evidence`, `exec_steps`, `executor` outside the ratchet — deferred to v3.14+ larger tranches.
- `_internal/session/cross_session_context.py` — final session-module omit, deferred to v3.14+ (multi-session aggregation + prune/save + hierarchical merge is more stateful; needs a dedicated fixture harness).

### v4.0 gates (tracked)

- `save_store()` removal (deprecated since v3.0.0; `canonical_store.py:132`).
- `allow_overwrite` default flip `True → False` on `promote_decision` + `forget` (CAS-first contract).
- FAZ-C feature surface: streaming cost tracking, Aider-style patch primitive, `governed_bugfix` full flow, retry/chaos benchmark variants, Windows platform.

## [3.12.0] - 2026-04-20

### Added — v3.12.0 Hygiene + Prompt Experiments (7 PRs)

**Context.** v3.11.0 shipped four Runtime Polish PRs (P1 `reset_tool_gateway_state()` + P2 executor activation/rollout + P3/P4 `_internal/*` coverage tranches) and flagged two follow-up buckets: (1) `env_unknown` / `env_missing_required` dead `PolicyViolation.kind` entries, and (2) `_internal/roadmap/*` + `_internal/session/*` remaining omitted from coverage. v3.11 also gated Prompt Experiments on "at least one stable operator-validated real-adapter smoke" per v3.9 Codex AGREE. v3.12 unlocks both: the executor activation landed in v3.11 P2 with a stable dormant-by-default contract, and the E-series (contract + read-only helper + runbook) is additive — no runtime loop, no policy mutation. v3.12 also absorbs an external-AI UX report (5 valid findings / 1 wrong-mental-model rejection) into P5 polish.

**Scope:** 3 hygiene PRs (H1 + H2a + H3), 3 experiment PRs (E1 + E2 + E3), 1 polish PR (P5).

**PR-H1 (#165) — `env_unknown` / `env_missing_required` dead-kind cleanup.**
- `ao_kernel/executor/errors.py::PolicyViolation.kind` Literal narrowed: `env_unknown` + `env_missing_required` removed. No `policy_enforcer` path was emitting either kind; operators writing `promote_to_block_on` against them would silently no-op against real runtime violations.
- `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` §2 workspace-override JSON example rewritten — the illustrative `promote_to_block_on` sample had stale aliases (`secret_leak_detected`, `cwd_escape_attempted`, `command_not_in_allowlist`) left over from the v3.11 P2 rewrite; now matches the live taxonomy (`secret_exposure_denied`, `cwd_escape`, `command_not_allowlisted`).
- +2 pins: `test_policy_violation_kind_taxonomy_drops_env_dead_kinds` (typing negative) + `test_real_adapter_runbook_has_no_stale_kind_aliases` (doc regression).

**PR-H3 (#166) — `_internal/session/agent_context_version` coverage tranche 6.**
- `pyproject.toml::coverage.run.omit` no longer masks `ao_kernel/_internal/session/agent_context_version.py` (the smallest of the three omitted session-module files). The other two (`compaction.py`, `distillation.py`) stay omitted pending the larger v3.12+ session tranche.
- +4 pins in `tests/test_internal_session_agent_context_version_coverage.py`: `validate_agent_context_version` accept current / accept legacy with warn log / reject future / reject malformed.
- Coverage: 85.27% → 85.29%.

**PR-H2a (#167) — `_internal/roadmap/*` small-files coverage tranche 5A.**
- `pyproject.toml::coverage.run.omit` split into 7 granular entries for `_internal/roadmap/*`: `compiler.py`, `checkpoint.py`, `exec_contracts.py` removed (now in scope); `change_proposals.py`, `sanitize.py`, `step_templates.py`, `evidence.py`, `exec_evidence.py`, `exec_steps.py`, `executor.py` kept omitted for v3.12+ large-scope tranches.
- `compiler.py` deferred to H2b (`compile_roadmap` requires schema_path + cache_root fixture harness outside the small-files tranche scope). Test class renamed `_TestCompilerInvariantGuards_DEFER` so pytest skips collection.
- +9 pins across `tests/test_internal_roadmap_small_coverage.py`: `TestCheckpointManager` (×5 — load-missing / atomic-write-rename / reload-round-trip / stale-purge / corrupt-recover) + `TestExecContracts` (×4 — RoadmapStepContract from_dict / invalid payload / sanitize round-trip / compile happy-path).
- Corrected during iter-1: class name `RoadmapCheckpointStore` → `RoadmapCheckpointManager`, path `checkpoints/` → `roadmap_checkpoints/`, filename `checkpoint.json` → `progress.v1.json`.
- Coverage: 85.29% → 85.42%.

**PR-E1 (#168) — Prompt variant contract + registry loader (contract-only).**
- New `ao_kernel/prompts.py`: `PromptVariant` dataclass + `PromptVariantError` + `load_prompt_variants(path)` loader. Fields: `variant_id` (`^[a-z0-9_.-]+$`), `experiment_id` (optional, same pattern), `intent` (enum), `template` (non-empty str), `description` (optional), `created_at` (optional ISO-8601).
- New `ao_kernel/defaults/schemas/prompt-variant.schema.v1.json` (JSON Schema Draft 2020-12) — source-of-truth for variant stamping contract.
- Loader validates against schema via `jsonschema.Draft202012Validator.iter_errors` BEFORE dataclass coercion (iter-1 BLOCKER absorb: field-level `str(...)` coercion was silently accepting non-string / pattern-violating / empty values); first schema error path surfaces in `PromptVariantError` message.
- +9 pins in `tests/test_prompts_v312_e1.py`: happy-path load + round-trip + experiment_id optional + created_at optional + pattern violation (iter-1) + non-string type (iter-1) + empty string (iter-1) + duplicate variant_id + missing required field.
- **Scope strictly contract-only**: no registry directory lookup, no `intent.metadata.variant_id` stamping side effects in runtime; operators load + hand to `compare_variants` (E2) manually. The stamping contract (operator stamps `intent.metadata.variant_id` per variant run) is documented in E3 (#170).

**PR-E2 (#169) — `ao_kernel.experiments.compare_variants` read-only helper.**
- New `ao_kernel/experiments/compare.py`: `VariantComparison` + `VariantComparisonEntry` dataclasses + `compare_variants(run_ids, workspace_root)` function + `VariantComparisonError`.
- Contract: each run's `intent.metadata.variant_id` (stamped by the operator per E1 contract) is REQUIRED; absence raises `VariantComparisonError` (fail-closed pairing). `experiment_id` optional. Artefact source: first `step_record.capability_output_refs["review_findings"]` across the run's steps wins.
- Artefact path resolution (iter-1 BLOCKER): `capability_output_refs` values are run-dir-relative per `workflow-run.schema.v1.json`. Helper resolves against `workspace_root/.ao/evidence/workflows/<run_id>/` not `workspace_root`. New `_run_dir()` helper.
- Path-traversal guard (iter-2 BLOCKER): `path.is_relative_to(run_dir_resolved)` check after `.resolve()` — a malformed / malicious run record carrying `review_findings_ref="../../../evil.json"` now surfaces as `load_error: "artefact ref escapes run directory: ..."` instead of silently loading an unrelated JSON file stamped as `review_findings`. Python 3.11+ `is_relative_to` (target minimum).
- Artefact load failures (missing file / malformed JSON / non-dict payload / containment violation) are packaged into `VariantComparisonEntry.load_error` (fail-open read) — the row still ships with metadata so operators can diff what shipped vs what didn't.
- `by_variant` groups entries by `variant_id` in discovery order across the input `run_ids`; `entries` preserves input order.
- +10 pins in `tests/test_experiments_compare_v312_e2.py`: missing `intent.metadata` / missing `variant_id` / empty `variant_id` / no review-findings step / missing artefact file / malformed artefact / successful load / ref escape rejection (iter-3) / `by_variant` grouping / `experiment_id` pass-through.
- **Read-only**: helper does NOT orchestrate runs. Operators start each variant run manually per E3 runbook.

**PR-E3 (#170) — `PROMPT-EXPERIMENTS-RUNBOOK.md` operator guide.**
- New `docs/PROMPT-EXPERIMENTS-RUNBOOK.md`: end-to-end operator walkthrough covering (1) defining variants with `PromptVariant` + JSON registry, (2) stamping `intent.metadata.variant_id` on every workflow run invocation (operator responsibility — the runtime does NOT auto-stamp), (3) running each variant through the normal workflow path (`governed_review_claude_code_cli` or any real-adapter flow) with the variant's `template` injected as the operator's prompt body, (4) running `compare_variants([run_a, run_b, ...], workspace_root=ws)` to collect paired `review_findings`, (5) diffing / scoring the payloads (operator tooling — the helper does not score).
- Cross-refs: `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` for the real-adapter setup prerequisite; `review-findings.schema.v1.json` for the artefact shape.
- Pragmatics section: why `compare_variants` is read-only (fail-open artefact load so partial runs still diff), why `variant_id` pairing is fail-closed (unstamped runs do not belong in an experiment comparison), why the helper doesn't score (operators own the diff / threshold tooling — `ao-kernel` provides the substrate).

**PR-P5 (#171) — `AoKernelClient.close()` + README `[llm]` extra clarification.**
- `AoKernelClient.close(*, save: bool = True)` public method — alias for the context manager teardown path (`end_session(save=save)` + `_close_owned_vector_store()`). Use case: explicit lifecycle control outside `with` blocks (service frameworks, long-running processes with scoped clients). Idempotent — multiple calls are safe.
- Idempotency fix (iter-2 BLOCKER): `_close_owned_vector_store` now flips `_owns_vector_store = False` BEFORE invoking `backend.close()`, so even if the backend raises during close the state transition completes and a subsequent `close()` call is a no-op rather than re-invoking `backend.close()`.
- README `Installation` section clarified: `pip install ao-kernel` ships the core (only `jsonschema` required), but production-grade LLM calls need `pip install ao-kernel[llm]` for `tenacity` (retry / backoff) and `tiktoken` (exact token counting). Without the extra the runtime falls back to single-attempt execution + heuristic token count (functional but weaker SLA). POSIX-only note added (cross-ref `docs/COORDINATION.md`).
- +5 pins in `tests/test_client.py::TestClientCloseV312P5`: close ends active session / close idempotent across calls / close without context manager / close forwards `save=False` flag / close idempotent on owned backend with MagicMock (iter-2).

### Migration note

- **Variant experiment authors**: to use `compare_variants`, stamp `intent.metadata.variant_id` on every workflow run invocation. The runtime does NOT auto-stamp — operator responsibility per the documented contract. Unstamped runs raise `VariantComparisonError` (fail-closed pairing).
- **Consumers using `AoKernelClient` outside `with` blocks**: `close()` is now the documented teardown method. Previous code paths using `end_session()` directly still work but will not close owned vector-store backends; prefer `close()` for full cleanup.
- **Workspace override `policy_worktree_profile` authors**: if you had `promote_to_block_on` carrying `env_unknown` / `env_missing_required`, those kinds are dropped from the taxonomy. The escalation was already a no-op (no `policy_enforcer` path emits them); remove them from your override to match the shipped taxonomy.

### Known follow-ups (post-v3.12)

- `_internal/roadmap/*` remaining omitted files (`change_proposals.py`, `sanitize.py`, `step_templates.py`, `evidence.py`, `exec_evidence.py`, `exec_steps.py`, `executor.py`) + `compiler.py` (deferred from H2a) — v3.12+ H2b tranche.
- `_internal/session/compaction.py` + `distillation.py` — remaining omitted session-module files after H3. v3.12+ session tranche.
- `init_cmd.py::build_workspace_config` hard-codes `"version": "3.2.0"` in the written `.ao/workspace.json` (external-AI UX report finding). Live tree verified uses `ao_kernel.__version__` dynamically — the `3.2.0` strings in stale workspaces come from pre-3.2.1 PyPI installs. Hygiene PR to backfill the dynamic version into any stale workspace.json via `ao-kernel migrate` or similar.
- `compare_variants` scoring helpers (`differing_findings()` etc.) intentionally out-of-scope for v3.12; operators write their own diff tooling per E3 runbook. Consider adding a thin canonical-diff helper in a future release.

### v4.0 gates (tracked)

- `save_store()` removal (deprecated since v3.0.0; `canonical_store.py:132`).
- `allow_overwrite` default flip `True → False` on `promote_decision` + `forget` (CAS-first contract).
- FAZ-C feature surface: streaming cost tracking, Aider-style patch primitive, `governed_bugfix` full flow, retry/chaos benchmark variants, Windows platform.

## [3.11.0] - 2026-04-19

### Added — v3.11.0 Runtime Polish (4 feature PRs + release)

**Context.** v3.10 shipped the External Real-Adapter Benchmark arc (A1+A2+A3) with claude-code-cli declaring `review_findings` + operator runbook. v3.11 clears the post-v3.10 debt pile in a single "Rolling Polish" release (pattern: v3.8 H-series). Four micro/core PRs cover public API ergonomics, activation + rollout semantics for `policy_worktree_profile`, and the final two `_internal/*` coverage tranches. Codex plan-time master AGREE with 2 revisions absorbed (P2 scope widened from "rollout honoring" to "activation + rollout semantics honoring"; `promote_to_block_on` stale names rewritten in same PR).

**PR-P1 (#160) — `AoKernelClient.reset_tool_gateway_state()` public helper.**
- Closes v3.9 B2 iter-3 residual debt: standalone `call_tool()` chains accumulate `_request_call_count` / `_recent_calls` across invocations. `llm_call()` resets the gateway automatically at every LLM request; `call_tool()` chains (documented agentic tool-use contract) do NOT reset implicitly. The new helper is the opt-in escape hatch for consumers that treat each standalone `call_tool()` as a fresh session.
- `AoKernelClient.reset_tool_gateway_state()` — thin wrapper over `self._gateway.reset_rounds()` with `getattr` ergonomics (no-op when no gateway exists).
- +4 pins in `tests/test_client.py` (dirty state → reset → clean; no-op when no gateway; standalone chain preserves counters; cap-hit → reset → fresh chain).

**PR-P2 (#162) — Executor activation + rollout semantics honoring.**
- `_run_adapter_step` now honors the three-tier contract declared in `policy_worktree_profile.v1.json`. Pre-P2 the runtime ran every check unconditionally and failed closed on any violation — `enabled=false` and `rollout.mode_default="report_only"` were declarative-only placeholders.
- Three tiers now honored:
  - `enabled=false` → policy layer bypassed; no `policy_checked` / `policy_denied` events; no fail. Sandbox still built from declared fields so the adapter has a runnable env.
  - `enabled=true` + `mode_default="report_only"` → violations collected; `policy_checked` emits with additive payload fields (`mode`, `would_block`, `violation_kinds`, `promoted_to_block`); step continues.
  - `enabled=true` + `mode_default="block"` (or unknown — fail-closed fallback) → `policy_checked` + (on violations) `policy_denied` + step fails closed with `PolicyViolationError`.
- Escalation: in `report_only`, any `violation.kind` in `rollout.promote_to_block_on` escalates to block (override preserves fail-closed semantics for highest-severity classes).
- `promote_to_block_on` stale names rewritten in the same PR (Codex plan-time directive) to match the `PolicyViolation.kind` closed taxonomy in `ao_kernel/executor/errors.py`: `secret_leak_detected` → `secret_exposure_denied`; `cwd_escape_attempted` → `cwd_escape`; `command_not_in_allowlist` → `command_not_allowlisted`. `env_unknown` dropped from the bundled default (declared in taxonomy but not actively emitted — Codex post-impl iter-2 polish; operators can re-add in workspace override if a future PR starts emitting it).
- Docs alignment in same PR: `docs/WORKTREE-PROFILE.md` §4 three-tier table rewritten; `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` §2 + §5 drop "declarative-only" narrative and document the shipped three-tier behavior; bundled policy `_mode_note` + `_comment` tightened to "enforcement dormant, sandbox shaping retained" (Codex iter-2 terminology polish).
- +7 pins: three-tier dispatch + escalation override + unknown-mode fail-closed + `dry_run_step` parity (Codex-requested) + `policy_checked` additive payload shape (legacy `violations_count` BC).

**PR-P4 (#161) — `_internal/shared/*` coverage tranche 3.**
- `pyproject.toml::coverage.run.omit` no longer masks `ao_kernel/_internal/shared/*`. `lock.py` / `logger.py` / `resource_loader.py` / `utils.py` already 86-98% covered transitively; new tranche pins the reachable remaining branches.
- +9 pins in `tests/test_internal_shared_coverage.py`: `TestLockPlatformGuard` (Windows sys.platform mock + success acquire/release), `TestLoggerEnvLevel` (`AO_LOG_LEVEL` valid/invalid), `TestResourceLoaderFallback` (`_find_repo_root` no-pyproject + bundled fallback + `load_resource_path` None), `TestLoadPolicyValidatedImportGuard` (jsonschema missing).
- Two branches intentionally uncovered: `lock.py` flock release-failure + timeout race (need second-process fixture).
- Coverage: 85.10% → 85.13%.

**PR-P3 (#163) — `_internal/providers/*` coverage tranche 4.**
- Fourth and final `_internal/*` coverage tranche in the v3.x series. `capability_model.py` (was ~73% transitive) + `token_counter.py` (was ~36%) pulled into scope.
- Tiktoken path tested via `types.ModuleType("tiktoken")` + fake encoding class (Codex plan-time note: "monkeypatch/fake module, not live dependency"). CI does not require the optional `[llm]` extra to cover the tiktoken branch.
- +19 pins: `TestCapabilityManifestSupports` (×3), `TestLoadCapabilityRegistry` (×2), `TestResolveManifest` (×3), `TestCountTokensHeuristic` (×2), `TestCountTokensTiktoken` (×3 — ImportError + fake encoding int return + `get_encoding` fallback on `KeyError`), `TestCountTokensDispatch` (×2 — openai → tiktoken, anthropic → heuristic), `TestUsageRecordAndTracker` (×4 — `to_dict`, unlimited budget, record + summary, budget denial).
- Coverage: 85.13% → 85.27%.

### Migration note

- **Operators with a workspace override `policy_worktree_profile.v1.json`**: `rollout.mode_default` is now a real runtime switch. If you had `enabled=true` + `mode_default="report_only"` while the executor was still fail-closed regardless, behavior now changes: violations log `policy_checked` but the step continues. Flip to `"block"` to restore fail-closed behavior. If your workspace override uses the pre-P2 `promote_to_block_on` placeholder names (`secret_leak_detected`, `cwd_escape_attempted`, etc.) the escalation won't fire against real runtime violations — rewrite to match `PolicyViolation.kind` taxonomy.
- **Standalone `call_tool()` chain users**: if you were working around cap/cycle accumulation by creating a fresh `AoKernelClient`, you can now call `client.reset_tool_gateway_state()` instead. The auto-reset inside `llm_call()` is unchanged.
- **Bundled policy unchanged in semantics**: `enabled=false` is still the bundled default — no-op for anyone using defaults.

### Known follow-ups (post-v3.11)

- `env_unknown` / `env_missing_required` are declared in `PolicyViolation.kind` taxonomy (`ao_kernel/executor/errors.py`) but not actively emitted by any `policy_enforcer` path. Either start emitting them (env-allowlist strict mode) or prune from the taxonomy + docstring. Small hygiene PR.
- `_internal/roadmap/*` (~2,497 LOC) and `_internal/session/*` (3 files) remain omitted from coverage. Large-scope tranches candidated for v3.12.
- v3.11 E (Prompt Experiments) stays conditional per v3.9 Codex AGREE: needs "at least one stable operator-validated real-adapter smoke" before opening.

### v4.0 gates (tracked)

- `save_store()` removal (deprecated since v3.0.0; `canonical_store.py:132`).
- `allow_overwrite` default flip `True → False` on `promote_decision` + `forget` (CAS-first contract).
- FAZ-C feature surface: streaming cost tracking, Aider-style patch primitive, `governed_bugfix` full flow, retry/chaos benchmark variants, Windows platform.

## [3.10.0] - 2026-04-19

### Added — v3.10.0 External Real-Adapter Benchmark + post-v3.9 hygiene

**Context.** v3.9 closed the dormant-contract drift in `policy_tool_calling.v1.json` (parser + runtime enforcement). v3.10 opens the external real-adapter path: `claude-code-cli` now advertises `review_findings`, a dedicated real-adapter benchmark workflow ships, and operators get a runbook documenting the full setup. Scope narrowed from 4 PRs to 3 per Codex plan-time BLOCKER (`commit_message` capability dropped — no evidence of a `$.commit_message` field in real `claude` stdout, adding an output_parse rule would fail-close every commit-ai run). The arc also absorbs two post-v3.9 follow-up micro-PRs.

**PR-A1 (#156) — `claude-code-cli` manifest advertises `review_findings`.**
- `ao_kernel/defaults/adapters/claude-code-cli.manifest.v1.json`: version `1.0.0` → `1.1.0` (capability surface widened, SemVer minor). `capabilities` += `review_findings`. New `output_parse.rules` entry pointing `$.review_findings` at `review-findings.schema.v1.json`.
- Runtime contract is **fail-closed**: `adapter_invoker._walk_output_parse` rejects any envelope where the declared `json_path` is absent or whose extracted payload doesn't match the schema. Operators follow the A3 runbook's prompt contract to produce the required shape.
- `docs/ADAPTERS.md` + `tests/benchmarks/test_full_mode_smoke.py`: doc drift absorbed (version + capability list match the shipped manifest).
- +5 pins in `tests/test_adapter_manifest_loader.py` including the Codex-requested `schema_ref` resolves-to-bundled anchor.

**PR-A2 (#157) — `governed_review_claude_code_cli.v1.json` workflow variant.**
- `ao_kernel/defaults/workflows/governed_review_claude_code_cli.v1.json` (new): sibling of `review_ai_flow` targeting `claude-code-cli` instead of the `codex-stub` placeholder. Steps mirror the stub flow (`compile_context` → `invoke_review_agent` → `await_acknowledgement`). `expected_adapter_refs=["claude-code-cli"]`; tags `real-adapter` + `benchmark` for operator discoverability.
- Naming per Codex plan-time preference: adapter-specific (`governed_review_claude_code_cli`) rather than abstract (`governed_review_real_adapter`).
- `review_ai_flow.v1.json` stays pinned at `codex-stub` for benchmark-baseline reproducibility; both flows coexist intentionally.
- Review step `policy_refs` include `policy_secrets.v1.json` as a **canonical declarative companion** (Codex post-impl note): live secret gate today is `policy_worktree_profile.secrets.allowlist_secret_ids` inside the executor; `policy_secrets.v1.json` is the documented registry downstream audits cross-reference.
- +4 pins in `tests/test_pr_b0_contracts.py` (schema validate, cross-ref valid against bundled adapters, adapter_refs == claude-code-cli only, discovery tag presence).

**PR-A3 (#158) — `BENCHMARK-REAL-ADAPTER-RUNBOOK.md`.**
- `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` (new, ~260 lines): full operator guide for running the real-adapter workflow. Sections: prerequisites, workspace override minimum viable (`policy_worktree_profile.enabled=true` + `ANTHROPIC_API_KEY` allowlist + `command_allowlist` += `claude`), prompt contract (fail-closed JSON envelope with `"status": "ok"` + `review_findings` payload — no code fences, no prose), disposable sandbox repo pattern (`/tmp` clone + `ao-kernel init` + `rm -rf` cleanup), evidence + troubleshooting with the closed `PolicyViolation.kind` taxonomy from `ao_kernel/executor/errors.py`, cost + budget.
- `docs/BENCHMARK-SUITE.md`: annotated `review_ai_flow` row as "pinned at codex-stub"; added row for `governed_review_claude_code_cli`; cross-ref to the runbook.
- Runbook explicitly flags `rollout.mode_default` as a declarative policy-doc setting the current executor does NOT branch on — honoring it (report_only vs block) is post-v3.10 runtime work (Codex iter-1 BLOCKER absorb).

### Changed — Post-v3.9 hygiene folded into v3.10.0

**PR-M1 (#153) — `_internal/utils/*` coverage tranche 2.**
- `pyproject.toml::coverage.run.omit` no longer masks `ao_kernel/_internal/utils/*`. `budget.py` + `jsonio.py` (38 LOC, already ~80–82% transitive) are now under the ratcheted 85% scope.
- `tests/test_internal_utils_coverage.py` adds targeted pins: `estimate_tokens` empty/non-str branches, `load_json`/`save_json` roundtrip, `to_canonical_json` sort_keys + unicode preservation.
- Mirror of the v3.8 H1 `_internal/secrets/*` single-tranche pattern.
- Coverage: 85.10% → 85.13%.

**PR-M2 (#154) — `ToolCallPolicy.from_dict()` legacy bool-strict + `max_tool_rounds` schema alignment.**
- Three legacy fields (`enabled`, `allow_unknown`, `max_tool_rounds`) now match the strict validation already applied to B1-absorbed fields. Pre-M2 they silently coerced `"true"` strings, `0/1` ints, and string-wrapped numbers.
- `max_tool_rounds` also picks up the schema-matching `1 <= x <= 10` inclusive bounds (Codex plan-time note: "half-alignment risk").
- Invalid payloads raise `ValueError` at parse time — fail-closed by design.
- +6 negative pins in `tests/test_tool_gateway.py`.

### Migration note

- **Operators running `governed_review_claude_code_cli`**: follow the runbook at `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md`. Bundled `policy_worktree_profile` stays dormant; the real path only engages under a workspace override. Existing workspaces that keep `review_ai_flow` pointed at `codex-stub` are unaffected.
- **Custom policy authors**: operator-written policies with silently-coerced legacy values (non-bool `enabled`, string `max_tool_rounds`, out-of-bounds `max_tool_rounds`) will now surface as `ValueError` at `ToolCallPolicy.from_dict()` time. Same fail-closed contract as the v3.9 B1 fields.

### Known follow-ups (post-v3.10)

- `AoKernelClient.call_tool()` standalone path is not gated by `llm_call()` reset — persistent gateway state leaks outside the LLM-request boundary. Preexisting design debt; Codex rejected a per-`call_tool()` auto-reset (would break the documented manual tool-use contract where `call_tool()` is the public execution surface for tool chains). Deferred to a future client API pass with an explicit `reset_tool_gateway_state()` helper or similar.
- `policy_worktree_profile.rollout.mode_default` runtime honoring — currently declarative only; the shipped executor fails closed on any violation when the policy is enabled. Honoring `report_only` vs `block` is post-v3.10 runtime work.

## [3.9.0] - 2026-04-19

### Added — v3.9.0 Tool Dispatch Governance Hardening (2 feature PRs)

**Context.** v3.8 shipped rolling hardening with no feature surface growth. v3.9 closes the dormant-contract drift in `policy_tool_calling.v1.json`: the policy file had 7 fields that operators could write but `ToolCallPolicy` parser and `ToolGateway` runtime ignored entirely. v3.9 = B1 (parser absorb) + B2 (runtime enforcement). Codex adversarial consensus: plan-time master AGREE on scope; B2 had 3 post-impl review iters (iter-1 BLOCKER: client persistent gateway never reset; iter-2 MEDIUM: denial audit `.ao/.ao/` nesting; iter-3 BLOCKER: `ao_memory_write` locked-DENY by default). Each absorbed with a regression pin.

**PR-B1 (#150) — `ToolCallPolicy` contract absorb (parser-only).**
- `ToolCallPolicy` now parses 7 previously-dormant fields from `policy_tool_calling.v1.json`: `max_calls_per_request`, `allowed_tools`, `blocked_tools`, `default_permission`, `mutating_requires_confirmation`, `cycle_detection_enabled`, `cycle_max_identical_calls`.
- `ToolCallPolicy.from_dict()` validates each field; invalid types / enum / negative ints raise `ValueError` (iter-2 absorb: strict `isinstance(bool)` check instead of silent coercion).
- `create_tool_gateway()` narrowed: policy LOAD/READ failures still fall back to a safe default; invalid absorbed content now surfaces as `ValueError` (no silent swallow).
- No runtime behavior change — enforcement lands in PR-B2.

**PR-B2 (#151) — Runtime enforcement + MCP integration.**
- `ToolGateway.dispatch()` now enforces every B1-absorbed field:
  - `max_calls_per_request` — per-request call cap (separate from `max_rounds` agentic loop count).
  - `allowed_tools` — empty = permissive (matches `create_tool_gateway()` bundled-default reality + `governance._check_tool_calling` alignment); non-empty = strict fail-closed.
  - `blocked_tools` — always overrides `allowed_tools`.
  - `cycle_detection` — suffix-based repeat-call detection using a JSON fingerprint with `default=repr` fallback. Denied attempts are NOT recorded in the history (prevents self-feeding deny loops).
  - `mutating_requires_confirmation` — gated by a new additive `ToolSpec.is_mutating` flag (default False, backward-compatible). No MCP governance tool currently carries the flag (B2 iter-3 absorb: until a confirmation flow exists, flagging `ao_memory_write=True` would lock it DENY under the bundled policy; the write governance still runs via `policy_mcp_memory.write` inside the handler).
- `authorize()` vs `dispatch()` split: `authorize()` handles static checks (policy/name/spec/blocklist/allowlist/max_rounds/mutating-confirm); `dispatch()` handles stateful/input-dependent checks (per-request cap, cycle detection).
- `ToolCallResult.reason_code` (new) — machine-readable denial key. 9 canonical codes: `POLICY_DISABLED`, `TOOL_NOT_REGISTERED`, `TOOL_NOT_ALLOWED`, `MAX_ROUNDS_EXCEEDED`, `BLOCKED_BY_POLICY`, `NOT_IN_ALLOWLIST`, `MAX_CALLS_PER_REQUEST_EXCEEDED`, `CYCLE_DETECTED`, `MUTATING_REQUIRES_CONFIRMATION`. `reason` field kept for human-readable text (mirrors `reason_code` when set).
- `reset_rounds()` extended to clear all transient per-request state (`_call_count`, `_request_call_count`, `_recent_calls`). `AoKernelClient.llm_call()` calls `reset_rounds()` at the top of every LLM request (iter-1 BLOCKER absorb: persistent gateway regression across calls).
- MCP `call_tool()` denial envelope propagates `gw_result.reason_code` in `reason_codes` (falls back to `reason` for pre-B2 callers). Denied calls audited via `record_mcp_event()` using `_resolve_workspace_for_call()` — same resolver as the success path (iter-2 MEDIUM absorb: avoids `.ao/.ao/evidence/...` nesting).
- `list_tools()` output now includes `is_mutating` so introspection surfaces the mutating flag.
- `governance._check_tool_calling()` aligned to the gateway semantic; legacy `TOOL_NO_ALLOWLIST` violation removed (the bundled default policy ships with `allowed_tools=[]` and would otherwise reject every governance call).
- Schema `policy-tool-calling.schema.v1.json` `allowed_tools.description` updated to document the empty=permissive / non-empty=strict contract.

### Migration note

The B2 runtime changes are **only observable** when an operator writes a non-default policy. Bundled policy ships with `enabled=false` (opt-in) and `allowed_tools=[]` (permissive under both pre-B2 and B2 semantics). Review if you author a custom policy:

- `allowed_tools=[]` → behavior preserved, permissive. No action.
- `allowed_tools=["tool_a", ...]` (non-empty) → now strictly enforced at the gateway. Tools outside list return `DENIED` with `reason_code="NOT_IN_ALLOWLIST"`.
- `blocked_tools=["unsafe"]` → enforced at the gateway; `reason_code="BLOCKED_BY_POLICY"`; overrides `allowed_tools`.
- `max_tool_calls_per_request` / `cycle_detection.max_identical_calls` → dormant pre-B1, enforced now. Gateways that accepted 100+ identical repeats or ran past the per-request cap return `DENIED` with the corresponding `reason_code`.
- `tool_permissions.mutating_requires_confirmation=true` + `default_permission="read_only"` → will begin denying tools flagged `is_mutating=True`. Bundled MCP governance tools intentionally carry no such flag in v3.9 (no confirmation flow yet). External callers who register their own tools via `ToolGateway.register_handler(..., is_mutating=True)` will see the `MUTATING_REQUIRES_CONFIRMATION` deny under the bundled policy.

### Known follow-ups (tracked at release time)

> The three items that shipped at v3.9.0 as "known follow-ups" (`_internal/utils/*` coverage tranche, legacy bool-strict hygiene, `call_tool()` standalone reset) have been triaged post-release: M1 + M2 landed under `[Unreleased]`; the `call_tool()` item remains open for v3.10 per Codex's plan-time rejection of a per-call auto-reset (public tool-use contract).

## [3.8.0] - 2026-04-19

### Added — v3.8.0 Rolling Hardening (5 PRs, no feature surface growth)

**Context.** v3.5–v3.7 were feature-heavy (consultation surfaces, memory loop, benchmark realism). v3.8 clears accumulated hardening debt without net-new features. Codex plan-time master AGREE with 3 revisions absorbed (H4 = dead-only cleanup, H3 deferred, H6 covers both workflows). Parallel-lane execution model: micro PRs (H6 + H5) shipped first, then H4, then core serial (H2 → H1). Two of the five PRs had Codex post-impl BLOCK → iter-2 MERGE (F2-style pattern).

**H6 (#144) — CI pip-install retry wrapper.**
- Wrap every `pip install` in `.github/workflows/test.yml` + `.github/workflows/publish.yml` with a 2-try `|| (sleep 5 && pip install ...)` pattern (inline bash; no new action deps). Motivated by a one-off `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC` seen on the v3.7 release CI. No runtime / product code changes.

**H5 (#145) — consultation lane observability accounting.**
- Closes Codex v3.6 E2 residual note: consultation lines were budget-aware (v3.6 E2 iter-2 absorb) but invisible to `items_included` / `items_excluded` / `selection_log` counters.
- `compile_context`:
  - Accepted consultation → `included_count++` + `selection_log` entry with `lane="consultation"`, `included=True`
  - Budget-dropped consultation → `consultation_excluded++` + `selection_log` entry with `reason="excluded: token budget (...) exceeded"`
  - **H5 iter-2 BLOCK absorb (Codex)**: cap-dropped consultations (`consultations[cap:]` tail) were initially invisible too. Fix iterates the cap-drop tail first, adding each to `consultation_excluded` with `reason="excluded: max_consultations (...) cap"` so EMERGENCY (cap=0) and TASK_EXECUTION (cap=3 with 5 inputs) surface every dropped record.
- Counter contract: `items_included + items_excluded` covers all four lanes.

**H4 (#146) — dead `quality_waiver` pytest marker cleanup.**
- `pyproject.toml::tool.pytest.ini_options.markers`: drop the unused `quality_waiver` entry (zero `@pytest.mark.quality_waiver` usage in code/tests/docs). Dynamic markers registered via `conftest.py::addinivalue_line` (e.g. `scorecard_primary`, `full_mode`) unaffected. Revival stays out of scope per Codex iter-1 AGREE (would require full design pass: marker + collection reporter + gate integration).

**H2 (#147) — `emit_adapter_log` FS lock parity.**
- **Codex plan-time scope pivot saved this PR.** My initial audit had 3 false positives (`consultation/evidence.py::append_event` runs under outer archive lock; `_internal/evidence/writer.py` is dormant/test-only; `cost/ledger.py` already sidecar-locked) + missed the real gap. Codex's deeper grep caught `executor/evidence_emitter.py::emit_adapter_log` which had only a comment-level "single-writer during invocation" assumption.
- Fix: wrap the append in `file_lock(adapter_log_path + ".lock")` — sidecar-lock pattern per CNS-20260414-010. POSIX-only; Windows fail-closed preserved.
- New concurrency regression test (`tests/test_emit_adapter_log_concurrent.py`): 8 threads × 4 appends → 32 total; invariants: line count, every line parses as JSON, sidecar `.lock` exists. Pattern follows repo precedent (`test_cost_ledger_concurrent.py`, `test_canonical_store_cas.py`).

**H1 (#148) — `_internal/secrets/*` coverage tranche (tranche 1).**
- Narrow the D13 "aşamalı dahil etme" omit list: `ao_kernel/_internal/secrets/*` removed from `coverage.run.omit`, so its ~174 stmts + ~130 branches feed the gate.
- **H1 iter-2 BLOCK absorb (Codex)**: initial commit lowered `fail_under` 85→84 as a ratchet-down (unacceptable as final v3.8 PR — global enforcement rollback). Iter-2 reverts to 85, widens `exclude_lines` to drop `@overload` stubs + `if TYPE_CHECKING:` blocks (typing-only, runtime-unreachable — not real coverage gaps), and adds 15 new pins covering the actual secrets-tree branches:
  - `api_key_resolver.py`: factory-exception → env fallback, audit True/False paths, missing-key returns, `environ=None` os.environ default, empty-string provider value, `env_names_for` unknown/known/case-insensitive lookups, `_default_provider` factory-load swallow
  - `factory.py`: unknown ValueError, `vault_stub` default path, `str → Path` coercion
  - `hashicorp_vault_provider.py`: missing-slash/addr/token, non-dict response body, non-string value, empty-string value
- Coverage overall: **85.03%** — preserves the 85 gate cleanly.

### Test baseline

- **2506 pass, 1 skipped** (up from v3.7.0's 2447 + 1; delta ≈ +59 across H5/H2/H1 new pins).
- Ruff + mypy clean on 205 source files.
- Coverage 85.03% (gate 85).

### Governance pattern

Plan-time master AGREE + per-PR post-impl Codex review. 2 of 5 PRs ran BLOCK → iter-2 absorb → MERGE (H5 cap-exclusion accounting, H1 global-gate reversal). Codex deep-grep saved H2 from an incorrect audit; F2-style scope pivot reuse. Parallel-lane execution model (micro PRs lane 1+2, core serial lane) matched the v3.8 plan §4 sequencing exactly.

### Scope boundaries (v3.8)

- **IN:** H6 CI retry + H5 observability accounting + H4 dead-marker cleanup + H2 lock parity (scope-pivoted to live gap) + H1 coverage tranche 1.
- **OUT (v3.9+):** external real-adapter benchmark smoke (F2.1+), remaining `_internal/*` coverage tranches (shared/utils/providers/prj_kernel_api still omit'd), `save_store()` deprecation cleanup (H3 deferred).
- **OUT (v4.0):** `save_store()` public symbol removal (breaking change).

## [3.7.0] - 2026-04-19

### Added — v3.7.0 Benchmark Realism (F1 + F2)

**Context.** v3.5–v3.6 closed the consultation producer/consumer loop. v3.7 tightens the benchmark surface by exposing a real-adapter-transport path (`--benchmark-mode=full`) and wiring event-backed cost-source detection into the scorecard. The default CI path is unchanged — `.github/workflows/test.yml` diff=0 — so the v3.7 changes are opt-in. Codex plan-time CNS: 2 rounds (scope correction) → AGREE. Each F-series PR also ran post-impl review per the v3.5+ two-gate rule.

**F1 (#141) — Benchmark full-mode activation scaffold + secret canonicalization.**
- New `pytest_addoption --benchmark-mode=fast|full` + `benchmark_mode` fixture + `@pytest.mark.full_mode` marker in `tests/benchmarks/conftest.py`. Collection hook gates benchmark tests by mode (fast skips `@full_mode`; full skips non-`@full_mode` benchmark tests). Only `tests/benchmarks/` items are affected.
- Bundled `policy_secrets.v1.json` allowlist widened to a 5-entry backward-compat set (`ANTHROPIC_API_KEY`, `CLAUDE_API_KEY`, `GH_TOKEN`, `GITHUB_TOKEN`, `OPENAI_API_KEY`). Actual fail-close gate remains `policy_worktree_profile.v1.json::secrets.allowlist_secret_ids`; the bundled policy is the docs/ops canonical surface.
- New `docs/BENCHMARK-FULL-MODE.md` operator runbook.
- F1 iter-2 BLOCK absorb: narrowed claims to **scaffold only** — F1 ships the option + marker + fixture + secret registry + `context_pack_ref` artefact pin but does NOT include a runnable `@full_mode` smoke (the first smoke lands in F2).

**F2 (#142) — Adapter-path cost reconcile benchmark uplift.**
- Removed `tests/benchmarks/mock_transport.py::_maybe_consume_budget` shim. Fast-mode mock runs no longer drain `budget.cost_usd`; the adapter-path `post_adapter_reconcile` middleware (v3.3.0 PR-C3) is the sole drainer.
- **Event-backed cost-source detection** (`ao_kernel/_internal/scorecard/collector.py::_detect_cost_source`):
  1. `llm_spend_recorded(payload.source="adapter_path")` in events → `cost_source="real_adapter"`.
  2. Else legacy positive budget drain (historical artefacts from the removed shim) → `"mock_shim"`.
  3. Otherwise `None` (the common F2+ fast-mode path).
- **Render footer wording** (per Codex iter-2 correction): `real_adapter` → "adapter-path reconcile (event-backed; non-shim)". Explicitly NOT "real adapter spend" — codex-stub emits canned events, not vendor billing.
- First runnable `@full_mode` smoke — `TestFullModeAdapterPathReconcile::test_governed_review_emits_adapter_path_spend_event` dispatches `governed_review` through real `invoke_cli` → codex-stub. Graceful skip when `python3` cannot import `ao_kernel` (prereq miss); other workflow failure categories surface via `pytest.fail`.
- Mode-gated `workspace_root` fixture: full mode flips `policy_cost_tracking.enabled=true`; fast mode keeps bundled dormant default. Mode-gated `pytest_sessionfinish`: fast={bugfix, review}; full={review}; empty registry (prereq skip) → empty expected set to preserve graceful skip.
- New assertion helpers: `assert_budget_unchanged` (fast-mode post-F2 pin), `assert_spend_recorded_event` (full-mode event-backed pin). `assert_cost_consumed` semantics preserved for historical artefacts.
- F2 iter-2 BLOCK absorb: graceful-skip ↔ session-finish invariant conflict resolved; prereq detection widened to include `COMMAND_NOT_FOUND` code.

**Test baseline.** 2437 → 2447 (+10 new pins across F1 + F2 collector/render/benchmark). 1 skipped (full-mode smoke prereq-gated in local env; CI with `pip install -e` exercises the real path). Ruff + mypy clean on 205 source files.

**Governance pattern.** Plan-time master AGREE (2 rounds — scope correction from "external claude-code-cli spend" to "minimal codex-stub path") + per-PR post-impl Codex review with BLOCK absorb on both F1 and F2 before MERGE.

**Scope boundaries (v3.7).**
- IN: F1 scaffold + F2 codex-stub adapter-path reconcile smoke + scorecard event-backed detection + secret canonicalization + operator runbook.
- OUT → **F2.1+ / v3.9 governance**: external `claude-code-cli` / `gh-cli-pr` wiring, bench workflow variants referencing real vendor adapters, `policy_worktree_profile.enabled=true` bundled flip, `review_findings` capability advertise on `claude-code-cli.manifest.v1.json`.
- OUT → **v3.8 Rolling Hardening**: `_internal` coverage lift tranche, FS lock parity audit, `save_store()` deprecation cleanup, `quality_waiver` dead-or-enforce decision, optional CI pip-install retry wrapper.
- OUT: v3.6 observability cleanup (`items_included/items_excluded/selection_log` consultation accounting) — nice-to-have; deferred to post-release patch or folded into v3.8.

## [3.6.0] - 2026-04-19

### Added — v3.6.0 Memory Loop Closure (consumer side for v3.5 promotion)

**Context.** v3.5 shipped the **producer side** of consultation memory (D1 paths, D2a archive, D2b opt-in canonical promotion). v3.6 closes the loop on the **consumer side** with three additive PRs. Codex plan-time master CNS: iter-1 conditional AGREE (8 revisions absorbed: compiler purity, section-header reuse, hydration policy, pagination narrative, docs scope widening, ProfileConfig SSOT, dedup test rewording, handler-local pagination) → iter-2 AGREE. Each E-series PR also ran post-impl review per the v3.5+ two-gate rule.

**E1 — PromotedConsultation reader facade (#137).**
- New typed dataclass `PromotedConsultation` (10 fields spanning value/provenance/top-level canonical entry layers).
- Public `query_promoted_consultations(workspace_root, *, verdict, topic, include_expired)` in `ao_kernel/consultation/promotion.py` — thin wrapper over `canonical_store.query(category="consultation")`.
- **Strict core, lenient edges hydration**: rows missing `cns_id` / `final_verdict` / `promoted_at` silently SKIPPED (reader never raises on malformed store content); `topic` / `from_agent` / `to_agent` None-tolerant; `confidence` derived from verdict when absent.
- **Category-authoritative filter** (Codex post-impl SUGGEST absorb): drops key-prefix restriction so `category="consultation"` rows under any canonical key still hydrate.
- **Malformed-store defence**: two distinct canonical rows resolving to the same `cns_id` deduped by most recent `promoted_at` (future store-format drift guard).

**E2 — Context pipeline consultation lane (#138).**
- `ProfileConfig.max_consultations` SSOT per-profile cap: PLANNING/REVIEW=10, STARTUP/TASK_EXECUTION/ASSESSMENT=3, EMERGENCY=0 (lean-context invariant).
- `compile_context` stays pure — accepts `consultations: Sequence[PromotedConsultation]` parameter; I/O handled in `compile_context_sdk` which queries via E1 facade, prefers AGREE over PARTIAL, slices by profile cap.
- **`## Consultations` section** in preamble (reuses existing section-header pattern). Render: `- [CNS-ID] topic VERDICT (from→to, resolved_at)`. Null-tolerant edges render as `(topic unknown)` / `(from)` / `(to)` / `unresolved` — never literal "None".
- **Canonical lane dedup** (Codex post-impl BLOCK #1 absorb): `compile_context_sdk` filters `category="consultation"` rows out of canonical_dict so promoted consultations appear exactly once under the typed section.
- **Budget-aware consultation truncation** (Codex post-impl BLOCK #2 absorb): consultation lines count toward `max_tokens * 4` char budget; tail-first drop when over budget; `total_tokens` reflects consultation chars; telemetry accurate.

**E3 — MCP memory_read pagination + consumer-side docs (#139).**
- `ao_memory_read` inputSchema additive: `max_results` (default 50, hard cap 200) + `offset` (default 0). Existing callers unaffected.
- Response `data` gains `total` (post-policy-filter total across the full query) + `next_offset` (cursor for next page, null when exhausted) alongside existing `items` + `count` (entries in this page).
- Handler-local pagination (Codex iter-1 revision #8): `canonical_store.query()` signature unchanged.
- Invalid pagination params → `deny` with `invalid_max_results` / `invalid_offset` reason codes.
- New **`docs/CONSULTATION-QUERY.md`** — 6-section consumer guide: policy opt-in, E1 Python API, E3 MCP pagination loop, AGREE/PARTIAL semantics.
- **4-lane doc updates**: `CLAUDE.md` §9 3-Lane → 4-Lane + canonical-lane filter note; `README.md` governance row; `docs/DEMO-SCRIPT.md` three-lane → four-lane inline; `docs/EVIDENCE-TIMELINE.md` cross-link to consumer doc.

**Test baseline.** +27 new pins across v3.6 (E1 11 + E2 10 + E3 8 — +3 more than plan because of iter-2 BLOCK absorbs). 2437 total pass (up from 2408 at v3.5.0). Ruff + mypy clean on 205 source files.

**Scope boundary.**
- IN: E1 typed reader facade + E2 4-lane compiler + E3 pagination + consumer docs
- OUT: multi-commit scorecard trend / sparkline (v3.6+ scope but deferred; same `scorecard-*` surface can grow later)
- OUT: category registry schema (v3.7+)
- OUT: delta / changelog subscription API (v4.x)
- OUT: cross-workspace consultation replication
- OUT: MCP write-side widening (producer surface stable from v3.5 D2b)

## [3.5.0] - 2026-04-19

### Added — v3.5.0 D3 Dev Scorecard (benchmark compare + PR comment)

**Context.** PR-B7 emits benchmark run-dir events + capability artefacts, but there was no aggregated surface for comparing a PR's benchmark output against the main-branch baseline or posting a compact scorecard comment. D3 closes that gap as the final v3.5.0 commitment. Codex plan-time CNS: 2 iterations → AGREE (iter-1 PARTIAL → iter-2 AGREE after absorbing canonical-input marker + CI SSOT + block/warn split revisions). Trend / sparkline visualisation deferred to v3.6+.

**Changes.**

- **New module** `ao_kernel/scorecard.py` (public facade) + `_internal/scorecard/{collector,compare,render,post_comment}.py`. Typed `BenchmarkResult` / `ScorecardDiff` dataclasses + atomic-write emit path, pure-function compare + render, `gh api` sticky-comment upsert.
- **Canonical input** via `@pytest.mark.scorecard_primary` on happy-path tests (`test_review_findings_flow_completes` + `test_end_to_end_completes`). Exactly-one-primary-per-scenario rule — duplicate AND missing both fail-close at session finish (`ScorecardCollectorError`). `EXPECTED_PRIMARY_SCENARIOS = {governed_bugfix, governed_review}`.
- **Schemas** `scorecard.schema.v1.json` (`urn:ao:scorecard:v1`, top-level strict, `benchmark_result` forward-extensible with `additionalProperties: true`) + `policy-scorecard.schema.v1.json` (`urn:ao:policy-scorecard:v1`, strict all layers).
- **Policy** `policy_scorecard.v1.json` — `enabled: true`, `fail_action: "warn"`, regression thresholds (`duration_ms_relative_pct: 30.0`, `cost_usd_relative_pct: 20.0`, `review_score_min_delta: -0.1`). `enabled` gates `compare` + comment only; `emit` is policy-agnostic.
- **CLI** `ao-kernel scorecard {emit,compare,render,post-comment}`. `compare --baseline ... --head ...` exits 0 on warn / 1 on block+regression. `post-comment --pr N --body-file F --sentinel M` is advisory-only (exit 0 even on failure).
- **CI workflow**: `benchmark-fast` job extended with `AO_SCORECARD_OUTPUT` env var + head-artefact upload + `scorecard-main` baseline upload on main push. New `scorecard` job (PR-only, `continue-on-error: true`, `dawidd6/action-download-artifact` SHA-pinned to `bf251b5a`) downloads head + baseline, runs `compare`, upserts a sentinel-tagged sticky PR comment.
- **Cost source label** — new `cost_source` schema field always populated (`"mock_shim"` v1, `"real_adapter"` post-C3). Render footer surfaces it as "benchmark-only; not real billing" so mock-shim baselines are never misread as real spend.

**Plan-time + post-impl gate** followed per v3.5+ two-gate rule (feedback_v35_codex_two_gate).

**Test baseline.** +51 new pins (collector 16 + compare 11 + render 8 + cli 12 + schema 4), 10 benchmark tests still pass with the collector wired in, 2408 total. Ruff + mypy clean.

**Codex post-impl review: BLOCK → MERGE after iter-2 absorb.** Two blockers + one suggest absorbed:
- Canonical-input contract violations (duplicate OR partial-missing primary markers) now propagate a non-zero pytest exit status (`ExitCode.USAGE_ERROR=4`), not just a log line.
- `finalize_session()` checks `expected_scenarios - observed` instead of only `observed == set()`, so partial misconfiguration (one scenario marked, another silently dropped) also fail-closes.
- `policy_scorecard.enabled` + `post_pr_comment` now wired end-to-end: `compare` emits an advisory banner + exit 0 without rendering when `enabled=false`; `post-comment` honours both flags and skips the upsert with an advisory stderr line.

**Scope boundary.**
- IN: scorecard emit + compare + render + sticky PR comment + bundled policy `warn`
- OUT: multi-commit trend / ASCII sparkline (v3.6+)
- OUT: CI-gate enforcement (bundled `fail_action=block`; only local/manual today)
- OUT: full-adapter real-billing cost axis (C3)
- OUT: new benchmark scenarios (B7.x+)

### Added — v3.5.0 D2b Canonical promotion (opt-in)

**Context.** D2a produced source-stable `resolution.record.v1.json` artefacts. D2b promotes eligible records (status=resolved AND final_verdict in {AGREE, PARTIAL}) into the existing canonical decision store (`.ao/canonical_decisions.v1.json`) via `ao_kernel.context.canonical_store.promote_decision()`. Opt-in (policy `promotion.enabled=false` default); `--force` bypasses only the policy flag, never integrity or eligibility gates. Codex plan-time CNS: 3 iterations → AGREE.

**Changes.**

- **New module** `ao_kernel/consultation/promotion.py` — thin adapter over `canonical_store.promote_decision()`. Key namespace: `consultation.<CNS-ID>`. Compact value (cns_id, topic, from_agent, to_agent, final_verdict, resolved_at) + provenance pointer (`evidence_path`, `resolution_record_path`, `record_digest`). Full response corpus stays on disk under evidence dir.
- **Shared digest helper** `record_digest()` promoted to public in `ao_kernel/consultation/normalize.py` so archive + promotion share one SSOT (Codex iter-3 execution note #1).
- **Policy widen** `policy_agent_consultation.v1.json::promotion` (optional object, `enabled: bool` only). Schema updated with strict `additionalProperties: false`.
- **New CLI** `ao-kernel consultation promote [--dry-run] [--force] [--output json|human]`.

**Pipeline guardrails**:

1. Policy gate (skip_disabled unless `--force`)
2. Integrity gate (`verify_consultation_manifest` must pass)
3. Eligibility (status=resolved AND final_verdict in {AGREE, PARTIAL})
4. Idempotency (`provenance.record_digest` compared; same digest → no-op)
5. Promotion via `promote_decision()` (telemetry `record_canonical_promote(category="consultation")` fires automatically — no double-count)

**Confidence mapping** (narrow, promotable only):
- `AGREE` → 1.0
- `PARTIAL` → 0.7

**Test baseline.** +18 new pins in `tests/test_consultation_d2b.py`: verdict confidence (3), eligibility (5), idempotency (2), key/value contract (2), policy flag (2), integrity + empty workspace (2), dry-run (1), request revisions (1). Ruff + mypy clean.

**Scope boundary.**
- IN: promote AGREE/PARTIAL resolved records + CLI + policy flag + schema widen
- OUT: REVISE/REJECT "negative consensus store" (v3.6+)
- OUT: Dual-read cut-over (v3.6 Memory Loop Closure)
- OUT: MCP memory query integration (v3.6)

### Added — v3.5.0 D2a Consultation archive + normalization + integrity manifest

**Context.** D1 canonicalized CNS paths. D2a walks the corpus, snapshots request/response files under a dedicated consultation evidence surface (`.ao/evidence/consultations/<CNS-ID>/`), normalizes heterogeneous verdicts into a 5-bucket enum, builds a **source-stable** resolution record (digest unchanged across re-runs with unchanged sources), emits events with persistent dedupe, and refreshes an SHA-256 integrity manifest. Archive/backfill only — live dual-write (MCP intercept of CNS writers) deferred to v3.6. Codex plan-time CNS: 4 iterations → AGREE.

**Changes.**

- **New modules**:
  - `ao_kernel/consultation/normalize.py` — `NormalizedVerdict` enum (AGREE / PARTIAL / REVISE / REJECT / UNCLASSIFIED), verdict mapping matrix covering string + `option_id` object variants (body heuristics deliberately excluded), `ResolutionRecord` dataclass with request revisions first-class + source-derived `resolved_at` (no `config_digest` — archive-time metadata separated).
  - `ao_kernel/consultation/evidence.py` — `ConsultationEventKind` (5 kinds: OPENED / REQUEST_REVISED / RESPONSE_RECEIVED / NORMALIZED / INVALID), per-kind identity dedupe (source-based vs record-digest-based), `preload_event_identities` for persistent dedupe across process restarts.
  - `ao_kernel/consultation/integrity.py` — consultation-specific SHA-256 manifest (`integrity.manifest.v1.json`) covering request + response snapshots + `events.jsonl` + `resolution.record.v1.json`. Excludes `archive-meta.json` (archive-time drift tolerated) and the manifest itself. `write_archive_meta` produces a separate `archive-meta.json` with `config_digest` + `archived_at`.
  - `ao_kernel/consultation/archive.py` — orchestrator. `archive_all(policy, *, workspace_root, dry_run=False, renormalize=False)`. Per-CNS `file_lock` via `_internal/shared/lock.py`.
- **New CLI** `ao-kernel consultation archive [--dry-run] [--renormalize] [--output json|human] [--project-root PATH]`.

**Idempotency guarantees** (Codex iter-4 AGREE):

- Same source + same `normalizer_version` → event append skipped (persistent dedupe via `events.jsonl` preload)
- Same `resolution_record_digest` → normalized event skipped
- Resolution record overwrite only when content digest changes
- Snapshot copies overwritten idempotently
- `--renormalize` forces record rebuild after `normalizer_version` upgrades (prevents automatic churn)

**Evidence surface layout**:
```
.ao/evidence/consultations/<CNS-ID>/
├── requests/<CNS-ID>[.iterN].request.v1.json    (snapshots)
├── responses/<CNS-ID>[.iterN].<agent>.response.v1.json
├── events.jsonl
├── resolution.record.v1.json                    (source-stable)
├── archive-meta.json                            (archive-time metadata)
└── integrity.manifest.v1.json
```

**Scope boundary**:
- IN: archive/backfill + normalize + manifest + CLI
- OUT (D2b): canonical decision promotion
- OUT (v3.6): live dual-write via writer intercept, abandonment TTL determination, dual-read cut-over
- OUT (v3.6+): normalizer version migration (explicit `--renormalize` only)

**Test baseline.** +25 new pins in `tests/test_consultation_d2a.py` across 5 classes: verdict normalization (10 pins including object variants + UNCLASSIFIED fallback), record source stability (5), per-kind dedupe (3), integrity manifest (4), iteration parsing (3).

### Added — v3.5.0 D1 Consultation path canonicalization

**Context.** Repo practice has treated `.ao/consultations/` as the canonical CNS (adversarial agent consultation) artefact directory since early FAZ-C, but `policy_agent_consultation.v1.json` still pointed at the pre-v3.5 `.cache/...` paths. v3.5.0 D1 closes the drift: policy + resolver + migration script now share one source of truth under `.ao/consultations/`, with the legacy `.cache/...` directories preserved as read-only fallbacks until cut-over.

**Changes.**

- **Policy widen** `policy_agent_consultation.v1.json::paths` — canonical `.ao/consultations/*` entries, `legacy_fallbacks` map holding the pre-v3.5 `.cache/...` paths
- **New module** `ao_kernel/consultation/paths.py`:
  - `ConsultationPaths` dataclass + `load_consultation_paths(policy, *, workspace_root)` loader
  - `resolve_consultation_dir(policy, artefact, *, workspace_root, prefer_legacy=False)` — canonical by default, legacy fallback on read
  - `FileClassification` enum: `VALID_CURRENT` / `LEGACY_SHAPE` / `INVALID_JSON` — Codex iter-2 advice: responses are classified, not strict-validated
  - `iter_consultation_files` walks canonical + legacy; request/response classifiers applied based on artefact type
- **New module** `ao_kernel/consultation/migrate.py`:
  - `migrate_consultations(policy, *, workspace_root, dry_run=False, force=False, include_invalid=False)` — copy-forward (not in-place move), non-destructive by default, manifest written under `.ao/consultations/.migration_backup/migration-{timestamp}.json`
- **New CLI** `ao-kernel consultation migrate [--dry-run] [--force] [--include-invalid] [--output json|human]`

**Scope.** Paths + classify + migration only. Evidence emit + normalization + canonical promotion land in D2a/D2b.

**Test baseline.** +13 new pins in `tests/test_consultation_paths.py`: policy asserts canonical paths, resolver prefers-legacy fallback, request/response classifiers (valid / legacy / invalid), iter walks both origins, migration dry-run / apply / idempotent.


## [3.4.0] — 2026-04-18

**v3.4.0 — Cost Runtime Maturity + Routing Extensibility**. Seven follow-ups landed in one session: reconciler daemon for orphan spends, evidence payload enrichment, marker compaction, full-actor dry-run parity, multi-step downgrade chain, per-workspace routing overrides, and a real-crash test harness. All backward compatible.

Shipped PRs (all merged in one session):

| # | PR | Scope |
|---|---|---|
| 1 | [#124](https://github.com/Halildeu/ao-kernel/pull/124) | Reconciliation daemon + CLI (`ao-kernel cost reconcile`) |
| 2 | [#125](https://github.com/Halildeu/ao-kernel/pull/125) | `llm_spend_recorded` vendor_model_id enrichment |
| 3 | [#126](https://github.com/Halildeu/ao-kernel/pull/126) | `cost_reconciled` marker compaction + CLI (`ao-kernel cost compact-markers`) |
| 4 | [#127](https://github.com/Halildeu/ao-kernel/pull/127) | Non-adapter dry-run fidelity (system + ao-kernel actors) |
| 5 | [#128](https://github.com/Halildeu/ao-kernel/pull/128) | Multi-step downgrade chain (cascaded budget routing) |
| 6 | [#129](https://github.com/Halildeu/ao-kernel/pull/129) | Per-workspace `soft_degrade` / routing overrides |
| 7 | [#130](https://github.com/Halildeu/ao-kernel/pull/130) | Subprocess crash-kill test harness |

Test baseline: v3.3.1 2260 → v3.4.0 **~2300** (+40 new across the seven PRs). Ruff + mypy clean.

### Added — v3.4.0 #7 Subprocess crash-kill test harness

**Context.** Mock-based idempotency tests (`test_cost_marker_idempotency`, `test_reconcile_daemon`) cover the exception-handling branches but cannot catch issues that only surface when the OS really terminates an interpreter mid-write — unflushed buffers, fsync gaps, open-file leaks. v3.4.0 #7 adds a stdlib-only harness that spawns a fresh Python subprocess, runs partial work up to a chosen checkpoint, and calls `os._exit` so finalizers never run. The parent process then inspects surviving on-disk state and runs recovery.

**Changes.**

- **New helper** `tests/_subprocess_crash_helper.py::run_crash_scenario(*, script, workspace_root, expected_exit_code=77, timeout_seconds=30.0)` — runs the supplied script in a subprocess with `workspace_root` as `sys.argv[1]`; asserts the process exits with the expected code. Returns `CompletedProcess` for diagnostic inspection.
- **New test** `tests/test_reconciler_crash_injection.py::TestReconcilerRealCrashRecovery` — end-to-end pin: real crash between ledger append (fsynced) and marker CAS leaves the ledger on disk, leaves `cost_reconciled` empty, and the reconcile daemon recovers in a parent-process scan (idempotent on second pass).

**Scope.** One helper + one end-to-end pin. Additional crash scenarios (marker stamp → emit gap, compaction mid-write, etc.) can follow the same pattern when motivated; the harness itself is reusable with no framework dependencies beyond stdlib + pytest.

### Added — v3.4.0 #4 Non-adapter dry-run fidelity (system + ao-kernel actors)

**Context.** v3.3.1 PR-C6.1 routed only `adapter` actors through `MultiStepDriver.dry_run_step`; `system` (ci-runner / patch-apply) and `ao-kernel` (context_compile / checkpoint) actors fell back to executor-only preview with no `parent_env` derivation. The CLI raised `NotImplementedError` for non-adapter via the driver entry point. v3.4.0 #4 closes that scope — all non-human actors now share a driver-managed dry-run path so the preview mirrors the real execution surface.

**Changes.**

- `MultiStepDriver.dry_run_step`: branches on `step_def.actor`:
  - `adapter` — unchanged from C6.1 (envelope + `_compute_adapter_parent_env`)
  - `system` — no envelope override, `_compute_sandbox_parent_env` (allowlist **MINUS** secrets, matching real CI/patch sandbox surface)
  - `ao-kernel` — no envelope, no parent_env (in-process execution has no sandbox surface)
  - Any other actor value (e.g. `human`) raises `NotImplementedError` with an explicit message — `human` steps are interactive and do not dry-run
- CLI `ao-kernel executor dry-run` — non-adapter actors now route through the driver by default (preserving the sandbox parent_env derivation); `--executor-only` still forces the pre-C6.1 executor-direct path for debugging

**Test baseline.** +2 new pins in `tests/test_dry_run_driver.py`: `system` actor sandbox parent_env propagation, `ao-kernel` actor in-process dispatch (no envelope, no parent_env).

### Added — v3.4.0 #2 `llm_spend_recorded` vendor_model_id enrichment

**Context.** v3.3.1 PR-C3.1 made `vendor_model_id` an adapter-reportable field on `cost_record` and threaded it into the spend ledger, but the corresponding `llm_spend_recorded` evidence event did not carry the attribution — audit tooling had to cross-reference the ledger to recover the vendor model identity. v3.4.0 #2 copies the field into the evidence payload so a single stream (events.jsonl) is sufficient for downstream analysis.

**Changes.**

- Governed-call path (`post_response_reconcile`): when `catalog_entry.vendor_model_id` is set, the emit payload includes it.
- Adapter path (`post_adapter_reconcile`): when `SpendEvent.vendor_model_id` (adapter-supplied per C3.1) is set, the emit payload includes it. Absent values continue to produce payloads WITHOUT the key (not `null`) — consistent with the ledger omission policy.

**Test baseline.** +2 new pins in `tests/test_post_adapter_reconcile.py::TestSpendEvidenceVendorEnrichment`: propagation when present, omission when adapter doesn't supply.

**Deferred.** `llm_usage_missing` evidence payload enrichment (same pattern but on the audit-only path) — low demand, future increment.

## [3.3.1] — 2026-04-18

**v3.3.1 — v3.3.0 Follow-Ups Closed**. Four known limitations documented in v3.3.0 CHANGELOG are addressed: the adapter-path double-drain bug, runtime activation of cross-class downgrade plumbing, adapter vendor_model_id attribution, and dry-run driver-layer parity. Backward compatible; no schema migration required.

Shipped PRs (all merged in one session, Codex adversarial consensus per PR):

| # | PR | Scope |
|---|---|---|
| 1 | [#119](https://github.com/Halildeu/ao-kernel/pull/119) | C3.2 post-reconcile crash-window + double-drain (marker-driven idempotency, 5 plan iterations) |
| 2 | [#120](https://github.com/Halildeu/ao-kernel/pull/120) | C4.1 cross-class downgrade runtime activation (4 plan iterations + 2 BLOCK post-impl absorbs) |
| 3 | [#121](https://github.com/Halildeu/ao-kernel/pull/121) | C3.1 adapter vendor_model_id attribution (1 plan iteration → AGREE) |
| 4 | [#122](https://github.com/Halildeu/ao-kernel/pull/122) | C6.1 adapter-step dry-run driver parity (5 plan iterations → AGREE) |

Test baseline: v3.3.0 `2210` → v3.3.1 **`2262`** (+52 new). Ruff + mypy clean across all 189 source files. All 8 CI gates green on each PR.

### Fixed — PR-C3.2 crash-window double-drain fix

**Context.** v3.3.0 shipped a post-reconcile idempotency bug: when `post_adapter_reconcile` / `post_response_reconcile` were invoked twice with the same `(run_id, step_id, attempt, billing_digest)`, `record_spend` correctly no-op'd (same-digest silent warn-log) but the subsequent `update_run` budget CAS ran unconditionally — a second identical reconcile double-drained the budget. Codex CNS-20260418-033 adversarial plan review (5 iterations) pinned the root cause; the refactor below closes it.

**Changes.**

- **New shared helper** `ao_kernel/cost/_reconcile.py::apply_spend_with_marker()` — unifies both cost reconcile paths (adapter + governed_call) behind a ledger-first + marker-guarded contract. Returns `True` when a NEW marker was committed; callers use the signal to gate evidence emit.
- **Marker schema** `workflow-run.cost_reconciled` (additive field on `workflow-run.schema.v1.json`) — array of `{source, step_id, attempt, billing_digest, recorded_at}`. Keyed by 4-tuple to avoid cross-path / cross-step suppression. Source enum: `adapter_path | governed_call | usage_missing`.
- **Order unification** — `post_response_reconcile` (governed_call path) now runs `record_spend` BEFORE `update_run`; previously budget-CAS ran first. `post_adapter_reconcile` was already ledger-first but now uses the shared helper. Crash semantics: ledger entry may exist without a marker (retry recovers), but NEVER the reverse.
- **Evidence emit guard** — `llm_spend_recorded` and `llm_usage_missing` events are emitted only when the helper commits a new marker. Duplicate reconcile calls produce no duplicate audit events. On the governed_call path, the `fail_closed_on_missing_usage` raise still fires regardless of marker state (terminal error per caller contract); on the adapter_path, usage-missing returns silently after the audit emit (existing contract — adapter callers handle the terminal error via the driver catch matrix).
- **Public digest helper** `ao_kernel.cost.compute_billing_digest()` — promoted from private `_compute_billing_digest`. Backward-compat alias retained. Callers invoke before `apply_spend_with_marker` to populate the marker key; helper raises `ValueError` on empty digest (Codex iter-5 precondition).
- **New exports** `ao_kernel.cost.{apply_spend_with_marker, compute_billing_digest, post_adapter_reconcile}`.

**Test baseline.** 2210 → **2222** (+12 new in `tests/test_cost_marker_idempotency.py`). Existing `test_same_digest_silent_no_op_on_second_call` extended with budget assertion — the v3.3.0 bug would have shown 9.90 remaining (double drain), now pinned to 9.95. Ruff + mypy clean. Scope explicitly excludes tam duplicate `governed_call` idempotency (reserve-phase problem, v3.4.0 follow-up); this PR closes post-reconcile phase only.

### Added — PR-C4.1 cross-class downgrade runtime activation

**Context.** v3.3.0 shipped `resolve_route(cross_class_downgrade=True, budget_remaining=...)` plumbing with the `route_cross_class_downgrade` event kind reserved, but the runtime ignored both kwargs. v3.3.1 turns it on: budget-aware soft-degrade rules now steer class selection when the run's remaining cost budget drops below a configured threshold. Codex CNS-20260418-034 adversarial plan review (4 iterations → AGREE) shaped the design against the existing `llm_resolver_rules.v1.json` shape instead of inventing a second taxonomy.

**Changes.**

- **Schema widen** `ao_kernel/defaults/schemas/schema_llm_resolver_rules.v1.json::soft_degrade.rules[]` — optional `budget_remaining_threshold_usd` (`type: "number"`, `minimum: 0`). Threshold-less rules (the bundled `DISCOVERY`/`BASELINE` degrade entries) stay **inert in v3.3.1 runtime** — behavior preserved, no unintended activation.
- **Router gating** `ao_kernel/_internal/prj_kernel_api/llm_router.py::resolve()` — five preconditions stack before a downgrade applies: (1) caller opts in via `cross_class_downgrade=True`, (2) `budget_remaining` snapshot present, (3) `strictness[from_class].degrade_allowed` not False (`REASONING_TEXT` / `CODE_AGENTIC` / `GOVERNANCE_ASSURANCE` block outright), (4) budget has a `cost_usd` axis with a remaining value, (5) a matching rule has a threshold AND `remaining < threshold_usd` (**strict** less-than — equality is no-downgrade).
- **Response additive fields** — `downgrade_applied: bool`, `original_class: str | None`, `downgraded_class: str | None`, `matched_rule_index: int | None`, `threshold_usd: float | None`, `budget_remaining_usd: float | None`. `selected_class` now reflects the **effective** class (post-downgrade) so callers / audit see the same value the provider selection used.
- **Startup schema validation** (inline, cached) — `llm_resolver_rules.v1.json` is validated against the additive-widened schema on first use. Malformed rules (e.g. negative threshold) raise `jsonschema.ValidationError` fail-closed. Reset hook `_reset_resolver_rules_cache()` provided for test isolation only.
- **Caller integration**:
  - `AoKernelClient._route(intent, run_id=...)` — loads the run budget snapshot via `load_run` + `budget_from_dict`, opts into `cross_class_downgrade=True` when a snapshot is available. Snapshot-load failures are silent (warn-log + no-downgrade) — route path stays on the core flow.
  - `AoKernelClient.llm_call` + `mcp_server.handle_llm_call` — when `route.downgrade_applied=True`, emit `route_cross_class_downgrade` event (fail-open `emit_event` wrap). Auto-route path only; explicit `provider_id` / `model` overrides bypass the route + emit entirely.

**Test baseline.** `tests/test_resolve_route_downgrade.py` (new, 16 tests across 6 test classes): budget-below / above / exactly-at threshold, threshold-less inert rule, strictness-deny gate, intent mismatch, budget-absence / axis-missing dormant paths, response contract completeness, effective-class selection, schema rejection, and three client `_route` integration pins. Backward compat for existing resolver rule callers verified by `test_resolve_route_kwargs.py` (6 tests unchanged).

**Migration.** No action required. Existing `soft_degrade.rules[]` without `budget_remaining_threshold_usd` are explicitly inert — pre-v3.3.1 dormant behavior is preserved. Operators who want budget-aware degradation add the threshold field to one or more rules in their workspace override.

### Fixed — PR-C3.1 adapter-path vendor_model_id attribution

**Enable + propagate.** v3.3.0 shipped `_build_adapter_spend_event` with `vendor_model_id=None` hardcoded — adapter-path spend events lost the concrete vendor model identity even when the adapter knew it. v3.3.1 makes the field adapter-reportable: `agent-adapter-contract.schema.v1.json::$defs/cost_record` gains an optional `vendor_model_id` (`minLength: 1` at the contract boundary), and the middleware propagates it into `SpendEvent`. Blank strings are normalized to `None` defensively in case a mal-formed producer writes whitespace. Codex CNS-20260418-035 post-AGREE with 3 clarity notes absorbed.

**Backward compat.** Adapters that don't populate the field (bundled fixtures `codex-stub`, `claude-code-cli`, `gh-cli-pr` — all mock/non-LLM; external adapters until they opt in) continue to produce ledger events with `vendor_model_id` omitted. No forced re-issue of historical ledger rows.

**Replay note.** If the same `(run_id, step_id, attempt)` tuple is reconciled a second time with a different `vendor_model_id`, the billing_digest changes → `SpendLedgerDuplicateError`. The digest already incorporates `vendor_model_id` (ledger.py:110); this is intentional behavior — attribution change is a caller bug, not a retry.

**Test baseline.** 2242 → **2250** (+8 new in `tests/test_post_adapter_reconcile.py`): propagation, absence fallback, blank-string normalization, `usage_missing` branch preservation, digest-based duplicate detection, and 3 schema-level pins (accept with, accept without, reject empty).

**Deferred to v3.4.0.**
- `llm_spend_recorded` evidence payload enrichment with `vendor_model_id`
- Cross-adapter reconciliation / audit replay keyed on `vendor_model_id`
- Multi-vendor cost compare in routing decisions

### Added — PR-C6.1 adapter-step dry-run parity

**Context.** v3.3.0 CLI `ao-kernel executor dry-run` routed directly through `Executor.dry_run_step`, which used a bare task-prompt envelope and an empty `parent_env` — driver-layer `context_pack_ref` + `parent_env` derivation was bypassed, so the preview did not match real adapter execution. Codex CNS-20260418-034 adversarial plan (5 iterations → AGREE) isolated the fix: add a driver entry point, widen the executor signature to pass through driver-managed context, and route adapter steps through the driver by default from the CLI.

**Changes.**

- **New driver method** `MultiStepDriver.dry_run_step(run_id, step_name, *, attempt=None)` — resolves the pinned workflow definition, applies 5 guards, and delegates to `Executor.dry_run_step` with the same `context_pack_ref` + `parent_env` the real `_run_adapter_step` path computes.
- **`Executor.dry_run_step` signature widen** — additive `input_envelope_override`, `step_id`, `driver_managed` kwargs forwarded to `run_step`. Backward compat preserved.
- **CLI actor-aware dispatch** — `ao-kernel executor dry-run` defaults to driver path for adapter actors; non-adapter actors (`aokernel`, `ci-runner`, `patch-apply`) use executor-only fallback (v3.3.0 behavior preserved). New `--executor-only` flag forces executor path. `--attempt` default flipped from `1` to `None` so the driver derives.

**Gating guards** (all `ValueError` except non-adapter → `NotImplementedError`):
1. Run-state guard: only `created` / `running`; terminal / `waiting_approval` / `interrupted` blocked.
2. Completed-step guard: highest-attempt `completed` blocks even with explicit `attempt=`.
3. Attempt validation: supplied `attempt` must equal `_next_attempt_number(record, step_name)`.
4. Running-placeholder reuse: highest attempt in `running` state at derived attempt → existing `step_id` reused.
5. Adapter-only (inner API): non-adapter raises `NotImplementedError`; CLI routes non-adapters to executor fallback.

**Test baseline.** 2250 → **2262** (+10 new in `tests/test_dry_run_driver.py`). Backward compat: 8/8 `test_dry_run_step.py` still pass.

**Scope boundary.** `v3.3.1` claim is **adapter-step parity**. Non-adapter full-fidelity, workflow-wide replay, canary runs, reverse-diff preview → v3.4.0.

### Deferred — out of v3.3.1 scope (v3.4.0)

- Full reconciliation daemon / API (`reconcile_orphan_spends`)
- Startup hook / CLI `ao-kernel cost reconcile`
- `cost_reconciled` array compaction (unbounded in v3.3.1 — Codex iter-3 advice: safer not to purge on finalize because late retry/replay could re-apply spend)
- Subprocess crash-kill test suite (mock-based crash coverage is sufficient for v3.3.1; subprocess tests pair with the reconciler daemon)

## [3.3.0] — 2026-04-18

**FAZ-C Runtime Closure + Strategic Extensions**. 9 PRs shipped in one session (#109 through #117) + B7.1 absorb.

### Added — FAZ-C Runtime Closure

- **PR-C1a (#109) `cba3e2e` — Adapter artifact surface + context_compile materialisation**. `ExecutionResult.output_ref` additive field; `context_compile` writes real markdown preamble; `Executor.run_step(input_envelope_override=None)`; driver resolver for `context_pack_ref`.
- **PR-C1b (#110) `7c3449a` — Patch plumbing + manifest parity**. `_load_pending_patch_content(workspace_root=...)` top-level `diff` fallback; `gh-cli-pr` manifest `input_envelope.context_pack_ref`.
- **PR-C2 (#111) `a581fb5` — parent_env security-split**. Adapter UNION `allowlist_secret_ids ∪ env_allowlist.allowed_keys`; sandbox env-only MINUS secrets (structural guard); `build_driver(policy_loader=...)` forwards to both.
- **PR-C2.1 (#115) `2201a6b` — Driver default bundled policy fallback**. `MultiStepDriver` uses `policy_config or _load_bundled_policy()` truthiness parity.
- **PR-C3 (#117) `fb72ac9` — post_adapter_reconcile cost runtime**. Reconcile-before-terminal-event ordering; fail-closed cost errors propagate; `source="adapter_path"` discriminator on `llm_spend_recorded`; wire: `cost_actual.{tokens_input,tokens_output,cost_usd}`.
- **PR-C6 (#114) `65d5250` — Executor.dry_run_step + CLI**. `DryRunResult`; `dry_run_execution_context` with 7 executor alias mocks; CLI `ao-kernel executor dry-run <run_id> <step_name>`.

### Added — FAZ-C Strategic Extensions

- **PR-C4 (#112) `41e110a` — resolve_route additive kwargs + `_KINDS` 27→28**. `budget_remaining`, `cross_class_downgrade` additive kwargs; response dict widen (`downgrade_applied`, `original_class`, `downgraded_class`). **Runtime dormant** — C4.1 follow-up for activation.
- **PR-C5 (#113) `11c54cf` — RFC 7396 JSON Merge Patch policy-sim**. `apply_merge_patch` + `simulate_policy_change(proposed_policy_patches=...)` + CLI `--proposed-patches`. Reversible filename: `<name>.v1.patch.json` → `<name>.v1.json`.

### Added — Test Infrastructure

- **PR-C1b.1 (#116) `9e0be80` — Full 7-step bundled bug_fix_flow E2E**. Validates C2.1 unblock claim. Platform-tolerant `pytest.skip` on runners without bundled prefix match.

### Changed

- `_KINDS` 27 → 28 with `route_cross_class_downgrade` reserved (not emitted in v3.3.0).
- `llm.resolve_route` return dict carries dormant `downgrade_applied`, `original_class`, `downgraded_class` on all success + FAIL paths.
- `_load_pending_patch_content` additive `workspace_root` kwarg.
- `simulate_policy_change` additive `proposed_policy_patches` kwarg (mutex with `proposed_policies`).
- `build_driver` additive `policy_loader` kwarg (forwards to Executor + MultiStepDriver).
- `Executor.run_step` additive `input_envelope_override` kwarg.
- `MultiStepDriver` catch matrix extended with 3 cost exceptions (`CostTrackingConfigError`, `SpendLedgerDuplicateError`, `SpendLedgerCorruptedError`).

### Known limitations — v3.3.1+ follow-ups

1. **Bundled `command_allowlist.prefixes` platform-specific** (`/usr/bin/`, `/usr/local/bin/`, `/opt/homebrew/bin/`). GitHub Actions runner Python at `/opt/hostedtoolcache/...` falls outside. Users on non-standard environments must supply custom policy override.
2. **C4.1 runtime activation deferred** — `resolve_route(cross_class_downgrade=True)` plumbing exists but runtime no-op. Threshold schema widen + directional `soft_degrade.rules` filter + evidence emit → v3.3.1.
3. **C3 catalog attribution deferred** — `vendor_model_id=None` always on adapter-path spend events. Adapter manifest widen needed → v3.3.1.
4. **C3 crash-window "lost spend after completed step"** — if process crashes between ledger append and budget CAS, ledger has spend but budget not drained. Recovery: operator scans for `cost_policy.enabled=true` + `cost_actual` present + no `llm_spend_recorded`/`llm_usage_missing` events. Atomic single-CAS restructure → v3.3.1.
5. **C6 parity fixup (dry_run driver wiring)** — `Executor.dry_run_step` bypasses driver-layer `context_pack_ref` + `parent_env` derivation. CLI provides executor-only preview. Full fidelity → v3.3.1.
6. **`_load_pending_patch_content` single-adapter scan** — helper stops at first completed adapter with `output_ref`; doesn't try older artifacts. v3.4.0+.

### Test baseline

**2210 tests passed** (2142 at v3.2.0 → **+68 new in this release**). Ruff + mypy clean. CI 8/8 green (lint + typecheck + Python 3.11/3.12/3.13 + coverage + extras-install + benchmark-fast).

### Added — FAZ-B PR-B7.1 (benchmark harness follow-up)

**Minor follow-up to PR-B7 (v3.2.0). Test + docs layer only;
runtime LOC unchanged.**

- `tests/benchmarks/mock_transport.py::_maybe_consume_budget` —
  benchmark-only shim that drains the run-state
  `budget.cost_usd.remaining` by the envelope's
  `cost_actual.cost_usd`. Docstring labels the shim explicitly
  and points at the real reconcile path
  (`ao_kernel.cost.middleware.post_response_reconcile` behind
  `ao_kernel.llm.governed_call`); closing that integration gap
  inside the adapter transport path (`invoke_cli` /
  `invoke_http`) is routed to **FAZ-C PR-C3**.
- `tests/benchmarks/assertions.py::assert_cost_consumed` — helper
  returns consumed amount + asserts `>= min_consumed`.
- `tests/benchmarks/test_governed_review.py::TestCostReconcile`
  pins the shim contract (0.12 USD envelope → 0.12 drain).
- `tests/benchmarks/fixtures/review_envelopes.py` +
  `tests/benchmarks/fixtures/bug_envelopes.py` — `cost_actual`
  now carries a `cost_usd` field on happy envelopes.
- `docs/BENCHMARK-SUITE.md §8.3` rewritten to route full bundled
  `bug_fix_flow` E2E → **FAZ-C PR-C1**, real-adapter full mode
  → **FAZ-C PR-C2**, and cost_usd runtime reconcile → **FAZ-C
  PR-C3**. The walker contract pin (cf8b30e) is reconciled with
  docs §3.2 and the missing-payload test is noted as unskipped.
- `docs/BENCHMARK-SUITE.md §9` new — 6-step "Adding a New
  Benchmark Scenario" recipe.

**Locked invariants**:
- Zero production `ao_kernel/` delta.
- Shim noop when `cost_actual.cost_usd` or `state.v1.json`
  absent; run-state schema round-trip preserved via
  `run_revision()` recompute.
- B7 v1 tests (6/6) pass unchanged; one new cost-reconcile
  test brings the benchmark total to 7.

## [3.2.0] — 2026-04-18

**FAZ-B — Ops Hardening**: 10 PRs landed across 6 workstreams
(agent coordination, cost runtime + routing, policy ops,
observability, AI workflow steps, quality gate). Public test
count 2141 (2135 main suite + 6 benchmark scenarios). Zero
production code change in PR-B7; tests + CI + docs only.

**Governance highlights**:
- Adversarial plan-time review via Codex across every PR
  (19 total iterations across B0-B7 plan-time + 14 across
  post-impl). Each verdict + absorb cycle captured in
  `.claude/plans/*.md` and `.ao/consultations/`.
- Post-impl Codex review adopted as a second quality gate
  before PR push (feedback_post_impl_review memory rule).
- Branch protection: `enforce_admins=false` made permanent
  (owner admin-bypass merge) after confirming CI gates (lint,
  typecheck, 3.11/3.12/3.13 pytest matrix, coverage, extras-
  install, benchmark-fast) are the actual ship contract.

**Shipped workstreams**:

- **Agent coordination (B1)**: `ao_kernel.coordination/` —
  lease / fencing / takeover. 5 plan-iter + runtime hardening.
- **Cost runtime + routing (B2, B2-e2e, B3)**:
  `ao_kernel.cost/` price catalog + spend ledger +
  `governed_call` wrapper; `cost-aware routing` via
  `routing_by_cost.priority="lowest_cost"`; tuple-partition
  helper + drop-if-any-known / fallback-if-none-known; new
  `RoutingCatalogMissingError(CostTrackingError)`.
- **Policy simulation (B4)**: `ao_kernel.policy_sim/` dry-run
  harness with 24-sentinel purity guard, centralised shape
  registry, canonical policy hash matching
  `executor/artifacts.py`, and `ao-kernel policy-sim run` CLI.
- **Metrics export (B5)**: `ao_kernel.metrics/` +
  `[metrics]` optional extra shipping eight Prometheus metric
  families derived from evidence; `ao-kernel metrics
  {export,debug-query}` CLI; cumulative-only textfile
  semantics; cost-disjunction + dormant banner policies.
- **AI workflow steps (B6)**: thin-driver `review_ai_flow`
  + `commit_ai_flow` runtimes with driver-owned capability
  artifact materialisation (`step_record.capability_output_refs`)
  + new `output_parse` contract on adapter manifests.
- **Quality gate (B7)**: `tests/benchmarks/` regression suite
  with mock transport (`invoke_cli`/`invoke_http` patch at
  executor's local alias) + `governed_review` (bundled
  workflow) + `governed_bugfix` (bench variant; full bundled
  flow deferred to B7.1 pending git/pytest sandbox allowlist).

### Added — FAZ-B PR-B7 (agent benchmark / regression suite)

**FAZ-B Tranche B 7/9 — `tests/benchmarks/` harness running
`governed_review` + `governed_bugfix` scenarios in fast-mode
only (real-adapter full mode deferred to B7.1). Mock patches
`invoke_cli` / `invoke_http` at the executor's local-alias
import site so the orchestrator + driver + executor +
adapter_invoker chain stays real; canned envelopes delegate to
the shipping `_invocation_from_envelope` walker so
`output_parse` contracts are exercised end-to-end.**

- New `tests/benchmarks/` package:
  * `mock_transport.py` — context manager patching the two
    executor-local adapter wrappers; `MockEnvelopeNotFoundError`
    (drift) + `_TransportError` sentinel (deliberate failure)
    kept distinct.
  * `assertions.py` — `assert_workflow_completed`,
    `assert_workflow_failed(expected_category=...)`,
    `assert_adapter_ok`, `assert_capability_artifact`,
    `assert_review_score`, `assert_budget_axis_seeded`,
    `resume_past_approval_gate` (wraps real
    `driver.resume_workflow(run_id, resume_token, payload)`).
  * `conftest.py` — `workspace_root` (install_workspace + bundled
    copy), `seeded_budget`, `seeded_run` factory,
    `benchmark_driver`.
  * `fixtures/` — `bug_envelopes.py`, `review_envelopes.py`,
    plus `workflows/governed_bugfix_bench.v1.json` (B7 v1
    minimal variant — full bundled `bug_fix_flow` deferred to
    B7.1 pending git/pytest sandbox allowlist).
  * `test_governed_bugfix.py` — happy + transport-error
    (`adapter_crash` category).
  * `test_governed_review.py` — happy + score-threshold
    parametrised + missing-payload negative (skipped pending
    walker contract reconciliation in B7.1).
- `docs/BENCHMARK-SUITE.md` §8 — runner example, scoring
  threshold case study, B7 v1 scope + deferred work list, mock
  boundary rationale.
- `.github/workflows/test.yml` — `test` + `coverage` jobs add
  `--ignore=tests/benchmarks`; new `benchmark-fast` job on
  Python 3.13 `needs: [test]`.
- Plan history captured in `.claude/plans/PR-B7-DRAFT-PLAN.md`
  v5 (Codex adversarial review 5-iter convergence slow → impl
  path chosen; remaining plan-drift residue fixed during impl).

**Locked invariants**:
- Mock boundary at `ao_kernel.executor.executor.invoke_cli` +
  `invoke_http` (executor local alias — patching
  `adapter_invoker.invoke_cli` would miss the bound reference).
- Fast-mode only; no `--benchmark-mode` flag shipped (full mode
  = B7.1).
- No production `ao_kernel/` delta — benchmarks live entirely
  under `tests/` + CI workflow + docs.
- `_KINDS == 27` preserved — benchmarks emit no new evidence
  kinds, they read the existing stream.

### Added — FAZ-B PR-B4 (policy simulation harness)

**FAZ-B Tranche B 4/9 — dry-run evaluation of proposed policy
changes. The simulator reuses `governance.check_policy` + the
executor's policy primitives under a 24-sentinel purity guard
that fail-closes on any side effect. Operators point it at a
scenario set + a `proposed_policies` dict and receive a
`DiffReport` with per-scenario transitions, per-policy
breakdown, and canonical policy hashes.**

- New `ao_kernel.policy_sim/` public package:
  * `errors.py` — 9 typed errors rooted at `PolicySimError`
    (purity violations, reentrancy, scenario validation,
    adapter discovery, target policy lookup, proposed policy
    shape, aggregate abort, report serialisation).
  * `_purity.py` — 24-sentinel monkey-patch context manager:
    4 `emit_event` paths (incl. public facade re-export),
    `worktree_builder.create_worktree`, 4 subprocess entry
    points, 4 pathlib Path writes, 4 os mutations, 4 tempfile
    allocators, 2 socket operations,
    `importlib.resources.as_file`. Not re-entrant — nested
    entry raises `PolicySimReentrantError`.
  * `_policy_shape_registry.py` — centralised primitive
    key-read introspection; validators aggregate
    `required_top_keys` and `type_contracts` across every
    registered consumer.
  * `scenario.py` — frozen dataclasses + loader +
    bundled-fixture helper. Per-scenario `target_policy_name`
    supports multi-policy ScenarioSets in a single run.
  * `diff.py` — `SimulationResult`, `ScenarioDelta`,
    `DiffReport` frozen dataclasses + canonical policy hash
    (aligned with `executor/artifacts.py`).
    `DiffReport.to_dict()` normalises `Path`, `frozenset`,
    `re.Pattern`, and manifest `source_path` for stable JSON
    output.
  * `loader.py` — `BaselineSource` enum (`BUNDLED` |
    `WORKSPACE_OVERRIDE` | `EXPLICIT`) +
    `validate_proposed_policy` +
    `policy_override_context` monkey-patch of
    `ao_kernel.config.load_with_override`.
  * `simulator.py` — public entrypoint
    `simulate_policy_change(*, project_root, scenarios,
    proposed_policies, baseline_source, baseline_overrides,
    include_host_fs_probes)`. Adapter snapshot taken BEFORE
    entering the purity context.
  * `report.py` — JSON + text formatters, atomic file writer,
    policies-from-dir loader.
- `ao-kernel policy-sim run` CLI — new subcommand with full
  `--scenarios`, `--proposed-policies`,
  `--baseline-source`, `--baseline-overrides`, `--format`,
  `--output`, `--enable-host-fs-probes`, `--project-root`
  flags. Exit codes: 0 (success), 1 (user error), 2 (internal),
  3 (tightening detected).
- Bundled JSON scenarios under
  `ao_kernel/defaults/policies/policy_sim_scenarios/`:
  `adapter_http_with_secret.v1.json`,
  `autonomy_unknown_intent.v1.json`,
  `path_poisoned_python.v1.json`, plus a manifest pointing at
  them.
- New JSON schema `policy-sim-scenario.schema.v1.json` with
  draft-2020-12 `allOf` branches enforcing the
  `target_policy_name` XOR `target_policy_names` invariant.
- `docs/POLICY-SIM.md` new — operator-facing contract,
  scenario model, public API walkthrough, CLI reference, report
  shape.

**Locked invariants**:
- Purity guard NOT re-entrant; originals always restored in
  `finally` (exception-safe).
- Model + adapter snapshot pre-captured outside the purity
  context so bundled fixtures do not trip
  `importlib.resources.as_file`.
- `_KINDS == 27` preserved (`executor/evidence_emitter.py:46`)
  — the simulator emits no new evidence kinds.
- Canonical policy hash bytes match `executor/artifacts.py`;
  cross-module drift surfaces as a contract-test failure.
- JSON-only scenarios in v1 (YAML deferred to an optional
  extra).

### Added — FAZ-B PR-B3 (cost-aware model routing)

**FAZ-B Tranche B 3/9 — opt-in cost-aware selection. When operators
set `policy_cost_tracking.routing_by_cost.{enabled: true, priority:
"lowest_cost"}`, the LLM router sorts the eligible provider set for
the target intent class ascending by price-catalog
input+output-per-1k average before iterating. Dormant default
preserves pre-B3 `fallback_order_by_class` semantics.**

- New `ao_kernel.cost.routing` module:
  * `_PROVIDER_ALIAS_MAP` normalizes router short names (`claude`,
    `openai`, ...) to catalog vendor names (`anthropic`, `openai`,
    ...) for catalog lookups.
  * `compute_model_cost_per_1k(entry)` — simple input+output
    per-1k average. Routing decisions ignore
    `cached_input_cost_per_1k`; billing continues to honor it.
  * `sort_providers_by_cost(provider_order, *, providers_map,
    catalog)` — partition helper returning `(known_cost_sorted,
    unknown_list)`. Router applies drop-if-any-known /
    fallback-if-none-known semantics (plan v5 §2.4 tek semantik).
- Extended `ao_kernel.cost.policy.RoutingByCost` dataclass with
  `priority` (closed-enum `provider_priority` | `lowest_cost`,
  default `provider_priority`) and
  `fail_closed_on_catalog_missing` (default `true`). Schema is
  additive — existing workspace overrides remain valid.
- New `RoutingCatalogMissingError(CostTrackingError)` raised when
  the cost-aware branch is active, catalog load fails, and
  `fail_closed_on_catalog_missing=true`. Preserves underlying
  cause as `__cause__` for operator drill-down.
- `llm_router.resolve` loader-trusted: no `try/except` around
  `load_cost_policy`. Missing workspace override → bundled
  dormant fallback (no raise); malformed →
  `json.JSONDecodeError` / `jsonschema.ValidationError`
  natural-propagates (honors the fail-closed contract in
  `cost/policy.py::_validate` + `load_cost_policy`).
- Explicit `provider_priority` caller arg bypasses cost sort
  (plan v5 Yüksek 2 invariant — caller intent wins over
  cost-aware re-ordering).
- `docs/COST-MODEL.md` §6 rewritten for the PR-B3 cost-aware
  contract (replaces the pre-B3 budget-aware fallback draft).
- `docs/MODEL-ROUTING.md` new — router resolution flow + PR-B3
  integration notes + extension guidance.

**Locked invariants**:
- Helper is partition-only; unknowns are dropped or preserved by
  the router, not the helper (plan v5 §2.3).
- Model aliasing intentionally out of scope in v1 — uncovered
  models use the unknown-bucket semantics (FAZ-C scope).
- Bundled dormant path unchanged: zero B2 / B5 / B6 test
  regression (full suite 2029+ passed).
- Router never swallows policy loader exceptions; fail-closed
  contract honored end-to-end (`llm.py::resolve_route`
  "Fail-closed" docstring).

### Added — FAZ-B PR-B5 (metrics export — Prometheus textfile + `[metrics]` extra)

**FAZ-B Tranche B 5/9 — evidence-derived metrics export. Stateless
CLI scans `events.jsonl` + run_store + coordination registry →
eight Prometheus metric families. Dormant-by-default; opt-in via
`policy_metrics.v1.json`. `[metrics]` optional extra keeps
prometheus-client out of the core dependency tree.**

- New `ao_kernel.metrics/` public package:
  * `policy.py` — `MetricsPolicy` frozen dataclass + `load_metrics_policy`
    with bundled-default + workspace-override resolution +
    `InvalidLabelAllowlistError` runtime defence against
    programmatic schema bypass.
  * `registry.py` — lazy `prometheus_client` adapter (mirrors
    `telemetry._check_otel` pattern). `build_registry(policy,
    include_llm_metrics=True)` returns a `BuiltRegistry` container
    with the eight metric families or `None` when the extra is
    missing.
  * `derivation.py` — `derive_metrics_from_evidence(ws, built, policy)`
    scans `.ao/evidence/workflows/*/events.jsonl`, dispatches events
    to metric populators, reads `state.v1.json.completed_at` for
    cancelled runs (plan v4 Q3 A), and queries
    `coordination.registry.live_claims_count()` for the active gauge
    (plan v4 Q1 A). Fail-closed on corrupt JSONL
    (`EvidenceSourceCorruptedError`).
  * `export.py` — `generate_textfile(built, metrics_dormant,
    cost_dormant)` serializes with banner comments for dormant /
    cost-dormant / extra-missing paths.
  * `errors.py` — five typed errors inheriting from `MetricsError`
    base.

- **Eight metric families** (`ao_llm_call_duration_seconds` histogram,
  `ao_llm_tokens_used_total` counter, `ao_llm_cost_usd_total`
  counter, `ao_llm_usage_missing_total` counter, `ao_policy_check_total`
  counter, `ao_workflow_duration_seconds` histogram,
  `ao_claim_active_total` gauge, `ao_claim_takeover_total` counter).
  LLM duration source canonicalized to
  `llm_spend_recorded.duration_ms` — the cost middleware emits the
  transport-layer `elapsed_ms` value (plan v4 iter-2 fix; reserve /
  normalize / reconcile overhead excluded).

- **`llm_spend_recorded.duration_ms` B2 event extension** (additive,
  backward-compatible). `ao_kernel/llm.py::governed_call` threads
  `transport_result["elapsed_ms"]` into `post_response_reconcile`,
  which emits the field only when present. Pre-B5 callers that omit
  the kwarg retain the legacy payload shape (plan v4 R13).

- **`coordination.registry.live_claims_count(workspace_root)` helper**
  — module-level read-only snapshot. Dormant policy → empty dict;
  otherwise loads the `_index` + each per-resource SSOT under
  `claims.lock` and applies the liveness predicate. The gauge
  source that prevents evidence-derived net-count races (plan v4
  Q1 A).

- **`workflow.run_store.list_terminal_runs(workspace_root)` helper**
  — internal read-only scan of `.ao/runs/*/state.v1.json` for
  terminal records (completed / failed / cancelled). No CAS lock or
  schema validation; malformed files are skipped silently (tolerates
  concurrent writer drift).

- **CLI surface** (`ao-kernel metrics …`):
  * `metrics export` — cumulative Prometheus textfile; atomic
    `--output` write via `write_text_atomic`. Exit codes: 0 success
    / dormant-graceful, 1 user error, 2 internal (corrupt JSONL),
    3 `[metrics]` extra missing informational.
  * `metrics debug-query` — non-Prometheus JSON query for operator
    debugging. `--since` is timezone-strict (`parse_iso8601_strict`
    rejects naive input); `--run` filters to a single run directory.
    Never emits Prometheus textfile.

- **Cost-disjunction invariant**: when
  `policy_cost_tracking.v1.json.enabled=false`, the metrics export
  builds the registry with `include_llm_metrics=False` and the
  `ao_llm_*` family is **absent** from the textfile (no metadata,
  no zero-synthetic samples). Operator banner:
  `# ao-kernel metrics: cost tracking dormant …`.

- **Cardinality hard-warning** in `docs/METRICS.md` §6.6: `agent_id`
  and `model` advanced labels must be bounded enumerations, not
  ephemeral / per-request strings. Schema closed-enum constrains
  names, not values — documented so operators avoid storage bombs.

- **Bundled Grafana dashboard** (`docs/grafana/ao_kernel_default.v1.json`):
  Grafana 10+ schema, 8 panels, `DS_PROMETHEUS` template variable,
  panel→metric matrix test guards the drift between dashboard and
  runtime. `docs/grafana/README.md` provides four import recipes
  (UI / file provisioning / K8s ConfigMap / HTTP API).

- **`[metrics]` optional extra** — `prometheus-client>=0.20.0` via
  `pip install ao-kernel[metrics]`. `enterprise` meta-extra widened
  to include it.

- **Tests** (~65 new across 6 files):
  * `test_metrics_policy.py` (13)
  * `test_metrics_registry.py` (13)
  * `test_cost_duration_ms.py` (4)
  * `test_metrics_derivation.py` (13)
  * `test_metrics_export.py` (6)
  * `test_metrics_cli.py` (4)
  * `test_metrics_helpers.py` (5)
  * `test_metrics_debug_query.py` (12)
  * `test_grafana_dashboard_shape.py` (8)

- Plan trace: CNS-20260417-035 (thread `019d9cec`), 3-iter plan-time
  absorb (REVISE → PARTIAL → AGREE). Full plan at
  [`.claude/plans/PR-B5-IMPLEMENTATION-PLAN.md`](../.claude/plans/PR-B5-IMPLEMENTATION-PLAN.md).

### Added — FAZ-B PR-B6 (review AI + commit AI workflow runtime — thin, driver-owned)

**FAZ-B Tranche B 6/9 — runtime for the B0-pinned review/commit AI
write-lite workflows. Closes the `output_parse`-walker lower half
(B0 shipped the walker + typed validation; B6 ships driver-owned
per-capability artifact materialization). Executor stays schema-
agnostic; MultiStepDriver owns the capability loop. New `commit_message`
capability + bundled `commit_ai_flow` workflow.**

- New `ao_kernel.executor.artifacts.write_capability_artifact(run_dir,
  step_id, attempt, capability, payload) -> (output_ref, output_sha256)`
  helper — mirrors the existing `write_artifact()` pattern (atomic
  tmp+fsync+rename, canonical JSON, SHA-256). Filename template
  `{step_id}-{capability}-attempt{n}.json` with capability key
  validated against `^[a-z][a-z0-9_]{0,63}$` (schema contract for
  `step_record.capability_output_refs`).

- `MultiStepDriver._run_adapter_step` now iterates
  `invocation_result.extracted_outputs` after `exec_result.step_state
  == "completed"` and writes one typed artifact per capability via
  `write_capability_artifact()`. Refs persist on
  `step_record.capability_output_refs` through both completion helpers:
  * `_record_step_completion` — ilk-attempt success path
  * `_update_placeholder_to_completed` — retry-success path
  Both widened with optional `capability_output_refs` kwarg; empty map
  → absent key (schema additionalProperties: false respected).

- Driver error translations widened (plan v3 iter-2 B2 absorb):
  * `AdapterInvocationFailedError` — transport-layer fail:
    - reason ∈ {timeout, http_timeout} → category=timeout
    - reason == subprocess_crash → category=adapter_crash
    - else → category=invocation_failed
  * `AdapterOutputParseError` (walker fail) → category=output_parse_failed
  * Capability artifact write failure → category=output_parse_failed,
    code=CAPABILITY_ARTIFACT_WRITE_FAILED
  All fail-closed via existing PR-A4b `_StepFailed` / `_handle_step_failure`
  error handler chain (no new emit path; step_failed evidence + CAS
  step_record.state="failed" unchanged).

- **`_LEGAL_CATEGORIES` schema parity sync** (plan v4 iter-2 B4 absorb)
  — pre-B6 drift between runtime set and
  `workflow-run.schema.v1.json::error.category.enum` eliminated:
  * Runtime had `adapter_error` (NOT in schema) — removed.
  * Schema had `invocation_failed`, `output_parse_failed`,
    `adapter_crash` (NOT in runtime) — added.
  * Final set: 10 values byte-identical across runtime + schema.
  * `test_error_category_parity.py` regression guard pins the
    invariant.

- **New typed artifact schema** `commit-message.schema.v1.json`
  (object-shape; required: schema_version + subject; optional: body,
  breaking_change, trailers). Subject max 72 chars (git soft limit).
  commit AI produces the MESSAGE ARTIFACT only; operator downstream
  applies the actual git commit. `commit_write` capability remains
  prohibited (agent-adapter-contract invariant preserved).

- **Adapter capability enum widen** (2 schemas, drift-test-guarded):
  `agent-adapter-contract.schema.v1.json` + `workflow-definition.schema.v1.json`
  `$defs/capability_enum += "commit_message"`.

- **`codex-stub` manifest updates**: capabilities += `"commit_message"`;
  output_parse gains a 2nd rule for `$.commit_message` →
  `commit-message.schema.v1.json`. Fixture (`ao_kernel.fixtures.codex_stub`)
  emits a deterministic object-shape commit_message payload so the
  walker's Mapping check accepts it (iter-1 caught v1 subagent's
  string-placeholder mistake).

- **New bundled workflow** `commit_ai_flow.v1.json` — 2-step flow
  (context_compile → invoke_commit_agent). Full schema compliance:
  default_policy_refs, created_at, step-level `on_failure` as STRING
  enum `"transition_to_failed"` (plan v3 iter-2 B1 absorb — NOT the
  object shape v2 incorrectly proposed).

- **Schema additive widen** `workflow-run.schema.v1.json::step_record`
  + `capability_output_refs` field (object with
  `patternProperties["^[a-z][a-z0-9_]{0,63}$"]`, `additionalProperties:
  false`). Pre-B6 run records parse cleanly without the field; new
  records include it when the adapter produced typed outputs.

- **BENCHMARK-SUITE.md narrative update**: "output_ref = review
  artifact" narrative (B0 pin that never shipped) replaced.
  `capability_output_refs` is the **B6-guaranteed** surface for
  per-capability typed artifacts. `output_ref` on the driver-managed
  adapter path remains a **legacy / non-guaranteed** surface: pre-B6
  the executor wrote the normalized invocation artifact but never
  threaded `output_ref` through `ExecutionResult`, so the driver
  completion helpers see no field and persist nothing. B6 preserves
  this pre-existing empty-stays-empty behavior; adapter-path
  `output_ref` persistence is NOT B6 scope and is NOT auto-assumed
  for B7 — it requires a dedicated follow-up (FAZ-C or explicit
  scope) and an `ExecutionResult` widen. `governed_review` release
  gate (§5.2) now mandates `capability_output_refs["review_findings"]`
  as the artifact pointer.

- **Locked invariants / contracts**:
  - Executor invariant preserved: `_normalize_invocation_for_artifact()`
    + `ExecutionResult` unchanged; materialization driver-owned.
  - `step_record.output_ref` pre-B6 shape preserved (normalized
    invocation artifact); capability artifacts are a new PARALLEL
    surface under `capability_output_refs`.
  - `_LEGAL_CATEGORIES` ⊆ schema error.category.enum (parity
    regression-test-enforced).
  - `commit_write` capability prohibition preserved — commit AI
    produces message artifact; operator downstream commits.

- **Out of scope** (per CNS-030 + CNS-033 advisory, B7 deferred):
  - `tests/benchmarks/` runner + `governed_review` scoring
  - `price-catalog` lookup in `cost_actual`
  - `score` threshold gate
  - Actual `git commit` application
  - Benchmark scenario fixtures

- **Adversarial consensus**: 5-commit DAG (squash-on-merge) shipped
  after CNS-20260417-033 `ready_for_impl=true` across 4 adversarial
  plan iterations (v1 subagent draft → v4 AGREE). Plan
  `.claude/plans/PR-B6-IMPLEMENTATION-PLAN.md` documents the absorb
  trail: 5 v1 findings (walker kontrat, driver error plumbing, executor
  invariant, naming, SHA refresh), 4 iter-2 findings (on_failure
  enum, AdapterInvocationFailedError translation, adapter_returned
  invariant, parity drift), 2 iter-3 findings (completion plumbing
  retry path, stale "schema widen" dili).

- **Gate status on merge**: ruff + mypy clean; pytest 1884 passed,
  3 skipped (+56 net tests from pre-B6 baseline 1828; 0 regressions).

### Added — FAZ-B PR-B2 (cost runtime — price catalog + spend ledger + governed_call)

**FAZ-B Tranche B 3/9 — runtime for the B0-pinned cost contract. LLM
calls now run through `ao_kernel.llm.governed_call` — a non-streaming
composition wrapper with optional cost governance (pre-dispatch
estimate + budget cap fail-closed + post-response reconcile +
canonical billing digest idempotent ledger). Dormant by default;
operators opt in via workspace policy override + adding a `cost_usd`
axis to workflow-run budgets.**

- New public package `ao_kernel/cost/` — six modules: errors (9
  typed classes), cost_math (Decimal-stable formula + estimate +
  `min(max_tokens, est_in*0.25)` output estimate), catalog (checksum
  verify + stale gate + 300s LRU), ledger (canonical billing digest
  idempotency + bounded tail-scan), policy (typed loader + 2 new
  knobs), middleware (pre_dispatch_reserve + post_response_reconcile
  with CAS-retried budget mutations).
- New `ao_kernel.llm.governed_call` facade — non-streaming LLM
  composer with rich `{status, normalized, resp_bytes, transport_result,
  elapsed_ms, request_id}` success dict; CAPABILITY_GAP + TRANSPORT_ERROR
  envelopes preserve pre-B2 caller contract. Cost-layer errors raise
  (BudgetExhausted, CostTrackingConfig, PriceCatalogNotFound,
  LLMUsageMissing). Streaming stays on existing `_execute_stream`
  path.
- `build_request_with_context` additive `injected_messages` return
  field for cost-estimate accuracy.
- 3 caller entrypoints wired through `governed_call`:
  `AoKernelClient.llm_call(run_id, step_id, attempt)` opt-in;
  `mcp_server.handle_llm_call(ao_run_id, ao_step_id, ao_attempt)`
  opt-in + MCP tool schema widen;
  `workflow.intent_router._llm_classify` bypass-only (standalone
  classifier, not a budget anchor).
- Budget granular axes `tokens_input` + `tokens_output` (additive
  BudgetAxis fields with back-compat reader + writer invariants).
- Normalizer strict helper `extract_usage_strict → UsagePresence`
  with None-sentinel; existing `extract_usage` (0-fallback) preserved.
- Schema additive widens: workflow-run budget +2 integer axes;
  spend-ledger +3 fields (attempt, usage_missing, billing_digest);
  policy-cost-tracking +2 knobs (fail_closed_on_missing_usage,
  idempotency_window_lines).
- Evidence taxonomy +3 (24 → 27): `llm_cost_estimated`,
  `llm_spend_recorded`, `llm_usage_missing` — all fail-open emits.
- Streaming cost tracking: FAZ-C deferred (documented gap in
  docs/COST-MODEL.md §9).
- Adversarial consensus: 7-commit DAG shipped after Codex CNS-
  20260417-031 `ready_for_impl=true` across 7 adversarial plan
  iterations (v1→v7). Plan `.claude/plans/PR-B2-IMPLEMENTATION-PLAN.md`
  documents the absorb trail.
- Gate status on merge: ruff + mypy clean; pytest 1823 passed /
  3 skipped (+121 net tests; 0 regressions — PR-B1 `_KINDS` exact-24
  assertion replaced by `>= 24` floor to stay regression-free across
  additive evidence kinds).

### Added — FAZ-B PR-B1 (coordination runtime — lease / fencing / takeover)

**FAZ-B Tranche B 2/9 — runtime for the B0-pinned coordination contract
(`docs/COORDINATION.md` + `claim.schema.v1.json` +
`fencing-state.schema.v1.json` +
`policy_coordination_claims.v1.json`). Multi-agent coding-agent
workflows can now safely share workspace resources (git worktrees,
evidence run directories, workflow run records) via
`.ao/claims/`-rooted lease primitives. Dormant by default; operators
opt in via workspace override.**

- **New public package `ao_kernel/coordination/`** — six modules:
  - `claim.py` — `Claim` frozen dataclass mirroring
    `claim.schema.v1.json`; `claim_revision()` canonical-JSON hash
    (`canonical_store.store_revision` pattern); `claim_from_dict` /
    `claim_to_dict` with schema validation + revision-hash verification
    (detects silent on-disk edits); `save_claim_cas(expected_revision)`
    CAS helper.
  - `fencing.py` — `FencingState` / `ResourceFencingState` frozen
    dataclasses mirroring `fencing-state.schema.v1.json`; pure
    `next_token` / `update_on_release` / `set_next_token` mutators;
    exact-equality `validate_fencing_token` (both stale and
    future/fabricated tokens raise); runtime-only
    `fencing_state_revision()` out-of-band CAS hash (B0 schema is
    closed, revision field NOT persisted);
    `save_fencing_state_cas(expected_revision)` atomic write.
  - `policy.py` — `CoordinationPolicy` + nested `EvidenceRedaction`
    frozen dataclasses; `load_coordination_policy(workspace_root, *,
    override=None)` three-stage resolution (inline → workspace
    override → bundled default); `match_resource_pattern` glob
    allowlist matcher. Fail-closed on malformed override JSON /
    schema violation.
  - `registry.py` — `ClaimRegistry(workspace_root, *,
    evidence_sink=None)` workspace-scoped orchestrator. Public API:
    `acquire_claim`, `heartbeat(resource_id, claim_id,
    owner_agent_id)`, `release_claim(resource_id, claim_id,
    owner_agent_id)`, `takeover_claim`, `get_claim`,
    `validate_fencing_token`, `prune_expired_claims(policy=None, *,
    max_batch=None)`, `list_agent_claims`. Thread-safe via POSIX
    `claims.lock`.
  - `errors.py` — 13 typed exceptions: `CoordinationError` base plus
    `ClaimConflictError` / `ClaimConflictGraceError` (both carry
    `current_fencing_token` for master plan §10 race test),
    `ClaimStaleFencingError`, `ClaimOwnershipError`,
    `ClaimRevisionConflictError`, `ClaimQuotaExceededError`,
    `ClaimResourcePatternError`, `ClaimResourceIdInvalidError`,
    `ClaimCoordinationDisabledError`, `ClaimCorruptedError` (SSOT
    only), `ClaimAlreadyReleasedError`, `ClaimNotFoundError`.
  - `__init__.py` — stable public surface; private helpers stay
    out of `__all__`.
- **Storage layout** under `{workspace_root}/.ao/claims/`:
  - Per-resource SSOT: `{resource_id}.v1.json` (source of truth;
    parse / schema / revision-hash failure raises
    `ClaimCorruptedError` fail-closed).
  - Fencing state SSOT: `_fencing.v1.json` (CAS via runtime-only
    `fencing_state_revision()` out-of-band hash; fail-closed).
  - Derived cache: `_index.v1.json` (`agent_id → [resource_id, ...]`
    reverse index; rebuilt silently on drift — fail-open for derived
    state).
  - Lock file: `claims.lock` (POSIX `fcntl` advisory; Windows raises
    `LockPlatformNotSupported`).
- **Evidence taxonomy 18 → 24** in
  `ao_kernel/executor/evidence_emitter.py::_KINDS`: additive
  expansion with six `claim_*` kinds (`claim_acquired`,
  `claim_released`, `claim_heartbeat`, `claim_expired`,
  `claim_takeover`, `claim_conflict`). PR-A 18 kinds preserved
  verbatim; `claim_acquired` and `claim_takeover` are mutually
  exclusive (W1v2 pin — a single acquire/takeover path emits
  exactly one).

### Changed — FAZ-B PR-B1

- `ao_kernel/executor/executor.py::Executor.__init__` gains an
  optional `claim_registry: Any = None` parameter. When supplied and
  the caller passes both `fencing_token` and `fencing_resource_id`
  kwargs to `run_step`, the executor validates the fencing token at
  entry (BEFORE any evidence emit, worktree build, or adapter
  invoke). Stale-fencing raises `ClaimStaleFencingError` which
  propagates to the caller — `MultiStepDriver` catches and applies
  its existing `step_failed` emission with
  `error_category="other"`, `code="STALE_FENCING"`. Canonical event
  order (`step_started` → ... → `step_failed`) intact. Partial
  fencing-pair supply or fencing without a `claim_registry` raises
  `ValueError`. Pre-PR-B1 callers unaffected (both kwargs default
  `None`).

### Locked invariants (B0 contract surface, enforced by B1 runtime)

- **Expiry authority:** `effective_expires_at = heartbeat_at +
  policy.expiry_seconds` computed at evaluation; `expires_at` on
  the claim shape is a DERIVED debug field, NOT source of truth.
- **Takeover threshold:** `now > heartbeat_at + expiry_seconds +
  takeover_grace_period_seconds`. Public `takeover_claim` enforces
  the gate — live / in-grace attempts raise `ClaimConflictError` /
  `ClaimConflictGraceError` with `claim_conflict` emit (audit
  symmetry with acquire).
- **Forward-only fencing:** reconcile computes `new_next_token =
  max(current_next_token, max_claim_fencing_token + 1)`; fencing
  state NEVER decreases.
- **Quota unlimited when `limit=0`:** enforcement line is
  `if limit > 0 and count >= limit: raise`. Live-count only —
  expired-but-unpruned claims are filtered out.
- **Validator runs before pattern allowlist:** `_validate_resource_id`
  regex `^[A-Za-z0-9][A-Za-z0-9._-]*$` rejects path separators /
  wildcards / whitespace / leading non-alphanumeric BEFORE the
  glob allowlist runs.
- **Release second-call raise:** absent claim on release raises
  `ClaimAlreadyReleasedError` rather than silent no-op (surfaces
  stale-caller bugs).
- **Release / prune fail-closed order:** fencing state loaded +
  validated BEFORE claim file delete, so corrupt fencing raises
  while the claim is still recoverable on disk.
- **Evidence fail-open:** `_safe_emit_coordination_event` wraps the
  caller-injected sink in try/except; emit failures are logged at
  `warning` level. Coordination correctness NEVER depends on
  emission success (CLAUDE.md §2 side-channel contract).
- **SSOT fail-closed:** `{resource_id}.v1.json` and `_fencing.v1.json`
  corruption (parse / schema / hash mismatch) raises
  `ClaimCorruptedError` and propagates. `_index.v1.json` corruption
  is handled fail-open (silent rebuild from SSOT scan).

### Adversarial Consensus

- **CNS-20260416-029** family (4 MCP threads across context expiry;
  current thread `019d99eb-6208-78c3-b5be-070b401f56d6`): plan-time
  adversarial review reached AGREE + `ready_for_impl: true` on
  iteration v3-iter-2 (`/Users/halilkocoglu/Documents/ao-kernel/
  .claude/plans/PR-B1-IMPLEMENTATION-PLAN.md` v5). Cumulative
  absorption across v1 → v5: 15 blockers + 17 warnings. Key
  absorbed issues: takeover live/grace gate bypass (B1v5), claim
  CAS `save_claim_cas(expected_revision)` helper (B2v5), release /
  prune fail-closed order (B3v5), fencing exact-equality (B2v3),
  forward-only monotonic reconcile (B3v3), evidence-sink
  injection API (B4v3), resource_id validator on both
  acquire and takeover (B5v3), quota SSOT-reconciled
  live-count (B1v2 + W3v5), CLAIM_CONFLICT `current_fencing_token`
  payload (B6v2), `_index` fail-open scope narrowed (W2v2),
  event mutual exclusion `claim_acquired` vs `claim_takeover`
  (W1v2), release second-call raise (W5v2),
  `ClaimNotFoundError` for public takeover on absent resource
  (B1v5), evidence redaction binding via
  `build_coordination_sink` wrapper pattern (W2v5).

### Added — FAZ-B PR-B0 (docs + schemas + dormant policies + extraction layer)

**FAZ-B Tranche B 1/9 — foundation only; runtime primitives for lease/
fencing (PR-B1), cost tracking (PR-B2/B3), policy simulation (PR-B4),
metrics export (PR-B5), review/commit AI workflows (PR-B6), and the
benchmark suite (PR-B7) consume the contracts pinned here.**

- **Four new operator-facing docs**:
  - `docs/COORDINATION.md` — lease/fencing spec. Includes the locked
    "Expiry Authority" table (`effective_expires_at = heartbeat_at +
    expiry_seconds`; `CLAIM_CONFLICT_GRACE` distinct from
    `CLAIM_CONFLICT`; in-grace revival; caller-driven cleanup).
  - `docs/COST-MODEL.md` — object-shape price catalog (with checksum +
    stale_after + source enum + `vendor_model_id` conditional) + spend
    ledger + cost-aware routing. Budget axis extension
    (`tokens_input` / `tokens_output`) described for PR-B2 runtime.
  - `docs/METRICS.md` — Prometheus default low-cardinality label set
    (`provider` / `direction` / `outcome` / `final_state`) + advanced
    label opt-in via `policy_metrics.labels_advanced`.
  - `docs/BENCHMARK-SUITE.md` — typed artifact transport chain and
    five edge-case contracts (multi-rule fail-closed; unresolvable
    `schema_ref` fail-closed; null payload schema-decided; missing
    `json_path` fail-closed; envelope field without rule silently
    ignored).
- **Eight new JSON schemas** under `ao_kernel/defaults/schemas/`:
  data: `claim.schema.v1.json`, `fencing-state.schema.v1.json`,
  `price-catalog.schema.v1.json`, `spend-ledger.schema.v1.json`,
  `review-findings.schema.v1.json`; policy:
  `policy-coordination-claims.schema.v1.json`,
  `policy-cost-tracking.schema.v1.json`,
  `policy-metrics.schema.v1.json`.
- **Three schema deltas** on pre-existing schemas:
  - `agent-adapter-contract.schema.v1.json::$defs.capability_enum`
    gains `review_findings` (seventh value).
  - `agent-adapter-contract.schema.v1.json` gains a NEW top-level
    `output_parse` contract surface (NET-NEW — distinct from
    `invocation_http.response_parse`, which handles HTTP-transport
    body→envelope parsing). `output_parse` is orchestrator-level
    envelope→typed-payload extraction; rules shape
    `{json_path, capability?, schema_ref?}`, JSONPath minimal subset
    `$.key(.key)*` preserved from PR-A3. Adapters that do not declare
    `output_parse` behave as before.
  - `workflow-definition.schema.v1.json::$defs.capability_enum` gains
    `review_findings` (drift parity —
    `test_workflow_registry.py::TestPatternDriftGuard` asserts set
    equality).
- **Three bundled dormant policies** (all `enabled: false`; operator
  opt-in via workspace override required): `policy_coordination_claims.
  v1.json` (30s heartbeat, 90s expiry, 15s grace, 5 claims/agent,
  allow-all resource pattern); `policy_cost_tracking.v1.json`
  (`fail_closed_on_exhaust: true` locked, `strict_freshness: false`
  default, `routing_by_cost` off); `policy_metrics.v1.json`
  (defence-in-depth: both `enabled` and `labels_advanced.enabled` off,
  allowlist closed enum `model | agent_id`).
- **Two bundled defaults**:
  `ao_kernel/defaults/catalogs/price-catalog.v1.json` (starter
  catalog, 6 entries — anthropic × 3, openai × 2, google × 1,
  canonical-JSON SHA-256 checksum over `entries[]`); operators
  override at `.ao/cost/catalog.v1.json`.
  `ao_kernel/defaults/workflows/review_ai_flow.v1.json` — contract
  pin for the `governed_review` benchmark (B6 runtime impl).

### Changed — FAZ-B PR-B0

- `ao_kernel/config.py::load_default` accepts a new `"catalogs"`
  resource type alongside the existing plural kinds
  (`policies/schemas/registry/extensions/operations`). Full-filename
  convention preserved; call site
  `load_default("catalogs", "price-catalog.v1.json")`.
- `ao_kernel/executor/adapter_invoker.py::_invocation_from_envelope`
  gains an optional `manifest` parameter. When the manifest carries
  an `output_parse` section, its rule walker populates
  `InvocationResult.extracted_outputs` (new optional field, default
  `MappingProxyType({})`). Layer separation: `adapter_invoker` =
  transport + capability-aware extraction; `Executor` stays
  schema-agnostic and still owns artifact write + `step_record` CAS.
- `InvocationResult` (public via `ao_kernel.executor.__init__.__all__`)
  gains one new **optional** field `extracted_outputs:
  Mapping[str, Mapping[str, Any]]`; existing fields are unchanged in
  name, order, and type. Pre-FAZ-B callers do not need to pass the
  new field. Semver handled as a minor bump, targeted at `v3.2.0` at
  the end of FAZ-B.
- `ao_kernel/adapters/manifest_loader.py::AdapterManifest` gains one
  new optional field `output_parse: Mapping | None = None` and the
  registry loader now rejects manifests with duplicate `capability`
  values across `output_parse.rules` as
  `SkippedManifest(reason="schema_invalid")` — edge-case contract #1
  enforcement at load time.

### Adversarial Consensus

- **CNS-20260416-028v2** (5 iterations, MCP thread
  `019d962d-1592-76b3-8702-b86322b83a6a`): plan-time review of PR-B0
  reached AGREE at iter 5 with `ready_for_impl: true`. Seven blockers
  + fourteen warnings absorbed across iters 1–4; iter 5 returned two
  non-blocking hardening warnings, both absorbed into plan v7 before
  implementation. Codex write-order advisory (Q1–Q6) absorbed as
  plan §3 (contract-first risk-first 7-step write order + 5-commit
  DAG + test-file sahiplik-bazlı dağıtım + CHANGELOG semver stance +
  four locked edge-case contracts).
- Consensus document: `.ao/consultations/CNS-20260416-028v2.
  consensus.md`.

## [3.1.0] - 2026-04-16

**FAZ-A Governed Demo MVP ship.** End-to-end governed workflow: intent → workflow → adapter → diff → CI → approval → PR → evidence. 8 PRs (A0–A6), 28 Codex adversarial iterations, 1500+ tests, 85%+ coverage.

### Added — FAZ-A PR-A6 (demo + adapters + meta-extra + v3.1.0)

- `examples/demo_bugfix.py` — runnable end-to-end demo with codex-stub adapter, programmatic auto-approval, evidence timeline + manifest verify.
- `ao_kernel/defaults/adapters/` — 3 bundled adapter manifests (claude-code-cli, codex-stub, gh-cli-pr) discoverable via `importlib.resources`. `AdapterRegistry.load_bundled()` new method; workspace > bundled precedence on same `adapter_id`.
- `ao_kernel/fixtures/gh_pr_stub.py` — deterministic PR-creation stub (no real `gh` CLI invocation; exercises CLI transport for demos).
- `ao_kernel/workflow/intent_router.py` — `llm_fallback` strategy concrete: lazy-import `ao_kernel.llm` (requires `[llm]` extra); prompt-based classification returning workflow_id; fail-closed `IntentClassificationError` on invalid response, transport error, or missing extra.
- `ao_kernel/workflow/errors.py` — `IntentClassificationError` typed exception for runtime classification failures (distinct from `IntentRulesCorruptedError` load-time validation).
- `pyproject.toml` — `[coding]` meta-extra (`[llm]` placeholder; code-index/LSP/metrics land in FAZ-C); `[enterprise]` placeholder.
- Version bump `3.0.0` → `3.1.0` (pyproject.toml + `ao_kernel.__init__.__version__`).
- `README.md` — CLI reference expanded with 4 evidence subcommands + demo quickstart section.

### Added — FAZ-A PR-A5 (evidence timeline CLI + SHA-256 manifest + replay)

Moved from [Unreleased]:

### Added — FAZ-A PR-A0 (docs + spec, no code)

- Agent adapter contract schema (`ao_kernel/defaults/schemas/agent-adapter-contract.schema.v1.json`). Defines how external coding agent runtimes (Claude Code CLI, Codex, Cursor background agent, GitHub Copilot cloud agent, gh CLI PR connector, custom CLI/HTTP) integrate with ao-kernel. 8 `adapter_kind` variants + 6 `capabilities` + `cli`/`http` invocation + input/output envelopes + evidence/policy refs. Referential integrity with workflow-run and worktree policy is narrative at PR-A0; loader-level validation lands in Tranche A PR-A2.
- Workflow run canonical state schema (`ao_kernel/defaults/schemas/workflow-run.schema.v1.json`). Durable 9-state machine with CAS revision token, checkpoint refs, budget (fail-closed on exhaust), HITL interrupt + governance approval tokens as separate domains, and allowed-transition table documented inline.
- Worktree execution profile policy (`ao_kernel/defaults/policies/policy_worktree_profile.v1.json`). CNS-016 D4 expanded minimum — per-agent worktree + sanitized env allowlist + secret deny-by-default with explicit `allowlist_secret_ids` + command allowlist (POSIX prefixes incl. Apple Silicon `/opt/homebrew/bin/`) + cwd confinement + evidence redaction (6 P0 patterns: `sk-`, `sk-ant-`, `ghp_`, `xoxb-`, `Bearer`, `Basic`). Three rollout tiers: dormant (bundled default) / report_only / block. SSH agent forwarding, network/egress OS sandbox, and extended redaction catalog (AWS / Google / xAI / structured JWT) deferred to FAZ-A PR-A5 or FAZ-B.
- Docs: `docs/ADAPTERS.md` (adapter contract human-readable + 3 walkthroughs), `docs/WORKTREE-PROFILE.md` (operator-facing sandbox guide + demo override example), `docs/EVIDENCE-TIMELINE.md` (17-event taxonomy across 8 categories + replay contract + JSONL layout), `docs/DEMO-SCRIPT.md` (FAZ-A release-gate 11-step end-to-end demo), `docs/COMPETITOR-MATRIX.md` (9-row live competitor / adapter matrix per CNS-016 W3, prevents "rakipsiz" regression).
- Adversarial consensus: CNS-20260415-019 iter-1 PARTIAL (2 blocking + 18 warning) → iter-2 AGREE (`ready_for_impl: true`). All blocking and 14 high-value warnings absorbed into plan v2 before implementation; 4 warnings relocated as scope / defer decisions.
- Foundation for FAZ-A governed demo MVP (v3.1.0 ship target). Implementation lands in Tranche A PR-A1 through PR-A6.

### Added — FAZ-A PR-A1 (workflow state machine + run store)

- `ao_kernel/workflow/` package: public facade for workflow run lifecycle. Seven modules, narrow re-export surface (private helpers `_mutate_with_cas`, `_run_path`, `_lock_path`, `_get_validator`, `load_workflow_run_schema` intentionally hidden).
- State machine (`state_machine.py`): 9-state transition table from PR-A0 `workflow-run.schema.v1.json` as pure functions + immutable `TRANSITIONS` mapping. Literal expected-table test (no schema-narrative parsing) covers all 9 × 9 transition pairs.
- Run store (`run_store.py`): CAS-backed CRUD mirroring `canonical_store.py` pattern. POSIX `file_lock` held for the whole load-mutate-write cycle. Atomic writes via `write_text_atomic` (tempfile + fsync + `os.replace`). `run_revision` hashes a projection of the record with the `revision` field omitted (self-reference-free content addressing). `_mutate_with_cas(workspace_root, run_id, *, mutator, expected_revision=None, allow_overwrite=False) -> tuple[dict, str]` is the single canonical write path (CNS-20260414-010 invariant). `create_run`, `save_run_cas`, and `update_run` all route through it. `run_id` validated as UUIDv4 (explicit `parsed.version == 4`) before use as a path component — path-traversal guard.
- Budget (`budget.py`): immutable `Budget` + `BudgetAxis` dataclasses. `cost_usd` tracked as `Decimal` internally for precision; serialized as `float` on persist per schema `type: number`. `fail_closed_on_exhaust: true` raises `WorkflowBudgetExhaustedError` when the post-spend `remaining` would be strictly negative; spending exactly the remaining amount is valid (next positive spend raises).
- Primitives (`primitives.py`): `InterruptRequest` / `Approval` dataclasses with separate `mint_interrupt_token` / `mint_approval_token` functions (distinct HITL vs governance audit domains). Tokens are `secrets.token_urlsafe(48)` (64-char URL-safe, stdlib — no new core dep). Resume operations are idempotent for repeat calls with identical payload; payload mismatch raises `WorkflowTokenInvalidError`.
- Typed errors (`errors.py`): `WorkflowError` hierarchy + `WorkflowRunIdInvalidError` for path-traversal guard + `WorkflowSchemaValidationError.errors: list[dict]` with `json_path`, `message`, `validator` (utils.py pattern).
- Schema validator (`schema_validator.py`): Draft 2020-12 wrapper around `workflow-run.schema.v1.json`; schema + validator cached via `functools.lru_cache`. Validation runs only at load / save boundaries (perf-safe).
- Tests: 180 new tests across 6 files + 1 fixture (`tests/fixtures/workflow_bug_fix_stub.json`). Per-module coverage: `state_machine`, `primitives`, `schema_validator`, `__init__` at 100%; `errors` 97%, `budget` 94%, `run_store` 89%. Package total 95%.
- Adversarial consensus: CNS-20260415-020 iter-1 PARTIAL (7 blocking + 11 warning absorbed) → iter-2 AGREE (`ready_for_impl=true`, `pr_split_recommendation=single_pr`). Residual impl-time fixes applied in this PR: lock-path `with_name`, UUIDv4 version check, post-stamp validation order, canonicalization aligned with `canonical_store.store_revision`.

### Added — FAZ-A PR-A2 (intent router + workflow registry + adapter manifest loader)

- `ao_kernel/workflow/registry.py`: `WorkflowRegistry` loads bundled `ao_kernel/defaults/workflows/*.v1.json` plus workspace `<workspace_root>/.ao/workflows/*.v1.json`, validates each against the new `workflow-definition.schema.v1.json`, indexes by `(workflow_id, workflow_version)`. Workspace-over-bundled precedence applies only for identical keys; different versions from different sources coexist and `get(id, version=None)` returns the highest SemVer across sources (local comparator, no new runtime dep). `validate_cross_refs(definition, adapter_registry)` returns a structured `list[CrossRefIssue]` with `kind`, `workflow_id`, `step_name`, `adapter_id`, and `missing_capabilities` fields so callers can triage missing-adapter vs capability-gap issues.
- `ao_kernel/workflow/intent_router.py`: rule-first `IntentRouter` with keyword / regex / combined match types, priority-ordered evaluation with duplicate-priority-match detection at classify time, bundled `default_rules.v1.json`. Three fallback strategies: `error_on_no_match` returns `None`; `use_default` requires a non-null `default_workflow_id` (schema conditional) and returns a result with `matched_rule_id='__default__'`; `llm_fallback` raises `NotImplementedError` (interface for PR-A6 `[llm]` extra). Duplicate `rule_id` and regex compile failures are loader-level `IntentRulesCorruptedError` exceptions.
- `ao_kernel/adapters/` new public facade package: `AdapterRegistry` loads `<workspace_root>/.ao/adapters/*.manifest.v1.json`, validates each against PR-A0 `agent-adapter-contract.schema.v1.json`, exposes `get`, `list_adapters`, `supports_capabilities`, and `missing_capabilities(adapter_id, required) -> frozenset[str]`. Filename convention: stem (minus `.manifest.v1.json`) must exactly equal `raw["adapter_id"]` — no underscore↔dash normalization, to prevent typosquatting. `LoadReport.skipped` carries a 6-reason taxonomy (`json_decode`, `schema_invalid`, `adapter_id_mismatch`, `read_error`, `not_an_object`, `duplicate_adapter_id`).
- Schemas: `workflow-definition.schema.v1.json` (closed contract — `additionalProperties: false` at top level and in every `$defs` object; `expected_adapter_refs` and `steps[*].adapter_id` items pinned to the PR-A0 adapter-id pattern; `on_failure` enum closed to `transition_to_failed` / `retry_once` / `escalate_to_human`; `actor=adapter` conditionally requires `adapter_id`). `intent-classifier-rules.schema.v1.json` (conditional validation ties `match_type` to non-empty `keywords` / `regex_any`; `fallback_strategy=use_default` conditionally requires a non-null `default_workflow_id`; optional per-rule `workflow_version` pin).
- Bundled defaults: `ao_kernel/defaults/workflows/bug_fix_flow.v1.json` and `ao_kernel/defaults/intent_rules/default_rules.v1.json`.
- Errors: extended `ao_kernel/workflow/errors.py` with `WorkflowDefinitionNotFoundError`, `WorkflowDefinitionCorruptedError`, `WorkflowDefinitionCrossRefError`, `IntentRulesCorruptedError`. New `ao_kernel/adapters/errors.py` with `AdapterError` hierarchy.
- Tests: 76 new tests across 4 files (`test_workflow_registry.py`, `test_intent_router.py`, `test_adapter_manifest_loader.py`, `test_pr_a2_integration.py`) plus 9 manifest fixtures (4 happy, 5 negative including `bad-id-mismatch`, `bad-schema`, `bad-not-object`, and two `bad-duplicate-*` manifests demonstrating filename-id matching). Pattern-drift regression guards cross-check `workflow_id` / `workflow_version` / `adapter_id` patterns and the `capability_enum` between workflow-definition, workflow-run, and agent-adapter-contract schemas.
- Adversarial consensus: CNS-20260415-021 iter-1 PARTIAL (7 blocking + 10 warning absorbed in plan v2) → iter-2 AGREE (`ready_for_impl=true`, `pr_split_recommendation=single_pr`).

### Fixed

- `agent-adapter-contract.schema.v1.json`: removed `additionalProperties: false` from the top-level `invocation` object so the `oneOf` discriminator over `invocation_cli` / `invocation_http` can validate transport-specific fields. The branch schemas retain their own `additionalProperties: false`, so extras at each branch level are still rejected. Bug surfaced the first time PR-A2 tests ran a real manifest through the validator; shipping alongside PR-A2.

### Added — FAZ-A PR-A3 (worktree executor + policy enforcement + adapter invocation)

- `ao_kernel/executor/` new public facade package: `Executor.run_step` is the single-step primitive that orchestrates worktree creation, runtime policy enforcement, adapter invocation (CLI or HTTP), evidence emission, and run record CAS update. Consumers: PR-A4 multi-step driver.
- **Worktree builder** (`worktree_builder.py`): creates per-run git worktrees under `.ao/runs/{run_id}/worktree/` with `chmod 0o700`; POSIX-only; idempotent cleanup via git-native `worktree remove` + filesystem fallback.
- **Policy enforcer** (`policy_enforcer.py`): runtime validation against `policy_worktree_profile.v1.json`. PATH hardening (plan v2 B1): resolved command realpath must be under a policy-declared path prefix — basename allowlist alone does NOT authorize an arbitrary filesystem location; `inherit_from_parent=False` (default) strictly disables host env passthrough; explicit_additions override; HTTP adapters with `auth_secret_id_ref` require `"http_header"` in `exposure_modes` or are pre-flight denied.
- **Evidence emitter** (`evidence_emitter.py`): per-run file lock (`events.jsonl.lock`) + monotonic `seq` field (the replay ordering key) + `secrets.token_urlsafe(48)` opaque `event_id`. 17-kind taxonomy whitelist. Redaction at emission via 6 P0 patterns inherited from `policy.evidence_redaction`. Manifest generation deferred to PR-A5 CLI (docs/EVIDENCE-TIMELINE.md §5 revised).
- **Adapter invoker** (`adapter_invoker.py`): CLI via `subprocess.run` (hermetic env, no host leakage); HTTP via `urllib.request` (stdlib only, no new runtime dep). JSON-first output parse; minimal dotted JSONPath subset (`$.key(.key)*`, no indices/wildcards) for `response_parse`; text/plain fallback guarded by content-type + unified diff marker + `write_diff` capability triple; exit-code mapping; timeout handling (partial + `finish_reason=timeout`); budget accounting via PR-A1 `record_spend`.
- **Executor orchestrator** (`executor.py`): single-step primitive contract (plan v2 Q1 add): validates `step_def` is part of pinned workflow definition; rejects duplicate completed steps; cross-reference validation re-runs per adapter step (no cache, plan v2 B8). Canonical event emission order: `step_started → policy_checked → (policy_denied ⇒ abort) → adapter_invoked → adapter_returned → step_completed|step_failed → run state CAS`.
- **Typed errors** (`errors.py`): `PolicyViolation` structured record + `PolicyViolationError`, `AdapterInvocationFailedError`, `AdapterOutputParseError`, `WorktreeBuilderError`, `EvidenceEmitError`.
- **Bundled deterministic stub** (`ao_kernel/fixtures/codex_stub.py`): canonical `output_envelope` JSON on stdout; used by CI integration and the DEMO-SCRIPT.md flow to exercise the full CLI transport without an LLM provider. `ao_kernel.fixtures` ships as a runtime package (setuptools-discoverable via `__init__.py`); stability note: fixture behaviour preserved within semver minor, not a production adapter authoring API.
- Tests: 5 new test files with ≥ 55 new tests exercising PATH poisoning denial, env hermeticity, seq monotonicity, redaction, JSONPath subset, text/plain fallback triple gate, cross-reference per-call, primitive contract (foreign step + duplicate step rejection), worktree chmod 0o700, idempotent cleanup, and end-to-end codex-stub adapter invocation via real subprocess.
- Adversarial consensus: CNS-20260415-022 via MCP iter-1 PARTIAL (8 blocking + 9 warning absorbed in plan v2) → iter-2 AGREE (`ready_for_impl=true`, `pr_split_recommendation=single_pr`). First plan review conducted over Codex MCP transport instead of `codex exec`.

### Fixed — PR-A3

- `docs/EVIDENCE-TIMELINE.md §5`: clarified that the SHA-256 integrity manifest is generated on demand by the PR-A5 evidence-timeline CLI, not updated per-event by PR-A3. PR-A3 writes events append-only with per-run lock + fsync.

### Added — FAZ-A PR-A4a (contract repair + diff/patch + CI gate primitives)

- **Contract repair (schema + state + evidence + bundled workflow + test fixtures):** `ao_kernel/workflow/state_machine.py` TRANSITIONS now allows `waiting_approval → running` (governance-approved non-patch resume) and `verifying → waiting_approval` (post-CI governance gate). Note: `running → running` is intentionally NOT added — retry_once uses append-only `step_record(attempt=2)` instead of a state edge. `workflow-run.schema.v1.json` adds `step_record.attempt` (int ≥ 1, default 1) for append-only retry semantics; `output_ref` description clarified as required-for-durability under PR-A4. `workflow-definition.schema.v1.json` adds `step_def.operation` enum (`context_compile`, `patch_preview`, `patch_apply`, `patch_rollback`, `ci_pytest`, `ci_ruff`, `ci_mypy`) with conditional `allOf` (required when actor ∈ {ao-kernel, system}; forbidden when actor ∈ {adapter, human}; `patch_apply` + `escalate_to_human` combination rejected schema-level as defence-in-depth). `ao_kernel/executor/evidence_emitter.py` event-kind whitelist expanded 17 → 18 with `diff_rolled_back`. Bundled `bug_fix_flow.v1.json` updated to declare `operation` on its four ao-kernel / system steps. `docs/EVIDENCE-TIMELINE.md` §2.4 / §2 / §3 / §4.2 updated to reflect the 18-kind taxonomy.
- `ao_kernel/workflow/registry.py` `StepDefinition` dataclass gains `operation: str | None = None` field; parser reads `raw_step["operation"]`; `validate_cross_refs` emits `CrossRefIssue(kind="operation_required")` when missing for ao-kernel/system actors and `CrossRefIssue(kind="invalid_on_failure_for_operation")` when `actor=ao-kernel AND operation=patch_apply AND on_failure=escalate_to_human` (defence-in-depth with typed diagnostic; schema already rejects the same cases at load time). `CrossRefIssue.adapter_id` is now optional (`str | None = None`) so non-adapter issues do not need a placeholder.
- `ao_kernel/patch/` new public facade package. `preview_diff` wraps `git apply --check --3way --index --numstat -` (flag-aligned with `apply_patch` to avoid false-reject 3-way-resolvable hunks — CNS-023 B6 absorb); parses `--numstat` output to surface `lines_added` / `lines_removed` / `binary_paths`. `apply_patch` runs `git apply --3way --index -` with a deterministic reverse-diff stored at `{run_dir}/patches/{patch_id}.revdiff` via atomic write (tempfile + fsync + rename); binary diffs rejected post-preview. `rollback_patch` replays the reverse diff and returns `RollbackResult(idempotent_skip=True)` when the post-apply index is clean (no net change) — detection uses preflight `git apply --check` + reverse-of-reverse check + post-apply `git diff --cached --quiet`. Typed errors: `PatchPreviewError`, `PatchApplyError`, `PatchApplyConflictError` (reports `.rej` file paths + forensic tarball at `{run_dir}/artifacts/rejected/{step_id}.tgz` captured BEFORE `git reset --hard HEAD` cleanup), `PatchRollbackError`, `PatchBinaryUnsupportedError`.
- `ao_kernel/ci/` new public facade package. `run_pytest` defaults to `python3 -m pytest`; `run_ruff` defaults to `python3 -m ruff check`; both invoke via `subprocess.run` under a hermetic caller-supplied `env_vars` mapping (in production, `policy_enforcer.SandboxedEnvironment.env_vars` with `inherit_from_parent=False`). `run_all` orchestrates multiple checks with optional `fail_fast`. `CIResult.status` ∈ `{"pass", "fail", "timeout"}` — all returned; exceptions (`CIRunnerNotFoundError`, `CITimeoutError` when `raise_on_timeout=True`) are reserved for preflight / explicit-opt-in paths per CNS-023 W7.
- Tests: 57 new tests across 5 files — `test_workflow_registry_operation.py` (10), `test_patch_diff_engine.py` (11), `test_patch_apply.py` (13), `test_patch_rollback.py` (8), `test_ci_runners.py` (15). Shared helper `tests/_patch_helpers.py` scaffolds ephemeral git repos from `tmp_path` + produces patches via real `git diff` so the tests exercise genuine unified-diff input. Total test count: 1385 (1328 baseline + 57). Branch coverage gate ≥ 85% retained.
- Invariants (PR-A3 preserved + PR-A4a new): POSIX-only, `inherit_from_parent=False` strict, PATH anchoring via realpath + policy prefix, per-run `events.jsonl.lock` + monotonic `seq`, cross-ref per-call. **New (PR-A4a):** patch preflight flag-aligned `--check --3way --index -`; reverse-diff deterministic path + atomic write; rollback idempotent on clean post-apply index; CI flaky tolerance = 0; patch_apply dirty-state cleanup protocol (`.rej` forensic capture BEFORE `git reset --hard HEAD`); `step_def.operation` required for ao-kernel / system actors (schema + registry defence-in-depth); `step_record.attempt` append-only retry model (no `running → running` state edge). No new core dependency; `jsonschema>=4.23.0` remains the sole required dep.
- Adversarial consensus: CNS-20260415-023 iter-1 PARTIAL (8 blocking + 7 warning absorbed in plan v2) → iter-2 AGREE via MCP thread `019d928f-978f-7ac2-91cb-b0f286798cbd`. PR split recommendation `split_2_pr`: PR-A4a ships contract repair + primitives + unit tests; PR-A4b ships multi-step driver + integration + Executor `output_ref` wiring on the heels of A4a.

### Added — FAZ-A PR-A4b (multi-step driver + Executor output_ref wiring)

- **`ao_kernel/executor/multi_step_driver.py`**: `MultiStepDriver` orchestrates `workflow_definition.steps` with actor / operation dispatch (adapter → `Executor.run_step(driver_managed=True)`; ao-kernel + operation in {`context_compile`, `patch_preview`, `patch_apply`, `patch_rollback`} → internal primitives; system + operation in {`ci_pytest`, `ci_ruff`} → CI runners; `ci_mypy` rejected explicitly as `UNSUPPORTED_OPERATION`; `human` + `gate` → `waiting_approval`). `on_failure` dispatch covers `transition_to_failed`, `retry_once`, and `escalate_to_human`. Evidence emits `workflow_started` / `workflow_completed` / `workflow_failed` at the workflow boundary plus existing step- and gate-level kinds (18-kind taxonomy unchanged — no new evidence kind in PR-A4b).
- **Executor driver-managed mode (CNS-024 iter-1 B1 absorb)**: `Executor.run_step` grows two kwargs, `attempt: int = 1` and `driver_managed: bool = False`. In default mode (A3 backward-compat) the executor still appends its own step_record and terminalises the run on adapter failure. In `driver_managed=True` mode it writes a canonical artifact via `ao_kernel/executor/artifacts.py::write_artifact` (tempfile + fsync + rename + directory fsync; `sort_keys=True, ensure_ascii=False, separators=(",",":")`) and emits `adapter_returned` with `{output_ref, output_sha256, attempt}` fields — but does NOT append step_record or transition run state. The driver owns both.
- **Retry append-only model (CNS-024 iter-1 B3 absorb)**: failure → driver appends a terminal `state=failed` step_record for the failed attempt; `on_failure=retry_once` then appends a fresh-`step_id` placeholder `step_record(state=running, attempt=2)` under CAS BEFORE the second invocation. Success / failure of attempt=2 updates the placeholder in-place (no new record). Run state stays `running` while retry is available; only a second fail emits `RETRY_EXHAUSTED` and transitions to terminal `failed`. Crash-safety rule: absent attempt=2 placeholder + failed attempt=1 + `on_failure=retry_once` → driver resume creates the placeholder and invokes (retry is NOT consumed).
- **Driver entry matrix (CNS-024 iter-1 B2 absorb)**: `run_workflow` dispatches on `run_record.state` — `created` starts + emits `workflow_started`; `running` resumes from derived position without re-emitting; `waiting_approval` / `interrupted` raises `DriverTokenRequiredError` (caller must use `resume_workflow`); terminal states return an idempotent `DriverResult` OR raise `DriverStateInconsistencyError` when `(step_name, highest_attempt)` is still retryable.
- **Error category mapping (CNS-024 iter-1 B4 absorb)**: internal failures map to the schema-legal `error.category` enum while machine-readable detail lives on `error.code` + `error.message` + evidence payload `reason`. Mapping: `budget_exhausted` → `budget_exhausted`; CI check fail → `ci_failed`; patch conflict → `apply_conflict`; approval denial → `approval_denied`; cross-ref / unsupported operation / state inconsistency / retry exhausted → `other` (with distinct `code` values `CROSS_REF`, `UNSUPPORTED_OPERATION`, `STATE_INCONSISTENCY`, `RETRY_EXHAUSTED`).
- **Approval idempotency decision-only (CNS-024 iter-1 B5 absorb)**: `resume_workflow(run_id, token, payload)` with an approval token accepts `payload = {"decision": "granted"|"denied", "notes": str | None}`; the idempotency key is the `decision` only (same decision = idempotent return; different decision = `WorkflowTokenInvalidError`). `notes` is emitted as redacted metadata in the `approval_granted` / `approval_denied` event payload — NOT hashed into the token idempotency, NOT persisted to the schema. PR-A1 `Approval` dataclass and primitive contract are preserved; no schema delta.
- `DriverResult` frozen dataclass (`run_id`, `final_state`, `steps_executed`, `steps_failed`, `steps_retried`, `resume_token`, `resume_token_kind`, `budget_consumed`, `duration_seconds`). Typed errors: `DriverStateConflictError`, `DriverBudgetExhaustedError`, `DriverTokenRequiredError`, `DriverStateInconsistencyError`, `WorkflowStateCorruptedError`. All re-exported from `ao_kernel.executor`.
- Tests: 32 new tests across 3 files — `test_multi_step_driver.py` (16 unit tests: dispatch, entry matrix, cross-ref early fail, governance gate, approval grant/deny, `ci_mypy` reject, DriverResult shape, error category mapping), `test_multi_step_driver_retry.py` (16 tests: retry_once success + exhausted, escalate_to_human, budget exhaust, helper methods, idempotent terminal reconstruction, state inconsistency guard), `test_multi_step_driver_integration.py` (4 tests with platform-tolerant skip guards for the adapter+CI subprocess chain + canonical event order verification). Total suite: 1482 passed, 3 skipped (platform variance in the adapter subprocess integration path).
- Plan v2 invariants 20-29 preserved: driver authoritative state via `(step_name, highest_attempt)`; resume position derived from `run_record.steps[]`; `adapter_returned` payload gains `output_sha256` distinct from the event envelope `payload_hash`; budget gating uses the functional `is_exhausted` / `record_spend` API; workflow-level cross-ref runs once at entry (Executor per-step cross-ref preserved for defence-in-depth); Executor `driver_managed=True` mode; driver entry matrix; retry append-only persistence; error category mapping; approval decision-only idempotency.
- **Known limitations** (tracked tech debt, not silent skips):
  - `ao_kernel/executor/multi_step_driver.py` is omitted from the `--cov-fail-under=85` ratchet (branch coverage ≈ 52% at ship). Unit tests cover entry matrix, retry append-only, escalate, idempotent terminal, and every helper; but the end-to-end subprocess branches (real adapter + ci runner + patch primitive chain) need production adapter fixtures to be reliably reachable. Closing target: **PR-A5** (evidence timeline CLI + replay coverage) and **PR-A6** (demo runnable + production `codex-cli` / `gh-cli-pr` / `claude-code-cli` manifests). The `pyproject.toml` omit entry carries this note inline.
  - `context_compile` operation is a stub that writes an empty-preamble artifact with `stub: True` in the `step_completed` event payload (CNS-024 iter-1 W5 visibility marker). Real context pipeline wiring lands in PR-A6 or FAZ-B.
  - Integration tests (`test_multi_step_driver_integration.py::TestAdapterPlusCIFlow`) skip when the host lacks a compatible adapter subprocess chain. The run_workflow path in those environments returns before a full end-to-end assertion; the driver dispatch code itself is still executed.
- Adversarial consensus: CNS-20260416-024 iter-1 PARTIAL (5 blocking + 7 warning absorbed into plan v2 / §10 absorption map / §2 invariants 25-29) → iter-2 AGREE via MCP thread `019d92fd-acf3-71d0-bffe-2d4b51e3c531` (fresh thread; PR-A4a thread closed at merge). Post-implementation review to follow per `feedback_post_impl_review.md`.

## [3.0.0] - 2026-04-14

**Tranche C release.** Ships the memory MCP surface (read + write),
finishes the CAS-based write path, opts every `_internal` submodule
into strict mypy, raises the coverage gate to 85, and declares
POSIX-only support. Every PR passed through an adversarial Codex
consultation (CNS-20260414-010 / 011 / 012); 16 blocking + 22 warning
objections were grep-verified and absorbed.

### Breaking changes

- **POSIX-only contract.** `pyproject.toml` classifier flipped to
  `Operating System :: POSIX`. `ao_kernel/_internal/shared/lock.py`
  raises `LockPlatformNotSupported` on Windows. Windows support
  remains a Tranche D follow-up.
- **`CanonicalStoreCorruptedError`** is now raised when the canonical
  store file cannot be parsed (previously the reader returned an
  empty default). Callers that relied on the silent fallback must
  catch the new error or restore a healthy file.
- **`save_store` deprecated.** Production write paths must route
  through `save_store_cas(...)` or the `canonical_store` mutator
  helpers; `save_store()` emits a `DeprecationWarning` since v3.0.0.
  It was originally targeted for a v4.0.0 removal; the v4.0.0 stable
  line retained compatibility and retargeted removal to a future major
  release.
- **Evidence contract clarified.** CLAUDE.md §2 now documents the
  dual form: MCP events land in JSONL (fsync-only, daily-rotated),
  while workspace artefacts keep the SHA256 integrity manifest. The
  MCP manifest is deferred to Tranche D.

### Added — Memory MCP surface (C6a + C6b, CNS-20260414-011 / 012)

- `ao_memory_read` MCP tool. Policy-gated, fail-closed, read-only
  canonical / fact query with per-workspace rate limiting and a
  param-aware workspace resolver.
- `ao_memory_write` MCP tool. Policy-gated, server-side fixed
  confidence (caller-supplied `confidence` is ignored per CNS-010
  iter-3 Q9), JSON-encoded value size guard, prefix allowlists.
- `ao_kernel/_internal/mcp/memory_tools.py` private sub-module
  carries both handlers, the strict resolver, the per-workspace
  rate-limit registry, and the validated policy loaders.
- `policy_mcp_memory.v1.json` + matching JSON schema (fail-closed
  defaults).
- `policy_tool_calling.v1.json` gains an optional
  `implicit_canonical_promote` block so operators can tune the
  promotion threshold + source prefix per workspace without code
  changes; the hard-coded 0.8 threshold was removed.

### Added — CAS write path (C5a / C5b, CNS-20260414-010)

- `canonical_store.save_store_cas(...)` public low-level writer.
- `canonical_store._mutate_with_cas(...)` private helper — **the**
  canonical write path; every mutator routes through it.
- POSIX FS lock (`ao_kernel/_internal/shared/lock.py::file_lock`).
- `write_text_atomic` now uses unique temp names (`mkstemp`) to
  eliminate the old fixed-suffix race.

### Added — Workspace contract (C0, CNS-20260414-010)

- `ao_kernel/workspace.py::project_root()` single source of truth;
  `mcp_server._find_workspace_root` delegates. Project root = the
  directory that contains `.ao/`, **not** `.ao/` itself.

### Changed — Strict typing & coverage (C1 / C2 / C3 / C4)

- Every `_internal/*` submodule opted into strict mypy (D13 staged
  plan completed): providers, shared, secrets, evidence, session,
  orchestrator, prj_kernel_api.
- Branch-coverage gate ratcheted 70 → 75 → 80 → 85 alongside new
  tests for `_internal/session/context_store`,
  `_internal/evidence/writer`, and `ao_kernel/workspace`.
- `ao_kernel/telemetry.py` moved into the coverage omit list — OTEL
  stays optional (D12), so CI without the `[otel]` extra cannot
  exercise the observability branches.

### Changed — Extension manifests (C7a)

- `intake_*` entrypoints now live solely on `PRJ-WORK-INTAKE`;
  `PRJ-KERNEL-API` no longer duplicates them.
- `PRJ-ZANZIBAR-OPENFGA` manifest rewritten to satisfy the
  extension-manifest schema (`semver`, `origin`, `owner`,
  `layer_contract`, `policies`, `ui_surfaces`, corrected `version`
  enum).
- `ExtensionRegistry.find_conflicts()` now returns `[]` on the
  bundled set (regression test added).

### Added — CLI + concurrency invariants (C8)

- `tests/test_cli_concurrency.py` exercises
  - `doctor` from a sub-directory (C0 / `project_root()` invariant)
  - `init` + `migrate --dry-run` happy path
  - parallel `promote_decision` through `_mutate_with_cas` FS lock

### Docs

- CLAUDE.md §2 invariant rewritten (evidence dual form).
- CLAUDE.md §5 architecture section updated for 7 MCP tools and
  the new `_internal/mcp/` package.
- README MCP-tool matrix expanded to 7 tools.
- Handoff + plan files under `.claude/plans/` track each PR.

### Adversarial consensus — Tranche C stats

| CNS | Topic | Iterations | Blocking | Warning |
|---|---|---|---|---|
| 010 | master plan + C0/C5/C6 | 3 | 10 | 7 |
| 011 | C6a implementation | 3 | 5 | 9 |
| 012 | C6b implementation | 2 | 1 | 6 |

Claude's first thesis survived 0/8 times — the "grep before
accepting" rule (see `feedback_codex_consultations.md`) fired on
every iteration.

## [2.3.0] - 2026-04-14

**Faz 4 Wiring release.** Closes Tranche B — every scaffold that shipped
in v2.2.0 now has a real production path, validated via adversarial
Codex consultations (CNS-007, CNS-008, CNS-009). 12 blocking + 7 warning
objections surfaced, every one verified with grep and absorbed into the
implementation.

### Added — Vector store pipeline (B1, CNS-007)
- `AoKernelClient(vector_store=..., owns_vector_store=..., embedding_config=...)`
  — explicit backend injection for tests / advanced use.
- `EmbeddingConfig` dataclass resolved via precedence
  constructor > policy > env > default. Decoupled from the chat route
  because most chat providers (Anthropic, DeepSeek, xAI) have no
  embeddings endpoint — propagating chat provider/model there would
  silently break semantic retrieval.
- Env surface: `AO_KERNEL_VECTOR_BACKEND`, `AO_KERNEL_PGVECTOR_DSN`,
  `AO_KERNEL_VECTOR_STRICT`, `AO_KERNEL_PGVECTOR_TABLE`,
  `AO_KERNEL_EMBEDDING_DIMENSION`, `AO_KERNEL_EMBEDDING_PROVIDER`,
  `AO_KERNEL_EMBEDDING_MODEL`, `AO_KERNEL_EMBEDDING_BASE_URL`.
- Policy `semantic_retrieval` block in `policy_context_memory_tiers.v1.json`
  (enable + backend.strict/fail_action + embedding.provider/model).
- Errors: `VectorStoreConfigError`, `VectorStoreConnectError`.
- `VectorStoreBackend.close()` default no-op so subclass authors don't
  have to bring their own. `PgvectorBackend` overrides for real cleanup.
- pgvector schema now carries `embedding_model` (BTREE-indexed). Store
  rejects dimension OR model mismatches; search transparently filters
  when bound so vectors from different embedding spaces never mingle.
- Sidecar write-path: `memory_pipeline.process_turn` and
  `canonical_store.promote_decision` now embed + index every decision
  via `semantic_indexer.index_decision` when a backend is configured.
  Write-path failures are silent by contract (deterministic fallback
  preserved).

### Added — Secrets dual-read (B2, CNS-005 D0.3)
- `ao_kernel/_internal/secrets/api_key_resolver.py`:
  `resolve_api_key(provider_id, *, environ=, secrets_provider=, audit=)`
  — factory-first, env fallback. `@overload` typed audit for mypy strict.
- Provider aliases: `claude` ↔ `ANTHROPIC_API_KEY`/`CLAUDE_API_KEY`,
  `google`/`gemini` ↔ `GOOGLE_API_KEY`/`GEMINI_API_KEY`,
  `qwen` ↔ `DASHSCOPE_API_KEY`/`QWEN_API_KEY`,
  `xai`/`grok` ↔ `XAI_API_KEY`. Unknown providers fall back to
  `{PROVIDER}_API_KEY` (pre-D0.3 behavior).
- `EnvSecretsProvider._SECRET_ID_TO_ENV` expanded from 1 to 9 entries.
- `mcp_server.py` `ao_llm_call` uses the resolver; `MISSING_API_KEY`
  now lists every env name that was checked so operators know which to
  set.

### Added — Extension activation (B3, CNS-008)
- `AoKernelClient.extensions` (ExtensionRegistry) + `client.action_registry`
  (ActionRegistry) + `client.call_action(name, params)`.
- `ao_kernel/extensions/dispatch.py` — explicit `ActionRegistry` with
  duplicate-registration protection. D7 preserved: no importlib magic,
  no setuptools `entry_points`.
- `ao_kernel/extensions/bootstrap.py` — `register_default_handlers()`
  with an explicit module list. Adding a bundled handler is a two-line
  change; failure in one handler never blocks the others.
- `PRJ-HELLO` reference extension + `hello_world` kernel_api_action.
- `ExtensionManifest` is now lossless — schema-required fields (owner,
  ui_surfaces, compat) plus discovery metadata (docs_ref, ai_context_refs,
  tests_entrypoints) all round-trip. `manifest_path`, `content_hash`,
  `source`, `activation_blockers`, `stale_refs` populated at load.
- `ExtensionRegistry.find_conflicts()` surfaces duplicate entrypoint
  declarations. Bundled set has three known conflicts
  (`intake_create_plan/next/status` between PRJ-KERNEL-API and
  PRJ-WORK-INTAKE); first-wins is deterministic across runs thanks to
  sorted iteration.
- Compat gate: manifests whose `core_min`/`core_max` excludes the running
  `ao_kernel.__version__` stay in `list_all()` but drop out of
  `list_enabled()` and receive `activation_blockers`.
- Workspace-root semantic normalized: loader expects the PROJECT ROOT
  (directory containing `.ao/`), matching `AoKernelClient` semantics.
- Schema accepts additional properties (`additionalProperties: true`)
  so forward-compat vendor fields don't gate the whole registry.

### Added — MCP evidence trail (B4)
- `ao_kernel/_internal/evidence/mcp_event_log.py` —
  `record_mcp_event(workspace, tool, envelope, params=, duration_ms=, extra=)`.
  Daily-rotated JSONL at `.ao/evidence/mcp/YYYY-MM-DD.jsonl`.
- Every MCP tool dispatch now emits one event (wrapper pattern;
  `TOOL_DISPATCH[name].__wrapped__` keeps test-facing handler identity).
- Redaction: keys matching `api_key`/`token`/`secret`/`messages`/
  `content`/`prompt` suffixes have values replaced with `***REDACTED***`;
  secret-shaped substrings (`sk-…`, `ghp_…`) scrubbed from free text.
- Shape projection for `params`/`data` fields — type names only, values
  never land in the log. Auditors can reconstruct the call surface
  without leaking content.
- Writer robustness: `_append_text` and `_append_jsonl` now `flush()` +
  `os.fsync()` with atomic parent `mkdir`. Integrity manifest is
  meaningful under crash.

### Added — Agent coordination SDK (B5, CNS-009)
- `ao_kernel.context` re-exports every coordination hook:
  `record_decision`, `query_memory`, `get_revision`, `has_changed`
  (new canonical name), `check_stale` (back-compat alias),
  `read_with_revision`, `compile_context_sdk`, `finalize_session_sdk`.
- `AoKernelClient` gains matching wrapper methods that auto-thread the
  client's `session_id` and `workspace_root` — canonical provenance
  (`promoted_from`) is no longer empty for client-driven writes.
  Library mode (no workspace) refuses memory ops with a clear error
  instead of silently failing later.
- `client.compile_context_sdk(...)` builds a preamble WITHOUT issuing
  an LLM call (handoff, audit, prompt-cache warming).
- `client.finalize_session(auto_promote, promote_threshold)` — single
  finalize primitive. Returns the canonical delta count.

### Changed — Agent coordination contracts (B5, CNS-009)
- **Breaking for direct callers of `agent_coordination`:**
  `record_decision(auto_promote=False)` no longer silently writes a
  short-TTL canonical entry. It now writes to the supplied session
  context (ephemeral) or reports `destination="dropped"` when no
  context is supplied. Flag name and behavior now agree.
- `get_revision()` returns the full 64-character SHA-256 hex digest
  instead of a 16-character truncation. Callers must treat the token as
  opaque; tests should not assert on its length.
- `session_lifecycle.end_session` gained `auto_promote` +
  `promote_threshold` parameters; `finalize_session_sdk` delegates
  promotion to `end_session` instead of running a second pass. Fixes
  silent double-promotion and threshold-mismatch bug where
  `auto_promote=False` was ignored.

### Fixed
- Extension loader previously dropped `owner`, `ui_surfaces`, and
  `compat` fields silently; schema-invalid manifests were accepted with
  defaulted values. Both paths now surface via `LoadReport.skipped` with
  a `schema_invalid` reason.
- `context_compiler.compile_context` now accepts `embedding_config=` and
  `vector_store=` so `_apply_semantic_reranking` can reach the
  embedding pipeline. Previously `semantic_search(api_key="")` returned
  an empty embedding every time — semantic reranking was effectively
  dead.
- `embed_decision` cache-invalidation now also keys on the configured
  model. Previously a model upgrade silently kept stale embeddings.
- `.gitignore` covers `.ao/canonical_decisions*.json`, `.ao/evidence/`,
  `.ao/sessions/`, `.ao/cache/`, and the defensive `.ao/.ao/` nested
  directory so runtime artefacts stop leaking into commits.

### Scope fences (deliberately deferred)
- OS-level filesystem lock / CAS for concurrent canonical writers —
  tracked as "multi-tenant write safety" CNS per CNS-009 consensus.
  `has_changed()` is ADVISORY ONLY and documents this limitation.
- MCP `ao_memory_*` tools — scope creep; the MCP surface needs
  dedicated governance review before memory read/write tools land.
- Integration back-fill of the other 17 bundled extensions — PRJ-HELLO
  is the first reference; others register as their code lands.
- `_internal/*` mypy coverage — remains on the D13 phased plan.

## [2.2.0] - 2026-04-14

Safety & Hygiene release. Faz 5 Preflight (operational security) + Tranş A
(productization + honest registry). Also rolls up Faz 4 scaffolds that
landed between v2.1.1 and v2.2.0.

### Added
- `SECURITY.md` — disclosure channel, threat model, secrets best practices,
  operational hardening guide.
- `examples/hello-llm/` — first runnable quickstart (README, main.py,
  requirements.txt, .env.example); zero-to-governed-LLM-call in under 5 min.
- README "SDK vs MCP" capability matrix — makes the thin-executor nature
  of `ao_llm_call` explicit at documentation surface.
- `.githooks/` versioned (pre-commit + pre-push) with secret / large-file /
  direct-main / WIP guards. Repos can opt in via `core.hooksPath=.githooks`.
- `.archive/patches/` — historical `.patch` backups moved out of repo root.
- GitHub `main` branch protection with 6 required checks (lint, test × 3,
  coverage, typecheck). Enforced for admins. Tag ruleset protects `v*`.
- CI: `test.yml` split into `lint` / `test (3.11|3.12|3.13)` / `coverage` /
  `typecheck` / `extras-install` jobs. Typecheck is now a real blocking gate.
- Regression guard test for capability overclaims
  (`test_registry_overclaim_guard.py`).
- Faz 4 scaffolds (from v2.1.1 → v2.2.0 interval):
  - Semantic retrieval feature flag (default OFF, `AO_SEMANTIC_SEARCH=1`)
  - Secrets provider factory + HashiCorp Vault provider (KV v2 HTTP)
  - Extension loader + runtime registry (18 bundled manifests)
  - Vector store abstraction (InMemoryVectorStore + PgvectorBackend)
  - Roadmap checkpoint/resume (SHA256 integrity, JSONL step audit)
  > NOTE: these are **scaffolds**, not yet wired to the production code
  > path. Integration (vector store → semantic_retrieval, secrets factory
  > → LLM transport, extension loader → startup) is tracked for Tranş B.
- Faz 3 additions: SecretsProvider ABC enforcement, MCP HTTP transport
  tests, memory distiller edge case tests.
- Faz 2 additions: tool use graduation (build_tools_param integration,
  registry `supported`), evidence writer client integration, compaction
  edge case tests.

### Fixed
- **Silent failures now visible.** `client.py` evidence writer, eval
  scorecard, and streaming post-processor failures no longer `except: pass`;
  they log structured warnings (`logger.warning` with request_id + provider).
- **Streaming evidence was never written** (keyword-only arg mismatch +
  missing model param). Preserved from Faz 2 fix.
- **Compaction tests** used wrong context key (`decisions` →
  `ephemeral_decisions`). Preserved from Faz 2 fix.
- Obsolete `src/*` shim references removed from `llm.py` docstrings.
- **`client.save_checkpoint` / `resume_checkpoint` real bug.** Public
  methods called the internal API with incompatible keyword arguments
  (`label` vs `session_id`, positional vs keyword-only). Tests only covered
  early-return error paths; happy path was broken. Fixed by realigning to
  the internal contract.
- **Strict mypy.** Resolved 131 type errors across the public facade.
  `_internal/*` remains under per-module `ignore_errors` (D13 phased
  coverage); `mcp_server.py` uses targeted `# type: ignore[...]` for MCP
  SDK's untyped decorators.
- 18 empty `__init__.py` files removed from `ao_kernel/defaults/extensions/
  PRJ-*/` (hyphenated names cannot be Python packages — dead files).
- Unused imports in `ao_kernel/llm.py:279` and
  `tests/test_roadmap_internal.py:12` (new ruff F401).

### Changed
- **PyPI classifier:** `Development Status :: 3 - Alpha` →
  `4 - Beta`. Accurately reflects production-grade core + ongoing
  productization.
- **Behavior change (caller-visible): registry overclaim cleanup.**
  `vision`, `audio`, `code_agentic`, and `structured_output` flags are now
  `unsupported` for every provider. Previously several providers advertised
  these as `supported` or `experimental` without a provider-side
  implementation, producing silent failures. Callers will now receive an
  explicit policy deny. See `provider_capability_registry.v1.json` notes.
- Global git config hardened in this maintainer's workspace (rerere,
  reflog 365d, fetch.prune, push.followTags). Not shipped in the package.

## [2.1.1] - 2026-04-13

### Fixed
- CI: exclude `_internal` from coverage gate to unblock Faz 1-2 test additions

## [2.1.0] - 2026-04-13

### Added
- `AoKernelClient` unified high-level SDK with full governed pipeline
- Self-editing memory (Letta/MemGPT inspired): remember/update/forget/recall
- Semantic vector retrieval with provider embedding + cosine similarity
- Embedding-based groundedness check in eval harness
- End-to-end integration tests (session roundtrip, client pipeline, MCP dispatch)
- Tool use activation: capability loader fix + registry propagation

### Fixed
- 5 integration wiring issues (lifecycle hook, canonical injection, stream tools, MCP desc, vision registry)
- Fail-closed enforcement + policy delegation
- Self-edit memory recall auto-prefix pattern consistency
- 4 ADV-002 advisory warning fixes

### Changed
- CLAUDE.md rewritten: 16 sections, comprehensive and stable

## [2.0.0] - 2026-04-13

### Changed
- **BREAKING:** `src/` shim removed, all internals under `ao_kernel._internal` namespace

### Added
- Hot/warm/cold memory tier enforcement
- MCP HTTP transport (starlette + uvicorn)
- Durable checkpoint/resume for session context
- Tool streaming support (v0.3.0 — tool call deltas reconstructed)
- Chaos/failure smoke tests
- Multi-agent coordination SDK hooks (revision tracking, stale detection)
- Context pipeline: 3-lane compilation, profile routing, decision extraction

## [0.2.0] - 2026-04-12

### Added
- `ao_kernel.llm` public facade: route, build, execute, normalize, stream
- Context management pipeline (compile → inject → extract → promote)
- Canonical decision store with temporal metadata
- Context compiler with 6 profiles (STARTUP, TASK_EXECUTION, REVIEW, EMERGENCY, ASSESSMENT, PLANNING)
- Memory pipeline with governed context loop
- Backlog modules: evidence writer, session management, secrets providers, tool gateway

## [0.1.0] - 2026-04-12

### Added
- Initial release: governed AI orchestration runtime
- Policy engine: 4 types (autonomy, tool calling, provider guardrails, generic)
- Fail-closed governance with JSONL evidence trail
- LLM routing with 6 provider support (Claude, OpenAI, Google, DeepSeek, Qwen, xAI)
- CLI: `ao-kernel init`, `doctor`, `migrate`, `mcp serve`, `version`
- Workspace mode + library mode dual operation
- 324 bundled JSON defaults (policies, schemas, registry, extensions)
