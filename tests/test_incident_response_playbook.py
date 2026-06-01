"""Invariant test suite for V5 Epic 6 E-6-6: Incident response playbook.

Codex 019e83c3 cross-AI plan-time AGREE (2 iters: REVISE → AGREE).

6 must-close findings closed + 18 hardening suggestions absorbed:
- F1 E-5-5 dependency boundary (existence-OR-deferred placeholder)
- F2 Typed severity bridge (enum mapping + cross-validation against E-5-4 catalog)
- F3 Schema-backed guard discipline (artifact-level, not just prose)
- F4 Regulatory + vendor escalation boundary
- F5 policy_deny_rate scenario 06 added
- F6 Targeted secret/PII scanner with placeholders allowlist
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
INCIDENT_DIR = REPO_ROOT / "docs" / "incident-response"
SCENARIO_DIR = INCIDENT_DIR / "scenarios"
SEVERITY_MATRIX_PATH = INCIDENT_DIR / "severity-matrix.v1.json"
SEVERITY_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "severity-matrix.schema.v1.json"
ESCALATION_PATH = INCIDENT_DIR / "escalation-policy.v1.yml"
TEMPLATE_PATH = INCIDENT_DIR / "incident-template.v1.md"
README_PATH = INCIDENT_DIR / "README.md"
CATALOG_PATH = REPO_ROOT / "docs" / "sli-catalog.v1.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_schema() -> dict[str, Any]:
    return json.loads(SEVERITY_SCHEMA_PATH.read_text())


def load_matrix() -> dict[str, Any]:
    return json.loads(SEVERITY_MATRIX_PATH.read_text())


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text())


def yaml_loader():
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("PyYAML not installed")
    return yaml


def load_escalation_yaml() -> dict[str, Any]:
    yaml = yaml_loader()
    return yaml.safe_load(ESCALATION_PATH.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (8 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    """Schema file is valid JSON Schema Draft 2020-12."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_root_additional_properties_false():
    schema = load_schema()
    assert schema.get("additionalProperties") is False


def test_schema_const_pins_at_root():
    schema = load_schema()
    props = schema["properties"]
    assert props["schema_version"]["const"] == "severity-matrix.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["operator_owned"]["const"] is True
    assert props["is_contractual_sla"]["const"] is False


def test_schema_guard_flags_const_false():
    schema = load_schema()
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_schema_tiers_exactly_three():
    schema = load_schema()
    tiers = schema["properties"]["tiers"]
    assert tiers["minItems"] == 3
    assert tiers["maxItems"] == 3


def test_schema_tier_alertmanager_severity_enum():
    schema = load_schema()
    enum_vals = schema["$defs"]["tier"]["properties"]["alertmanager_severity"]["enum"]
    assert set(enum_vals) == {"critical", "warning", "advisory"}


def test_schema_tier_id_enum():
    schema = load_schema()
    enum_vals = schema["$defs"]["tier"]["properties"]["id"]["enum"]
    assert set(enum_vals) == {"SEV-1", "SEV-2", "SEV-3"}


def test_schema_comms_policy_enum():
    schema = load_schema()
    enum_vals = schema["$defs"]["tier"]["properties"]["comms_policy"]["enum"]
    assert set(enum_vals) == {"owner_immediate", "owner_business_hours", "operator_only"}


# ---------------------------------------------------------------------------
# Section 2 — Schema negative tests (5 invariants)
# ---------------------------------------------------------------------------


