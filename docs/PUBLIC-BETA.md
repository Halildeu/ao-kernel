# Public Beta (v4.0.0b1) — Support Matrix SSOT

> **Sürüm durumu (2026-04-20)**: stable kanal `v3.13.3`, bu branch /
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

## Shipped (v4.0.0b1)

| Yüzey | Durum | Not |
|---|---|---|
| `ao-kernel version` | Shipped | Konsol entrypoint kontratı (test_cli_entrypoints.py pinli) |
| `python -m ao_kernel version` | Shipped | Module entrypoint kontratı |
| `python -m ao_kernel.cli version` | Shipped | CLI module kontratı |
| Bundled `review_ai_flow` + bundled `codex-stub` | Shipped | Desteklenen demo workflow |
| `examples/demo_review.py` | Shipped | Disposable workspace + canlı smoke `completed` |
| `ao-kernel doctor` | Shipped | Workspace health check (8/8 OK) |
| CI coverage gate 85% | Shipped | `pyproject.toml` ile hizalı (`test.yml --fail-under=85`) |
| Adapter CLI command enforcement | Shipped | `policy_checked` / `policy_denied` artık resolved command ihlallerini de içerir; canonical sıra `step_started -> policy_checked -> adapter_invoked` korunur |
| `{python_executable}` localized exception | Shipped | Yalnız manifest `command` alanı explicit `{python_executable}` kullandığında, yalnız resolved `sys.executable` realpath'i için geçerli; sandbox allowlist'ini mutate etmez |
| Wheel-install packaging smoke CI | Shipped | `scripts/packaging_smoke.py` blocking job olarak `test.yml`'de ve publish öncesi `publish.yml`'de koşar |

## Beta

| Yüzey | Durum | Not |
|---|---|---|
| Public Beta yüzeyinin tamamı | Beta | Stable kanal hâlâ `3.13.3`; genel kullanım için pre-release install gerekir |
| Real-adapter benchmark tam modu | Beta | Operator-managed yüzey; deterministik stub lane kadar stabil değil |

## Deferred

| Yüzey | Durum | Not |
|---|---|---|
| `bug_fix_flow` release closure | Deferred | Public Beta kapsamı dışında |
| `gh-cli-pr` ile tam E2E PR açılışı | Deferred | Roadmap/spec yüzeyi |
| `docs/roadmap/DEMO-SCRIPT-SPEC.md` içindeki 11 adımlı üç-adapter akış | Deferred | Canlı destek vaadi değildir |
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
