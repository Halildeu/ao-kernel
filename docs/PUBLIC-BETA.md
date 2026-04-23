# Public Beta (v4.0.0b1) — Support Matrix SSOT

> **Sürüm durumu (2026-04-22)**: stable kanal `v3.13.3`, bu branch /
> pre-release paket sürümü `4.0.0b1`. Bu doküman `v4.0.0b1` için canlı
> destek matrisi ve operator-facing SSOT'tur.

## Kurulum

### Stable kanal

```bash
pip install ao-kernel
```

### Public Beta pre-release

```bash
pip install ao-kernel==4.0.0b1
pip install --pre ao-kernel
```

`pip install ao-kernel` varsayılan olarak stable kanalda kalır; pre-release
istemek gerekir.

## Operational References

- [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md)
- [`OPERATIONS-RUNBOOK.md`](OPERATIONS-RUNBOOK.md)
- [`UPGRADE-NOTES.md`](UPGRADE-NOTES.md)
- [`ROLLBACK.md`](ROLLBACK.md)
- [`KNOWN-BUGS.md`](KNOWN-BUGS.md)

## Shipped (v4.0.0b1)

| Yüzey | Durum | Not |
|---|---|---|
| `ao-kernel version` | Shipped | Konsol entrypoint kontratı (test_cli_entrypoints.py pinli) |
| `python -m ao_kernel version` | Shipped | Module entrypoint kontratı |
| `python -m ao_kernel.cli version` | Shipped | CLI module kontratı |
| Bundled `review_ai_flow` + bundled `codex-stub` | Shipped | Desteklenen demo workflow |
| `examples/demo_review.py` | Shipped | Disposable workspace + canlı smoke `completed`; komut, `ao-kernel` kurulu bir Python environment'ı içinde çalıştırılmalıdır |
| `ao-kernel doctor` | Shipped | Workspace health check + bundled extension truth audit; may emit WARN while quarantined inventory remains |
| `PRJ-KERNEL-API` read-only runtime-backed actions | Shipped | `system_status` and `doc_nav_check`; explicit bootstrap handlers, offline, read-only, behavior-tested |
| CI coverage gate 85% | Shipped | `pyproject.toml` ile hizalı (`test.yml --fail-under=85`) |
| Adapter CLI command enforcement | Shipped | `policy_checked` / `policy_denied` artık resolved command ihlallerini de içerir; canonical sıra `step_started -> policy_checked -> adapter_invoked` korunur |
| `{python_executable}` localized exception | Shipped | Yalnız manifest `command` alanı explicit `{python_executable}` kullandığında, yalnız resolved `sys.executable` realpath'i için geçerli; sandbox allowlist'ini mutate etmez |
| Wheel-install packaging smoke CI | Shipped | `scripts/packaging_smoke.py` blocking job olarak `test.yml`'de ve publish öncesi `publish.yml`'de koşar |

## Beta

> **Not:** Bu tablodaki yüzeyler shipped baseline değildir. Çalışan smoke ve
> helper kanıtları vardır, fakat operator-managed kullanım ve ek önkoşullar
> gerektirirler.

| Yüzey | Durum | Not |
|---|---|---|
| Public Beta yüzeyinin tamamı | Beta | Stable kanal hâlâ `3.13.3`; genel kullanım için pre-release install gerekir |
| `claude-code-cli` helper-backed real-adapter lane | Beta (operator-managed) | `python3 scripts/claude_code_cli_smoke.py --output text` sonucu `overall_status: pass` olmalıdır. Bu smoke içinde hem `auth_status` hem `prompt_access` check'i geçmelidir; yalnız `claude auth status` yeşili yeterli kabul edilmez. Varsayılan shipped demo değildir. `PB-6.6` closeout verdict'i: `stay_beta_operator_managed` |
| `gh-cli-pr` helper-backed preflight lane | Beta (operator-managed preflight + live-write readiness probe) | Varsayılan `python3 scripts/gh_cli_pr_smoke.py --output text` preflight yoludur ve side-effect-safe `gh pr create --dry-run` zincirini çalıştırır. Live-write probe (`--mode live-write --allow-live-write --head <branch> --base <branch>`) explicit opt-in + create->verify->rollback ister. Varsayılan disposable guard keyword `sandbox`'dır; repo adında bu keyword yoksa lane `blocked` döner (`gh_pr_live_write_repo_not_disposable`). `--keep-live-write-pr-open` lane'i riskli sayar ve `blocked` döner. Support widening değildir |
| `PRJ-KERNEL-API` write-side actions | Beta (operator-managed write contract) | `project_status`, `roadmap_follow`, `roadmap_finish` runtime-backed. `workspace_root` zorunlu, varsayılan `dry_run=true`, gerçek yazma için `confirm_write=I_UNDERSTAND_SIDE_EFFECTS` gerekir; conflict/idempotency/rollback davranışı behavior testlerle pinlidir |
| Real-adapter benchmark tam modu | Beta (operator-managed) | Deterministik stub lane kadar stabil değildir; adapter-altı gerçek tier sınırları yukarıdaki satırlarda tanımlanır |

