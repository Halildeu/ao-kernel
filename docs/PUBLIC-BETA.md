# Support Matrix SSOT (v4.0.0 stable + beta lanes)

> **Sürüm durumu (2026-04-24)**: `v4.0.0` tag'i publish edilmiştir ve
> `ao-kernel==4.0.0` PyPI üzerinde canlıdır. Fresh-venv doğrulaması hem exact
> pin (`ao-kernel==4.0.0`) hem stable kanal (`pip install ao-kernel`) için
> `ao-kernel 4.0.0` sonucunu verdi. Bu doküman stable shipped baseline, beta
> lanes, deferred lanes ve known bugs için operator-facing SSOT'tur.

## Kurulum

### Stable kanal

```bash
pip install ao-kernel
pip install ao-kernel==4.0.0  # exact stable pin
```

### Historical Public Beta pre-release

```bash
pip install ao-kernel==4.0.0b2
pip install --pre ao-kernel
```

`4.0.0b2` historical Public Beta pre-release pin'idir. Normal kullanıcı ve
stable rollback yolu değildir. `--pre` yalnız pre-release hattını bilinçli
takip eden operatörler için kullanılmalıdır; gelecekte yeni pre-release varsa
onu da seçebilir. Stable `4.0.0` canlı hale geldiğinde varsayılan kullanıcı
yolu stable kanal olur.

## Operational References

- [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md)
- [`OPERATIONS-RUNBOOK.md`](OPERATIONS-RUNBOOK.md)
- [`UPGRADE-NOTES.md`](UPGRADE-NOTES.md)
- [`ROLLBACK.md`](ROLLBACK.md)
- [`KNOWN-BUGS.md`](KNOWN-BUGS.md)

## Stable Support Boundary

`ST-2` froze the support boundary and `ST-8` published it unchanged for
`4.0.0` stable. The stable support set is exactly the `Shipped` table below
unless a later gate changes this document with new evidence.

Stable rules:

1. `Beta`, `Deferred`, `Contract inventory`, and `Example-only` rows are not
   stable shipped support claims.
2. `claude-code-cli`, `gh-cli-pr`, `PRJ-KERNEL-API` write-side actions, and
   real-adapter benchmark full mode remain operator-managed beta.
3. `bug_fix_flow` release closure, full remote PR opening, roadmap/spec demo
   widening, and adapter-path `cost_usd` public support remain deferred.
4. There is currently no known bug that blocks the shipped baseline; current
   known bugs affect operator-managed beta lanes only.
5. This boundary still does not claim ao-kernel is a general-purpose
   production coding automation platform.

## Shipped (v4.0.0 stable)

