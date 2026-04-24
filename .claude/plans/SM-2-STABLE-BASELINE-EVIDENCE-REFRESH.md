# SM-2 — Stable Baseline Evidence Refresh

**Status:** Completed
**Date:** 2026-04-24
**Tracker:** [#380](https://github.com/Halildeu/ao-kernel/issues/380)
**Parent context:** `SM-1` stable maintenance baseline

## Purpose

Refresh the evidence for the current narrow stable baseline after `SM-1`
established stable maintenance as the default operating mode.

This is evidence hygiene only. It does not change runtime behavior, widen
support, bump the package version, tag, or publish.

## Boundary

The stable support boundary remains unchanged:

1. `v4.0.0` is the live stable package.
2. The shipped support surface remains narrow: entrypoints, `doctor`,
   bundled `review_ai_flow + codex-stub`, `examples/demo_review.py`,
   policy command enforcement, packaging smoke, and documented read-only
   `PRJ-KERNEL-API` actions.
3. `claude-code-cli`, `gh-cli-pr`, kernel API write-side actions, and
   real-adapter benchmark full mode remain Beta/operator-managed.
4. `bug_fix_flow` release closure, full remote PR opening, roadmap/spec demo,
   and adapter-path `cost_usd` public support remain Deferred.
5. There is still no active support-widening runtime gate.

## Evidence

### Entrypoints

```bash
python3 -m ao_kernel version
python3 -m ao_kernel.cli version
```

Result:

```text
ao-kernel 4.0.0
ao-kernel 4.0.0
```

### Doctor

```bash
python3 -m ao_kernel doctor
```

Result:

```text
ao-kernel doctor v4.0.0
8 OK, 1 WARN, 0 FAIL
runtime_backed=2 contract_only=1 quarantined=16
remap_candidate_refs=61 missing_runtime_refs=152
runtime_backed_ids=PRJ-HELLO, PRJ-KERNEL-API
```

The warning is the expected extension truth inventory warning. It does not
block the shipped baseline because the support boundary does not promote the
quarantined inventory.

### Truth Inventory Ratchet

```bash
python3 scripts/truth_inventory_ratchet.py --output json
```

Summary:

```text
contract_only: 1
missing_runtime_refs: 152
quarantined: 16
remap_candidate_refs: 61
runtime_backed: 2
total_extensions: 19
```

This snapshot is unchanged from the expected support-boundary interpretation:
truth inventory visibility is not support widening.

### Wheel-Installed Packaging Smoke

```bash
python3 scripts/packaging_smoke.py
```

Result:

```text
Successfully built ao_kernel-4.0.0.tar.gz and ao_kernel-4.0.0-py3-none-any.whl
Successfully installed ao-kernel-4.0.0
ao-kernel 4.0.0
ao-kernel 4.0.0
ao-kernel 4.0.0
[demo] final state: completed
[demo] workspace cleaned up
```

The smoke used a fresh venv and installed the built wheel, then ran:

1. `ao-kernel version`
2. `python -m ao_kernel version`
3. `python -m ao_kernel.cli version`
4. `examples/demo_review.py --cleanup`

### Targeted Tests

```bash
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
```

Result:

```text
3 passed, 1 skipped
```

There is no separate `tests/test_packaging_smoke.py` file; packaging smoke is
covered by the executable `scripts/packaging_smoke.py` and the blocking CI job.

## Decision

The stable shipped baseline is still green under the narrow support boundary.
No production-platform support widening is granted by this refresh.

## Exit Criteria

1. Evidence record is merged.
2. Program status points to `SM-2` as the latest stable evidence refresh.
3. `SM-1` remains the operating-mode baseline.
4. Issue [#380](https://github.com/Halildeu/ao-kernel/issues/380) is closed.
