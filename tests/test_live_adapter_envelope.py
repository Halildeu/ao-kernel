"""V5 Epic 2 E-2-1 invariants: live adapter envelope schema.

Infrastructure-only governance envelope for a single (would-be) LLM call.
The schema is fail-closed and pins the guard flag:
  - mode is exactly {stub, dry_run}; 'live' is forbidden (Epic 9 v2 schema only)
  - live_adapter_execution is const false (recompute-not-trust, ADR-0002)
  - strict closure (additionalProperties:false + unevaluatedProperties:false)
  - cost is decimal-string (8 dp), never float (precision drift)
  - conditional invariants: mode<->status coupling; CLOSED breaker => 0 failures
  - secret_boundary affirms no secret material is captured

Machine-enforced invariants (not narrative): every claim below is checked by
constructing a payload and asserting the validator's accept/reject decision.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_NAME = "live_adapter_envelope.schema.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / _SCHEMA_NAME


def _schema() -> dict[str, Any]:
    return load_default("schemas", _SCHEMA_NAME)


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def _is_valid(payload: dict[str, Any]) -> bool:
    return not list(_validator().iter_errors(payload))


def _valid_envelope() -> dict[str, Any]:
    """A minimal-but-complete envelope that MUST validate."""
    return {
        "schema_version": "live-adapter-envelope.v1",
        "artifact_kind": "live_adapter_envelope",
        "envelope_digest": "e" * 64,
        "mode": "dry_run",
        "live_adapter_execution": False,
        "request": {
            "provider_id": "openai",
            "model": "gpt-4o-mini",
            "request_id": "0a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9",
            "intent": "FAST_TEXT",
            "messages_digest": "a" * 64,
            "params": {"temperature": 0.0, "max_tokens": 256},
        },
        "response": {
            "text_digest": "b" * 64,
            "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
            "latency_ms": 0.0,
            "status": "dry_run_emitted",
        },
        "cost": {
            "currency": "USD",
            "input_cost_per_1k_usd": "0.00015000",
            "output_cost_per_1k_usd": "0.00060000",
            "actual_cost_usd": "0.00000660",
            "pricing_source_digest": "sha256:" + ("c" * 64),
        },
        "circuit_breaker": {"state": "CLOSED", "failure_count": 0, "last_failure_at": None},
        "secret_boundary": "no_secret_material_emitted_no_token_no_credential",
        "timestamps": {
            "created_at": "2026-06-04T10:00:00Z",
            "finalized_at": "2026-06-04T10:00:01Z",
        },
    }


# ---- 1. schema health (2) ----------------------------------------------


def test_schema_present_and_valid_draft_2020_12() -> None:
    assert _SCHEMA_PATH.is_file(), f"{_SCHEMA_NAME} missing (E-2-1)"
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_valid_envelope_validates() -> None:
    assert _is_valid(_valid_envelope()), "the reference envelope must validate"


# ---- 2. guard-flag pin (3) ---------------------------------------------


def test_live_adapter_execution_pinned_false() -> None:
    payload = _valid_envelope()
    payload["live_adapter_execution"] = True
    assert not _is_valid(payload), "live_adapter_execution=true must be rejected (guard pin)"


def test_optional_guard_flags_must_be_false_if_present() -> None:
    for flag in ("support_widening", "production_platform_claim"):
        payload = _valid_envelope()
        payload[flag] = True
        assert not _is_valid(payload), f"{flag}=true must be rejected"
        ok = _valid_envelope()
        ok[flag] = False
        assert _is_valid(ok), f"{flag}=false must be accepted"


def test_mode_live_is_forbidden() -> None:
    payload = _valid_envelope()
    payload["mode"] = "live"
    assert not _is_valid(payload), "mode='live' must be rejected (Epic 9 v2 schema only)"


# ---- 3. strict closure + required scope (2) ----------------------------


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("request",),
        ("request", "params"),
        ("response",),
        ("response", "usage"),
        ("cost",),
        ("circuit_breaker",),
        ("timestamps",),
    ],
)
def test_additional_properties_rejected_at_every_object(path: tuple[str, ...]) -> None:
    """Strict closure must hold at EVERY object, not just the top level —
    a stray field anywhere (including objects touched by allOf conditionals
    like 'response' and 'circuit_breaker') must be rejected."""
    payload = _valid_envelope()
    target: Any = payload
    for key in path:
        target = target[key]
    target["unexpected_field"] = "x"
    location = "top-level" if not path else ".".join(path)
    assert not _is_valid(payload), f"additionalProperties at {location} must be rejected"


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "artifact_kind",
        "envelope_digest",
        "mode",
        "live_adapter_execution",
        "request",
        "response",
        "cost",
        "circuit_breaker",
        "secret_boundary",
        "timestamps",
    ],
)
def test_each_required_top_level_field_is_enforced(field: str) -> None:
    payload = _valid_envelope()
    del payload[field]
    assert not _is_valid(payload), f"removing required '{field}' must fail validation"


# ---- 4. const + enum pins (3) ------------------------------------------


def test_const_pins_reject_wrong_values() -> None:
    for field, bad in (
        ("schema_version", "live-adapter-envelope.v2"),
        ("artifact_kind", "something_else"),
        ("secret_boundary", "leaked"),
    ):
        payload = _valid_envelope()
        payload[field] = bad
        assert not _is_valid(payload), f"{field} const pin must reject '{bad}'"


def test_mode_enum_is_exactly_stub_and_dry_run() -> None:
    schema = _schema()
    assert set(schema["properties"]["mode"]["enum"]) == {"stub", "dry_run"}


def test_response_status_enum_complete() -> None:
    schema = _schema()
    statuses = set(schema["properties"]["response"]["properties"]["status"]["enum"])
    assert statuses == {"ok", "stub_emitted", "dry_run_emitted", "error"}


# ---- 5. conditional invariants (allOf) (3) -----------------------------


def test_stub_mode_requires_stub_emitted_status() -> None:
    payload = _valid_envelope()
    payload["mode"] = "stub"
    payload["response"]["status"] = "ok"  # mismatched
    assert not _is_valid(payload), "mode=stub with status=ok must be rejected"
    payload["response"]["status"] = "stub_emitted"
    assert _is_valid(payload), "mode=stub with status=stub_emitted must validate"


def test_dry_run_mode_requires_dry_run_emitted_status() -> None:
    payload = _valid_envelope()
    payload["mode"] = "dry_run"
    payload["response"]["status"] = "stub_emitted"  # mismatched
    assert not _is_valid(payload), "mode=dry_run with status=stub_emitted must be rejected"


def test_closed_breaker_requires_zero_failures() -> None:
    payload = _valid_envelope()
    payload["circuit_breaker"]["state"] = "CLOSED"
    payload["circuit_breaker"]["failure_count"] = 3
    assert not _is_valid(payload), "CLOSED breaker with failure_count>0 must be rejected"
    # OPEN breaker may carry failures
    open_payload = _valid_envelope()
    open_payload["circuit_breaker"]["state"] = "OPEN"
    open_payload["circuit_breaker"]["failure_count"] = 3
    open_payload["circuit_breaker"]["last_failure_at"] = "2026-06-04T09:59:00Z"
    assert _is_valid(open_payload), "OPEN breaker with failures must validate"


# ---- 6. cost + digest precision (2) ------------------------------------


def test_cost_must_be_decimal_string_8dp_not_float() -> None:
    payload = _valid_envelope()
    payload["cost"]["actual_cost_usd"] = 0.0000066  # float, not allowed
    assert not _is_valid(payload), "float cost must be rejected (precision drift)"
    payload2 = _valid_envelope()
    payload2["cost"]["actual_cost_usd"] = "0.01"  # wrong precision
    assert not _is_valid(payload2), "2dp cost must be rejected; 8dp required"


def test_digest_patterns_enforced() -> None:
    payload = _valid_envelope()
    payload["request"]["messages_digest"] = "not-a-sha"
    assert not _is_valid(payload), "non-sha256 messages_digest must be rejected"
    payload2 = _valid_envelope()
    payload2["cost"]["pricing_source_digest"] = "d" * 64  # missing sha256: prefix
    assert not _is_valid(payload2), "pricing_source_digest must carry sha256: prefix"


def test_envelope_digest_is_bare_sha256() -> None:
    payload = _valid_envelope()
    payload["envelope_digest"] = "sha256:" + ("e" * 64)  # bare hex required, no prefix
    assert not _is_valid(payload), "envelope_digest must be bare 64-hex (no sha256: prefix)"
    payload2 = _valid_envelope()
    payload2["envelope_digest"] = "xyz"
    assert not _is_valid(payload2), "malformed envelope_digest must be rejected"


# ---- 7. timestamp fail-closed (RFC3339 regex, not format-only) (1) ------


def test_timestamps_are_fail_closed_via_regex() -> None:
    """jsonschema does not enforce `format: date-time` by default, so the
    schema carries an explicit RFC3339 `pattern`. A non-date string must be
    rejected at every timestamp field (Codex E-2-1 review absorb)."""
    # created_at + finalized_at: free-text AND range-invalid (e.g. month 99) must fail
    for field in ("created_at", "finalized_at"):
        for bad in ("not-a-date", "2026-99-99T99:99:99+99:99"):
            payload = _valid_envelope()
            payload["timestamps"][field] = bad
            assert not _is_valid(payload), f"timestamps.{field} must reject {bad!r} (range-aware RFC3339)"
    # last_failure_at string branch (null is still allowed)
    for bad in ("also-not-a-date", "2026-13-40T25:61:61Z"):
        cb = _valid_envelope()
        cb["circuit_breaker"]["state"] = "OPEN"
        cb["circuit_breaker"]["failure_count"] = 1
        cb["circuit_breaker"]["last_failure_at"] = bad
        assert not _is_valid(cb), f"circuit_breaker.last_failure_at must reject {bad!r}"
    # null remains valid
    ok = _valid_envelope()
    ok["circuit_breaker"]["last_failure_at"] = None
    assert _is_valid(ok), "last_failure_at=null must remain valid"


# ---- 8. governance: no workflow mutation (1) ---------------------------


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_live_adapter_envelope.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-2-1 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-2-1 must not touch .github/workflows/. Touched: {touched}"
