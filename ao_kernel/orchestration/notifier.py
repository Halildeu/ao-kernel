"""AO-MA-11H notifier: pure notification-intent decision core.

The autonomous run governor (AO-MA-11I) emits ``escalation_required`` /
``safe_stop_required`` on a ``GovernorDecision``; the master plan's Phase 4
(AO-MA-11H) turns governance *events* into *notification intents* that an
external side-effect executor (AO-MA-11H-2: Mavis CLI chat + ``gh``
GitHub-native) delivers, recording a receipt that the governor feedback slice
(AO-MA-11H-3) consumes (``blocked_notification_failed`` -> safe-stop).

This module is the AO-MA-11H-1 *pure* core. Like ``run_governor.decide`` it
performs NO I/O, NO subprocess, NO network, NO LLM, NO GitHub write: it maps a
governance event to a schema-valid notification intent (severity, channels,
audience, redacted summary, delivery-success condition, dedupe key). The side
effect lives in the executor, not here:

  delivery_authority = "external_executor_only"
  intent_authority   = "notification_decision_only"

Fail-closed: a malformed or unknown event becomes a *critical, sanitized*
notify (never a silent suppress). Secret material is machine-redacted from
every free-text field before the intent is built, and ``no_secret_payload`` is
asserted only after that redaction actually verifies clean.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

Severity = Literal["info", "high", "critical"]
Action = Literal["notify", "suppress"]
Channel = Literal["mavis_chat", "github_native"]
Audience = Literal["operator", "peer_agents"]
DeliveryCondition = Literal[
    "none",
    "at_least_one_required_channel_delivered",
    "all_required_channels_delivered",
]

SCHEMA_VERSION = "ao-ma-notification-intent.v1"
ARTIFACT_KIND = "ao_ma_notification_intent"

# Sanitized constants for the fail-closed paths. Raw event content is never
# echoed for malformed/unknown events; only these fixed strings + diagnostic
# codes reach the operator-facing intent.
_MALFORMED_EVENT_KIND = "malformed_event"
_UNKNOWN_EVENT_PREFIX = "unknown_event"
_MALFORMED_SUMMARY = "Malformed notification event; operator review required"
_REDACTION_PLACEHOLDER = "[REDACTED]"

# Length caps that mirror the bundled intent schema's maxLength constraints, so
# a clean-but-oversized event_kind / slice_id / source_ref can never produce a
# schema-INVALID intent (fail-closed must stay schema-valid). Kept strictly
# below the schema bounds (event_kind<=200, dedupe_key<=400).
_MAX_EVENT_KIND = 200
_MAX_DEDUPE_FIELD = 120
_MAX_DEDUPE_KEY = 400


class NotifierError(ValueError):
    """Raised only by helpers that validate developer-supplied arguments.

    ``decide_notification`` itself never raises on event content (fail-closed:
    bad events become critical sanitized notifications); this exception is for
    contract misuse such as a non-string ``evaluated_at``.
    """


# ---------------------------------------------------------------------------
# Severity matrix — the single source of truth for event -> severity
# ---------------------------------------------------------------------------
# Keys are governor halt_reason codes (the exact 12 from
# run_governor.HaltReason, no abbreviation) plus program-lifecycle event kinds.
# requires_delivery_confirmation is *derived* from severity (critical => True)
# and cross-checked in tests, so the matrix stays a pure severity map.
_SEVERITY_MATRIX: dict[str, Severity] = {
    # --- governor halt_reasons (12, exact) ---
    "operator_pause_flag": "high",
    "wall_clock_exceeded": "high",
    "max_slices_exceeded": "high",
    "max_consensus_rounds_exceeded": "high",
    "max_retries_exceeded": "high",
    "max_total_retries_exceeded": "high",
    "max_governor_steps_exceeded": "high",
    "max_total_output_tokens_exceeded": "high",
    "clock_anomaly_negative_elapsed": "critical",
    "usage_axis_missing": "critical",
    "config_invalid": "critical",
    "state_invalid": "critical",
    # --- program lifecycle events ---
    "approval_required": "critical",
    "consensus_required": "high",
    "consensus_round_budget_exhausted": "critical",
    "drift_detected": "critical",
    "mirror_drift_detected": "high",
    "slice_closeout": "info",
}

# Events that explicitly warrant NO operator notification (best-effort, pure
# no-op). Suppression is explicit (listed here), never the fallback for an
# unrecognized event.
_SUPPRESS_EVENTS: frozenset[str] = frozenset({"governor_continue", "run_heartbeat", "no_op"})

# Channel / audience projections from severity. critical+high reach both
# channels and both audiences; info is a quiet peer-only chat note.
_CHANNELS_BY_SEVERITY: dict[Severity, tuple[Channel, ...]] = {
    "critical": ("mavis_chat", "github_native"),
    "high": ("mavis_chat", "github_native"),
    "info": ("mavis_chat",),
}
_AUDIENCE_BY_SEVERITY: dict[Severity, tuple[Audience, ...]] = {
    "critical": ("operator", "peer_agents"),
    "high": ("operator", "peer_agents"),
    "info": ("peer_agents",),
}


def _delivery_condition(severity: Severity) -> DeliveryCondition:
    """critical => at_least_one (operator must actually be reached); else none."""

    return "at_least_one_required_channel_delivered" if severity == "critical" else "none"


def _requires_confirmation(severity: Severity) -> bool:
    """Derive delivery-confirmation requirement from severity (critical only)."""

    return severity == "critical"


# ---------------------------------------------------------------------------
# Secret redaction — machine guard, not self-attestation
# ---------------------------------------------------------------------------
# A conservative denylist of high-signal secret shapes. The point is not to be
# a complete secret scanner but to *guarantee* no obvious credential, token,
# webhook URL, bearer header, or email/PII pattern survives into an intent's
# free-text fields. ``no_secret_payload`` is only set True after _is_clean()
# confirms a redacted string carries none of these.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"gh[pos]_[A-Za-z0-9]{16,}"),  # GitHub PAT/oauth/server
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),  # GitHub fine-grained PAT
    re.compile(r"sk-ant-[A-Za-z0-9_-]{12,}"),  # Anthropic key
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),  # OpenAI key (incl. sk-proj-)
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack token
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),  # JWT
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),  # bearer header
    re.compile(r"https://hooks\.[A-Za-z0-9.-]+/\S+"),  # generic webhook
    re.compile(r"https://discord(?:app)?\.com/api/webhooks/\S+"),  # discord webhook
    re.compile(r"https://[A-Za-z0-9.-]*slack\.com/\S*"),  # slack webhook/url
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email / PII
)


def _redact(text: str) -> str:
    """Replace every denylisted secret shape with a fixed placeholder."""

    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(_REDACTION_PLACEHOLDER, redacted)
    return redacted


def _is_clean(text: str) -> bool:
    """True iff ``text`` carries none of the denylisted secret shapes."""

    return not any(pattern.search(text) for pattern in _SECRET_PATTERNS)


# ---------------------------------------------------------------------------
# Evidence ref validation (structured: sha256 digest or safe repo-relative path)
# ---------------------------------------------------------------------------
# sha256:<64hex>  OR  a repo-relative path whose every segment starts with an
# alphanumeric/underscore (so "..", "./", absolute "/x", URLs, query strings,
# and env-var names are all rejected — no path traversal, no external refs).
_EVIDENCE_RE = re.compile(
    r"^(sha256:[0-9a-f]{64})$"
    r"|^([A-Za-z0-9_][A-Za-z0-9._-]*(/[A-Za-z0-9_][A-Za-z0-9._-]*)*)$"
)


def _valid_evidence_ref(ref: object) -> bool:
    return isinstance(ref, str) and _EVIDENCE_RE.match(ref) is not None


# ---------------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NotificationDecision:
    """Pure notification-routing decision (no delivery, no I/O).

    ``action`` is "notify" or "suppress". For "suppress" the channel/audience
    lists are empty, confirmation is False, and ``delivery_success_condition``
    is None (the schema's if/then mirrors this).
    """

    action: Action
    event_kind: str
    severity: Severity
    channels: tuple[Channel, ...]
    audience: tuple[Audience, ...]
    redacted_summary: str
    evidence_refs: tuple[str, ...]
    requires_delivery_confirmation: bool
    delivery_success_condition: DeliveryCondition | None
    dedupe_key: str
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Pure decision
# ---------------------------------------------------------------------------
def decide_notification(event: Mapping[str, Any]) -> NotificationDecision:
    """Map a governance event to a notification decision (pure, no I/O).

    Order (fail-closed):
    1. event not a mapping / event_kind not a non-empty str -> malformed
       (critical, sanitized; raw content never echoed).
    2. event_kind in _SUPPRESS_EVENTS -> suppress (explicit no-op).
    3. severity key (halt_reason if present else event_kind) in matrix
       -> notify at that severity.
    4. otherwise -> unknown event -> critical, sanitized notify
       (never a silent suppress).

    The input mapping is never mutated.
    """

    # 1. Malformed structure.
    if not isinstance(event, Mapping):
        return _malformed_decision("event_not_a_mapping")
    raw_kind = event.get("event_kind")
    if not isinstance(raw_kind, str) or not raw_kind.strip():
        return _malformed_decision("event_kind_missing_or_blank")

    # ``lookup_kind`` is the stripped raw value used ONLY for matrix/suppress
    # lookups against known-safe constants; it is never stored. ``event_kind``
    # is the redacted form that flows into the dedupe key and the artifact, so a
    # secret-shaped event_kind can never leak through the matrix-miss echo path.
    lookup_kind = raw_kind.strip()
    event_kind = _redact(lookup_kind)[:_MAX_EVENT_KIND]
    kind_had_secret = event_kind != lookup_kind[:_MAX_EVENT_KIND]
    slice_id = _safe_str(event.get("slice_id"))[:_MAX_DEDUPE_FIELD]
    source_ref = _safe_str(event.get("source_ref"))[:_MAX_DEDUPE_FIELD]
    dedupe_key = _dedupe_key(event_kind[:_MAX_DEDUPE_FIELD], slice_id, source_ref)

    # 2. Explicit suppression.
    if lookup_kind in _SUPPRESS_EVENTS:
        return NotificationDecision(
            action="suppress",
            event_kind=event_kind,
            severity="info",
            channels=(),
            audience=(),
            redacted_summary="event suppressed; no operator notification required",
            evidence_refs=(),
            requires_delivery_confirmation=False,
            delivery_success_condition=None,
            dedupe_key=dedupe_key,
            diagnostics=("suppressed_event",),
        )

    # 3 / 4. Severity lookup (halt_reason wins when present), unknown -> critical.
    # Lookup uses the stripped raw halt_reason / event_kind against known-safe
    # matrix keys; a secret never matches, so it falls through to the critical
    # unknown path with a redacted event_kind.
    halt_reason = event.get("halt_reason")
    lookup_severity_key = halt_reason.strip() if isinstance(halt_reason, str) and halt_reason.strip() else lookup_kind
    severity = _SEVERITY_MATRIX.get(lookup_severity_key)
    diagnostics: list[str] = []
    if kind_had_secret:
        diagnostics.append("event_kind_redacted")
    if severity is None:
        severity = "critical"
        diagnostics.append("unknown_event_critical_fallback")
        # event_kind is already redacted; if it carried a secret it collapses to
        # the bare prefix so nothing secret-shaped survives even as a fragment.
        suffix = "" if kind_had_secret else f":{event_kind}"
        event_kind = f"{_UNKNOWN_EVENT_PREFIX}{suffix}"[:_MAX_EVENT_KIND]

    evidence_refs, dropped = _collect_evidence_refs(event)
    if dropped:
        diagnostics.append("invalid_evidence_ref_dropped")

    summary = _build_summary(event, severity, event_kind)

    return NotificationDecision(
        action="notify",
        event_kind=event_kind,
        severity=severity,
        channels=_CHANNELS_BY_SEVERITY[severity],
        audience=_AUDIENCE_BY_SEVERITY[severity],
        redacted_summary=summary,
        evidence_refs=evidence_refs,
        requires_delivery_confirmation=_requires_confirmation(severity),
        delivery_success_condition=_delivery_condition(severity),
        dedupe_key=dedupe_key,
        diagnostics=tuple(diagnostics),
    )


def _malformed_decision(code: str) -> NotificationDecision:
    """Critical, fully sanitized decision for malformed events (no raw echo)."""

    return NotificationDecision(
        action="notify",
        event_kind=_MALFORMED_EVENT_KIND,
        severity="critical",
        channels=_CHANNELS_BY_SEVERITY["critical"],
        audience=_AUDIENCE_BY_SEVERITY["critical"],
        redacted_summary=_MALFORMED_SUMMARY,
        evidence_refs=(),
        requires_delivery_confirmation=True,
        delivery_success_condition="at_least_one_required_channel_delivered",
        dedupe_key=_dedupe_key(_MALFORMED_EVENT_KIND, "", ""),
        diagnostics=("event_schema_invalid", code),
    )


def _safe_str(value: object) -> str:
    """Return a redacted string for str inputs, else empty (no raw coercion)."""

    if isinstance(value, str):
        return _redact(value).strip()
    return ""


def _dedupe_key(event_kind: str, slice_id: str, source_ref: str) -> str:
    """Deterministic dedupe key from stable, secret-free fields (no time/random)."""

    return "|".join((event_kind or "-", slice_id or "-", source_ref or "-"))[:_MAX_DEDUPE_KEY]


def _collect_evidence_refs(event: Mapping[str, Any]) -> tuple[tuple[str, ...], bool]:
    """Keep only refs that are BOTH structurally valid AND secret-clean.

    A single-segment ref such as ``ghp_AAAA...`` or ``sk-proj-...`` satisfies the
    repo-relative-path shape (no slash required), so structural validity alone is
    not enough: a secret-shaped ref would otherwise enter the intent verbatim
    with ``no_secret_payload=true``. We therefore require ``_is_clean`` too, and
    a ref failing EITHER check is dropped (reported so the caller can diagnose).
    """

    raw = event.get("evidence_refs")
    if not isinstance(raw, (list, tuple)):
        return (), False
    kept: list[str] = []
    dropped = False
    for ref in raw:
        if not _valid_evidence_ref(ref) or not _is_clean(ref):
            dropped = True  # structurally-invalid OR secret-shaped refs are dropped
        elif ref not in kept:
            kept.append(ref)  # safe chars (regex) AND secret-clean (denylist)
        # a duplicate of an already-kept valid ref is silently collapsed
    return tuple(kept), dropped


def _build_summary(event: Mapping[str, Any], severity: Severity, event_kind: str) -> str:
    """Build a redacted, machine-clean operator summary.

    Uses the event's own ``summary`` when present (redacted); otherwise a
    synthesized line. The result is re-redacted defensively; if it still is not
    clean it falls back to a fixed safe string so the intent can never carry a
    secret.
    """

    provided = event.get("summary")
    if isinstance(provided, str) and provided.strip():
        candidate = provided
    else:
        candidate = f"{severity} governance notification for {event_kind}"
    # Redact UNCONDITIONALLY: this covers both a caller-provided summary and the
    # synthesized line (which interpolates event_kind). Even if event_kind ever
    # reached here unredacted, no secret-shaped value can survive this point.
    candidate = _redact(candidate).strip()[:2000]
    if not candidate or not _is_clean(candidate):
        return f"{severity} governance notification (summary redacted)"
    return candidate


# ---------------------------------------------------------------------------
# Artifact rendering (schema-shaped dict; validation lives in tests)
# ---------------------------------------------------------------------------
def decision_to_intent_artifact(decision: NotificationDecision, *, evaluated_at: str) -> dict[str, Any]:
    """Render a NotificationDecision as an ao-ma-notification-intent.v1 dict.

    ``evaluated_at`` is carried verbatim (no wall-clock behaviour in this
    module; parity with run_governor.decision_to_artifact). Raises NotifierError
    only on contract misuse (non-string evaluated_at). The returned dict is
    shaped to satisfy the bundled schema; the secret guard asserts cleanliness
    of every free-text field before ``no_secret_payload`` is set True.
    """

    if not isinstance(evaluated_at, str) or not evaluated_at.strip():
        raise NotifierError("evaluated_at must be a non-empty string")
    # evaluated_at is a timestamp, never free text: reject any secret-shaped
    # content outright so it cannot ride into the artifact past the guard below.
    if not _is_clean(evaluated_at):
        raise NotifierError("evaluated_at must not contain secret-shaped content")

    # Machine guard: confirm EVERY free-text field that reaches the artifact is
    # clean before attesting no_secret_payload. event_kind is included because a
    # hand-constructed decision (bypassing decide_notification) could still carry
    # a secret there; decide_notification already redacts it on the normal path.
    free_text = [decision.redacted_summary, decision.dedupe_key, decision.event_kind, *decision.diagnostics]
    clean = all(_is_clean(text) for text in free_text) and all(
        _valid_evidence_ref(ref) and _is_clean(ref) for ref in decision.evidence_refs
    )
    if not clean:
        # Fail-closed rebuild: sanitize summary, dedupe key and event_kind;
        # DROP the (possibly dirty) diagnostics entirely and replace with a
        # single marker; drop evidence refs. Nothing dirty survives.
        safe_summary = f"{decision.severity} governance notification (summary redacted)"
        safe_dedupe = _redact(decision.dedupe_key)
        safe_event_kind = _redact(decision.event_kind)
        diagnostics: tuple[str, ...] = ("secret_guard_resanitized",)
        evidence_refs: tuple[str, ...] = ()
    else:
        safe_summary = decision.redacted_summary
        safe_dedupe = decision.dedupe_key
        safe_event_kind = decision.event_kind
        diagnostics = decision.diagnostics
        evidence_refs = decision.evidence_refs

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "event_kind": safe_event_kind,
        "action": decision.action,
        "severity": decision.severity,
        "channels": list(decision.channels),
        "audience": list(decision.audience),
        "redacted_summary": safe_summary,
        "evidence_refs": list(evidence_refs),
        "requires_delivery_confirmation": decision.requires_delivery_confirmation,
        "delivery_success_condition": decision.delivery_success_condition,
        "dedupe_key": safe_dedupe,
        "diagnostics": list(diagnostics),
        "no_secret_payload": True,
        "delivery_authority": "external_executor_only",
        "intent_authority": "notification_decision_only",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "evaluated_at": evaluated_at,
    }
