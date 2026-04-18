"""Agent benchmark / regression suite (PR-B7).

Two governed flows exercised end-to-end under a mock-transport
harness: `governed_bugfix` (bug_fix_flow) + `governed_review`
(review_ai_flow). Mock lives at the public `invoke_cli` /
`invoke_http` boundary (patched at the executor's local import
site) so orchestrator + driver + executor + adapter_invoker
chain stays real.

Scope: fast-mode only (full real-adapter mode + cost_usd
reconcile + retry variants deferred to B7.1 / FAZ-C).

See `docs/BENCHMARK-SUITE.md` + `.claude/plans/PR-B7-DRAFT-PLAN.md`
v5 for the operator + design contract.
"""
