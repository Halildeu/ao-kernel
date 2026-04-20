# Public Beta (v4.0.0b1 Planı) — Support Matrix SSOT

> **Sürüm durumu (2026-04-20)**: `v3.13.2` yayında. Bu doküman tam
> Public Beta `v4.0.0b1` hattının **plan + SSOT**'sudur. Aşağıdaki
> "Shipped" satırları `v3.13.2` gövdesinde hâlihazırda çalışır; "Beta"
> ve "Deferred" bölümleri `v4.0.0b1` ship hattıyla kapanır. Bu patch
> release `v3.13.2`'de Public Beta yüzeyinin çekirdeğini (module
> entrypoint + demo pivotu + CI gate) gövdeye aldı.

## Kurulum

### v3.13.2 (stable patch, mevcut)

```bash
pip install ao-kernel
```

### v4.0.0b1 (Public Beta pre-release — henüz PyPI'de yayınlanmadı)

Yayınlandığında:

```bash
pip install ao-kernel==4.0.0b1
pip install --pre ao-kernel
```

`pip install ao-kernel` varsayılan olarak stable kanalda kalır; pre-release
istemek gerekir.

## Shipped (v3.13.2)

| Yüzey | Durum | Not |
|---|---|---|
| `ao-kernel version` | Shipped | Konsol entrypoint kontratı (test_cli_entrypoints.py pinli) |
| `python -m ao_kernel version` | Shipped | Module entrypoint kontratı |
| `python -m ao_kernel.cli version` | Shipped | CLI module kontratı |
| Bundled `review_ai_flow` + bundled `codex-stub` | Shipped | Desteklenen demo workflow |
| `examples/demo_review.py` | Shipped | Disposable workspace + canlı smoke `completed` |
| `ao-kernel doctor` | Shipped | Workspace health check (8/8 OK) |
| CI coverage gate 85% | Shipped | `pyproject.toml` ile hizalı (`test.yml --fail-under=85`) |

## Beta (v4.0.0b1 hattı, v3.13.2'de temeli hazır)

| Yüzey | Durum | Not |
|---|---|---|
| `codex-stub` subprocess invocation | Beta | `{python_executable}` reserved token ile aktif interpreter'ın **mutlak yolu** (`sys.executable`) doğrudan çalıştırılır (demo/packaging compat fix). Önceki `"python3"` sandbox PATH çözümüne tabiydi; yeni wiring PATH resolution'dan bağımsız — enabled policy + command_allowlist operator'ları için interpreter seçimi semantiği v3.13.1'e göre değişti. Policy command validation entegrasyonu (runtime anchor + rollout semantics) v4.0.0b1 lane'inde — v3.13.2'de sandbox preflight YOK. |
| Public Beta docs (bu doküman) | Beta | v4.0.0b1'de SSOT olacak |
| Wheel-install packaging smoke CI job | Beta (plan) | v4.0.0b1 scope — henüz `test.yml`'de yok; `publish.yml` build+twine check var ama fresh-venv install + demo smoke job eklenecek |

## Deferred

| Yüzey | Durum | Not |
|---|---|---|
| `bug_fix_flow` release closure | Deferred | Public Beta kapsamı dışında |
| `gh-cli-pr` ile tam E2E PR açılışı | Deferred | Roadmap/spec yüzeyi |
| `docs/roadmap/DEMO-SCRIPT-SPEC.md` içindeki 11 adımlı üç-adapter akış | Deferred | Canlı destek vaadi değildir |
| Real-adapter benchmark tam modu | Deferred | Fast-mode/deterministic yüzey dışında |
| Adapter-path `cost_usd` reconcile | Deferred | Ayrı correctness işi |

## Known Bugs

| Konum | Etki | Workaround | Beta blocker? | Hedef |
|---|---|---|---|---|
| `ao_kernel/_internal/roadmap/sanitize.py:39` | E-posta regex algısı hatalı davranabilir | Public Beta demo bu yolu sürmez | Hayır | Post-beta correctness patch |
| `ao_kernel/_internal/roadmap/compiler.py:139` | `id` alanı olmayan milestone girdisi `KeyError` üretebilir | Public Beta demo `compile_roadmap` no-id milestone ile çağırmaz | Hayır | Post-beta correctness patch |
| `ao_kernel/init_cmd.py:30-33` | `workspace_root_override` write-side asimetrik | Public Beta dokümanlarında `--workspace-root X` örneği verilmez | Hayır | Post-beta correctness patch |

## Kapsam Dışı Notlar

- Public Beta “hemen çalışır” iddiası yalnızca bundled
  `review_ai_flow` + bundled `codex-stub` yolu için geçerlidir.
- `docs/roadmap/DEMO-SCRIPT-SPEC.md` roadmap/spec dokümanıdır; canlı
  CLI komut listesi değildir.
