# V5 Epic 8 E-8-4: API Reference (Sphinx + autodoc) Scaffold

> **Risk class:** conservative low-risk (scaffold-only; opt-in build)
> **Implementer:** Anthropic Claude / **Reviewer:** OpenAI Codex (post-impl)

## 1. Scope

Sphinx + autodoc + napoleon scaffold for the auto-generated API
reference of the `ao_kernel` public facade. Build is operator-invoked
(`pip install 'ao-kernel[docs]'` + `sphinx-build`); not scheduled in
CI in this slice.

**In scope:**
- `docs/api/conf.py` (Sphinx config, lazy version read, autodoc_mock_imports for extras)
- `docs/api/index.rst` (public facade module list + Out of Scope + cross-doc refs)
- `docs/api/README.md` (build instructions + operator boundaries)
- `pyproject.toml` `[docs]` extra (sphinx + sphinx-autodoc-typehints)
- 18 invariant tests

**Out of scope (ZERO TOUCH):**
- `.github/workflows/*` (CI scheduled build + GitHub Pages publication are future operator decisions)
- `ao_kernel._internal/*` (autodoc-excluded by design)
- Bundled JSON resources under `ao_kernel/defaults/`
- Live provider client imports (anthropic, openai, requests, httpx)
- Any guard flag flip

## 2. conf.py Discipline

- Extensions: `autodoc + napoleon + viewcode + intersphinx`
- `autodoc_default_options.exclude-members: "_internal"` (private namespace excluded)
- `autodoc_mock_imports = [tenacity, tiktoken, mcp, starlette, uvicorn, opentelemetry]` (core install works)
- `__version__` read via text parse from `ao_kernel/__init__.py` (NOT via `import ao_kernel`; keeps build lazy)
- `rst_prolog` pins the 3 guard flags const false disclaimer in every rendered page
- No live provider client import (anthropic / openai / requests / httpx blocked by invariant test)

## 3. index.rst Coverage

| Module | Status |
|---|---|
| `ao_kernel` | listed |
| `ao_kernel.client` | listed |
| `ao_kernel.governance` | listed |
| `ao_kernel.llm` | listed |
| `ao_kernel.config` | listed |
| `ao_kernel.session` | listed |
| `ao_kernel.workspace` | listed |
| `ao_kernel.tool_gateway` | listed |
| `ao_kernel.mcp_server` | listed |
| `ao_kernel.telemetry` | listed |
| `ao_kernel.errors` | listed |
| `ao_kernel.cli` | listed |
| `ao_kernel.context` | listed |
| `_internal` | excluded (Out of Scope) |
| Bundled JSON | excluded |
| Tests | excluded |

## 4. Test Sections (18 invariants)

| Section | Count | Focus |
|---|---|---|
| 1. Scaffold presence | 4 | api/ + conf.py + index.rst + README.md |
| 2. conf.py discipline | 6 | autodoc+napoleon + excludes _internal + mocks extras + lazy version + rst_prolog guard flags + no live provider imports |
| 3. index.rst content | 4 | public facade modules + excludes _internal + guard flags disclaimer + refs E-8-1/E-8-3/E-8-5 |
| 4. pyproject [docs] extra | 3 | docs extra present + sphinx pinned + no live provider deps |
| 5. Governance ZERO TOUCH | 1 | no `.github/workflows/` mutation |

## 5. Build

```bash
pip install 'ao-kernel[docs]'
sphinx-build -b html docs/api docs/api/_build/html
```

HTML output: `docs/api/_build/html/index.html`.

## 6. References

- E-8-1 deployment guide (PR #815 merged)
- E-8-3 operator runbook (PR #816 merged)
- E-8-5 tutorial (PR #817 merged)
- E-8-6 migration guide (merged earlier)
- V5 roadmap + HARD RULE Cross-AI Peer Review + Uzun Vadeli
