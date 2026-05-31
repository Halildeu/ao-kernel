"""AO-MA-11H-1 notifier pure-decision core tests.

Covers: schema validity (intent + receipt, Draft 2020-12), artifact
conformance, the full severity matrix (12 governor halt_reasons exact + 6
lifecycle events), suppress/notify/malformed/unknown fail-closed paths,
suppress/high/info/critical schema projection (if/then), the three guard flags
const false, AST import-allowlist (no subprocess/os/socket/network/LLM),
machine-enforced secret/JWT/webhook/email redaction (incl. event_kind, dedupe
key and artifact-level resanitize), evidence-ref rejection, and the receipt
contract (structured intent_ref + delivered/failed/skipped if/then).

Secret fixtures are CONSTRUCTED at runtime via concatenation so no literal
credential shape ever appears in this source file (keeps secret scanners green
while still exercising the redaction patterns on realistic runtime strings).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import ao_kernel
from ao_kernel.orchestration.notifier import (
    _SECRET_PATTERNS,
    _SEVERITY_MATRIX,
    NotificationDecision,
    NotifierError,
    decide_notification,
    decision_to_intent_artifact,
)

_PKG = Path(ao_kernel.__file__).resolve().parent
_SCHEMAS = _PKG / "defaults" / "schemas"
_INTENT_SCHEMA = _SCHEMAS / "ao-ma-notification-intent.schema.v1.json"
_RECEIPT_SCHEMA = _SCHEMAS / "ao-ma-notification-receipt.schema.v1.json"
_MODULE_SRC = _PKG / "orchestration" / "notifier.py"

# Pure module: only these imports are permitted (parity with run_governor's
# AST allowlist test). No subprocess/os/socket/requests/httpx/LLM clients.
_ALLOWED_IMPORTS = {"__future__", "re", "dataclasses", "typing"}

# The exact 12 governor halt_reasons (run_governor.HaltReason), no abbreviation.
_GOVERNOR_HALT_REASONS = (
    "operator_pause_flag",
    "wall_clock_exceeded",
    "max_slices_exceeded",
    "max_consensus_rounds_exceeded",
    "max_retries_exceeded",
    "max_total_retries_exceeded",
    "max_governor_steps_exceeded",
    "max_total_output_tokens_exceeded",
    "clock_anomaly_negative_elapsed",
    "usage_axis_missing",
    "config_invalid",
    "state_invalid",
)

# --- Constructed synthetic secrets (no literal secret shape in source) ---
_GHP = "ghp_" + "A" * 36
_GH_PAT = "github_pat_" + "B" * 30
_SK = "sk-" + "c" * 40
_SK_PROJ = "sk-proj-" + "d" * 40
_SK_ANT = "sk-ant-" + "e" * 30
_XOXB = "xoxb-" + "1" * 12 + "-" + "f" * 12
_JWT = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
_BEARER = "Bearer " + "g" * 24
_WEBHOOK = "https://hooks." + "example.net/abc/def"
_EMAIL = "alice" + "@" + "example.com"

# (constructed secret, a distinctive body fragment that must NOT survive)
_SECRET_CASES = [
    (_GHP, "A" * 36),
    (_GH_PAT, "B" * 30),
    (_SK, "c" * 40),
    (_SK_PROJ, "d" * 40),
    (_SK_ANT, "e" * 30),
    (_XOXB, "f" * 12),
    (_JWT, "a" * 20),
    (_BEARER, "g" * 24),
    (_WEBHOOK, "example.net/abc"),
    (_EMAIL, "alice@example.com"),
]


def _intent_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(_INTENT_SCHEMA.read_text(encoding="utf-8")))


def _receipt_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(_RECEIPT_SCHEMA.read_text(encoding="utf-8")))


def _artifact(event: dict[str, Any]) -> dict[str, Any]:
    return decision_to_intent_artifact(decide_notification(event), evaluated_at="2026-05-31T00:00:00Z")


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------
def test_intent_schema_valid() -> None:
    schema = json.loads(_INTENT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-notification-intent:v1"
    assert schema["additionalProperties"] is False


def test_receipt_schema_valid() -> None:
    schema = json.loads(_RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-notification-receipt:v1"
    assert schema["additionalProperties"] is False


def test_intent_schema_pins_three_guard_flags() -> None:
    schema = json.loads(_INTENT_SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in schema["required"], f"{flag} must be required"
        assert props[flag]["const"] is False, f"{flag} must be const false"


def test_intent_schema_pins_authority_fields() -> None:
    props = json.loads(_INTENT_SCHEMA.read_text(encoding="utf-8"))["properties"]
    assert props["delivery_authority"]["const"] == "external_executor_only"
    assert props["intent_authority"]["const"] == "notification_decision_only"
    assert props["no_secret_payload"]["const"] is True


# ---------------------------------------------------------------------------
# Severity matrix — exact governor halt_reason coverage
# ---------------------------------------------------------------------------
def test_all_twelve_governor_halt_reasons_mapped() -> None:
    for reason in _GOVERNOR_HALT_REASONS:
        assert reason in _SEVERITY_MATRIX, f"halt_reason {reason} missing from severity matrix"


@pytest.mark.parametrize(
    "halt_reason,expected",
    [
        ("operator_pause_flag", "high"),
        ("wall_clock_exceeded", "high"),
        ("max_slices_exceeded", "high"),
        ("max_consensus_rounds_exceeded", "high"),
        ("max_retries_exceeded", "high"),
        ("max_total_retries_exceeded", "high"),
        ("max_governor_steps_exceeded", "high"),
        ("max_total_output_tokens_exceeded", "high"),
        ("clock_anomaly_negative_elapsed", "critical"),
        ("usage_axis_missing", "critical"),
        ("config_invalid", "critical"),
        ("state_invalid", "critical"),
    ],
)
def test_halt_reason_severity(halt_reason: str, expected: str) -> None:
    d = decide_notification({"event_kind": "governor_halt", "halt_reason": halt_reason})
    assert d.action == "notify"
    assert d.severity == expected
    assert d.requires_delivery_confirmation is (expected == "critical")


@pytest.mark.parametrize(
    "event_kind,expected",
    [
        ("approval_required", "critical"),
        ("consensus_required", "high"),
        ("consensus_round_budget_exhausted", "critical"),
        ("drift_detected", "critical"),
        ("mirror_drift_detected", "high"),
        ("slice_closeout", "info"),
    ],
)
def test_lifecycle_event_severity(event_kind: str, expected: str) -> None:
    d = decide_notification({"event_kind": event_kind})
    assert d.action == "notify"
    assert d.severity == expected


def test_halt_reason_wins_over_event_kind() -> None:
    d = decide_notification({"event_kind": "slice_closeout", "halt_reason": "config_invalid"})
    assert d.severity == "critical"


def test_blank_halt_reason_falls_back_to_event_kind() -> None:
    d = decide_notification({"event_kind": "drift_detected", "halt_reason": "   "})
    assert d.severity == "critical"  # from event_kind drift_detected


def test_non_str_halt_reason_falls_back_to_event_kind() -> None:
    d = decide_notification({"event_kind": "slice_closeout", "halt_reason": 5})
    assert d.severity == "info"


# ---------------------------------------------------------------------------
# Channel / audience / delivery condition projections
# ---------------------------------------------------------------------------
def test_critical_reaches_both_channels_and_operator() -> None:
    d = decide_notification({"event_kind": "x", "halt_reason": "config_invalid"})
    assert set(d.channels) == {"mavis_chat", "github_native"}
    assert "operator" in d.audience
    assert d.delivery_success_condition == "at_least_one_required_channel_delivered"


def test_high_reaches_both_channels_no_confirmation() -> None:
    d = decide_notification({"event_kind": "x", "halt_reason": "operator_pause_flag"})
    assert set(d.channels) == {"mavis_chat", "github_native"}
    assert d.requires_delivery_confirmation is False
    assert d.delivery_success_condition == "none"


def test_info_is_quiet_peer_only() -> None:
    d = decide_notification({"event_kind": "slice_closeout"})
    assert d.channels == ("mavis_chat",)
    assert d.audience == ("peer_agents",)
    assert d.requires_delivery_confirmation is False


# ---------------------------------------------------------------------------
# Fail-closed paths
# ---------------------------------------------------------------------------
def test_suppress_event_is_noop() -> None:
    d = decide_notification({"event_kind": "governor_continue"})
    assert d.action == "suppress"
    assert d.channels == ()
    assert d.audience == ()
    assert d.requires_delivery_confirmation is False
    assert d.delivery_success_condition is None


@pytest.mark.parametrize("event", [{"foo": "bar"}, {"event_kind": ""}, {"event_kind": "   "}, {"event_kind": 123}])
def test_malformed_event_is_critical_sanitized(event: dict[str, Any]) -> None:
    d = decide_notification(event)
    assert d.action == "notify"
    assert d.severity == "critical"
    assert d.event_kind == "malformed_event"
    assert d.redacted_summary == "Malformed notification event; operator review required"
    assert "event_schema_invalid" in d.diagnostics
    assert d.evidence_refs == ()


def test_non_mapping_event_is_critical() -> None:
    d = decide_notification([])  # type: ignore[arg-type]
    assert d.severity == "critical"
    assert d.event_kind == "malformed_event"


def test_unknown_event_is_critical_not_silent() -> None:
    d = decide_notification({"event_kind": "totally_new_event"})
    assert d.action == "notify"
    assert d.severity == "critical"
    assert d.event_kind.startswith("unknown_event")
    assert "unknown_event_critical_fallback" in d.diagnostics


# ---------------------------------------------------------------------------
# Artifact conformance
# ---------------------------------------------------------------------------
def test_every_severity_artifact_is_schema_valid() -> None:
    V = _intent_validator()
    events: list[dict[str, Any]] = [{"event_kind": "x", "halt_reason": r} for r in _GOVERNOR_HALT_REASONS]
    events += [
        {"event_kind": k}
        for k in (
            "approval_required",
            "consensus_required",
            "consensus_round_budget_exhausted",
            "drift_detected",
            "mirror_drift_detected",
            "slice_closeout",
            "governor_continue",
            "totally_new_event",
        )
    ]
    events += [{"foo": "bar"}]
    for ev in events:
        art = _artifact(ev)
        errs = list(V.iter_errors(art))
        assert not errs, f"event {ev} -> invalid artifact: {errs[0].message if errs else ''}"


def test_artifact_guard_flags_false() -> None:
    art = _artifact({"event_kind": "drift_detected"})
    assert art["support_widening"] is False
    assert art["production_platform_claim"] is False
    assert art["live_adapter_execution"] is False
    assert art["no_secret_payload"] is True


def test_suppress_artifact_satisfies_if_then() -> None:
    V = _intent_validator()
    art = _artifact({"event_kind": "governor_continue"})
    assert art["action"] == "suppress"
    assert art["channels"] == []
    assert art["delivery_success_condition"] is None
    assert not list(V.iter_errors(art))


def test_evaluated_at_must_be_nonempty() -> None:
    d = decide_notification({"event_kind": "drift_detected"})
    with pytest.raises(NotifierError):
        decision_to_intent_artifact(d, evaluated_at="")
    with pytest.raises(NotifierError):
        decision_to_intent_artifact(d, evaluated_at=123)  # type: ignore[arg-type]


def test_evaluated_at_rejects_secret_content() -> None:
    # A caller must not be able to smuggle a secret through evaluated_at and
    # still get no_secret_payload=true; the guard rejects it outright.
    d = decide_notification({"event_kind": "drift_detected"})
    with pytest.raises(NotifierError):
        decision_to_intent_artifact(d, evaluated_at=f"2026-05-31 {_GHP}")
    with pytest.raises(NotifierError):
        decision_to_intent_artifact(d, evaluated_at=_SK_PROJ)


def test_input_event_not_mutated() -> None:
    event = {"event_kind": "drift_detected", "summary": "hello"}
    snapshot = dict(event)
    decide_notification(event)
    assert event == snapshot


# ---------------------------------------------------------------------------
# Schema projection (if/then) — tamper resistance
# ---------------------------------------------------------------------------
def test_intent_schema_rejects_critical_without_both_channels() -> None:
    art = _artifact({"event_kind": "drift_detected"})
    art["channels"] = ["mavis_chat"]
    assert list(_intent_validator().iter_errors(art))


def test_intent_schema_rejects_high_with_delivery_confirmation() -> None:
    art = _artifact({"event_kind": "mirror_drift_detected"})
    art["requires_delivery_confirmation"] = True
    art["delivery_success_condition"] = "at_least_one_required_channel_delivered"
    assert list(_intent_validator().iter_errors(art))


def test_intent_schema_rejects_info_with_two_channels() -> None:
    art = _artifact({"event_kind": "slice_closeout"})
    art["channels"] = ["mavis_chat", "github_native"]
    assert list(_intent_validator().iter_errors(art))


# ---------------------------------------------------------------------------
# Secret redaction (machine-enforced; negative tests)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("secret,body", _SECRET_CASES)
def test_secret_redacted_from_summary(secret: str, body: str) -> None:
    d = decide_notification({"event_kind": "drift_detected", "summary": f"context {secret} more"})
    assert body not in d.redacted_summary
    # And it must not survive into the rendered artifact either.
    assert body not in json.dumps(_artifact({"event_kind": "drift_detected", "summary": f"x {secret} y"}))


def test_openai_project_key_redacted() -> None:
    d = decide_notification({"event_kind": "drift_detected", "summary": f"leak {_SK_PROJ} end"})
    assert "d" * 40 not in d.redacted_summary
    assert _SK_PROJ not in json.dumps(_artifact({"event_kind": "drift_detected", "summary": _SK_PROJ}))


def test_secret_in_slice_id_redacted_in_dedupe_key() -> None:
    d = decide_notification({"event_kind": "drift_detected", "slice_id": _GHP})
    assert _GHP not in d.dedupe_key
    assert "A" * 36 not in d.dedupe_key


def test_unknown_event_kind_secret_never_echoes_into_artifact() -> None:
    d = decide_notification({"event_kind": _GHP})
    art = decision_to_intent_artifact(d, evaluated_at="2026-05-31T00:00:00Z")
    blob = json.dumps(art)
    assert _GHP not in blob
    assert "A" * 36 not in blob
    assert art["event_kind"] == "unknown_event"
    assert _GHP not in art["dedupe_key"]
    assert art["no_secret_payload"] is True
    assert "event_kind_redacted" in art["diagnostics"]


def test_clean_unknown_event_kind_kept() -> None:
    d = decide_notification({"event_kind": "brand_new_clean_event"})
    assert d.event_kind == "unknown_event:brand_new_clean_event"
    assert "event_kind_redacted" not in d.diagnostics


def test_artifact_resanitize_drops_dirty_diagnostics_and_dedupe() -> None:
    # A hand-built decision (bypassing decide_notification) that still carries a
    # secret in dedupe_key + diagnostics must be fully rebuilt by the artifact
    # guard: secret gone, diagnostics collapsed to the marker, flag still true.
    dirty = NotificationDecision(
        action="notify",
        event_kind="drift_detected",
        severity="critical",
        channels=("mavis_chat", "github_native"),
        audience=("operator", "peer_agents"),
        redacted_summary="clean summary",
        evidence_refs=("docs/evidence/run-1.json",),
        requires_delivery_confirmation=True,
        delivery_success_condition="at_least_one_required_channel_delivered",
        dedupe_key=f"drift_detected|{_GHP}|-",
        diagnostics=(f"diag {_GHP}",),
    )
    art = decision_to_intent_artifact(dirty, evaluated_at="2026-05-31T00:00:00Z")
    blob = json.dumps(art)
    assert _GHP not in blob
    assert "A" * 36 not in blob
    assert art["dedupe_key"] != dirty.dedupe_key
    assert art["diagnostics"] == ["secret_guard_resanitized"]
    assert art["evidence_refs"] == []
    assert art["no_secret_payload"] is True


def test_artifact_resanitize_on_dirty_event_kind() -> None:
    dirty = NotificationDecision(
        action="notify",
        event_kind=f"unknown_event:{_GHP}",
        severity="critical",
        channels=("mavis_chat", "github_native"),
        audience=("operator", "peer_agents"),
        redacted_summary="clean",
        evidence_refs=(),
        requires_delivery_confirmation=True,
        delivery_success_condition="at_least_one_required_channel_delivered",
        dedupe_key="x|-|-",
        diagnostics=(),
    )
    art = decision_to_intent_artifact(dirty, evaluated_at="t")
    assert "A" * 36 not in json.dumps(art)
    assert "secret_guard_resanitized" in art["diagnostics"]


def test_artifact_resanitize_on_bad_evidence_ref() -> None:
    bad = NotificationDecision(
        action="notify",
        event_kind="drift_detected",
        severity="high",
        channels=("mavis_chat", "github_native"),
        audience=("operator", "peer_agents"),
        redacted_summary="clean summary",
        evidence_refs=("../etc/passwd",),
        requires_delivery_confirmation=False,
        delivery_success_condition="none",
        dedupe_key="drift_detected|-|-",
        diagnostics=(),
    )
    art = decision_to_intent_artifact(bad, evaluated_at="t")
    assert art["evidence_refs"] == []
    assert "secret_guard_resanitized" in art["diagnostics"]


def test_clean_decision_artifact_keeps_diagnostics() -> None:
    d = decide_notification({"event_kind": "drift_detected", "evidence_refs": ["../bad"]})
    art = decision_to_intent_artifact(d, evaluated_at="t")
    # invalid_evidence_ref_dropped is a clean diagnostic -> preserved.
    assert "invalid_evidence_ref_dropped" in art["diagnostics"]


# ---------------------------------------------------------------------------
# Summary handling
# ---------------------------------------------------------------------------
def test_whitespace_summary_falls_back_to_synthesized() -> None:
    d = decide_notification({"event_kind": "drift_detected", "summary": "   "})
    assert d.redacted_summary
    assert "drift_detected" in d.redacted_summary


def test_clean_provided_summary_used_verbatim() -> None:
    d = decide_notification({"event_kind": "drift_detected", "summary": "all clear here"})
    assert d.redacted_summary == "all clear here"


def test_absent_summary_synthesized() -> None:
    d = decide_notification({"event_kind": "drift_detected"})
    assert "drift_detected" in d.redacted_summary
    assert "critical" in d.redacted_summary


def test_long_summary_truncated() -> None:
    d = decide_notification({"event_kind": "drift_detected", "summary": "a" * 5000})
    assert len(d.redacted_summary) <= 2000


# ---------------------------------------------------------------------------
# Evidence ref handling
# ---------------------------------------------------------------------------
def test_valid_evidence_refs_kept() -> None:
    refs = ["sha256:" + "a" * 64, "docs/evidence/run-1.json", "ao_kernel/orchestration/notifier.py"]
    d = decide_notification({"event_kind": "drift_detected", "evidence_refs": refs})
    assert set(d.evidence_refs) == set(refs)


@pytest.mark.parametrize(
    "bad",
    [
        "../etc/passwd",
        "/abs/path",
        "https://example.com/x",
        "docs/evidence?x=1",
        "sha256:tooshort",
        "$ENV_VAR",
        "./relative",
    ],
)
def test_invalid_evidence_refs_dropped(bad: str) -> None:
    d = decide_notification({"event_kind": "drift_detected", "evidence_refs": [bad]})
    assert bad not in d.evidence_refs
    assert "invalid_evidence_ref_dropped" in d.diagnostics


def test_evidence_refs_non_list_ignored() -> None:
    d = decide_notification({"event_kind": "drift_detected", "evidence_refs": "not-a-list"})
    assert d.evidence_refs == ()


def test_secret_shaped_evidence_ref_dropped() -> None:
    # A single-segment ref can satisfy the repo-relative-path shape (no slash
    # required), so a secret-shaped ref like a GitHub PAT or an OpenAI key must
    # be dropped by the secret-clean check, not just the structural one.
    for secret_ref in (_GHP, _SK_PROJ, _SK, _JWT):
        d = decide_notification({"event_kind": "drift_detected", "evidence_refs": [secret_ref]})
        assert secret_ref not in d.evidence_refs
        assert "invalid_evidence_ref_dropped" in d.diagnostics
        art = decision_to_intent_artifact(d, evaluated_at="2026-05-31T00:00:00Z")
        assert secret_ref not in json.dumps(art)
        assert art["no_secret_payload"] is True


def test_artifact_guard_resanitizes_secret_evidence_ref_on_handbuilt_decision() -> None:
    # Defense in depth: a hand-built decision (bypassing decide_notification)
    # carrying a secret-shaped but structurally-valid evidence_ref must be
    # rebuilt by the artifact guard (refs dropped, diagnostics collapsed).
    dirty = NotificationDecision(
        action="notify",
        event_kind="drift_detected",
        severity="critical",
        channels=("mavis_chat", "github_native"),
        audience=("operator", "peer_agents"),
        redacted_summary="clean summary",
        evidence_refs=(_GHP,),
        requires_delivery_confirmation=True,
        delivery_success_condition="at_least_one_required_channel_delivered",
        dedupe_key="drift_detected|-|-",
        diagnostics=(),
    )
    art = decision_to_intent_artifact(dirty, evaluated_at="2026-05-31T00:00:00Z")
    assert _GHP not in json.dumps(art)
    assert art["evidence_refs"] == []
    assert "secret_guard_resanitized" in art["diagnostics"]
    assert art["no_secret_payload"] is True


def test_duplicate_valid_evidence_ref_deduped_without_invalid_diagnostic() -> None:
    ref = "sha256:" + "c" * 64
    d = decide_notification({"event_kind": "drift_detected", "evidence_refs": [ref, ref]})
    assert d.evidence_refs == (ref,)
    assert "invalid_evidence_ref_dropped" not in d.diagnostics


# ---------------------------------------------------------------------------
# Dedupe key determinism
# ---------------------------------------------------------------------------
def test_dedupe_key_deterministic() -> None:
    ev = {"event_kind": "drift_detected", "slice_id": "AO-MA-11H-1", "source_ref": "x/y.json"}
    assert decide_notification(ev).dedupe_key == decide_notification(dict(ev)).dedupe_key


def test_non_str_slice_id_yields_placeholder_dedupe() -> None:
    d = decide_notification({"event_kind": "drift_detected", "slice_id": 123, "source_ref": None})
    assert d.dedupe_key == "drift_detected|-|-"


# ---------------------------------------------------------------------------
# Receipt contract (produced by 11H-2; pure schema here)
# ---------------------------------------------------------------------------
def _receipt(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "ao-ma-notification-receipt.v1",
        "artifact_kind": "ao_ma_notification_receipt",
        "intent_ref": {
            "path": "docs/intents/intent-1.json",
            "sha256": "sha256:" + "b" * 64,
            "artifact_kind": "ao_ma_notification_intent",
            "schema_version": "ao-ma-notification-intent.v1",
        },
        "channel": "mavis_chat",
        "delivery_status": "delivered",
        "attempted_at": "2026-05-31T00:00:00Z",
        "failure_code": None,
        "failure_summary_redacted": None,
        "receipt_authority": "delivery_observation_only",
        "delivery_authority": "external_executor_only",
        "no_secret_payload": True,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    base.update(overrides)
    return base


def test_receipt_delivered_valid() -> None:
    assert not list(_receipt_validator().iter_errors(_receipt()))


def test_receipt_failed_requires_failure_fields() -> None:
    V = _receipt_validator()
    ok = _receipt(delivery_status="failed", failure_code="transport_error", failure_summary_redacted="link down")
    assert not list(V.iter_errors(ok))
    bad = _receipt(delivery_status="failed")
    assert list(V.iter_errors(bad))


def test_receipt_delivered_forbids_failure_fields() -> None:
    bad = _receipt(delivery_status="delivered", failure_code="timeout", failure_summary_redacted="x")
    assert list(_receipt_validator().iter_errors(bad))


def test_receipt_skipped_forbids_failure_fields() -> None:
    ok = _receipt(delivery_status="skipped")
    assert not list(_receipt_validator().iter_errors(ok))
    bad = _receipt(delivery_status="skipped", failure_code="unknown", failure_summary_redacted="x")
    assert list(_receipt_validator().iter_errors(bad))


def test_receipt_intent_ref_must_be_structured() -> None:
    bad = _receipt(intent_ref="docs/intents/intent-1.json")
    assert list(_receipt_validator().iter_errors(bad))


def test_receipt_guard_flags_pinned() -> None:
    schema = json.loads(_RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]
    assert props["receipt_authority"]["const"] == "delivery_observation_only"
    assert props["delivery_authority"]["const"] == "external_executor_only"
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert props[flag]["const"] is False


# ---------------------------------------------------------------------------
# Purity: AST import-allowlist + no I/O/network usage
# ---------------------------------------------------------------------------
def test_module_imports_are_allowlisted() -> None:
    tree = ast.parse(_MODULE_SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    forbidden = imported - _ALLOWED_IMPORTS
    assert not forbidden, f"notifier.py imports outside allowlist: {sorted(forbidden)}"


def test_module_has_no_io_or_network_usage() -> None:
    # Check for actual *usage* patterns, not the word appearing in a docstring.
    src = _MODULE_SRC.read_text(encoding="utf-8")
    for pattern in (
        r"\bimport\s+subprocess\b",
        r"\bimport\s+os\b",
        r"\bimport\s+socket\b",
        r"\bsubprocess\.",
        r"\bsocket\.",
        r"\bos\.system\b",
        r"\bPopen\b",
        r"\bopen\(",
        r"\brequests\.",
        r"\bhttpx\.",
        r"\burllib\b",
    ):
        assert not re.search(pattern, src), f"notifier.py must not use {pattern}"


def test_decision_is_frozen_dataclass() -> None:
    d = decide_notification({"event_kind": "drift_detected"})
    assert isinstance(d, NotificationDecision)
    with pytest.raises(Exception):
        d.severity = "info"  # type: ignore[misc]


def test_secret_patterns_nonempty() -> None:
    assert len(_SECRET_PATTERNS) >= 8


# ---------------------------------------------------------------------------
# Direct private-helper branch coverage
# ---------------------------------------------------------------------------
from ao_kernel.orchestration.notifier import (  # noqa: E402
    _build_summary,
    _collect_evidence_refs,
    _delivery_condition,
    _is_clean,
    _malformed_decision,
    _redact,
    _requires_confirmation,
    _safe_str,
    _valid_evidence_ref,
)


def test_redact_no_match_returns_input_unchanged() -> None:
    assert _redact("plain clean text") == "plain clean text"


def test_redact_replaces_match() -> None:
    out = _redact(f"token {_GHP} end")
    assert "A" * 36 not in out
    assert "[REDACTED]" in out


def test_is_clean_true_and_false() -> None:
    assert _is_clean("nothing here") is True
    assert _is_clean(_SK) is False


def test_safe_str_str_and_non_str() -> None:
    assert _safe_str("  hello  ") == "hello"
    assert _safe_str(None) == ""
    assert _safe_str(42) == ""


def test_delivery_condition_branches() -> None:
    assert _delivery_condition("critical") == "at_least_one_required_channel_delivered"
    assert _delivery_condition("high") == "none"
    assert _delivery_condition("info") == "none"


def test_requires_confirmation_branches() -> None:
    assert _requires_confirmation("critical") is True
    assert _requires_confirmation("high") is False
    assert _requires_confirmation("info") is False


def test_valid_evidence_ref_branches() -> None:
    assert _valid_evidence_ref("sha256:" + "a" * 64) is True
    assert _valid_evidence_ref("docs/x/y.json") is True
    assert _valid_evidence_ref("../escape") is False
    assert _valid_evidence_ref(123) is False
    assert _valid_evidence_ref("/abs") is False


def test_collect_evidence_refs_branches() -> None:
    assert _collect_evidence_refs({"evidence_refs": "x"}) == ((), False)
    assert _collect_evidence_refs({}) == ((), False)
    refs, dropped = _collect_evidence_refs({"evidence_refs": ["docs/a.json", "../bad"]})
    assert refs == ("docs/a.json",) and dropped is True
    refs2, dropped2 = _collect_evidence_refs({"evidence_refs": ["docs/a.json", "docs/a.json"]})
    assert refs2 == ("docs/a.json",) and dropped2 is False


def test_build_summary_branches() -> None:
    assert _build_summary({"summary": "clear"}, "high", "drift_detected") == "clear"
    s = _build_summary({}, "critical", "config_invalid")
    assert "config_invalid" in s and "critical" in s
    s2 = _build_summary({"summary": "   "}, "info", "slice_closeout")
    assert "slice_closeout" in s2


def test_malformed_decision_is_fully_sanitized() -> None:
    d = _malformed_decision("some_code")
    assert d.severity == "critical"
    assert d.event_kind == "malformed_event"
    assert "some_code" in d.diagnostics
    assert d.evidence_refs == ()
    assert d.requires_delivery_confirmation is True