def _validate_or_raise(instance: dict, schema: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(schema).validate(instance)


def test_schema_rejects_production_platform_claim_true():
    schema = load_schema()
    matrix = load_matrix()
    matrix["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate_or_raise(matrix, schema)


def test_schema_rejects_support_widening_true():
    schema = load_schema()
    matrix = load_matrix()
    matrix["guard_flags"]["support_widening_allowed"] = True
    with pytest.raises(Exception):
        _validate_or_raise(matrix, schema)


def test_schema_rejects_is_contractual_sla_true():
    schema = load_schema()
    matrix = load_matrix()
    matrix["is_contractual_sla"] = True
    with pytest.raises(Exception):
        _validate_or_raise(matrix, schema)


def test_schema_rejects_alertmanager_severity_outside_enum():
    schema = load_schema()
    matrix = load_matrix()
    matrix["tiers"][0]["alertmanager_severity"] = "error"  # not in enum
    with pytest.raises(Exception):
        _validate_or_raise(matrix, schema)


def test_schema_rejects_unknown_tier_id():
    schema = load_schema()
    matrix = load_matrix()
    matrix["tiers"][0]["id"] = "SEV-0"  # not in enum
    with pytest.raises(Exception):
        _validate_or_raise(matrix, schema)


# ---------------------------------------------------------------------------
# Section 3 — Severity matrix instance (5 invariants)
# ---------------------------------------------------------------------------


def test_matrix_validates_against_schema():
    schema = load_schema()
    matrix = load_matrix()
    _validate_or_raise(matrix, schema)


def test_matrix_tier_ids_sequence_sev_1_2_3():
    matrix = load_matrix()
    ids = [t["id"] for t in matrix["tiers"]]
    assert ids == ["SEV-1", "SEV-2", "SEV-3"]


def test_matrix_severity_mapping_one_to_one():
    matrix = load_matrix()
    expected = {
        "SEV-1": "critical",
        "SEV-2": "warning",
        "SEV-3": "advisory",
    }
    for tier in matrix["tiers"]:
        assert tier["alertmanager_severity"] == expected[tier["id"]]


def test_matrix_applicable_indicators_in_e54_catalog():
    """F2 absorb: cross-validation against E-5-4 catalog indicator names."""
    matrix = load_matrix()
    catalog = load_catalog()
    catalog_names = {ind["name"] for ind in catalog["indicators"]}
    for tier in matrix["tiers"]:
        for ind_name in tier["applicable_indicator_names"]:
            assert ind_name in catalog_names, f"tier {tier['id']} references unknown indicator: {ind_name}"


def test_matrix_sev3_has_null_cadence_fields():
    """SEV-3 advisory: no hard MTTR/ack/cadence (operator-defined)."""
    matrix = load_matrix()
    sev3 = next(t for t in matrix["tiers"] if t["id"] == "SEV-3")
    assert sev3["mttr_target_minutes"] is None
    assert sev3["ack_timeout_minutes"] is None
    assert sev3["escalation_cadence_minutes"] is None
    assert sev3["comms_policy"] == "operator_only"


# ---------------------------------------------------------------------------
# Section 4 — Escalation policy YAML (3 invariants)
# ---------------------------------------------------------------------------


def test_escalation_yaml_parses():
    cfg = load_escalation_yaml()
    assert cfg["schema_version"] == "escalation-policy.v1"
    assert cfg["service"] == "ao-kernel"


def test_escalation_three_stages():
    cfg = load_escalation_yaml()
    stages = cfg["stages"]
    assert len(stages) == 3
    stage_names = {s["stage"] for s in stages}
    assert stage_names == {"primary_on_call", "secondary_on_call", "engineering_manager"}


def test_escalation_severity_cadence_per_tier():
    cfg = load_escalation_yaml()
    cadence = cfg["severity_cadence"]
    assert cadence["SEV-1"]["ack_timeout_minutes"] == 15
    assert cadence["SEV-1"]["escalation_cadence_minutes"] == 15
    assert cadence["SEV-2"]["ack_timeout_minutes"] == 30
    assert cadence["SEV-2"]["escalation_cadence_minutes"] == 60
    assert cadence["SEV-3"]["ack_timeout_minutes"] is None
    assert cadence["SEV-3"]["escalation_cadence_minutes"] is None


# ---------------------------------------------------------------------------
# Section 5 — Post-mortem template (4 invariants)
# ---------------------------------------------------------------------------


def test_template_has_required_sections():
    text = TEMPLATE_PATH.read_text()
    required_sections = (
        "## Metadata",
        "## Impact Summary",
        "## UTC Timeline",
        "## Root Cause Analysis",
        "## 5 Whys",
        "## Contributing Factors",
        "## Corrective Actions",
        "## Linked Artifacts",
        "## Evidence Links",
        "## Redaction Attestation",
    )
    for section in required_sections:
        assert section in text, f"missing post-mortem section: {section}"


def test_template_corrective_actions_table_has_owner_due_columns():
    text = TEMPLATE_PATH.read_text()
    # Markdown table header contains Owner + Due date columns
    assert "| Action | Owner | Due date" in text or "| Owner |" in text


def test_template_distribution_scope_operator_owner_security_only():
    text = TEMPLATE_PATH.read_text().lower()
    assert "distribution" in text
    assert "operator" in text and "owner" in text
    assert "security-stakeholder" in text or "security stakeholder" in text
    # Public post-mortem deferred
    assert "public post-mortem deferred" in text or "not public" in text


def test_template_redaction_attestation_present():
    text = TEMPLATE_PATH.read_text().lower()
    assert "redaction attestation" in text
    assert "no end-user pii" in text or "contains no end-user pii" in text


# ---------------------------------------------------------------------------
# Section 6 — README discipline (6 invariants)
# ---------------------------------------------------------------------------


def test_readme_has_numbered_sections():
    text = README_PATH.read_text()
    for section_num in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        assert re.search(rf"^## {section_num}\.", text, re.MULTILINE), f"missing README section {section_num}"


def test_readme_disclaimer_phrases():
    text = README_PATH.read_text()
    assert "Not SLA" in text
    assert "Not a production platform claim" in text
    assert "operator-tunable" in text.lower() or "operator-owned" in text.lower()


def test_readme_guard_flags_const_false_mention():
    text = README_PATH.read_text().lower()
    assert "const false" in text or "`const false`" in README_PATH.read_text()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text


def test_readme_microsoft_teams_primary():
    text = README_PATH.read_text()
    assert "Microsoft Teams" in text
    assert "primary" in text.lower()
    assert "ADR-0029" in text or "Workspace Tooling" in text


def test_readme_slack_dormant_context_only():
    text = README_PATH.read_text().lower()
    assert "dormant" in text
    # No Slack primary claim
    forbidden = ("slack primary", "slack as the active", "slack receives alerts first")
    for phrase in forbidden:
        assert phrase not in text


def test_readme_regulatory_and_vendor_boundary_sections():
    """F4 absorb: regulatory + vendor escalation explicit fence."""
    text = README_PATH.read_text().lower()
    assert "regulatory disclosure boundary" in text
    assert "vendor escalation boundary" in text
    assert "legal/security-owner decision" in text or "legal/compliance counsel" in text


# ---------------------------------------------------------------------------
# Section 7 — Scenarios (6 invariants)
# ---------------------------------------------------------------------------


EXPECTED_SCENARIO_FILES = {
    "01-llm-usage-accounting-drop.md": "llm_usage_accounting_completeness",
    "02-llm-latency-burn.md": "llm_latency_under_30s_ratio",
    "03-workflow-success-drop.md": "workflow_terminal_success_rate",
    "04-cost-burn-breach.md": "monthly_cost_burn_projection_usd",
    "05-coordination-takeover-spike.md": "coordination_takeover_rate",
    "06-policy-deny-spike.md": "policy_deny_rate",
}


def test_scenario_files_exist():
    for fname in EXPECTED_SCENARIO_FILES:
        path = SCENARIO_DIR / fname
        assert path.exists(), f"missing scenario file: {fname}"


@pytest.mark.parametrize("fname,indicator", list(EXPECTED_SCENARIO_FILES.items()))
def test_scenario_references_correct_e54_indicator(fname, indicator):
    """Each scenario references the exact E-5-4 catalog indicator name."""
    path = SCENARIO_DIR / fname
    text = path.read_text()
    assert indicator in text, f"{fname} does not reference indicator {indicator}"


def test_scenarios_reference_sev_tier_mapping():
    """Each scenario references at least one SEV tier."""
    for fname in EXPECTED_SCENARIO_FILES:
        text = (SCENARIO_DIR / fname).read_text()
        assert any(sev in text for sev in ("SEV-1", "SEV-2", "SEV-3")), f"{fname} does not reference any SEV tier"


# Codex absorb: diagnostic commands must avoid integration config material.
FORBIDDEN_INTEGRATION_CONFIG_PATTERNS = (
    re.compile(r"\bpagerduty\.com/[\w/]+"),  # URL
    re.compile(r"\bopsgenie\.com/[\w/]+"),  # URL
    re.compile(r"PAGERDUTY_(?:API_KEY|ROUTING_KEY|TOKEN)", re.IGNORECASE),
    re.compile(r"OPSGENIE_(?:API_KEY|ROUTING_KEY|TOKEN)", re.IGNORECASE),
    re.compile(r"service_key:\s*[\"'][^\"']{8,}"),  # YAML config block
    re.compile(r"integration_endpoint:\s*[\"']?https?://"),
    re.compile(r"routing_key:\s*[\"'][^\"']{8,}"),
)


def test_scenarios_no_external_integration_config():
    """Codex absorb: out-of-scope follow-ups can mention names; integration
    config/API material (URL/token/key/endpoint) YASAK in active scenarios."""
    for fname in EXPECTED_SCENARIO_FILES:
        text = (SCENARIO_DIR / fname).read_text()
        for pat in FORBIDDEN_INTEGRATION_CONFIG_PATTERNS:
            assert not pat.search(text), f"{fname} contains forbidden integration config: {pat.pattern}"


def test_scenarios_diagnostic_commands_are_read_only():
    """Diagnostic commands must be read-only (curl GET, kubectl get, no
    mutation patterns like apply/delete/patch/scale/rollout)."""
    forbidden_cmds = (
        re.compile(r"kubectl\s+(?:apply|delete|patch|scale|rollout\s+restart)"),
        re.compile(r"gh\s+(?:pr\s+merge|workflow\s+run|api\s+(?:-X\s+)?(?:POST|PUT|DELETE|PATCH))"),
        re.compile(r"helm\s+(?:install|upgrade|uninstall|rollback)"),
        re.compile(r"curl\s+(?:-X\s+)?(?:POST|PUT|DELETE|PATCH)\b", re.IGNORECASE),
    )
    for fname in EXPECTED_SCENARIO_FILES:
        text = (SCENARIO_DIR / fname).read_text()
        for pat in forbidden_cmds:
            assert not pat.search(text), f"{fname} contains non-read-only command: {pat.pattern}"


# ---------------------------------------------------------------------------
# Section 8 — Targeted secret/PII scanner (1 invariant)
# ---------------------------------------------------------------------------


# F6 absorb: targeted patterns + allowed placeholders.
FORBIDDEN_PATTERNS = {
    "teams_webhook_url": re.compile(r"https://[\w.-]*outlook\.office\.com/webhook/[^\s\"']{10,}", re.IGNORECASE),
    "teams_hooks_url": re.compile(r"https://hooks\.[A-Za-z0-9.-]+/[\w/]+", re.IGNORECASE),
    "slack_webhook_url": re.compile(r"https://hooks\.slack\.com/services/[A-Z0-9/]+"),
    "github_pat": re.compile(r"\bghp_[A-Za-z0-9]{36,}"),
    "jwt_token": re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{40,}"),
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{40,}"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "bearer_header": re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}", re.IGNORECASE),
    "private_key": re.compile(r"-----BEGIN .+ PRIVATE KEY-----"),
}

ALLOWED_PLACEHOLDERS = (
    "REDACTED",
    "PLACEHOLDER",
    "TBD",
    "__SECRET__",
    "__TEAMS_WEBHOOK_URL__",
    "example.com",
    "redacted.example",
)


def _scan_artifact_for_secrets(path: Path) -> list[tuple[str, str]]:
    text = path.read_text()
    hits = []
    for name, pat in FORBIDDEN_PATTERNS.items():
        for m in pat.finditer(text):
            matched = m.group(0)
            if any(allowed in matched for allowed in ALLOWED_PLACEHOLDERS):
                continue
            hits.append((name, matched))
    return hits


def test_incident_artifacts_have_no_secrets_or_pii():
    """F6 absorb: targeted scanner; allows redacted placeholders."""
    for path in INCIDENT_DIR.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".json", ".yml", ".yaml"):
            hits = _scan_artifact_for_secrets(path)
            assert not hits, f"secret/PII pattern in {path.relative_to(REPO_ROOT)}: {hits}"


