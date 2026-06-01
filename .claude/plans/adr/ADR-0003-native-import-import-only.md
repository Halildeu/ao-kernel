---
id: ADR-0003
title: Native worker result import-only contract (ao-kernel never spawns the worker)
status: accepted
date: 2026-05-31
deciders:
  - Claude (Anthropic)
  - Codex (OpenAI, threads 019e8000, 019e8028)
  - Operator (gladyatore@hotmail.com)
retrospective: true
review_status: back_populated_pending_cross_ai_revalidation
back_populated_at: 2026-06-01T03:00:00Z
slice_ref: AO-MA-4.6-1
guard_flags:
  support_widening: false
  production_platform_claim: false
  live_adapter_execution: false
register_authority: evidence_record_only
github_write_authorized: false
---

# ADR-0003: Native worker result import-only contract

## Context

AO-MA-4.5 ships a pinned deterministic local worker stub: ao-kernel
`subprocess`-invokes the stub, which writes a `worker_result.v1.json`. To
move past stubbed output we need **real AI** worker results in the AO-MA
pipeline — but spawning Claude / Codex / Mavis from inside ao-kernel would
mean a live adapter execution, which the program's guard flags
(`live_adapter_execution=false`) and the CLI-subscription model
explicitly forbid.

## Decision

ao-kernel **calls nothing** to obtain real AI worker output. The
contract is **import-only**: the operator (or a native AI interface —
`claude-cli`, `codex-cli`, `mavis-cli`, or a local file) produces
`worker_result.v1.json` externally; ao-kernel reads the file, schema-
validates the full artifact chain (worker_result + runner_report +
manifest envelope + task_graph + agent_assignment), provenance-binds
the result to the AO-MA-4 runner truth, and atomically copies the
validated artifact into the canonical
`<artifact_dir>/workers/<task_id>/worker_result.v1.json` so AO-MA-5/6/7
can consume it.

Two error classes are pinned (Codex iter-3/4 of `019e8000`):

- **Fatal trust-boundary** errors raise `NativeWorkerImportError`
  *before* any import_report is written and *before* any integrated
  copy: artifact schema-invalid (guard + no_secret_attestation included),
  JSON parse failure, manifest sha mismatch, cross-id mismatch.
- **Reportable policy-invalid** errors emit a schema-valid import_report
  with `valid=false`, `integrated_path=null`, no copy: source_interface
  / provider mismatches, runner status non-eligible, declared/actual
  drift, known_gaps non-empty, existing integrated different sha.

Structural guarantee: an **AST import-allowlist** pins the importer to
`hashlib / json / jsonschema / pathlib / dataclasses / typing / re /
__future__ / collections + os.fsync`. `subprocess`, `socket`,
`requests`, `httpx`, `urllib`, `asyncio.subprocess`, `anthropic`,
`openai`, MCP / Mavis clients are unimportable; `os.system`, `popen`,
`exec*`, `spawn*`, `fork*` are rejected at AST attribute level. The
module physically cannot spawn a worker.

## Consequences

- Real AI output enters the pipeline without re-opening
  `live_adapter_execution`. Any future move to a live adapter requires
  an explicit operator-bound GPP supersession with the flag flipped —
  it can never sneak in via 4.6.
- The operator (or operator-authorized CLI) is the only entity that can
  introduce new worker artifacts; ao-kernel's role is to verify and
  bind, not to execute.
- `verify_import_binding` replays the full build-side chain (artifact
  shas, schemas, envelope, cross-id, cross-ref, declared/actual,
  source_interface/provider, runner status eligibility) so a forged
  all-pass report cannot pass without the underlying disk state being
  semantically coherent.

## Alternatives Considered

- **Spawn the native CLI from ao-kernel.** Rejected: would flip
  `live_adapter_execution=true` and break the CLI-subscription
  boundary. The operator subscribes to (and pays for) the CLI; ao-kernel
  is a control plane, not a transport.
- **Plain copy + schema validate without manifest anchoring.** Rejected
  per Codex iter-2 of `019e8000`: without anchoring `manifest_sha256`
  to `runner_report.manifest_sha256`, an attacker could re-bind to a
  forged manifest and pass `diff_scope`.

## References

- PR #766 (AO-MA-4.6-1)
- `ao_kernel/orchestration/native_worker_import.py`
- `ao_kernel/defaults/schemas/ao-ma-native-worker-import-report.schema.v1.json`
- Codex threads: 019e8000 (plan), 019e8028 (post-impl)
- AO-MA-SPM master plan §Faz 6
