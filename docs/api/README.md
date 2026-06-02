# ao-kernel API Reference Build (V5 Epic 8 E-8-4)

> **Documentation only.** This directory is the Sphinx scaffold for the
> auto-generated API reference. Build is **operator-invoked**, not
> scheduled in CI. Does NOT flip any guard flag.

## Build

```bash
pip install 'ao-kernel[docs]'
sphinx-build -b html docs/api docs/api/_build/html
```

The build produces HTML at `docs/api/_build/html/index.html`.

## What's documented

- `ao_kernel.*` public facade modules (`client`, `governance`, `llm`,
  `config`, `session`, `workspace`, `tool_gateway`, `mcp_server`,
  `telemetry`, `errors`, `cli`, `context`)

## What's excluded by design

- `ao_kernel._internal/*` (private implementation namespace)
- Bundled JSON resources under `ao_kernel/defaults/`
- Test suite under `tests/`
- Live provider client surfaces (`live_adapter_execution=const false`)

## Why opt-in (not scheduled in CI yet)

- Sphinx adds non-trivial install footprint (alabaster, docutils, etc.);
  the `[docs]` extra keeps that optional
- Hosted-docs URL + GitHub Pages publication is a separate operator
  decision (CDN + custom domain + cache strategy)
- E-8-4 deliberately scaffolds the build; CI scheduling + GitHub Pages
  publication is a follow-up slice operator decides when to flip

## Operator boundaries

This reference is **descriptive of the public facade**; it does NOT:

- Replace `PRODUCTION-DEPLOYMENT-GUIDE.md` (E-8-1)
- Replace `OPERATOR-RUNBOOK.md` (E-8-3)
- Replace `MIGRATION-GUIDE-V4-TO-V5.md` (E-8-6)
- Replace the tutorial `TUTORIAL-BUILD-AO-MA-SPM-PROGRAM.md` (E-8-5)
- Authorize any guard flag flip
- Make any production-ready claim

## References

- V5 roadmap: `../../.claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md`
- Plan doc: `../../.claude/plans/EPIC-8-4-API-REFERENCE-SPHINX.md`
- HARD RULE Cross-AI Peer Review (2026-05-05 + 2026-05-14)
