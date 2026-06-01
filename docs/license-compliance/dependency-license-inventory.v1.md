# ao-kernel Dependency License Inventory (V5 Epic 6 E-6-4)

> **Not legal counsel.** **Not legal advice.** **Operator responsibility.**
> Generated from `tests/fixtures/sample-sbom.cdx.json` (SHA256: `7382c405d036...`) and policy `docs/license-compliance/license-compliance-policy.v1.json` (SHA256: `7dc4e07e4c6b...`). Do not edit by hand; regenerate via `python scripts/generate_license_inventory.py`.

**Report status:** `review_required`

## Summary

- Component count: **8**
- Pass (allow tier match): **5**
- Review required: **3**
- Deny tier match: **0**

## Components

| Component | Version | License (id / expression / name) | Tier | Decision | Review reason |
|---|---|---|---|---|---|
| `example-dual-license` | `1.0.0` | `MIT OR Apache-2.0` | `n/a` | `review` | `unsupported_expression` |
| `example-name-only` | `1.0.0` | `Custom Permissive License` | `n/a` | `review` | `unresolved_name` |
| `jsonschema` | `4.23.0` | `MIT` | `allow` | `pass` | `-` |
| `mcp` | `1.0.0` | `MIT` | `allow` | `pass` | `-` |
| `opentelemetry-api` | `1.27.0` | `Apache-2.0` | `allow` | `pass` | `-` |
| `psycopg2-binary` | `2.9.9` | `LGPL-3.0-or-later` | `review` | `review` | `policy_review_tier` |
| `tenacity` | `8.5.0` | `Apache-2.0` | `allow` | `pass` | `-` |
| `tiktoken` | `0.7.0` | `MIT` | `allow` | `pass` | `-` |

