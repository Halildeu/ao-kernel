# E-3-6 — Recompute-not-trust Validator

> V5 Epic 3 support-widening matrix infrastructure slice. This record adds a
> deterministic validator for future support-widening supersession evidence. It
> does not widen support, claim production readiness, execute live adapters,
> mutate workflows, or mutate GitHub rulesets.

## Status

- **Work package:** E-3-6
- **Issue:** #858
- **Branch:** `codex/epic3-e3-6-validator`
- **Risk:** low
- **Authority:** `.claude/plans/EPIC-3-SUPPORT-WIDENING-MATRIX.md`
- **Guard flags:** unchanged:
  - `support_widening_allowed=false`
  - `production_platform_claim_allowed=false`
  - `live_adapter_execution_allowed=false`

## Added Surface

E-3-6 adds the v1-only validator surface for support-widening evidence:

- `ao_kernel/_internal/support_widening/validator.py`
- `scripts/validate_widening_evidence.py`
- `ao_kernel/defaults/schemas/widening-supersession-evidence-pack.schema.v1.json`
- `tests/test_widening_evidence_validator.py`

The validator accepts:

1. Existing `support_widening_evidence.v1` artifacts from E-3-1/E-3-2 and
   reuses the E-3-1 parse/recompute guard-pin logic.
2. New `widening_supersession_evidence_pack.v1` artifacts that model the
   future operator-bound Epic 9 support-widening supersession evidence pack.

## Non-Authority Boundary

The E-3-6 validator is not release authority and cannot authorize support
widening:

- `support_widening`, `production_platform_claim`, and
  `live_adapter_execution` remain false.
- `widening_authorized` is `const false` in the v1 evidence-pack schema.
- `support_widening_evidence.v2` and all other future schemas are rejected with
  `unsupported_future_schema_in_epic_3`.
- `validator_v2.py` and `support_widening_evidence.schema.v2.json` are
  intentionally absent from the Epic 3 codebase.
- GitHub/API observations are caller-supplied as read-only context; the module
  performs no network calls or GitHub writes.

## Machine Invariants

`tests/test_widening_evidence_validator.py` pins:

- Schema health and recursive strict closure.
- Existing `support_widening_evidence.v1` compatibility.
- v2/future schema rejection.
- Guard-flag and `widening_authorized` true rejection.
- Absence of `validator_v2.py` and schema v2.
- Forged consensus / hidden negative verdict rejection.
- Same-provider, implementer-reviewer, and operator-login collision rejection.
- Legacy `artifact_sha256` alias rejection at top-level and nested locations.
- Mutual `simulated_only=true` + `live_call_made=true` rejection.
- Stale replay and seven-day timing-window race rejection.
- Plan digest, final diff digest, PR head SHA, workflow-run, artifact, reviewer
  hash, verdict binding, raw verdict SHA, raw transcript artifact digest, and
  raw transcript artifact reference/provenance drift rejection.
- CLI success/reject exit-code behavior.

## Validation Plan

Minimum local validation before merge:

```bash
python3 -m json.tool ao_kernel/defaults/schemas/widening-supersession-evidence-pack.schema.v1.json
pytest tests/test_widening_evidence_validator.py \
  tests/test_widening_supersession_checklist.py \
  tests/test_support_widening_evidence_v1.py -q
ruff check ao_kernel/_internal/support_widening/validator.py \
  scripts/validate_widening_evidence.py \
  tests/test_widening_evidence_validator.py
mypy ao_kernel/_internal/support_widening/validator.py \
  scripts/validate_widening_evidence.py \
  tests/test_widening_evidence_validator.py
python3 scripts/gpp_next.py
git diff --check origin/main...HEAD
```

## Closure Notes

E-3-6 is the final Epic 3 support-widening infrastructure slice. Closing this
slice closes the validator runway for future operator-bound support-widening
supersession PRs, but it still does not flip any guard flag or change public
support tier.