| Yüzey | Durum | Not |
|---|---|---|
| `ao-kernel version` | Shipped | Konsol entrypoint kontratı (test_cli_entrypoints.py pinli) |
| `python -m ao_kernel version` | Shipped | Module entrypoint kontratı |
| `python -m ao_kernel.cli version` | Shipped | CLI module kontratı |
| Bundled `review_ai_flow` + bundled `codex-stub` | Shipped | Desteklenen demo workflow |
| `examples/demo_review.py` | Shipped | Disposable workspace + public package fresh-venv smoke `completed`; komut, `ao-kernel` kurulu bir Python environment'ı içinde çalıştırılmalıdır |
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
| Historical Public Beta pre-release | Beta | `4.0.0b2` remains a pre-release pin for operators that intentionally stay on that line; stable support is the shipped baseline above |
| `claude-code-cli` helper-backed real-adapter lane | Beta (operator-managed) | `python3 scripts/claude_code_cli_smoke.py --output text --timeout-seconds 30` sonucu `overall_status: pass` olmalıdır. Bu smoke içinde hem `auth_status` hem `prompt_access` check'i geçmelidir; yalnız `claude auth status` yeşili yeterli kabul edilmez. Governed workflow evidence için ek komut: `python3 scripts/claude_code_cli_workflow_smoke.py --output text --timeout-seconds 60`. Varsayılan shipped demo değildir. `GP-3.6` closeout verdict'i `close_keep_operator_beta`; `GP-4.5` closeout verdict'i `close_no_widening_keep_operator_beta`; production-certified read-only değildir. Gerekçe: external `claude` binary/session auth operatör durumudur, `KB-001`/`KB-002` açıktır ve protected live gate evidence hâlâ blocked durumdadır |
| `gh-cli-pr` helper-backed preflight lane | Beta (operator-managed preflight + live-write readiness probe) | Varsayılan `python3 scripts/gh_cli_pr_smoke.py --output text` preflight yoludur ve side-effect-safe `gh pr create --dry-run` zincirini çalıştırır. Live-write probe (`--mode live-write --allow-live-write --repo <owner>/<sandbox-repo> --head <branch> --base <branch>`) explicit opt-in + create->verify->rollback ister. Varsayılan disposable guard keyword `sandbox`'dır; repo adında bu keyword yoksa lane `blocked` döner (`gh_pr_live_write_repo_not_disposable`). `GP-2.5a` sandbox rehearsal geçmiştir, fakat `--keep-live-write-pr-open` lane'i hâlâ riskli sayar ve `blocked` döner. Support widening değildir |
| `PRJ-KERNEL-API` write-side actions | Beta (operator-managed write contract) | `project_status`, `roadmap_follow`, `roadmap_finish` runtime-backed. `workspace_root` zorunlu, varsayılan `dry_run=true`, gerçek yazma için `confirm_write=I_UNDERSTAND_SIDE_EFFECTS` gerekir; conflict/idempotency/audit davranışı behavior testlerle pinlidir. Operator smoke: `python3 scripts/kernel_api_write_smoke.py --output text` |
| Real-adapter benchmark tam modu | Beta (operator-managed) | Deterministik stub lane kadar stabil değildir; adapter-altı gerçek tier sınırları yukarıdaki satırlarda tanımlanır |
| `repo scan` read-only repo intelligence | Beta / experimental | `python3 -m ao_kernel repo scan --project-root . --output json` yalnız lokal dosya ağacı, dil sayımı, Python modül/entrypoint adayları, AST-derived Python import graph, top-level symbol index, deterministic chunk manifest ve deterministic Markdown agent pack için `.ao/context/repo_map.json`, `.ao/context/import_graph.json`, `.ao/context/symbol_index.json`, `.ao/context/repo_chunks.json`, `.ao/context/agent_pack.md` ve `.ao/context/repo_index_manifest.json` üretir. Root dosyalara yazmaz; embedding call, vector write, LLM summary, MCP tool, target-specific Claude/Codex export ve root context-pack export bu satırın dışında kalır |
| `repo index --dry-run` vector write-plan | Beta / experimental dry-run | `python3 -m ao_kernel repo index --project-root . --workspace-root .ao --dry-run --output json` mevcut `.ao/context/repo_chunks.json` artefaktını okuyup yalnız `.ao/context/repo_vector_write_plan.json` üretir. Planlanan repo chunk vector key/upsert/delete listesini ve embedding space kimliğini deterministik kaydeder. Embedding çağrısı, network access, vector backend bağlantısı, vector write, MCP tool ve root dosya yazımı yapmaz |
| `repo index --write-vectors` explicit vector write | Beta / experimental explicit write | `python3 -m ao_kernel repo index --project-root . --workspace-root .ao --write-vectors --confirm-vector-index I_UNDERSTAND_REPO_VECTOR_WRITES --output json` mevcut chunk manifestten repo vector write-plan üretir, configured vector backend ve embedding config ile repo chunk vector kayıtlarını yazar, stale key cleanup uygular ve `.ao/context/repo_vector_write_plan.json` ile `.ao/context/repo_vector_index_manifest.json` üretir. Confirmation, configured vector backend ve embedding API key olmadan fail-closed çalışır. Root authority dosyası, MCP tool veya retrieval integration üretmez |
| `repo query` read-only repo vector retrieval | Beta / experimental read-only retrieval | `python3 -m ao_kernel repo query --project-root . --workspace-root .ao --query "..." --output json` mevcut `.ao/context/repo_vector_index_manifest.json` artefaktını ve configured vector backend'i okuyarak repo chunk vector araması yapar. `--output markdown` aynı read-only sonucu agent-readable Markdown olarak stdout'a basar ve explicit handoff contract taşır: operatör çıktıyı görünür agent input'u olarak kendisi verir. Embedding API key ve configured backend olmadan fail-closed çalışır. Sonuçlar yalnız `repo_chunk::<project_identity>::<embedding_space>::` namespace'i, repo chunk metadata'sı ve mevcut source hash/line-range doğrulaması geçerse döner. Root dosyaya, `.ao/context/` artefaktına veya vector backend'e yazmaz; MCP tool, `context_compiler` auto-injection, root export ve canonical/session memory karışımı üretmez |
| Repo-intelligence explicit workflow building block | Beta / explicit handoff only | `GP-5.3e` kararıyla `repo query --output markdown` çıktısı future GP-5 read-only workflow rehearsal'larında yalnız operatör tarafından görünür input olarak verildiğinde beta building block sayılır. Bu production workflow integration değildir; automatic prompt injection, MCP tool, root export, workflow runtime wiring, `context_compiler` auto-feed ve real-adapter support widening içermez |
| GP-5 read-only workflow rehearsal | Beta / deterministic rehearsal only | `python3 scripts/gp5_read_only_rehearsal.py --output json` wheel-installed temporary virtualenv içinde `review_ai_flow + codex-stub` demo yolunu çalıştırır ve deterministic repo-intelligence Markdown handoff fixture'ını `--intent-file` ile görünür workflow intent input'u olarak verir. Rapor `gp5-read-only-rehearsal-report.schema.v1.json` ile validate edilir ve `support_widening=false` taşır. Bu live real-adapter, production semantic-correctness, MCP/root export, `context_compiler` auto-feed veya write-side support değildir |
| Repo-intelligence workflow/context opt-in contract | Contract inventory / not runtime-wired | `repo-intelligence-workflow-context-opt-in.schema.v1.json` gelecekteki explicit workflow opt-in şeklidir. Bugünkü runtime bu schema'yı workflow definition, executor, MCP, root export veya `context_compiler` içinde tüketmez; support widening değildir |

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
| `bug_fix_flow` release closure | Deferred | `PB-8.3` closeout kararı (`stay_deferred`) `GP-1.3` re-evaluation ile yeniden doğrulandı. Workflow-level `open_pr` adımı explicit opt-in guard (`AO_KERNEL_ALLOW_GH_CLI_PR_LIVE_WRITE=1`) arkasına alındı ve failure metadata/evidence parity güçlendirildi; buna rağmen disposable/live rollback zinciri workflow runtime contract'ında promoted support kapısı değil |
| `gh-cli-pr` ile tam E2E PR açılışı | Deferred | `GP-2.5a` disposable sandbox rehearsal create->verify->rollback zincirini geçmiştir; buna rağmen gerçek remote PR açılışı stable support vaadi değildir. Lane operator-managed/deferred boundary içinde değerlendirilir ve widening için ayrı promotion decision gerekir |
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
- `PB-9.4` closeout kararı `stay_beta_operator_managed` olarak sabitlenmiştir;
  bu release çizgisinde support widening yapılmaz.
