from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _module() -> Any:
    module_path = _repo_root() / "scripts" / "gpp_next.py"
    spec = importlib.util.spec_from_file_location("gpp_next", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status_path() -> Path:
    return _repo_root() / ".claude" / "plans" / "gpp_status.v1.json"


def test_gpp_status_contract_keeps_support_widening_closed() -> None:
    payload = json.loads(_status_path().read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1"
    assert payload["program_id"] == "general-purpose-production-promotion"
    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["current_wp"]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/482"
    assert payload["current_wp"]["exit_decision"] == "blocked_attestation_missing"
    assert any(item["id"] == "GPP-1b" for item in payload["completed_wps"])
    assert any(
        item["id"] == "GPP-2a" and item["decision"] == "still_blocked_protected_prerequisites_missing"
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2d"
        and item["decision"] == "repeatable_attestation_available_current_gate_still_blocked"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/487"
        for item in payload["completed_wps"]
    )
    assert any(
        item["id"] == "GPP-2e"
        and item["decision"] == "decision_recorded_not_approved_no_support_widening"
        and item["issue"] == "https://github.com/Halildeu/ao-kernel/issues/489"
        and (_repo_root() / item["record"]).exists()
        for item in payload["completed_wps"]
    )
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False
    assert payload["pending_external_actions"][0]["id"] == "GPP-2b"
    assert payload["pending_external_actions"][0]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/482"
    assert payload["pending_external_actions"][0]["status"] == "partially_provisioned_blocked"
    assert (
        payload["pending_external_actions"][0]["decision"]
        == "environment_created_secret_and_reviewer_still_missing"
    )
    assert payload["pending_external_actions"][1]["id"] == "GPP-2c"
    assert payload["pending_external_actions"][1]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/485"
    assert payload["pending_external_actions"][1]["status"] == "blocked_external_admin_decision_required"
    assert (
        payload["pending_external_actions"][1]["decision"]
        == "missing_environment_secret_and_non_self_reviewer_gate"
    )
    assert {item["id"] for item in payload["pending_external_actions"]} == {"GPP-2b", "GPP-2c"}
    assert {item["id"] for item in payload["blocked_wps"]} == {"GPP-2"}
    assert any("python3 scripts/gpp_next.py" == item["command"] for item in payload["required_startup_checks"])
    assert any(
        action == "keep the single-admin equivalent release gate not approved unless issue #489 is explicitly superseded"
        for action in payload["next_allowed_actions"]
    )
    assert any(
        action == "use --equivalent-release-gate-approved while GPP-2e remains not_approved"
        for action in payload["forbidden_actions"]
    )


def test_gpp2e_equivalent_gate_decision_defaults_to_not_approved() -> None:
    decision = (
        _repo_root() / ".claude/plans/GPP-2e-SINGLE-ADMIN-EQUIVALENT-GATE-DECISION.md"
    ).read_text(encoding="utf-8")

    assert "**Decision:** `not_approved`" in decision
    assert "does not approve that equivalent gate" in decision
    assert "--equivalent-release-gate-approved" in decision
    assert "must not be used for production prerequisite attestation" in decision


def test_gpp_next_load_status_validates_required_guards() -> None:
    mod = _module()

    payload = mod.load_status(_status_path())

    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["current_wp"]["issue"] == "https://github.com/Halildeu/ao-kernel/issues/482"
    assert payload["blocked_wps"][0]["id"] == "GPP-2"
    assert "credential handle and reviewer/equivalent gate exist" in payload["blocked_wps"][0]["blocked_until"]
    assert payload["support_widening_allowed"] is False


def test_gpp_next_rejects_fake_support_widening(tmp_path: Path) -> None:
    mod = _module()
    payload = json.loads(_status_path().read_text(encoding="utf-8"))
    payload["support_widening_allowed"] = True
    status_path = tmp_path / "gpp_status.v1.json"
    status_path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        mod.load_status(status_path)
    except mod.GppStatusError as exc:
        assert "support_widening_allowed must be false" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("expected GppStatusError for fake support widening")


def test_gpp_next_text_output_names_current_and_blocked_work() -> None:
    mod = _module()
    payload = mod.load_status(_status_path())

    rendered = mod.render_text(payload, git_summary={"status": "## main...origin/main", "divergence": "0\t0"})

    assert "Current WP: GPP-2 - Protected Live-Adapter Gate Runtime Binding" in rendered
    assert "Current status: blocked" in rendered
    assert "Support widening allowed: false" in rendered
    assert "Production platform claim allowed: false" in rendered
    assert "Live adapter execution allowed: false" in rendered
    assert "- GPP-2: AO_CLAUDE_CODE_CLI_AUTH handle and reviewer/equivalent gate" in rendered
    assert "divergence: 0\t0" in rendered


def test_gpp_next_cli_json_output(capsys: Any) -> None:
    mod = _module()

    result = mod.main(["--status-path", str(_status_path()), "--output", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 0
    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["blocked_wps"][0]["id"] == "GPP-2"
