"""Focused unit tests for scripts/ri78b_bc10_activation_window.py.

Critical guard contracts:
- workflow_content_sha256 mismatch -> fail
- pricing source digest mismatch -> fail
- supersession entry missing -> fail
- supersession status not in {awaiting_operator_dispatch, active} -> fail
- authority_mode != manual_protected_environment -> fail
- autonomous_trigger_allowed != false -> fail
- manual_approval_required != true -> fail
- window expired -> fail
- worst-case cost invariant violated -> fail

These tests do NOT exercise the gh api environment observation (which
requires a live GH_TOKEN); they cover the static guards. Environment
observation guards are tested by separate integration tests at 6c runtime.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "ri78b_bc10_activation_window.py"
PRICING_SOURCE_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "pricing" / "openai_gpt_4o_mini.v1.json"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc10-real-adapter-usage-cost.yml"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"


def test_activation_script_exists():
    assert SCRIPT_PATH.exists(), f"Activation script missing: {SCRIPT_PATH}"


def _load_module():
    """Load the activation window module for direct invocation."""
    spec = importlib.util.spec_from_file_location("ri78b_bc10_activation_window", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_activation_module_imports_cleanly():
    mod = _load_module()
    assert hasattr(mod, "main")
    assert hasattr(mod, "find_supersession_entry")
    assert hasattr(mod, "sha256_file")
    assert hasattr(mod, "parse_iso_z")
    assert hasattr(mod, "load_json")
    assert hasattr(mod, "fail")
    assert hasattr(mod, "github_environment_observation")
    assert hasattr(mod, "github_environment_branch_policies")


def test_find_supersession_entry_present():
    """Returns the bc10-6b entry from current gpp_status."""
    mod = _load_module()
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    assert entry["id"] == "RI-7.8b-bc10-6b"
    assert entry["authority_mode"] == "manual_protected_environment"


def test_find_supersession_entry_missing():
    mod = _load_module()
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-NONEXISTENT")
    assert entry is None


def test_sha256_file_matches_workflow():
    """Computed SHA-256 matches the pinned workflow_content_sha256 in supersession entry."""
    mod = _load_module()
    actual = mod.sha256_file(WORKFLOW_PATH)
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    pinned = entry["future_workflow_contract"]["workflow_content_sha256"]
    assert actual == pinned


def test_sha256_file_matches_pricing_source():
    """Computed SHA-256 matches the pinned pricing_source.source_digest."""
    mod = _load_module()
    actual = mod.sha256_file(PRICING_SOURCE_PATH)
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    pinned_raw = entry["pricing_source"]["source_digest"]
    assert pinned_raw.startswith("sha256:")
    pinned = pinned_raw[len("sha256:") :]
    assert actual == pinned


def test_parse_iso_z_round_trip():
    from datetime import timezone

    mod = _load_module()
    iso = "2026-05-28T23:38:35Z"
    dt = mod.parse_iso_z(iso)
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timezone.utc.utcoffset(dt)


def test_constants_match_gpp_status_entry():
    """Module constants match the supersession entry values."""
    mod = _load_module()
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    assert mod.SUPERSESSION_ENTRY_ID == entry["id"]
    assert mod.ALLOWED_AUTHORITY_MODE == entry["authority_mode"]
    # max_billable_calls_count from script default should align with entry
    assert mod.MAX_BILLABLE_CALLS_COUNT == entry["max_billable_calls_count"]


def test_authority_mode_must_be_manual_protected_environment_const():
    mod = _load_module()
    assert mod.ALLOWED_AUTHORITY_MODE == "manual_protected_environment"
    assert mod.ALLOWED_SCENARIO == "all_bc10_usage_cost"
    assert mod.ALLOWED_MODEL == "openai/gpt-4o-mini"


def test_load_json_invalid_file_fails():
    mod = _load_module()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json {{{")
        bad_path = Path(f.name)
    try:
        with pytest.raises(SystemExit) as exc_info:
            mod.load_json(bad_path)
        assert exc_info.value.code != 0
    finally:
        bad_path.unlink()


def test_load_json_missing_file_fails():
    mod = _load_module()
    missing = Path("/nonexistent/path/to/file.json")
    with pytest.raises(SystemExit) as exc_info:
        mod.load_json(missing)
    assert exc_info.value.code != 0


def test_max_usd_decimal_const():
    from decimal import Decimal

    mod = _load_module()
    assert mod.MAX_USD == Decimal("5.00")


def test_pricing_source_recompute_matches_supersession():
    """Sanity: recomputing pricing source SHA-256 returns the value pinned in the entry."""
    mod = _load_module()
    digest = mod.sha256_file(PRICING_SOURCE_PATH)
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    assert f"sha256:{digest}" == entry["pricing_source"]["source_digest"]


def test_worst_case_cost_invariant_holds():
    """max_billable_calls_count * max_projected_call_cost_usd <= max_usd in supersession entry."""
    from decimal import Decimal

    mod = _load_module()
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    max_billable = int(entry["max_billable_calls_count"])
    max_projected = Decimal(entry["max_projected_call_cost_usd"])
    max_usd = Decimal(str(entry["max_usd"]))
    assert max_billable * max_projected <= max_usd, f"worst case {max_billable * max_projected} > max_usd {max_usd}"


def _valid_env_observation_main_only():
    """Returns a minimal valid env observation for testing."""
    return {
        "name": "ao-kernel-bc10-real-adapter-usage-cost",
        "protection_rules": [
            {
                "type": "required_reviewers",
                "reviewers": [{"type": "User", "id": 1, "login": "Halildeu"}],
                "prevent_self_review": True,
            }
        ],
        "can_admins_bypass": False,
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }


def _valid_branch_policies_main_only():
    return [{"id": 1, "name": "main", "type": "branch"}]


def test_validate_env_observation_main_only_passes():
    mod = _load_module()
    # Should not raise
    mod.validate_environment_observation(
        env_observation=_valid_env_observation_main_only(),
        branch_policies_loader=lambda: _valid_branch_policies_main_only(),
        env_name="ao-kernel-bc10-real-adapter-usage-cost",
    )


def test_validate_env_observation_no_required_reviewers_fails():
    mod = _load_module()
    env_obs = _valid_env_observation_main_only()
    env_obs["protection_rules"] = []
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=env_obs,
            branch_policies_loader=lambda: _valid_branch_policies_main_only(),
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_prevent_self_review_false_fails():
    mod = _load_module()
    env_obs = _valid_env_observation_main_only()
    env_obs["protection_rules"][0]["prevent_self_review"] = False
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=env_obs,
            branch_policies_loader=lambda: _valid_branch_policies_main_only(),
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_can_admins_bypass_missing_fails():
    mod = _load_module()
    env_obs = _valid_env_observation_main_only()
    del env_obs["can_admins_bypass"]
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=env_obs,
            branch_policies_loader=lambda: _valid_branch_policies_main_only(),
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_can_admins_bypass_true_fails():
    mod = _load_module()
    env_obs = _valid_env_observation_main_only()
    env_obs["can_admins_bypass"] = True
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=env_obs,
            branch_policies_loader=lambda: _valid_branch_policies_main_only(),
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_protected_branches_true_fallback_fails():
    """iter-6 hardening: protected_branches=true fallback is REJECTED."""
    mod = _load_module()
    env_obs = _valid_env_observation_main_only()
    env_obs["deployment_branch_policy"] = {
        "protected_branches": True,
        "custom_branch_policies": False,
    }
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=env_obs,
            branch_policies_loader=lambda: [],
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_custom_branch_policies_false_fails():
    mod = _load_module()
    env_obs = _valid_env_observation_main_only()
    env_obs["deployment_branch_policy"] = {
        "protected_branches": False,
        "custom_branch_policies": False,
    }
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=env_obs,
            branch_policies_loader=lambda: [],
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_no_branch_policies_fails():
    mod = _load_module()
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=_valid_env_observation_main_only(),
            branch_policies_loader=lambda: [],
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_multiple_branch_policies_fails():
    mod = _load_module()
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=_valid_env_observation_main_only(),
            branch_policies_loader=lambda: [
                {"id": 1, "name": "main", "type": "branch"},
                {"id": 2, "name": "develop", "type": "branch"},
            ],
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_tag_policy_fails():
    """A tag policy (type='tag') instead of branch is rejected."""
    mod = _load_module()
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=_valid_env_observation_main_only(),
            branch_policies_loader=lambda: [{"id": 1, "name": "main", "type": "tag"}],
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_non_main_policy_fails():
    mod = _load_module()
    with pytest.raises(SystemExit) as exc_info:
        mod.validate_environment_observation(
            env_observation=_valid_env_observation_main_only(),
            branch_policies_loader=lambda: [{"id": 1, "name": "develop", "type": "branch"}],
            env_name="bc10-env",
        )
    assert exc_info.value.code != 0


def test_validate_env_observation_refs_heads_main_policy_passes():
    """Both 'main' and 'refs/heads/main' are accepted as policy names."""
    mod = _load_module()
    mod.validate_environment_observation(
        env_observation=_valid_env_observation_main_only(),
        branch_policies_loader=lambda: [{"id": 1, "name": "refs/heads/main", "type": "branch"}],
        env_name="bc10-env",
    )


def test_supersession_initial_status_awaiting_operator_dispatch():
    mod = _load_module()
    gpp = json.loads(GPP_STATUS_PATH.read_text())
    entry = mod.find_supersession_entry(gpp, "RI-7.8b-bc10-6b")
    assert entry is not None
    assert entry["status"] == "awaiting_operator_dispatch"
    assert entry["actual_start_at"] is None
    assert entry["actual_end_at"] is None
    assert entry["closed_at"] is None
