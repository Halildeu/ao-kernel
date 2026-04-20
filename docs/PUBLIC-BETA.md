# Public Beta

Bu doküman `ao-kernel` Public Beta yüzeyinin SSOT kaynağıdır.
README kısa giriş sağlar; desteklenen/ertelenen yüzey, kurulum kanalı ve
bilinen hatalar burada tutulur.

## Kurulum

```bash
pip install ao-kernel==4.0.0b1
pip install --pre ao-kernel
```

`pip install ao-kernel` varsayılan olarak stable kanalda kalır. Public
Beta kurmak için pre-release sürümü açıkça istemek gerekir.

## Shipped

| Yüzey | Durum | Not |
|---|---|---|
| `ao-kernel version` | Shipped | Konsol entrypoint kontratı |
| `python -m ao_kernel version` | Shipped | Module entrypoint kontratı |
| `python -m ao_kernel.cli version` | Shipped | CLI module kontratı |
| Bundled `review_ai_flow` + bundled `codex-stub` | Shipped | Desteklenen tek demo workflow |
| `examples/demo_review.py` | Shipped | Source checkout üzerinden çalışan demo |
| Wheel-install packaging smoke CI | Shipped | Fresh venv + built wheel gate |

## Beta

| Yüzey | Durum | Not |
|---|---|---|
| `codex-stub` subprocess invocation | Beta | `{python_executable}` reserved token ile aktif interpreter kullanılır |
| Public Beta docs | Beta | Bu doküman support matrix için SSOT |

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
