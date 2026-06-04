# Live Adapter Dry-Run Harness

The V5 E-2-4 dry-run harness emits the real governance evidence shape for a
would-be live adapter call while forcing the response to a deterministic stub.
It is infrastructure-only: it never opens a provider network connection, never
reads or serializes secret material, and never flips the guard flags.

## Command

```bash
python3 scripts/run_live_adapter_dryrun.py \
  --provider openai \
  --model gpt-4o-mini \
  --intent FAST_TEXT \
  --output evidence/dryrun-$(date -u +%Y%m%dT%H%M%SZ).envelope.v1.json
```

When the output path is inside an `evidence/` directory, the parent directory is
treated as the workspace root and the harness also appends the E-2-2 audit row to
`evidence/per_call_audit.jsonl`. If the output path is elsewhere and no
`--workspace-root` is provided, the harness runs in library mode and validates
the audit row without persisting it.

## Evidence

The envelope validates against `live_adapter_envelope.schema.v1.json`:

- `mode: dry_run`
- `response.status: dry_run_emitted`
- `cost.actual_cost_usd: 0.00000000` by default
- `live_adapter_execution: false`
- `support_widening: false`
- `production_platform_claim: false`
- `envelope_digest` recomputed from canonical JSON excluding the digest field

The audit row validates against `per_call_audit.schema.v1.json` and foreign-keys
to the envelope through `envelope_digest`.

## Kill-Switch

While evidence is generated, the harness installs a runtime kill-switch that
blocks raw sockets, subprocess families, shell exec helpers, stdlib HTTP,
optional HTTP clients (`httpx`, `urllib3`, `requests`, `aiohttp` when installed),
and native escape hatches (`ctypes.CDLL`, `cffi.FFI` when installed). Bypass
coverage is pinned by `tests/test_dryrun_killswitch_bypass.py` and static native
usage is pinned by `tests/test_dryrun_import_denylist.py`.

## Cost Ceiling

Default dry-run cost is zero, so cost ceiling state is `not_applicable`. For
testing the E-2-3 integration, `--dry-run-cost-usd` can simulate a non-zero
dry-run cost. If the configured hard ceiling is exceeded, the command exits `2`
and records the E-2-2 hard-breach audit row through the cost ceiling module.

This command is not live evidence and does not authorize live adapter execution.
