from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.repo_intelligence import validate_repo_intelligence_product_onboarding


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / "repo-intelligence-product-onboarding.schema.v1.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _valid_contract() -> dict:
    return {
        "schema_version": "1",
        "artifact_kind": "repo_intelligence_product_onboarding",
        "enabled": True,
        "support_tier": "beta_read_only_product_onboarding",
        "setup": {
            "github_app": {
                "installation": "required",
                "repository_selection": "selected_repositories",
                "permission_boundary": "read_only_repo_intelligence",
            },
            "repo_local_config": {
                "path": ".ao/config.yml",
                "required": False,
            },
            "end_user_infrastructure": {
                "cloud_run_required": False,
                "vault_required": False,
                "webhook_required": False,
                "github_app_private_key_required": False,
                "release_gate_service_required": False,
                "deployment_protection_service_required": False,
            },
        },
        "workflow": {
            "mode": "read_only",
            "activation": "explicit_opt_in",
            "default_enabled": False,
            "default_auto_feed": False,
        },
        "safety": {
            "hidden_prompt_injection": False,
            "mcp_tool_exposure": False,
            "root_export_required": False,
            "context_compiler_auto_feed": False,
            "implicit_vector_writes": False,
            "implicit_artifact_writes": False,
            "live_adapter_execution": False,
            "support_widening": False,
            "production_platform_claim": False,
        },
    }


def test_repo_intelligence_product_onboarding_schema_accepts_minimal_product_contract() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(_valid_contract()))
    assert errors == []


def test_repo_intelligence_product_onboarding_schema_rejects_end_user_infra_or_auto_feed() -> None:
    validator = Draft202012Validator(_schema())

    cloud_run = _valid_contract()
    cloud_run["setup"]["end_user_infrastructure"]["cloud_run_required"] = True
    with pytest.raises(ValidationError):
        validator.validate(cloud_run)

    auto_feed = _valid_contract()
    auto_feed["workflow"]["default_auto_feed"] = True
    with pytest.raises(ValidationError):
        validator.validate(auto_feed)

    support_widening = _valid_contract()
    support_widening["safety"]["support_widening"] = True
    with pytest.raises(ValidationError):
        validator.validate(support_widening)


def test_product_onboarding_accepts_github_app_selected_repo_only() -> None:
    result = validate_repo_intelligence_product_onboarding(_valid_contract())

    assert result["status"] == "accepted"
    assert result["decision"] == "accepted_repo_intelligence_product_onboarding"
    assert result["required_end_user_steps"] == ["install_github_app", "select_repositories"]
    assert result["optional_repo_config_path"] == ".ao/config.yml"
    assert result["operator_owned_infrastructure"] == [
        "deployment_protection_policy_service",
        "ao_release_gate_service",
    ]
    assert result["end_user_infrastructure_required"] == {
        "cloud_run_required": False,
        "vault_required": False,
        "webhook_required": False,
        "github_app_private_key_required": False,
        "release_gate_service_required": False,
        "deployment_protection_service_required": False,
    }
    assert result["workflow"] == {
        "mode": "read_only",
        "activation": "explicit_opt_in",
        "default_enabled": False,
        "default_auto_feed": False,
    }
    assert result["safety"]["context_compiler_auto_feed"] is False
    assert result["safety"]["live_adapter_execution"] is False
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False
    assert result["live_adapter_execution_allowed"] is False


def test_product_onboarding_disabled_is_noop() -> None:
    assert validate_repo_intelligence_product_onboarding(None) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_product_onboarding_not_enabled",
    }
    assert validate_repo_intelligence_product_onboarding({"enabled": False}) == {
        "status": "disabled",
        "enabled": False,
        "decision": "repo_intelligence_product_onboarding_not_enabled",
    }


def test_product_onboarding_blocks_end_user_hosting_and_private_key_requirements() -> None:
    contract = _valid_contract()
    contract["setup"]["end_user_infrastructure"]["webhook_required"] = True
    contract["setup"]["end_user_infrastructure"]["github_app_private_key_required"] = True
    contract["setup"]["end_user_infrastructure"]["release_gate_service_required"] = True

    result = validate_repo_intelligence_product_onboarding(contract)

    assert result["status"] == "blocked"
    assert result["decision"] == "blocked_repo_intelligence_product_onboarding"
    assert "end_user_webhook_required_not_false" in result["findings"]
    assert "end_user_github_app_private_key_required_not_false" in result["findings"]
    assert "end_user_release_gate_service_required_not_false" in result["findings"]
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False
    assert result["live_adapter_execution_allowed"] is False


def test_product_onboarding_blocks_implicit_context_feed_or_live_adapter_execution() -> None:
    contract = _valid_contract()
    contract["workflow"]["default_enabled"] = True
    contract["workflow"]["default_auto_feed"] = True
    contract["safety"]["context_compiler_auto_feed"] = True
    contract["safety"]["live_adapter_execution"] = True

    result = validate_repo_intelligence_product_onboarding(contract)

    assert result["status"] == "blocked"
    assert "workflow_default_enabled_not_false" in result["findings"]
    assert "workflow_default_auto_feed_not_false" in result["findings"]
    assert "safety_context_compiler_auto_feed_not_false" in result["findings"]
    assert "safety_live_adapter_execution_not_false" in result["findings"]


def test_product_onboarding_blocks_unapproved_repo_config_path_or_support_claim() -> None:
    contract = _valid_contract()
    contract["support_tier"] = "production"
    contract["setup"]["repo_local_config"]["path"] = "../.ao/config.yml"
    contract["setup"]["repo_local_config"]["required"] = True
    contract["safety"]["production_platform_claim"] = True

    result = validate_repo_intelligence_product_onboarding(contract)

    assert result["status"] == "blocked"
    assert "support_tier_not_beta_read_only_product_onboarding" in result["findings"]
    assert "repo_local_config_path_not_approved" in result["findings"]
    assert "repo_local_config_required_not_false" in result["findings"]
    assert "safety_production_platform_claim_not_false" in result["findings"]
    assert result["support_widening"] is False
    assert result["production_platform_claim"] is False