- Bundled extension inventory runtime-backed olsa da support-tier ayrımı korunur:
  `PRJ-KERNEL-API` içinde `system_status` / `doc_nav_check` shipped read-only
  satırındadır; `project_status` / `roadmap_follow` / `roadmap_finish` ise
  explicit write contract ile Beta (operator-managed) satırındadır.
  `PRJ-CONTEXT-ORCHESTRATION` bugün contract-only katmandadır
  (manifest/contract cleanup sonrası, runtime handler hâlâ yoktur);
  `GP-1.4` kararı da bu sınırı değiştirmemiştir (`stay_contract_only`).
- `GP-1.5` program closeout kararı support boundary'yi widen etmemiştir;
  genel hüküm `stay_beta_operator_managed` çizgisinin korunmasıdır.
  kalan manifestler doctor truth audit'inde quarantined olarak görülebilir.
- Bu doküman, ao-kernel'in genel amaçlı bir production coding automation
  platformu olduğunu iddia etmez; destek vaadi dar ve açıkça tablolanmış
  yüzeyler içindir.
- `GP-4` CI-managed live adapter gate tasarımı support widening değildir.
  `claude-code-cli` production-certified support için gelecekte protected
  manual/scheduled live gate veya eşdeğer release gate gerekir; bu dokümanda
  shipped veya beta satırı otomatik değişmez.
- `GP-4.1` manual workflow skeleton'ı
  `live-adapter-gate-contract.v1.json` artifact'i üretir. `GP-4.2` bunun
  yanına schema-backed `live-adapter-gate-evidence.v1.json` artifact'ini
  ekler. Bu artifact bugün `overall_status="blocked"` /
  `support_widening=false` / `production_certified=false` döner ve canlı
  adapter execution kanıtı değildir.
- `GP-4.3` protected environment / secret contract hattı
  `live-adapter-gate-environment-contract.v1.json` artifact'ini ekler. Bu
  artifact required environment olarak `ao-kernel-live-adapter-gate` ve secret
  handle olarak `AO_CLAUDE_CODE_CLI_AUTH` adlarını tanımlar; secret değeri
  içermez, environment oluşturmaz, canlı `claude` çağırmaz ve support widening
  yapmaz.
- `GP-4.4` protected live rehearsal decision hattı
  `live-adapter-gate-rehearsal-decision.v1.json` artifact'ini ekler. Bugünkü
  karar `blocked_no_rehearsal`dir; required environment ve project-owned
  credential attested olmadığı için live rehearsal denenmez ve support boundary
  değişmez.
- `GP-4.5` support-boundary closeout kararı
  `close_no_widening_keep_operator_beta` olarak kapanmıştır. Bu karar
  `claude-code-cli` lane'ini Beta/operator-managed tutar; shipped baseline,
  production-certified real-adapter support ve genel amaçlı production platform
  claim'i genişlemez.
- `docs/roadmap/DEMO-SCRIPT-SPEC.md` roadmap/spec dokümanıdır; canlı
  CLI komut listesi değildir.
