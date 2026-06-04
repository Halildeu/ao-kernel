"""AO-MA-11E-1 derived tracking SSOT tests.

Covers: schema validity (Draft 2020-12), the bundled ao_ma_status.v1.json
validating against its schema, guard-flag / authority-model pinning, the
state-machine refs (missing object is a schema error, not a silent
not_started), and the pure local drift comparator (positive + negative).
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import ao_kernel

_REPO_ROOT = Path(ao_kernel.__file__).resolve().parent.parent
_SCHEMA = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-status.schema.v1.json"
_STATUS = _REPO_ROOT / ".claude" / "plans" / "ao_ma_status.v1.json"

# scripts/ is not a package; put it on sys.path so the module imports normally
# (a plain import keeps coverage instrumentation visible, unlike load-by-path).
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import ao_ma_next  # noqa: E402  (path inserted above)


def _load_status() -> dict[str, Any]:
    return json.loads(_STATUS.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------
def test_schema_is_valid_draft202012() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:ao-ma-status:v1"
    assert schema["additionalProperties"] is False


def test_bundled_status_satisfies_schema() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(_load_status()))
    assert errors == [], f"status file schema errors: {[e.message for e in errors]}"


def test_status_role_and_authority_are_derived_not_authority() -> None:
    payload = _load_status()
    assert payload["status_role"] == "machine_readable_derived_tracking_index"
    assert payload["authority_model"] == "derived_from_master_plan_and_merged_ao_ma_artifacts"
    assert payload["ai_output_release_authority"] is False
    assert payload["release_authority"] == "ao-release-gate+github-ruleset"
    assert payload["github_mirror"]["authority"] is False
    assert payload["github_mirror"]["manual_edit_override_allowed"] is False


def test_guard_flags_pinned_false() -> None:
    payload = _load_status()
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False


def test_guard_flag_true_fails_schema() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["live_adapter_execution_allowed"] = True
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "guard flag True must fail the schema const"


def test_master_plan_ref_present_and_bound() -> None:
    payload = _load_status()
    ref = payload["master_plan_ref"]
    assert ref["path"] == ".claude/plans/AO-MA-SPM-MASTER-PLAN.md"
    assert ref["sha256"].startswith("sha256:")
    assert len(ref["commit_sha"]) == 40


# ---------------------------------------------------------------------------
# State-machine refs: missing object is a schema error, not silent not_started
# ---------------------------------------------------------------------------
def test_slice_requires_consensus_ref_object() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    del payload["slices"][0]["consensus_ref"]
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "a slice missing consensus_ref must fail the schema (no silent not_started)"


def test_consensus_ref_requires_state() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][0]["consensus_ref"] = {}
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "consensus_ref without 'state' must fail the schema"


def test_approval_ref_state_enum_enforced() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][0]["approval_ref"] = {"state": "rubber_stamped"}
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "approval_ref.state outside the enum must fail"


def test_anchor_required_on_every_slice() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    del payload["slices"][0]["anchor"]
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "a slice without an anchor must fail the schema"


# ---------------------------------------------------------------------------
# Drift comparator (pure local)
# ---------------------------------------------------------------------------
def test_bundled_status_has_no_drift() -> None:
    payload = _load_status()
    drift = ao_ma_next.check_drift(payload)
    assert drift == [], f"bundled status must be internally consistent: {drift}"


def test_drift_detects_merged_count_mismatch() -> None:
    payload = _load_status()
    payload["progress_estimates"]["slices"]["merged_count"] += 1
    drift = ao_ma_next.check_drift(payload)
    assert any("merged_count" in d for d in drift)


def test_drift_detects_unknown_slice_reference() -> None:
    payload = _load_status()
    payload["phases"][0]["slice_ids"].append("AO-MA-GHOST-1")
    drift = ao_ma_next.check_drift(payload)
    assert any("unknown slice" in d for d in drift)


def test_drift_detects_merged_without_consensus() -> None:
    payload = _load_status()
    merged = next(s for s in payload["slices"] if s["status"] == "merged")
    merged["consensus_ref"] = {"state": "not_started"}
    drift = ao_ma_next.check_drift(payload)
    assert any("consensus_ref.state=agreed" in d for d in drift)


def test_drift_detects_anchor_id_mismatch() -> None:
    payload = _load_status()
    payload["slices"][0]["anchor"]["slice_id"] = "AO-MA-WRONG"
    drift = ao_ma_next.check_drift(payload)
    assert any("anchor phase/slice id mismatch" in d for d in drift)


def test_drift_detects_current_phase_not_present() -> None:
    payload = _load_status()
    payload["current_phase"] = "AO-MA-ZZ"
    drift = ao_ma_next.check_drift(payload)
    assert any("current_phase" in d for d in drift)


def test_drift_detects_guard_flag_flip_in_comparator() -> None:
    # check_drift is a defensive backstop independent of the schema.
    payload = _load_status()
    payload["support_widening_allowed"] = True
    drift = ao_ma_next.check_drift(payload)
    assert any("support_widening_allowed" in d for d in drift)


def test_drift_detects_high_risk_merged_without_pr() -> None:
    payload = _load_status()
    merged = next(s for s in payload["slices"] if s["status"] == "merged")
    merged["risk_class"] = "high"
    merged["pr_refs"] = []
    drift = ao_ma_next.check_drift(payload)
    assert any("no pr_refs" in d for d in drift)


def test_drift_detects_slice_not_under_any_phase() -> None:
    payload = _load_status()
    # Add a slice that no phase lists -> "not listed under any phase.slice_ids".
    orphan = deepcopy(payload["slices"][0])
    orphan["slice_id"] = "AO-MA-ORPHAN-1"
    orphan["anchor"]["slice_id"] = "AO-MA-ORPHAN-1"
    payload["slices"].append(orphan)
    drift = ao_ma_next.check_drift(payload)
    assert any("not listed under any phase" in d for d in drift)


def test_drift_detects_slice_unknown_phase() -> None:
    payload = _load_status()
    payload["slices"][0]["phase_id"] = "AO-MA-NOPHASE"
    payload["slices"][0]["anchor"]["phase_id"] = "AO-MA-NOPHASE"
    drift = ao_ma_next.check_drift(payload)
    assert any("unknown phase" in d for d in drift)


def test_drift_detects_current_slice_not_present() -> None:
    payload = _load_status()
    payload["current_slice"] = "AO-MA-GHOST-9"
    drift = ao_ma_next.check_drift(payload)
    assert any("current_slice" in d for d in drift)


def test_drift_detects_approval_decision_mismatch() -> None:
    payload = _load_status()
    merged = next(s for s in payload["slices"] if s["status"] == "merged")
    merged["approval_ref"] = {"state": "approved", "decision": "rejected"}
    drift = ao_ma_next.check_drift(payload)
    assert any("decision != approved" in d for d in drift)


def test_drift_detects_total_count_mismatch() -> None:
    payload = _load_status()
    payload["progress_estimates"]["slices"]["total_count"] += 3
    drift = ao_ma_next.check_drift(payload)
    assert any("total_count" in d for d in drift)


def test_drift_detects_phases_done_count_mismatch() -> None:
    payload = _load_status()
    payload["progress_estimates"]["phases"]["done_count"] += 1
    drift = ao_ma_next.check_drift(payload)
    assert any("done_count" in d for d in drift)


def test_next_action_default_when_empty() -> None:
    payload = _load_status()
    payload["next_allowed_actions"] = []
    assert "consult the master plan" in ao_ma_next.next_action(payload)


def test_drift_detects_master_plan_hash_mismatch() -> None:
    payload = _load_status()
    payload["master_plan_ref"]["sha256"] = "sha256:" + "0" * 64
    drift = ao_ma_next.check_drift(payload)
    assert any("master_plan_ref.sha256" in d for d in drift)


def test_drift_skips_master_plan_hash_when_file_absent(tmp_path: Path) -> None:
    # repo_root with no master plan file -> hash check skipped (not failed),
    # keeping the comparator a pure digest check, not a presence requirement.
    payload = _load_status()
    drift = ao_ma_next.check_drift(payload, repo_root=tmp_path)
    assert not any("master_plan_ref.sha256" in d for d in drift)


def test_drift_detects_anchor_artifact_hash_mismatch() -> None:
    payload = _load_status()
    merged = next(s for s in payload["slices"] if s["slice_id"] == "AO-MA-11A-1")
    merged["anchor"]["artifact_sha256"] = "sha256:" + "1" * 64
    drift = ao_ma_next.check_drift(payload)
    assert any("anchor artifact_sha256" in d for d in drift)


def test_drift_detects_duplicate_slice_id() -> None:
    payload = _load_status()
    dup = deepcopy(payload["slices"][0])
    payload["slices"].append(dup)
    payload["phases"][0]["slice_ids"].append(dup["slice_id"]) if dup["slice_id"] not in payload["phases"][0][
        "slice_ids"
    ] else None
    drift = ao_ma_next.check_drift(payload)
    assert any("duplicate slice_id" in d for d in drift)


def test_drift_detects_current_slice_phase_mismatch() -> None:
    payload = _load_status()
    # Force a deterministic mismatch from the payload's OWN data, independent of
    # which phase/slice the program currently sits on (current_* advances as
    # phases land): pin current_slice to a known slice, then set current_phase
    # to a DIFFERENT existing phase than that slice's.
    target = payload["slices"][0]
    payload["current_slice"] = target["slice_id"]
    payload["current_phase"] = next(p["phase_id"] for p in payload["phases"] if p["phase_id"] != target["phase_id"])
    drift = ao_ma_next.check_drift(payload)
    assert any("not current_phase" in d for d in drift)


def test_drift_detects_in_review_without_consensus() -> None:
    payload = _load_status()
    # Construct the violating state from the payload's own data rather than
    # assuming a slice already sits at in_review: force the first slice to
    # in_review with a not_started consensus. This stays correct as current_*
    # advance across phases (an in_review slice may not exist at any moment).
    target = payload["slices"][0]
    target["status"] = "in_review"
    target["consensus_ref"] = {"state": "not_started"}
    drift = ao_ma_next.check_drift(payload)
    assert any("must have consensus_ref.state=agreed" in d for d in drift)


def test_drift_detects_phase_done_with_unmerged_slice() -> None:
    payload = _load_status()
    phase = next(p for p in payload["phases"] if p["phase_id"] == "AO-MA-11E")
    phase["status"] = "done"  # 11E still has unmerged slice AO-MA-11E-2.
    drift = ao_ma_next.check_drift(payload)
    assert any("done but slices not merged" in d for d in drift)


def test_drift_detects_slice_percent_mismatch() -> None:
    payload = _load_status()
    payload["progress_estimates"]["slices"]["percent"] = 99
    drift = ao_ma_next.check_drift(payload)
    assert any("slices.percent" in d for d in drift)


def test_drift_detects_phase_total_and_percent_mismatch() -> None:
    payload = _load_status()
    payload["progress_estimates"]["phases"]["total_count"] = 99
    drift = ao_ma_next.check_drift(payload)
    assert any("phases.total_count" in d for d in drift)


def test_sha256_of_file_returns_none_on_missing(tmp_path: Path) -> None:
    assert ao_ma_next._sha256_of_file(tmp_path / "nope.bin") is None


def test_sha256_of_file_hashes_existing(tmp_path: Path) -> None:
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    digest = ao_ma_next._sha256_of_file(p)
    assert digest is not None and digest.startswith("sha256:")


def test_consensus_agreed_requires_evidence_schema() -> None:
    # state=agreed with neither bundle binding nor consultation_refs must fail.
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][0]["consensus_ref"] = {"state": "agreed"}
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "agreed consensus without evidence must fail the if/then schema"


def test_approval_decided_requires_evidence_schema() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    merged = next(s for s in payload["slices"] if s["slice_id"] == "AO-MA-11A-1")
    merged["approval_ref"] = {"state": "approved"}
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "approved approval without evidence must fail the if/then schema"


def _full_quorum_refs() -> list[dict[str, str]]:
    return [
        {"provider_id": "anthropic", "ref": "claude:x"},
        {"provider_id": "openai", "ref": "codex:y"},
        {"provider_id": "minimax", "ref": "mavis:z"},
    ]


def test_consensus_agreed_with_full_quorum_refs_is_valid() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][1]["consensus_ref"] = {"state": "agreed", "consultation_refs": _full_quorum_refs()}
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors == []


def test_consensus_agreed_single_provider_refs_fails() -> None:
    # A single-provider consultation_refs must NOT satisfy 'agreed'
    # (no single-provider consensus claim).
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][1]["consensus_ref"] = {
        "state": "agreed",
        "consultation_refs": [{"provider_id": "openai", "ref": "codex:y"}],
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "single-provider consultation_refs must fail (quorum coverage required)"


def test_consensus_agreed_missing_one_provider_fails() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][1]["consensus_ref"] = {
        "state": "agreed",
        "consultation_refs": [
            {"provider_id": "anthropic", "ref": "claude:x"},
            {"provider_id": "openai", "ref": "codex:y"},
            {"provider_id": "openai", "ref": "codex:y2"},
        ],
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "missing minimax in quorum must fail the contains coverage"


def test_consultation_ref_untyped_string_fails() -> None:
    # Plain strings are no longer allowed; refs must be {provider_id, ref}.
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    payload = _load_status()
    payload["slices"][1]["consensus_ref"] = {
        "state": "agreed",
        "consultation_refs": ["codex:abc", "claude:x", "mavis:z"],
    }
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    assert errors, "untyped string consultation refs must fail"


def test_bundled_status_quorum_refs_cover_three_providers() -> None:
    # The bundled status's agreed slices must each name all three providers.
    payload = _load_status()
    for sl in payload["slices"]:
        cref = sl["consensus_ref"]
        if cref["state"] == "agreed" and "consultation_refs" in cref:
            providers = {r["provider_id"] for r in cref["consultation_refs"]}
            assert providers == {"anthropic", "openai", "minimax"}, f"{sl['slice_id']} quorum incomplete: {providers}"


def test_main_next_only_exit_one_on_drift(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    drifted = deepcopy(_load_status())
    drifted["progress_estimates"]["slices"]["merged_count"] += 9
    p = tmp_path / "ao_ma_status.v1.json"
    p.write_text(json.dumps(drifted), encoding="utf-8")
    rc = ao_ma_next.main(["--status", str(p), "--next-only"])
    capsys.readouterr()
    assert rc == 1


# ---------------------------------------------------------------------------
# load_status + next_action + main
# ---------------------------------------------------------------------------
def test_load_status_round_trip() -> None:
    payload = ao_ma_next.load_status(_STATUS)
    assert payload["program_id"] == "ao-ma-spm"


def test_load_status_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ao_ma_next.AoMaStatusError, match="not found"):
        ao_ma_next.load_status(tmp_path / "nope.json")


def test_load_status_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "ao_ma_status.v1.json"
    p.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(ao_ma_next.AoMaStatusError, match="failed to read"):
        ao_ma_next.load_status(p)


def test_load_status_not_an_object(tmp_path: Path) -> None:
    p = tmp_path / "ao_ma_status.v1.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ao_ma_next.AoMaStatusError, match="must be a JSON object"):
        ao_ma_next.load_status(p)


def test_load_status_schema_load_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Point the schema path at a non-existent file to exercise the schema-load
    # error branch (fail-closed when the bundled schema can't be read).
    p = tmp_path / "ao_ma_status.v1.json"
    p.write_text(json.dumps(_load_status()), encoding="utf-8")
    monkeypatch.setattr(ao_ma_next, "_SCHEMA_PATH", tmp_path / "no-such-schema.json")
    with pytest.raises(ao_ma_next.AoMaStatusError, match="failed to load AO-MA status schema"):
        ao_ma_next.load_status(p)


def test_load_status_schema_invalid(tmp_path: Path) -> None:
    bad = deepcopy(_load_status())
    bad["live_adapter_execution_allowed"] = True
    p = tmp_path / "ao_ma_status.v1.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ao_ma_next.AoMaStatusError, match="failed schema"):
        ao_ma_next.load_status(p)


def test_next_action_returns_first() -> None:
    payload = _load_status()
    assert ao_ma_next.next_action(payload) == payload["next_allowed_actions"][0]


def test_ao_ma_11a_2_status_is_bound_to_environment_wiring_evidence() -> None:
    payload = _load_status()
    target = next(s for s in payload["slices"] if s["slice_id"] == "AO-MA-11A-2")

    assert target["status"] == "merged"
    assert target["risk_class"] == "high"
    assert target["pr_refs"] == [792]
    assert target["consensus_ref"]["state"] == "agreed"
    assert target["approval_ref"]["state"] == "approved"
    assert target["approval_ref"]["decision"] == "approved"
    assert "prevent_self_review=true" in target["approval_ref"]["operator_decision_ref"]
    assert "can_admins_bypass=false" in target["approval_ref"]["operator_decision_ref"]

    evidence = target["evidence_refs"]
    assert evidence == [
        {
            "kind": "github_environment_wiring",
            "path": ".claude/plans/AO-MA-11A-2-ENVIRONMENT-WIRING-EVIDENCE.v1.json",
            "required_for_closeout": True,
            "sha256": "sha256:eca714a017edf9809b508ccfa974cc5bd9a9fd598c9e05bcc28677871a955172",
        }
    ]
    assert target["anchor"]["ao_authority_artifact"] == evidence[0]["path"]
    assert target["anchor"]["artifact_sha256"] == evidence[0]["sha256"]
    assert target["anchor"]["plan_digest"] == (
        "sha256:340d8d71b64c357e8d36c8f211faaa7741157d10b428524d818cb717bcbd28dc"
    )


def test_main_text_exit_zero_on_clean(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ao_ma_next.main(["--status", str(_STATUS)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Program:" in out
    assert "Next allowed action:" in out


def test_main_json_format(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ao_ma_next.main(["--status", str(_STATUS), "--format", "json"])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)
    assert "next_allowed_action" in parsed
    assert parsed["drift"] == []


def test_main_next_only(capsys: pytest.CaptureFixture[str]) -> None:
    rc = ao_ma_next.main(["--status", str(_STATUS), "--next-only"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out == _load_status()["next_allowed_actions"][0]


def test_main_exit_two_on_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = ao_ma_next.main(["--status", str(tmp_path / "missing.json")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "error:" in err


def test_main_exit_one_on_drift(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    drifted = deepcopy(_load_status())
    drifted["progress_estimates"]["slices"]["merged_count"] += 5
    p = tmp_path / "ao_ma_status.v1.json"
    p.write_text(json.dumps(drifted), encoding="utf-8")
    rc = ao_ma_next.main(["--status", str(p)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "DRIFT DETECTED" in out