## Contract / Inventory Layer

| Yüzey | Durum | Not |
|---|---|---|
| Extension loader + manifest validation | Shipped infra | Loader/validator kodu ve truth-tier audit gerçektir; bu, her bundled manifestin end-to-end production-ready olduğu anlamına gelmez |
| Bundled `defaults/registry`, `defaults/extensions`, `defaults/operations`, `defaults/adapters` içeriği | Contract inventory | Ağaçta görünmesi destek vaadi değildir; ancak ilgili doküman/test/Public Beta matrisi o yüzeyi ayrıca işaretliyorsa destekli sayılır |
| `examples/hello-llm/` | Example-only | SDK kullanım örneğidir; Public Beta destek vaadinin parçası değildir |

### Truth-tier yorum kuralı

`ao-kernel doctor` truth sınıfları support boundary ile aşağıdaki kuralla
eşlenir:

| Truth tier | Support yorumu |
|---|---|
| `runtime_backed` | Runtime owner vardır; yine de shipped/beta claim için behavior test + smoke + docs parity birlikte gerekir |
| `contract_only` | Contract katmanı vardır, runtime register yoktur; support claim değildir |
| `quarantined` | Açık runtime gap vardır; support dışı/deferred sınıfında kalır |

Bu kuralın amacı, inventory görünürlüğünü support widening ile karıştırmamaktır.
`PB-9.2` kapsamında debt işlem sırası ve truth-tier tabanlı karar ratchet'i
`.claude/plans/PB-9.2-TRUTH-INVENTORY-DEBT-RATCHET.md` içinde tutulur.
Bu ratchet support tier'ı tek başına widen etmez.
Canlı snapshot üretimi için: `python3 scripts/truth_inventory_ratchet.py --output json`.

## Deferred

| Yüzey | Durum | Not |
|---|---|---|
| `bug_fix_flow` release closure | Deferred | `PB-8.3` closeout kararı: `stay_deferred`. Workflow-level `open_pr` adımı explicit opt-in guard (`AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1`) arkasına alındı ve failure metadata/evidence parity güçlendirildi; buna rağmen disposable/live rollback zinciri workflow runtime contract'ında promoted support kapısı değil |
| `gh-cli-pr` ile tam E2E PR açılışı | Deferred | Live-write probe create->verify->rollback guard'larıyla güçlense de gerçek remote PR açılışı hâlâ destek vaadi değildir; lane operator-managed/deferred boundary içinde değerlendirilir |
| `docs/roadmap/DEMO-SCRIPT-SPEC.md` içindeki 11 adımlı üç-adapter akış | Deferred | Canlı destek vaadi değildir |
| Adapter-path `cost_usd` reconcile | Deferred | Public support claim olarak hâlâ deferred; benchmark/internal runtime hook varlığı bunu tek başına shipped veya beta support yüzeyine yükseltmez |

## Known Bugs

> Full operator registry: [`KNOWN-BUGS.md`](KNOWN-BUGS.md)

| Konum | Etki | Workaround | Beta blocker? | Hedef |
|---|---|---|---|---|
| `KB-001` / `claude-code-cli` beta lane | `claude auth status` yeşil görünse bile gerçek `claude -p` prompt access bloklu olabilir | `claude auth status` yerine `python3 scripts/claude_code_cli_smoke.py --output text` çıktısını belirleyici kabul et; gerekirse session re-login yap | Yalnız operator-managed lane için evet; shipped baseline için hayır | Open |
| `KB-002` / `claude-code-cli` token fallback | `claude setup-token` türevi uzun ömürlü token route'u `Invalid bearer token` verebilir | session auth kullan; env-token fallback'i primary recovery olarak görme | Hayır | Open |

## Kapsam Dışı Notlar

- Public Beta “hemen çalışır” iddiası yalnızca bundled
  `review_ai_flow` + bundled `codex-stub` yolu için geçerlidir.
- `claude-code-cli` ve `gh-cli-pr` bugün default demo yüzeyi değildir;
  yalnız helper-backed operator-managed beta satırları kadar desteklenir.
- Bundled extension inventory runtime-backed olsa da support-tier ayrımı korunur:
  `PRJ-KERNEL-API` içinde `system_status` / `doc_nav_check` shipped read-only
  satırındadır; `project_status` / `roadmap_follow` / `roadmap_finish` ise
  explicit write contract ile Beta (operator-managed) satırındadır.
  `PRJ-CONTEXT-ORCHESTRATION` bugün contract-only katmandadır
  (manifest/contract cleanup sonrası, runtime handler hâlâ yoktur);
  kalan manifestler doctor truth audit'inde quarantined olarak görülebilir.
- Bu doküman, ao-kernel'in genel amaçlı bir production coding automation
  platformu olduğunu iddia etmez; destek vaadi dar ve açıkça tablolanmış
  yüzeyler içindir.
- `docs/roadmap/DEMO-SCRIPT-SPEC.md` roadmap/spec dokümanıdır; canlı
  CLI komut listesi değildir.
