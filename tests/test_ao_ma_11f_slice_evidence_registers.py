"""AO-MA-11F-1 slice evidence registers tests.

Covers: five schemas valid (Draft 2020-12), artifact conformance for all
builders, the test-report all_passed / required_tests_present invariants, the
suggestion-register disposition + rationale + accept-closing + coverage +
explicit-empty-provenance rules, machine redaction of free text, the
update-ledger monotonic-seq rule, the closeout SHA-binding plus the
recompute-not-trust fail-closed checks (green-by-totals, register-closed,
cross-artifact slice_id), the bundle-manifest exact-set semantic binding
(role + kind + schema_version + sha256 + line_count), tamper detection on both
verifiers, the three guard flags const false across every artifact, and the AST
import-allowlist (pure: only hashlib/json/re/dataclasses/typing/__future__).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import ao_kernel
from ao_kernel.orchestration import slice_evidence_registers as ser

_PKG = Path(ao_kernel.__file__).resolve().parent
_SCHEMAS = _PKG / "defaults" / "schemas"
_MODULE_SRC = _PKG / "orchestration" / "slice_evidence_registers.py"

_ALLOWED_IMPORTS = {"__future__", "hashlib", "json", "re", "dataclasses", "typing"}

_SCHEMA_NAMES = [
    "ao-ma-slice-test-report",
    "ao-ma-ai-suggestion-register",
    "ao-ma-slice-update-ledger-line",
    "ao-ma-slice-closeout",
    "ao-ma-slice-evidence-bundle-manifest",
]

_SLICE = "AO-MA-11F-1"
_GHP = "ghp_" + "A" * 36


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((_SCHEMAS / f"{name}.schema.v1.json").read_text(encoding="utf-8")))


def _obj(**over):
    base = {
        "objection_id": "o1",
        "provider": "openai",
        "source_kind": "codex_mcp",
        "source_id": "019e7fce",
        "iteration": 1,
        "objection": "a real objection text",
        "disposition": "accept",
        "applied_ref": "abc1234",
    }
    base.update(over)
    return base


def _good_report(slice_id: str = _SLICE):
    return ser.build_test_report(
        slice_id=slice_id,
        generated_at="t",
        suites=[{"name": "unit", "tests": 10, "failed": 0, "errors": 0, "skipped": 1}],
        coverage_percent=92.5,
    )


def _good_register(slice_id: str = _SLICE):
    return ser.build_suggestion_register(
        slice_id=slice_id, generated_at="t", harvest_mode="provided", objections=[_obj()]
    )


def _good_ledger(slice_id: str = _SLICE):
    return ser.build_update_ledger(
        slice_id=slice_id, lines=[{"seq": 0, "ts": "t0", "event_kind": "impl", "summary": "impl"}]
    )


def _good_closeout(slice_id: str = _SLICE, *, slice_passed: bool = True):
    tr, sr, led = _good_report(slice_id), _good_register(slice_id), _good_ledger(slice_id)
    return (
        ser.build_closeout(
            slice_id=slice_id,
            generated_at="t",
            test_report=tr,
            suggestion_register=sr,
            update_ledger=led,
            consensus_status="agreed",
            slice_passed=slice_passed,
        ),
        tr,
        sr,
        led,
    )


# ---------------------------------------------------------------------------
# Schema validity + guard pins
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", _SCHEMA_NAMES)
def test_schema_is_valid_draft_2020_12(name: str) -> None:
    schema = json.loads((_SCHEMAS / f"{name}.schema.v1.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert schema["$id"].startswith("urn:ao:")


@pytest.mark.parametrize("name", _SCHEMA_NAMES)
def test_schema_pins_three_guard_flags(name: str) -> None:
    schema = json.loads((_SCHEMAS / f"{name}.schema.v1.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in schema["required"], f"{name}: {flag} must be required"
        assert props[flag]["const"] is False, f"{name}: {flag} must be const false"
    assert props["register_authority"]["const"] == "evidence_record_only"
    assert props["github_write_authorized"]["const"] is False


# ---------------------------------------------------------------------------
# Test report
# ---------------------------------------------------------------------------
def test_test_report_all_passed_and_valid() -> None:
    tr = _good_report()
    assert not list(_validator("ao-ma-slice-test-report").iter_errors(tr))
    assert tr["all_passed"] is True
    assert tr["required_tests_present"] is True
    assert tr["totals"]["passed"] == 9


def test_test_report_with_failures_not_all_passed() -> None:
    tr = ser.build_test_report(slice_id="x", generated_at="t", suites=[{"name": "u", "tests": 5, "failed": 2}])
    assert tr["all_passed"] is False
    assert not list(_validator("ao-ma-slice-test-report").iter_errors(tr))


def test_all_skipped_is_not_a_pass() -> None:
    tr = ser.build_test_report(
        slice_id="x", generated_at="t", suites=[{"name": "u", "tests": 3, "failed": 0, "errors": 0, "skipped": 3}]
    )
    assert tr["required_tests_present"] is False
    assert tr["all_passed"] is False


def test_test_report_rejects_inconsistent_totals() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_test_report(slice_id="x", generated_at="t", suites=[{"name": "u", "tests": 1, "failed": 5}])


# ---------------------------------------------------------------------------
# Suggestion register
# ---------------------------------------------------------------------------
def test_suggestion_register_valid() -> None:
    sr = _good_register()
    assert not list(_validator("ao-ma-ai-suggestion-register").iter_errors(sr))
    assert sr["register_status"] == "complete"
    assert sr["expected_objections_count"] == 1
    assert sr["objections"][0]["objection_digest"].startswith("sha256:")


def test_empty_register_requires_explicit_expected_zero() -> None:
    # Implicit empty (no expected count) is rejected.
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(slice_id="x", generated_at="t", harvest_mode="not_applicable", objections=[])
    # Explicit expected=0 is accepted and yields no_objections.
    sr = ser.build_suggestion_register(
        slice_id="x", generated_at="t", harvest_mode="not_applicable", objections=[], expected_objections_count=0
    )
    assert sr["register_status"] == "no_objections"
    assert not list(_validator("ao-ma-ai-suggestion-register").iter_errors(sr))


def test_reject_requires_rationale() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            objections=[_obj(disposition="reject", rationale="   ", applied_ref=None)],
        )


def test_partial_requires_rationale() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            objections=[_obj(disposition="partial", applied_ref=None)],
        )


def test_accept_requires_applied_ref_or_rationale() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            objections=[_obj(disposition="accept", applied_ref=None)],
        )
    sr = ser.build_suggestion_register(
        slice_id="x",
        generated_at="t",
        harvest_mode="provided",
        objections=[_obj(disposition="accept", applied_ref=None, rationale="no-op: already covered")],
    )
    assert sr["objections"][0]["disposition"] == "accept"


def test_coverage_mismatch_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            register_status="complete",
            expected_objections_count=5,
            objections=[_obj()],
        )


def test_duplicate_objection_id_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            objections=[_obj(objection_id="dup"), _obj(objection_id="dup", source_id="other")],
        )


def test_duplicate_objection_identity_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            objections=[_obj(objection_id="a"), _obj(objection_id="b")],
        )


def test_secret_redacted_from_objection_text() -> None:
    sr = ser.build_suggestion_register(
        slice_id="x",
        generated_at="t",
        harvest_mode="provided",
        objections=[_obj(objection=f"leak {_GHP} here", rationale="noop")],
    )
    blob = json.dumps(sr)
    assert "A" * 36 not in blob
    assert sr["no_secret_payload"] is True


def test_invalid_provider_and_source_kind_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x", generated_at="t", harvest_mode="provided", objections=[_obj(provider="google")]
        )
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x", generated_at="t", harvest_mode="provided", objections=[_obj(source_kind="email")]
        )


def test_explicit_no_objections_with_records_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            register_status="no_objections",
            objections=[_obj()],
            expected_objections_count=0,
        )


def test_explicit_complete_without_records_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_suggestion_register(
            slice_id="x",
            generated_at="t",
            harvest_mode="provided",
            register_status="complete",
            objections=[],
            expected_objections_count=0,
        )


# ---------------------------------------------------------------------------
# Update ledger
# ---------------------------------------------------------------------------
def test_ledger_lines_valid_and_monotonic() -> None:
    led = ser.build_update_ledger(
        slice_id="x",
        lines=[
            {"seq": 0, "ts": "t0", "event_kind": "impl", "summary": "a"},
            {"seq": 0, "ts": "t1", "event_kind": "fix", "summary": "b"},
            {"seq": 1, "ts": "t2", "event_kind": "consensus", "summary": "c", "ref_sha": "abc1234"},
        ],
    )
    v = _validator("ao-ma-slice-update-ledger-line")
    assert all(not list(v.iter_errors(line)) for line in led)


def test_ledger_non_monotonic_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_update_ledger(
            slice_id="x",
            lines=[
                {"seq": 5, "ts": "t", "event_kind": "impl", "summary": "a"},
                {"seq": 2, "ts": "t", "event_kind": "fix", "summary": "b"},
            ],
        )


def test_ledger_bad_event_kind_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_update_ledger(slice_id="x", lines=[{"seq": 0, "ts": "t", "event_kind": "deploy", "summary": "a"}])


def test_ledger_bad_ref_sha_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_update_ledger(
            slice_id="x", lines=[{"seq": 0, "ts": "t", "event_kind": "impl", "summary": "a", "ref_sha": "NOTHEX!"}]
        )


def test_test_report_negative_passed_rejected() -> None:
    # tests < failed+errors+skipped -> passed would be negative -> rejected.
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_test_report(
            slice_id="x", generated_at="t", suites=[{"name": "u", "tests": 1, "failed": 3, "skipped": 2}]
        )


def test_test_report_coverage_out_of_range_rejected() -> None:
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_test_report(
            slice_id="x", generated_at="t", suites=[{"name": "u", "tests": 1}], coverage_percent=150.0
        )


def test_verify_closeout_binding_rejects_open_register_on_passed() -> None:
    # A slice_passed=True closeout whose bound register is in_progress must
    # verify False even when all the sha digests match.
    sr_open = ser.build_suggestion_register(
        slice_id=_SLICE,
        generated_at="t",
        harvest_mode="provided",
        register_status="in_progress",
        objections=[_obj()],
        expected_objections_count=3,
    )
    tr, led = _good_report(), _good_ledger()
    co = {
        "schema_version": ser.CLOSEOUT_VERSION,
        "artifact_kind": ser.CLOSEOUT_KIND,
        "slice_id": _SLICE,
        "generated_at": "t",
        "slice_passed": True,
        "bound_artifacts": {
            "test_report": {
                "artifact_kind": ser.TEST_REPORT_KIND,
                "schema_version": ser.TEST_REPORT_VERSION,
                "sha256": ser.sha256_of(tr),
                "line_count": None,
            },
            "suggestion_register": {
                "artifact_kind": ser.SUGGESTION_REGISTER_KIND,
                "schema_version": ser.SUGGESTION_REGISTER_VERSION,
                "sha256": ser.sha256_of(sr_open),
                "line_count": None,
            },
            "update_ledger": {
                "artifact_kind": ser.LEDGER_LINE_KIND,
                "schema_version": ser.LEDGER_LINE_VERSION,
                "sha256": ser._ledger_hash(led),
                "line_count": len(led),
            },
        },
    }
    assert not ser.verify_closeout_binding(co, test_report=tr, suggestion_register=sr_open, update_ledger=led)


# ---------------------------------------------------------------------------
# Closeout + binding (recompute-not-trust)
# ---------------------------------------------------------------------------
def test_closeout_valid_and_binding_verifies() -> None:
    co, tr, sr, led = _good_closeout()
    assert not list(_validator("ao-ma-slice-closeout").iter_errors(co))
    assert ser.verify_closeout_binding(co, test_report=tr, suggestion_register=sr, update_ledger=led)


def test_closeout_slice_passed_requires_green_report() -> None:
    tr_fail = ser.build_test_report(slice_id=_SLICE, generated_at="t", suites=[{"name": "u", "tests": 3, "failed": 1}])
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_closeout(
            slice_id=_SLICE,
            generated_at="t",
            test_report=tr_fail,
            suggestion_register=_good_register(),
            update_ledger=_good_ledger(),
            consensus_status="agreed",
            slice_passed=True,
        )


def test_closeout_slice_passed_requires_closed_register() -> None:
    # An in_progress register cannot back slice_passed=True.
    sr_open = ser.build_suggestion_register(
        slice_id=_SLICE,
        generated_at="t",
        harvest_mode="provided",
        register_status="in_progress",
        objections=[_obj()],
        expected_objections_count=3,
    )
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_closeout(
            slice_id=_SLICE,
            generated_at="t",
            test_report=_good_report(),
            suggestion_register=sr_open,
            update_ledger=_good_ledger(),
            consensus_status="agreed",
            slice_passed=True,
        )


def test_closeout_requires_matching_slice_id_across_siblings() -> None:
    # A sibling from a different slice cannot be bound into this closeout.
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_closeout(
            slice_id=_SLICE,
            generated_at="t",
            test_report=_good_report("OTHER-SLICE"),
            suggestion_register=_good_register(),
            update_ledger=_good_ledger(),
            consensus_status="agreed",
            slice_passed=True,
        )


def test_closeout_binding_detects_tamper() -> None:
    co, tr, sr, led = _good_closeout()
    tampered = dict(tr)
    tampered["generated_at"] = "DIFFERENT"
    assert not ser.verify_closeout_binding(co, test_report=tampered, suggestion_register=sr, update_ledger=led)


def test_build_closeout_rejects_forged_all_passed_flag() -> None:
    forged = ser.build_test_report(slice_id=_SLICE, generated_at="t", suites=[{"name": "u", "tests": 5, "failed": 2}])
    forged = dict(forged)
    forged["all_passed"] = True  # the lie
    with pytest.raises(ser.SliceEvidenceError):
        ser.build_closeout(
            slice_id=_SLICE,
            generated_at="t",
            test_report=forged,
            suggestion_register=_good_register(),
            update_ledger=_good_ledger(),
            consensus_status="agreed",
            slice_passed=True,
        )


def test_verify_closeout_binding_rejects_forged_green_even_if_sha_matches() -> None:
    forged = ser.build_test_report(slice_id=_SLICE, generated_at="t", suites=[{"name": "u", "tests": 5, "failed": 2}])
    forged = dict(forged)
    forged["all_passed"] = True
    sr, led = _good_register(), _good_ledger()
    co = {
        "schema_version": ser.CLOSEOUT_VERSION,
        "artifact_kind": ser.CLOSEOUT_KIND,
        "slice_id": _SLICE,
        "generated_at": "t",
        "slice_passed": True,
        "bound_artifacts": {
            "test_report": {
                "artifact_kind": ser.TEST_REPORT_KIND,
                "schema_version": ser.TEST_REPORT_VERSION,
                "sha256": ser.sha256_of(forged),
                "line_count": None,
            },
            "suggestion_register": {
                "artifact_kind": ser.SUGGESTION_REGISTER_KIND,
                "schema_version": ser.SUGGESTION_REGISTER_VERSION,
                "sha256": ser.sha256_of(sr),
                "line_count": None,
            },
            "update_ledger": {
                "artifact_kind": ser.LEDGER_LINE_KIND,
                "schema_version": ser.LEDGER_LINE_VERSION,
                "sha256": ser._ledger_hash(led),
                "line_count": len(led),
            },
        },
    }
    assert not ser.verify_closeout_binding(co, test_report=forged, suggestion_register=sr, update_ledger=led)


def test_closeout_not_passed_with_failing_report_allowed() -> None:
    tr_fail = ser.build_test_report(slice_id=_SLICE, generated_at="t", suites=[{"name": "u", "tests": 3, "failed": 1}])
    co = ser.build_closeout(
        slice_id=_SLICE,
        generated_at="t",
        test_report=tr_fail,
        suggestion_register=_good_register(),
        update_ledger=_good_ledger(),
        consensus_status="not_agreed",
        slice_passed=False,
    )
    assert co["slice_passed"] is False


def test_verify_closeout_binding_handles_malformed_closeout() -> None:
    co, tr, sr, led = _good_closeout()
    assert not ser.verify_closeout_binding({}, test_report=tr, suggestion_register=sr, update_ledger=led)
    assert not ser.verify_closeout_binding(
        {"bound_artifacts": {"test_report": {}}}, test_report=tr, suggestion_register=sr, update_ledger=led
    )


# ---------------------------------------------------------------------------
# Bundle manifest (exact-set semantic binding)
# ---------------------------------------------------------------------------
def test_bundle_manifest_valid_and_verifies() -> None:
    co, tr, sr, led = _good_closeout()
    mf = ser.build_bundle_manifest(
        slice_id=_SLICE, generated_at="t", test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co
    )
    assert not list(_validator("ao-ma-slice-evidence-bundle-manifest").iter_errors(mf))
    assert ser.verify_bundle_manifest(mf, test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co)
    assert {m["member_role"] for m in mf["members"]} == {
        "test_report",
        "suggestion_register",
        "update_ledger",
        "closeout",
    }


def test_bundle_manifest_detects_member_tamper() -> None:
    co, tr, sr, led = _good_closeout()
    mf = ser.build_bundle_manifest(
        slice_id=_SLICE, generated_at="t", test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co
    )
    other = ser.build_test_report(slice_id=_SLICE, generated_at="DIFF", suites=[{"name": "u", "tests": 1}])
    assert not ser.verify_bundle_manifest(mf, test_report=other, suggestion_register=sr, update_ledger=led, closeout=co)


def test_bundle_manifest_detects_wrong_kind_with_right_sha() -> None:
    co, tr, sr, led = _good_closeout()
    mf = ser.build_bundle_manifest(
        slice_id=_SLICE, generated_at="t", test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co
    )
    # Right sha, wrong artifact_kind -> still rejected (semantic verify).
    bad = dict(mf)
    bad["members"] = [dict(m) for m in mf["members"]]
    for m in bad["members"]:
        if m["member_role"] == "test_report":
            m["artifact_kind"] = "ao_ma_something_else"
    assert not ser.verify_bundle_manifest(bad, test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co)


def test_bundle_manifest_missing_or_duplicate_member_rejected() -> None:
    co, tr, sr, led = _good_closeout()
    mf = ser.build_bundle_manifest(
        slice_id=_SLICE, generated_at="t", test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co
    )
    short = dict(mf)
    short["members"] = mf["members"][:3]
    assert not ser.verify_bundle_manifest(short, test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co)
    dup = dict(mf)
    dup["members"] = [mf["members"][0], mf["members"][0], mf["members"][1], mf["members"][2]]
    assert not ser.verify_bundle_manifest(dup, test_report=tr, suggestion_register=sr, update_ledger=led, closeout=co)


def test_manifest_closeout_not_circular() -> None:
    co, _, _, _ = _good_closeout()
    assert set(co["bound_artifacts"]) == {"test_report", "suggestion_register", "update_ledger"}


# ---------------------------------------------------------------------------
# Canonical bytes determinism
# ---------------------------------------------------------------------------
def test_canonical_bytes_deterministic() -> None:
    tr = _good_report()
    assert ser.canonical_bytes(tr) == ser.canonical_bytes(dict(tr))
    assert ser.sha256_of(tr) == ser.sha256_of(dict(tr))
    assert ser.canonical_bytes(tr).endswith(b"\n")


# ---------------------------------------------------------------------------
# Purity: AST import-allowlist (the structural guarantee that no I/O / network /
# subprocess can occur — a forbidden module cannot be used without importing it)
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
    assert not forbidden, f"slice_evidence_registers imports outside allowlist: {sorted(forbidden)}"
