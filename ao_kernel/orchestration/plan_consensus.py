"""AO-MA-11A plan-consensus + single operator-approval gate policy (v1).

Front-of-pipeline governance for the autonomous multi-AI coding workflow:
the three mandated providers (anthropic + openai + minimax) review a proposed
plan in rounds; this module aggregates their latest-round verdicts into a
single ``unanimous_status`` and decides whether the plan may be presented at
the SINGLE operator approval gate. Only a unanimous-AGREE plan reaches the
gate; the operator's decision is recorded as an ``ao-ma-11a-plan-approval.v1``
artifact bound by SHA to the exact consensus bundle, plan and approval
request (triple bind).

**HARD RULE pins (mirrors the AO-MA-5 integrator contract):**

- **No agent execution, no LLM call** — this module is pure deterministic
  policy over on-disk artifacts. It imports only the standard library plus
  ``jsonschema`` (enforced by an import-allowlist test), so it cannot
  shell out, reach the network, or invoke an LLM.
- **No GitHub write** — no ``git push``, no ``gh pr create``, no ``gh api``.
  The GitHub Environment that realizes the gate is wired in a follow-up
  (AO-MA-11A-2); this module only validates artifacts.
- **No ``subprocess`` import** in this module — static-test enforced.
- ``release_authority`` schema const ``"ao-release-gate+github-ruleset"``
  pins that plan consensus / approval is NOT release authority. The single
  gate authorizes an autonomous *run start*, not a merge/release.
- **No self-attestation** — ``unanimous_status`` is recomputed from
  ``provider_verdicts`` here; a stored value that disagrees with the
  recomputation is a fail-closed integrity error, never silently trusted.

**Unanimity rule:** ``AGREE`` iff every required provider has at least one
verdict and that provider's LATEST-round verdict is ``AGREE``. Any required
provider missing, or any recorded provider whose latest verdict is
``REVISE``/``PARTIAL``/``RED``, yields ``NOT_AGREE`` and no approval may be
requested.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"

_CONSENSUS_BUNDLE_SCHEMA_NAME = "ao-ma-11a-plan-consensus-bundle.schema.v1.json"
_PLAN_APPROVAL_SCHEMA_NAME = "ao-ma-11a-plan-approval.schema.v1.json"

_GUARD_FLAGS = ("support_widening", "production_platform_claim", "live_adapter_execution")

# The fixed set of providers that must reach AGREE for unanimity. The bundle
# schema pins ``required_providers`` to exactly this set; this constant is the
# defensive cross-check (belt + suspenders) so a future schema regression
# cannot silently widen the quorum.
_REQUIRED_PROVIDERS: frozenset[str] = frozenset({"anthropic", "openai", "minimax"})

UnanimousStatus = Literal["AGREE", "NOT_AGREE"]
GateState = Literal[
    "consensus_not_reached",
    "awaiting_operator_approval",
    "approved_autonomous_run_may_start",
    "halted_operator_rejected",
]


class PlanConsensusError(RuntimeError):
    """Raised for I/O / schema-load failures and trust-boundary violations.

    Trust-boundary violations include: a stored ``unanimous_status`` that
    disagrees with the recomputation, a duplicate ``(provider, round)`` entry,
    non-contiguous rounds, ``rounds_used`` not equal to the highest verdict
    round, a verdict round above ``round_budget``, a quorum that is not exactly
    the required provider set, and an approval whose SHA bindings,
    ``plan_digest``, ``unanimous_status`` or ``bypass_detected`` do not hold
    against the bound bundle and request. These are NOT normal policy outcomes
    — they mean an artifact is malformed or forged, so the gate fails closed.
    """


@dataclass
class ConsensusDecision:
    """Outcome of validating a plan-consensus bundle."""

    unanimous_status: UnanimousStatus
    can_request_approval: bool
    rounds_used: int
    round_budget: int
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class ApprovalDecision:
    """Outcome of validating an operator approval against its bundle."""

    decision: Literal["approved", "rejected", "expired"]
    proceed: bool
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class GateDecision:
    """Single-gate state derived from a bundle and an optional approval."""

    state: GateState
    proceed: bool
    unanimous_status: UnanimousStatus
    diagnostics: list[str] = field(default_factory=list)


def _load_schema(name: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanConsensusError(f"failed to load bundled schema {name!r}: {exc}") from exc


def _validate_schema(payload: dict[str, Any], schema_name: str, source: Path) -> None:
    schema = _load_schema(schema_name)
    try:
        Draft202012Validator(schema).validate(payload)
    except ValidationError as exc:
        raise PlanConsensusError(
            f"{source.name} failed schema {schema_name!r}: {exc.message} (at {list(exc.absolute_path)})"
        ) from exc


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PlanConsensusError(f"file not found: {path!s}")
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanConsensusError(f"failed to read {path!s}: {exc}") from exc


def sha256_of(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_verdict_by_provider(provider_verdicts: list[dict[str, Any]]) -> dict[str, str]:
    """Return ``{provider_id: latest-round verdict}``.

    A duplicate ``(provider_id, round_index)`` pair is a data-integrity
    violation (ambiguous truth) and fails closed.
    """

    seen_rounds: dict[tuple[str, int], str] = {}
    latest_round: dict[str, int] = {}
    latest_verdict: dict[str, str] = {}
    for entry in provider_verdicts:
        provider = entry["provider_id"]
        round_index = entry["round_index"]
        verdict = entry["verdict"]
        key = (provider, round_index)
        if key in seen_rounds:
            raise PlanConsensusError(
                f"duplicate verdict for provider {provider!r} round {round_index}; "
                f"consensus bundle carries ambiguous truth"
            )
        seen_rounds[key] = verdict
        if provider not in latest_round or round_index > latest_round[provider]:
            latest_round[provider] = round_index
            latest_verdict[provider] = verdict
    return latest_verdict


def compute_unanimous_status(
    provider_verdicts: list[dict[str, Any]],
    required_providers: list[str],
) -> UnanimousStatus:
    """Recompute unanimity from per-provider latest-round verdicts.

    AGREE iff every required provider has a latest-round verdict equal to
    ``AGREE`` AND no recorded provider's latest verdict is non-AGREE. Missing
    provider or any non-AGREE latest verdict → NOT_AGREE.
    """

    latest = _latest_verdict_by_provider(provider_verdicts)
    for provider in required_providers:
        if latest.get(provider) != "AGREE":
            return "NOT_AGREE"
    # Conservative: any recorded provider whose latest verdict is not AGREE
    # blocks consensus, even one outside the required quorum (defense in depth
    # should the provider_id enum ever widen beyond the mandated three).
    for verdict in latest.values():
        if verdict != "AGREE":
            return "NOT_AGREE"
    return "AGREE"


def _check_bundle_invariants(bundle: dict[str, Any], source: str) -> tuple[UnanimousStatus, int, int]:
    """Cross-field invariants beyond JSON Schema (defensive depth).

    These checks back-stop the bundle schema: even if the schema regressed,
    a bundle that widens the quorum, flips a guard flag, presents
    non-contiguous rounds, sets ``rounds_used`` inconsistent with the actual
    verdict rounds, slips a verdict round above ``round_budget``, or
    self-attests a ``unanimous_status`` that disagrees with its
    ``provider_verdicts`` is rejected fail-closed. Callable directly so the
    back-stops are unit-testable without crafting schema-valid input.

    Returns the recomputed ``(unanimous_status, rounds_used, round_budget)``.
    """

    declared_quorum = set(bundle["required_providers"])
    if declared_quorum != set(_REQUIRED_PROVIDERS):
        raise PlanConsensusError(
            f"{source}: required_providers {sorted(declared_quorum)} != {sorted(_REQUIRED_PROVIDERS)}; quorum tampering"
        )

    guard_flags = bundle["guard_flags"]
    for flag in _GUARD_FLAGS:
        if guard_flags.get(flag) is not False:
            raise PlanConsensusError(f"{source}: guard_flags.{flag} must be literal False; AO-MA no-widening contract")

    rounds_used = bundle["rounds_used"]
    round_budget = bundle["round_budget"]
    verdicts = bundle["provider_verdicts"]

    # Bind the round budget to the actual verdict rounds — otherwise a bundle
    # could claim round_budget=1 while carrying round_index=3 verdicts.
    rounds_present = {entry["round_index"] for entry in verdicts}
    max_round = max(rounds_present)
    if rounds_present != set(range(1, max_round + 1)):
        raise PlanConsensusError(
            f"{source}: verdict rounds {sorted(rounds_present)} are not contiguous 1..{max_round}; round gap"
        )
    if rounds_used != max_round:
        raise PlanConsensusError(
            f"{source}: rounds_used {rounds_used} != highest verdict round {max_round}; rounds_used must match"
        )
    if max_round > round_budget:
        raise PlanConsensusError(
            f"{source}: verdict round {max_round} exceeds round_budget {round_budget}; budget bypass via round_index"
        )

    computed = compute_unanimous_status(verdicts, bundle["required_providers"])
    stored = bundle["unanimous_status"]
    if computed != stored:
        raise PlanConsensusError(
            f"{source}: unanimous_status mismatch: bundle stored {stored!r} but provider_verdicts "
            f"recompute to {computed!r}; refusing self-attested consensus"
        )
    return computed, rounds_used, round_budget


def validate_consensus_bundle(bundle_path: Path) -> ConsensusDecision:
    """Schema-validate a plan-consensus bundle and recompute its unanimity.

    Raises ``PlanConsensusError`` on schema failure or any trust-boundary
    violation (lying ``unanimous_status``, duplicate/non-contiguous rounds,
    round-budget bypass, wrong quorum). Returns a ``ConsensusDecision``
    otherwise.

    Note: ``plan_digest`` and ``plan_binding.base_sha`` are operator-/
    pipeline-supplied descriptors of the agreed plan and its base; binding
    them to an on-disk plan file is the environment job's responsibility in
    AO-MA-11A-2.
    """

    bundle_path = bundle_path.resolve()
    bundle = _load_json(bundle_path)
    _validate_schema(bundle, _CONSENSUS_BUNDLE_SCHEMA_NAME, bundle_path)

    computed, rounds_used, round_budget = _check_bundle_invariants(bundle, bundle_path.name)

    latest = _latest_verdict_by_provider(bundle["provider_verdicts"])
    diagnostics = [f"{provider}: latest={latest.get(provider, 'MISSING')}" for provider in sorted(_REQUIRED_PROVIDERS)]

    return ConsensusDecision(
        unanimous_status=computed,
        can_request_approval=computed == "AGREE",
        rounds_used=rounds_used,
        round_budget=round_budget,
        diagnostics=diagnostics,
    )


def _check_approval_bindings(
    approval: dict[str, Any],
    bundle: dict[str, Any],
    bundle_sha: str,
    approval_request_sha: str,
) -> None:
    """Bind an approval to its consensus bundle and request (defensive depth).

    All checks fail closed: consensus_id match, exact bundle-bytes SHA, exact
    approval-request-bytes SHA, plan_digest match, no admin/bypass, and guard
    flags literal False. Callable directly so the back-stops are covered even
    if the schema regresses.
    """

    if approval["consensus_id"] != bundle["consensus_id"]:
        raise PlanConsensusError(
            f"approval consensus_id {approval['consensus_id']!r} != "
            f"bundle consensus_id {bundle['consensus_id']!r}; unbound approval"
        )
    if approval["consensus_bundle_sha256"] != bundle_sha:
        raise PlanConsensusError(
            f"approval consensus_bundle_sha256 {approval['consensus_bundle_sha256']!r} != "
            f"sha256_of(bundle) {bundle_sha!r}; bundle modified after approval"
        )
    if approval["approval_request_sha256"] != approval_request_sha:
        raise PlanConsensusError(
            f"approval approval_request_sha256 {approval['approval_request_sha256']!r} != "
            f"sha256_of(approval_request) {approval_request_sha!r}; approval not bound to the presented request"
        )
    if approval["plan_digest"] != bundle["plan_digest"]:
        raise PlanConsensusError(
            f"approval plan_digest {approval['plan_digest']!r} != "
            f"bundle plan_digest {bundle['plan_digest']!r}; plan drift between consensus and approval"
        )
    if approval["bypass_detected"] is not False:
        raise PlanConsensusError("approval bypass_detected must be False; admin/bypass approval is not valid")
    approval_guard = approval["guard_flags"]
    for flag in _GUARD_FLAGS:
        if approval_guard.get(flag) is not False:
            raise PlanConsensusError(f"approval guard_flags.{flag} must be literal False")


def validate_approval(approval_path: Path, bundle_path: Path, approval_request_path: Path) -> ApprovalDecision:
    """Validate an operator approval against the consensus bundle it gates.

    Trust boundary (all fail-closed via ``PlanConsensusError``):
    1. approval schema-valid + bundle schema-valid + bundle recomputes AGREE
    2. approval.consensus_id == bundle.consensus_id
    3. approval.consensus_bundle_sha256 == sha256_of(bundle_path)
    4. approval.approval_request_sha256 == sha256_of(approval_request_path)
    5. approval.plan_digest == bundle.plan_digest
    6. approval.bypass_detected is False + guard_flags all literal False

    ``approval_request_path`` is the exact request payload presented to the
    operator at the gate; the approval is bound to its bytes (triple SHA-bind
    with the bundle and plan_digest). The operator's ``decision``
    (approved/rejected/expired) is a normal outcome and is returned, not
    raised. ``proceed`` is True only for a well-bound ``approved`` decision
    over a unanimous-AGREE bundle.
    """

    approval_path = approval_path.resolve()
    bundle_path = bundle_path.resolve()
    approval_request_path = approval_request_path.resolve()
    approval = _load_json(approval_path)
    _validate_schema(approval, _PLAN_APPROVAL_SCHEMA_NAME, approval_path)

    consensus = validate_consensus_bundle(bundle_path)
    if consensus.unanimous_status != "AGREE":
        raise PlanConsensusError(
            "approval bound to a non-AGREE consensus bundle; an approval may only exist for unanimous_status == 'AGREE'"
        )

    bundle = _load_json(bundle_path)
    _check_approval_bindings(approval, bundle, sha256_of(bundle_path), sha256_of(approval_request_path))

    decision = cast(Literal["approved", "rejected", "expired"], approval["decision"])
    proceed = decision == "approved"
    diagnostics = [f"decision={decision}", f"approved_by={approval['approved_by']}"]
    return ApprovalDecision(decision=decision, proceed=proceed, diagnostics=diagnostics)


def gate_status(
    bundle_path: Path,
    approval_path: Path | None = None,
    approval_request_path: Path | None = None,
) -> GateDecision:
    """Derive the single-gate state from a bundle and an optional approval.

    - consensus NOT_AGREE → ``consensus_not_reached`` (approval not requestable)
    - AGREE, no approval → ``awaiting_operator_approval``
    - AGREE, approval approved → ``approved_autonomous_run_may_start``
    - AGREE, approval rejected/expired → ``halted_operator_rejected``

    When ``approval_path`` is given, ``approval_request_path`` is required so
    the approval can be bound to the exact presented request.
    """

    consensus = validate_consensus_bundle(bundle_path)
    if consensus.unanimous_status != "AGREE":
        return GateDecision(
            state="consensus_not_reached",
            proceed=False,
            unanimous_status=consensus.unanimous_status,
            diagnostics=consensus.diagnostics,
        )

    if approval_path is None:
        return GateDecision(
            state="awaiting_operator_approval",
            proceed=False,
            unanimous_status="AGREE",
            diagnostics=consensus.diagnostics,
        )

    if approval_request_path is None:
        raise PlanConsensusError(
            "approval_request_path is required to validate an approval; the gate must bind to the presented request"
        )

    approval = validate_approval(approval_path, bundle_path, approval_request_path)
    state: GateState = "approved_autonomous_run_may_start" if approval.proceed else "halted_operator_rejected"
    return GateDecision(
        state=state,
        proceed=approval.proceed,
        unanimous_status="AGREE",
        diagnostics=consensus.diagnostics + approval.diagnostics,
    )