# ---------------------------------------------------------------------------
# Section 9 — E-5-5 dependency boundary (2 invariants)
# ---------------------------------------------------------------------------


def test_readme_references_e55_paths():
    """F1 absorb: E-5-5 path references must be present in README."""
    readme = README_PATH.read_text()
    assert "docs/alertmanager/" in readme or "../alertmanager/" in readme
    assert "PR #800" in readme  # deferred placeholder boundary mark


def test_e55_paths_exist_or_deferred_marker_present():
    """F1 absorb: existence-OR-deferred-placeholder pattern."""
    readme = README_PATH.read_text()
    e55_prom_rules = REPO_ROOT / "docs" / "alertmanager" / "prometheus-rules.v1.yml"
    if e55_prom_rules.exists():
        # If E-5-5 has landed, README scenarios reference exact alert names.
        scenario_01 = (SCENARIO_DIR / "01-llm-usage-accounting-drop.md").read_text()
        # Alert name should appear in at least one scenario
        prom_text = e55_prom_rules.read_text()
        assert "AOSLOLlmUsageAccountingCompletenessBurnRateCritical" in prom_text
        assert "AOSLOLlmUsageAccountingCompletenessBurnRateCritical" in scenario_01
    else:
        # E-5-5 not yet merged; README must explicitly mark deferred boundary.
        assert "PR #800" in readme or "deferred placeholder" in readme.lower()


# ---------------------------------------------------------------------------
# Section 10 — Governance (2 invariants)
# ---------------------------------------------------------------------------


def test_severity_matrix_guard_flags_const_false():
    matrix = load_matrix()
    flags = matrix["guard_flags"]
    assert flags["support_widening_allowed"] is False
    assert flags["production_platform_claim_allowed"] is False
    assert flags["live_adapter_execution_allowed"] is False


def test_no_production_platform_claim_in_active_artifacts():
    """No positive production platform claim language in active artifacts.
    Disclaimer phrases ("Not a production platform claim") are allowed.
    """
    negation_markers = ("not ", "never", "no ", "without ", "non-")
    artifact_paths = [SEVERITY_MATRIX_PATH, ESCALATION_PATH, TEMPLATE_PATH, README_PATH] + [
        SCENARIO_DIR / fname for fname in EXPECTED_SCENARIO_FILES
    ]
    for path in artifact_paths:
        text = path.read_text()
        for line in text.splitlines():
            lowered = line.lower()
            if "production platform" in lowered:
                if any(neg in lowered for neg in negation_markers):
                    continue
                pytest.fail(f"production platform claim in {path.relative_to(REPO_ROOT)}: {line!r}")
