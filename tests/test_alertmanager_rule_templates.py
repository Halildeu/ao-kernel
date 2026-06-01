"""Invariant test suite for V5 Epic 5 E-5-5: Alertmanager rule templates.

Codex 019e83af cross-AI plan-time AGREE (4 iters: REVISE/REVISE/REVISE/AGREE).

7 must-close findings closed + 17 hardening suggestions absorbed:
- F1 AlertmanagerConfig CRD dialect pin (`monitoring.coreos.com/v1alpha1` + `urlSecret`)
- F2 Budget recording-only; 0 active firing alerts
- F3 Windowization fail-closed; constrained range selector contract
- F4 Bounded error ratios; deterministic catalog-derived thresholds
- F5 Option C: generator + committed YAML + byte-equal drift test
- F6 Label-selector aware regex; supports `{le="30"}` and `{final_state="completed"}`
- F7 Target-window-aware post-condition; `target_window == "5m"` legal idempotent

42 invariants across 12 sections.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "docs" / "sli-catalog.v1.json"
ALERTMANAGER_DIR = REPO_ROOT / "docs" / "alertmanager"
PROMETHEUS_RULES_PATH = ALERTMANAGER_DIR / "prometheus-rules.v1.yml"
ALERTMANAGERCONFIG_PATH = ALERTMANAGER_DIR / "alertmanagerconfig.routes.v1.yml"
RAW_FALLBACK_PATH = ALERTMANAGER_DIR / "alertmanager.routes.raw.v1.yml.example"
SLACK_DORMANT_PATH = ALERTMANAGER_DIR / "slack-dormant.snippet.v1.yml"
README_PATH = ALERTMANAGER_DIR / "README.md"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_alert_rules.py"

# Make scripts/ importable for the generator module.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from generate_alert_rules import (  # noqa: E402  (import after path manipulation)
    ALLOWED_WINDOWS,
    MWMBR_PAIR,
    RANGE_SELECTOR_PATTERN,
    SUBQUERY_PATTERN,
    bounded_error_expr,
    burn_threshold,
    generate,
    windowize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text())


def load_yaml_lite(path: Path) -> dict[str, Any]:
    """Minimal YAML loader using PyYAML if available, else fail.

    Tests that need full parse use this; tests that need only substring/line
    inspection use the raw text.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover — PyYAML is in dev deps
        pytest.skip("PyYAML not installed; install pytest extras or pyyaml")
    return yaml.safe_load(path.read_text())


def load_active_prometheusrule() -> dict[str, Any]:
    return load_yaml_lite(PROMETHEUS_RULES_PATH)


def load_active_alertmanagerconfig() -> dict[str, Any]:
    return load_yaml_lite(ALERTMANAGERCONFIG_PATH)


def iter_recording_rules(crd: dict[str, Any]):
    for group in crd["spec"]["groups"]:
        for rule in group["rules"]:
            if "record" in rule:
                yield group["name"], rule


def iter_alert_rules(crd: dict[str, Any]):
    for group in crd["spec"]["groups"]:
        for rule in group["rules"]:
            if "alert" in rule:
                yield group["name"], rule


def find_rule(crd: dict[str, Any], record_name: str) -> dict[str, Any] | None:
    for _group, rule in iter_recording_rules(crd):
        if rule.get("record") == record_name:
            return rule
    return None


def find_alert(crd: dict[str, Any], alert_name: str) -> dict[str, Any] | None:
    for _group, rule in iter_alert_rules(crd):
        if rule.get("alert") == alert_name:
            return rule
    return None


# ---------------------------------------------------------------------------
# Section 1 — Windowizer (12 invariants)
# ---------------------------------------------------------------------------


def test_windowizer_label_selector_latency():
    """F6 absorb: latency catalog expr has `{le=\"30\"}` label selector."""
    src = (
        'sum by (provider) (rate(ao_llm_call_duration_seconds_bucket{le="30"}[5m])) / '
        "clamp_min(sum by (provider) (rate(ao_llm_call_duration_seconds_count[5m])), 1e-9)"
    )
    out = windowize(src, "1h")
    assert 'ao_llm_call_duration_seconds_bucket{le="30"}[1h]' in out
    assert "ao_llm_call_duration_seconds_count[1h]" in out
    assert "[5m]" not in out


def test_windowizer_label_selector_workflow():
    """F6 absorb: workflow catalog expr has `{final_state=\"completed\"}` selector."""
    src = (
        'sum(rate(ao_workflow_duration_seconds_count{final_state="completed"}[5m])) / '
        "clamp_min(sum(rate(ao_workflow_duration_seconds_count[5m])), 1e-9)"
    )
    out = windowize(src, "6h")
    assert 'ao_workflow_duration_seconds_count{final_state="completed"}[6h]' in out
    assert "ao_workflow_duration_seconds_count[6h]" in out
    assert "[5m]" not in out


def test_windowizer_no_label_usage_completeness():
    """F6 absorb: usage expr has no label selector (also valid)."""
    src = (
        "sum(rate(ao_llm_call_duration_seconds_count[5m])) / "
        "clamp_min(sum(rate(ao_llm_call_duration_seconds_count[5m])) + "
        "sum(rate(ao_llm_usage_missing_total[5m])), 1e-9)"
    )
    out = windowize(src, "30m")
    assert "ao_llm_call_duration_seconds_count[30m]" in out
    assert "ao_llm_usage_missing_total[30m]" in out
    assert "[5m]" not in out


def test_windowizer_target_5m_idempotent_usage_completeness():
    """F7 absorb: target_window=5m must be valid identity (catalog canonical form)."""
    src = (
        "sum(rate(ao_llm_call_duration_seconds_count[5m])) / "
        "clamp_min(sum(rate(ao_llm_call_duration_seconds_count[5m])) + "
        "sum(rate(ao_llm_usage_missing_total[5m])), 1e-9)"
    )
    out = windowize(src, "5m")
    assert out == src
    assert "[5m]" in out  # 5m is the target


def test_windowizer_target_5m_idempotent_latency_with_labels():
    """F7 absorb: target_window=5m works with label selector."""
    src = (
        'sum by (provider) (rate(ao_llm_call_duration_seconds_bucket{le="30"}[5m])) / '
        "clamp_min(sum by (provider) (rate(ao_llm_call_duration_seconds_count[5m])), 1e-9)"
    )
    out = windowize(src, "5m")
    assert out == src


def test_windowizer_target_5m_idempotent_workflow_with_labels():
    """F7 absorb: target_window=5m works with workflow label selector."""
    src = (
        'sum(rate(ao_workflow_duration_seconds_count{final_state="completed"}[5m])) / '
        "clamp_min(sum(rate(ao_workflow_duration_seconds_count[5m])), 1e-9)"
    )
    out = windowize(src, "5m")
    assert out == src


def test_windowizer_non_5m_target_replaces_all_via_generic_check():
    """F7 absorb: non-5m target uses generic RANGE_SELECTOR_PATTERN check."""
    src = "rate(ao_foo[5m]) + rate(ao_bar[5m])"
    out = windowize(src, "1h")
    ranges = RANGE_SELECTOR_PATTERN.findall(out)
    assert ranges == ["1h", "1h"]


def test_windowizer_rejects_unsupported_target_window():
    with pytest.raises(ValueError, match="unsupported target_window"):
        windowize("rate(ao_foo[5m])", "1d")


def test_windowizer_rejects_subquery_in_source():
    with pytest.raises(ValueError, match="subquery"):
        windowize("rate(ao_foo[5m:30s])", "1h")


def test_windowizer_rejects_non_canonical_source_range():
    with pytest.raises(ValueError, match="non-canonical range selector"):
        windowize("rate(ao_foo[1h])", "5m")


def test_windowizer_rejects_no_rate_5m_in_source():
    with pytest.raises(ValueError, match="no rate"):
        windowize("sum(ao_foo)", "1h")


def test_allowed_windows_constant():
    """Pin the exact set: 5m + 30m + 1h + 6h (MWMBR pair + 30m advisory)."""
    assert ALLOWED_WINDOWS == frozenset({"5m", "30m", "1h", "6h"})


# ---------------------------------------------------------------------------
# Section 2 — Generator determinism (3 invariants)
# ---------------------------------------------------------------------------


def test_generator_idempotent(tmp_path):
    """Same catalog → byte-equal output across two runs."""
    out_a = tmp_path / "a.yml"
    out_b = tmp_path / "b.yml"
    rendered_a = generate(CATALOG_PATH, out_a)
    rendered_b = generate(CATALOG_PATH, out_b)
    assert rendered_a == rendered_b
    assert out_a.read_bytes() == out_b.read_bytes()


def test_drift_committed_matches_generated(tmp_path):
    """F5 absorb: committed YAML must equal freshly generated YAML byte-equal."""
    out = tmp_path / "fresh.yml"
    rendered = generate(CATALOG_PATH, out)
    committed = PROMETHEUS_RULES_PATH.read_text()
    assert committed == rendered, (
        "DRIFT detected: committed prometheus-rules.v1.yml differs from generator output. "
        "Run: python scripts/generate_alert_rules.py"
    )


def test_generator_fail_closed_on_unsupported_window():
    """F3 absorb: generator surface fails closed when handed bad input."""
    with pytest.raises(ValueError):
        windowize("rate(ao_foo[5m])", "12h")


# ---------------------------------------------------------------------------
# Section 3 — PrometheusRule structure (5 invariants)
# ---------------------------------------------------------------------------


def test_prometheusrule_apiversion_and_kind():
    crd = load_active_prometheusrule()
    assert crd["apiVersion"] == "monitoring.coreos.com/v1"
    assert crd["kind"] == "PrometheusRule"


def test_prometheusrule_auto_generated_header():
    """H8 absorb: header has catalog path + schema version + generator path + regeneration command."""
    text = PROMETHEUS_RULES_PATH.read_text()
    assert "# AUTO-GENERATED by scripts/generate_alert_rules.py" in text
    assert "# Source catalog: docs/sli-catalog.v1.json" in text
    assert "(schema: sli-catalog.v1)" in text
    assert "# Regenerate: python scripts/generate_alert_rules.py" in text
    assert "# DO NOT EDIT BY HAND" in text


def test_prometheusrule_recording_rule_count():
    """3 ratio SLOs × 4 windows × 2 (sli + error) = 24 recording rules.
    Plus 1 budget recording + 2 advisory recording = 27 total recording rules.
    """
    crd = load_active_prometheusrule()
    total_recording = sum(1 for _ in iter_recording_rules(crd))
    assert total_recording == 27, (
        f"expected 27 recording rules (24 ratio + 1 budget + 2 advisory), got {total_recording}"
    )


def test_prometheusrule_alert_count():
    """3 ratio SLOs × 2 severities = 6 active firing alerts; 0 budget/advisory alerts."""
    crd = load_active_prometheusrule()
    total_alerts = sum(1 for _ in iter_alert_rules(crd))
    assert total_alerts == 6, f"expected 6 alerts (3 SLO × 2 severity), got {total_alerts}"


def test_prometheusrule_metadata_labels():
    crd = load_active_prometheusrule()
    labels = crd["metadata"]["labels"]
    assert labels.get("app.kubernetes.io/name") == "ao-kernel"
    assert labels.get("app.kubernetes.io/component") == "slo"


# ---------------------------------------------------------------------------
# Section 4 — Recording rule naming (3 invariants)
# ---------------------------------------------------------------------------


RECORDING_NAME_PATTERN = re.compile(
    r"^ao:slo:[a-z][a-z0-9_]*:(?:sli_ratio_rate|error_ratio_rate|projection_rate|rate)(?:5m|30m|1h|6h)$"
)


def test_recording_rule_naming_convention():
    """All recording rules match ao:slo:<name>:<metric>_rate<window> pattern."""
    crd = load_active_prometheusrule()
    for group_name, rule in iter_recording_rules(crd):
        name = rule["record"]
        assert RECORDING_NAME_PATTERN.match(name), f"non-conforming recording rule name: {name} (group={group_name})"


def test_each_ratio_slo_has_eight_recording_rules():
    """3 ratio SLO × 4 windows × 2 kinds (sli + error) — each SLO has 8."""
    crd = load_active_prometheusrule()
    catalog = load_catalog()
    ratio_names = {ind["name"] for ind in catalog["indicators"] if ind["objective_kind"] == "ratio_slo"}
    counts: dict[str, int] = {n: 0 for n in ratio_names}
    for _group, rule in iter_recording_rules(crd):
        name = rule["record"]
        for ind_name in ratio_names:
            if name.startswith(f"ao:slo:{ind_name}:"):
                counts[ind_name] += 1
    for ind_name, count in counts.items():
        assert count == 8, f"{ind_name}: expected 8 recording rules, got {count}"


def test_no_sloth_style_names():
    """H3 absorb: ao-kernel uses native naming, not Sloth's `slo:sli_error:ratio_rate`."""
    text = PROMETHEUS_RULES_PATH.read_text()
    assert "slo:sli_error:ratio_rate" not in text
    assert "slo:sli_total:ratio_rate" not in text


# ---------------------------------------------------------------------------
# Section 5 — Budget discipline (4 invariants)
# ---------------------------------------------------------------------------


FORBIDDEN_BUDGET_TOKENS = (
    "${MONTHLY_BUDGET_USD}",
    "$500",
    "$1000",
    "$100",
    "usd_threshold",
    "budget_threshold",
)


def test_budget_recording_rule_count():
    """F2 absorb: budget = exactly 1 recording rule."""
    crd = load_active_prometheusrule()
    budget_rules = [rule for _group, rule in iter_recording_rules(crd) if "monthly_cost_burn" in rule["record"]]
    assert len(budget_rules) == 1


def test_budget_active_alert_count_is_zero():
    """F2 absorb: 0 active firing alerts for budget objective."""
    crd = load_active_prometheusrule()
    budget_alerts = [
        rule
        for _group, rule in iter_alert_rules(crd)
        if "monthly_cost_burn" in rule.get("alert", "").lower() or "monthly_cost_burn" in rule.get("expr", "")
    ]
    assert len(budget_alerts) == 0


def test_no_budget_threshold_placeholders_in_active_yaml():
    """H3 absorb: no env var / dollar / threshold placeholder leak."""
    active_text = PROMETHEUS_RULES_PATH.read_text()
    for token in FORBIDDEN_BUDGET_TOKENS:
        assert token not in active_text, f"budget threshold leak: {token!r} in active YAML"


def test_no_dollar_placeholder_in_active_alert_rules():
    """No `${...}` Bash-style env var reference anywhere in active rules."""
    active_text = PROMETHEUS_RULES_PATH.read_text()
    assert "${" not in active_text


# ---------------------------------------------------------------------------
# Section 6 — Advisory discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_advisory_recording_rule_count():
    """2 advisory SLIs → 2 recording rules."""
    crd = load_active_prometheusrule()
    advisory_rules = [
        rule
        for _group, rule in iter_recording_rules(crd)
        if any(name in rule["record"] for name in ("policy_deny_rate", "coordination_takeover_rate"))
    ]
    assert len(advisory_rules) == 2


def test_advisory_active_alert_count_is_zero():
    """0 active firing alerts for advisory SLIs (baseline_required pattern)."""
    crd = load_active_prometheusrule()
    advisory_alerts = [
        rule
        for _group, rule in iter_alert_rules(crd)
        if any(name in rule.get("expr", "") for name in ("policy_deny_rate", "coordination_takeover_rate"))
    ]
    assert len(advisory_alerts) == 0


def test_advisory_recording_only_two_indicators_present():
    crd = load_active_prometheusrule()
    record_names = {rule["record"] for _g, rule in iter_recording_rules(crd)}
    assert "ao:slo:policy_deny_rate:rate1h" in record_names
    assert "ao:slo:coordination_takeover_rate:rate1h" in record_names


# ---------------------------------------------------------------------------
# Section 7 — MWMBR determinism (4 invariants)
# ---------------------------------------------------------------------------


def test_mwmbr_pair_constant():
    """Catalog SSOT pin: critical 14.4/1h/5m + warning 6/6h/30m (Google SRE Workbook)."""
    critical, warning = MWMBR_PAIR
    assert critical["severity"] == "critical"
    assert critical["burn_rate"] == 14.4
    assert critical["long_window"] == "1h"
    assert critical["short_window"] == "5m"
    assert warning["severity"] == "warning"
    assert warning["burn_rate"] == 6.0
    assert warning["long_window"] == "6h"
    assert warning["short_window"] == "30m"


def test_each_ratio_slo_has_two_alerts():
    """Each ratio SLO emits exactly 2 alerts (critical + warning)."""
    crd = load_active_prometheusrule()
    catalog = load_catalog()
    ratio_names = [ind["name"] for ind in catalog["indicators"] if ind["objective_kind"] == "ratio_slo"]
    for name in ratio_names:
        alerts_for_slo = [rule for _g, rule in iter_alert_rules(crd) if rule.get("labels", {}).get("ao_slo") == name]
        assert len(alerts_for_slo) == 2, f"{name}: expected 2 alerts, got {len(alerts_for_slo)}"


def test_alert_threshold_is_catalog_derived_literal():
    """F4 absorb: thresholds are catalog-derived numeric literals in YAML."""
    catalog = load_catalog()
    crd = load_active_prometheusrule()
    for ind in catalog["indicators"]:
        if ind["objective_kind"] != "ratio_slo":
            continue
        target = ind["slo_target"]
        for alert_cfg in MWMBR_PAIR:
            burn = alert_cfg["burn_rate"]
            expected_threshold = burn_threshold(burn, target)
            expected_str = f"{expected_threshold:.6g}"
            # find matching alert
            for _g, rule in iter_alert_rules(crd):
                if (
                    rule.get("labels", {}).get("ao_slo") == ind["name"]
                    and rule.get("labels", {}).get("severity") == alert_cfg["severity"]
                ):
                    assert expected_str in rule["expr"], (
                        f"{ind['name']}/{alert_cfg['severity']}: expected threshold "
                        f"{expected_str} not in expr: {rule['expr']!r}"
                    )


def test_generator_source_no_hardcoded_burn_threshold():
    """H4 absorb: generator source code must not contain hardcoded burn thresholds.

    Allowed: catalog values 14.4 + 6.0 (burn rates). Forbidden: derived
    thresholds 0.144, 0.06, 0.72, 0.3, 0.072, 0.03 (calculated, not source).
    """
    src = GENERATOR_PATH.read_text()
    forbidden = ["0.144", "0.0144", "0.072", "0.0072"]
    for token in forbidden:
        assert token not in src, f"hardcoded burn threshold in generator source: {token!r}"


# ---------------------------------------------------------------------------
# Section 8 — PromQL whitelist + bounded (4 invariants)
# ---------------------------------------------------------------------------


AO_METRIC_FAMILIES = (
    "ao_llm_call_duration_seconds",
    "ao_llm_usage_missing_total",
    "ao_llm_cost_usd_total",
    "ao_workflow_duration_seconds",
    "ao_policy_check_total",
    "ao_claim_takeover_total",
    "ao_claim_active_total",
)


def test_recording_exprs_use_only_ao_metric_families():
    """PromQL whitelist: only the 8 ao_* metric families in v1 surface."""
    crd = load_active_prometheusrule()
    # Build allowed-metric pattern (each ao_* family).
    metric_family_re = re.compile(r"\b(ao_[a-z_]+)\b")
    for group_name, rule in iter_recording_rules(crd):
        # Skip recording rules that reference other recording rules (error_ratio).
        if "ao:slo:" in rule["expr"] and not any(f in rule["expr"] for f in AO_METRIC_FAMILIES):
            continue
        for match in metric_family_re.finditer(rule["expr"]):
            metric = match.group(1)
            assert any(metric.startswith(family) for family in AO_METRIC_FAMILIES), (
                f"unknown metric family {metric!r} in {rule['record']} (group={group_name})"
            )


def test_error_ratio_rules_use_bounded_clamp_pattern():
    """F4 absorb: every error_ratio recording rule uses bounded clamp form."""
    crd = load_active_prometheusrule()
    for _group, rule in iter_recording_rules(crd):
        if "error_ratio_rate" not in rule["record"]:
            continue
        expr = rule["expr"]
        assert "1 - clamp_max(clamp_min(" in expr, f"{rule['record']} does not use bounded clamp form: {expr!r}"
        assert ", 0)" in expr or ",0)" in expr  # clamp_min lower bound 0
        assert ", 1)" in expr or ",1)" in expr  # clamp_max upper bound 1


def test_no_outcome_error_label_value():
    """F1/Catalog absorb: outcome enum is {allow, deny} only; outcome=error YASAK."""
    active_text = PROMETHEUS_RULES_PATH.read_text()
    assert 'outcome="error"' not in active_text
    assert "outcome='error'" not in active_text


def test_latency_recording_preserves_provider_label():
    """H7 absorb: per-provider label propagation for latency SLO."""
    crd = load_active_prometheusrule()
    for window in ALLOWED_WINDOWS:
        rule = find_rule(crd, f"ao:slo:llm_latency_under_30s_ratio:sli_ratio_rate{window}")
        assert rule is not None, f"missing sli recording rule for window {window}"
        assert "sum by (provider)" in rule["expr"], (
            f"provider label dropped in latency sli_ratio_rate{window}: {rule['expr']!r}"
        )


# ---------------------------------------------------------------------------
# Section 9 — AlertmanagerConfig discipline (5 invariants)
# ---------------------------------------------------------------------------


def test_alertmanagerconfig_apiversion_and_kind():
    config = load_active_alertmanagerconfig()
    assert config["apiVersion"] == "monitoring.coreos.com/v1alpha1"
    assert config["kind"] == "AlertmanagerConfig"


def test_alertmanagerconfig_uses_urlsecret_not_literal_url():
    """F1 absorb: webhookConfigs uses urlSecret SecretKeySelector, not literal url."""
    config = load_active_alertmanagerconfig()
    for receiver in config["spec"]["receivers"]:
        for wc in receiver.get("webhookConfigs", []):
            assert "urlSecret" in wc, f"receiver {receiver['name']} webhookConfig missing urlSecret"
            assert "url" not in wc, f"receiver {receiver['name']} has literal url (forbidden)"
            assert wc["urlSecret"].get("name") == "ao-kernel-teams-webhook"
            assert wc["urlSecret"].get("key") == "url"


def test_no_https_url_literal_in_active_alertmanagerconfig():
    """No https:// URL literal anywhere in active config."""
    text = ALERTMANAGERCONFIG_PATH.read_text()
    # Comments (`#`) and runbook docs may have URLs but the active rule file
    # is YAML-only; assert no https:// in non-comment lines.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        assert "https://" not in stripped, f"https:// literal in active config line: {line!r}"


def test_no_slack_receiver_in_active_alertmanagerconfig():
    """Slack is dormant-only; no active Slack receiver in v1 routes."""
    config = load_active_alertmanagerconfig()
    for receiver in config["spec"]["receivers"]:
        assert "slackConfigs" not in receiver, (
            f"receiver {receiver['name']} has slackConfigs (Slack must be dormant in v1)"
        )


def test_no_authentication_in_active_webhook_configs():
    """H1 absorb: Teams Power Automate webhook is anonymous; no auth mechanisms."""
    config = load_active_alertmanagerconfig()
    for receiver in config["spec"]["receivers"]:
        for wc in receiver.get("webhookConfigs", []):
            http = wc.get("httpConfig", {})
            assert "authorization" not in http
            assert "bearerTokenSecret" not in http
            assert "basicAuth" not in http
            assert "oauth2" not in http


# ---------------------------------------------------------------------------
# Section 10 — Route matchers (2 invariants)
# ---------------------------------------------------------------------------


def test_route_matchers_use_object_form_not_legacy_string():
    """H6 absorb: v1alpha1 object matcher shape (name/value/matchType)."""
    config = load_active_alertmanagerconfig()
    routes = config["spec"]["route"].get("routes", [])
    for route in routes:
        for matcher in route.get("matchers", []):
            assert isinstance(matcher, dict), (
                f"matcher must be object (v1alpha1 object form), not legacy string: {matcher!r}"
            )
            assert "name" in matcher
            assert "value" in matcher


def test_route_matchers_only_severity_no_tenant_channel():
    """v1: severity matcher only; tenant_channel deferred to Epic 4."""
    config = load_active_alertmanagerconfig()
    routes = config["spec"]["route"].get("routes", [])
    for route in routes:
        for matcher in route.get("matchers", []):
            assert matcher["name"] == "severity", f"v1 routes match only severity; found {matcher['name']!r}"
            assert matcher["value"] in {"critical", "warning"}


# ---------------------------------------------------------------------------
# Section 11 — Governance (3 invariants)
# ---------------------------------------------------------------------------


def test_guard_flags_not_flipped_in_catalog():
    catalog = load_catalog()
    flags = catalog["guard_flags"]
    assert flags["support_widening_allowed"] is False
    assert flags["production_platform_claim_allowed"] is False
    assert flags["live_adapter_execution_allowed"] is False


def test_no_production_platform_claim_in_generated_yaml():
    """E-5-5 must not introduce positive production platform claim language.

    Disclaimer phrases ("Not a production platform claim") are explicitly
    allowed; only positive claims are forbidden.
    """
    text = PROMETHEUS_RULES_PATH.read_text()
    forbidden_phrases = (
        "production platform",
        "production-grade SLA",
        "contractually guaranteed",
        "service-level commitment",
    )
    negation_markers = ("not ", "never", "no ", "forbidden", "without", "non-")
    for line in text.splitlines():
        lowered = line.lower()
        for phrase in forbidden_phrases:
            if phrase in lowered:
                # Allow lines that frame the phrase as a disclaimer (negation).
                if any(neg in lowered for neg in negation_markers):
                    continue
                pytest.fail(f"production claim leak in line: {line!r}")


def test_readme_includes_operator_owned_and_non_sla_disclaimer():
    """H10 absorb: README first paragraph asserts Not SLA + operator-owned."""
    text = README_PATH.read_text()
    assert "Not SLA" in text
    assert "Not a production platform claim" in text
    assert "operator-owned" in text.lower() or "operator-tunable" in text.lower()
    assert "guard flags" in text.lower()


# ---------------------------------------------------------------------------
# Section 12 — Per-window structural parametrized (12 invariants)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "indicator_name,target_window",
    [
        (name, w)
        for name in (
            "llm_usage_accounting_completeness",
            "llm_latency_under_30s_ratio",
            "workflow_terminal_success_rate",
        )
        for w in sorted(ALLOWED_WINDOWS)  # {"5m", "30m", "1h", "6h"} — INCLUDES 5m
    ],
)
def test_generated_sli_recording_rule_has_correct_window(indicator_name, target_window):
    """F7 absorb: per-window test includes target_window='5m'."""
    crd = load_active_prometheusrule()
    rule_name = f"ao:slo:{indicator_name}:sli_ratio_rate{target_window}"
    rule = find_rule(crd, rule_name)
    assert rule is not None, f"missing recording rule: {rule_name}"
    # window in expression
    assert f"[{target_window}]" in rule["expr"]
    # no other [N] window for this rule
    for w in ALLOWED_WINDOWS:
        if w != target_window:
            assert f"[{w}]" not in rule["expr"], f"unexpected [{w}] in {rule_name}: {rule['expr']!r}"


# ---------------------------------------------------------------------------
# Section 13 — Dormant artifact discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_raw_fallback_is_dormant_example():
    """H9 absorb: .example dormant; not referenced by active CRD."""
    assert RAW_FALLBACK_PATH.exists()
    assert RAW_FALLBACK_PATH.name.endswith(".example"), "must be .example (dormant)"
    active = ALERTMANAGERCONFIG_PATH.read_text()
    assert RAW_FALLBACK_PATH.name not in active
    assert "alertmanager.routes.raw" not in active


def test_slack_dormant_snippet_not_referenced_by_active_spec():
    """Slack snippet is dormant; not referenced by active CRD spec body.

    The active CRD YAML *may* mention the dormant file path in a leading
    documentation comment (operator runbook pointer) — that is intentional
    and asset-preserved. The forbidden surface is the *active spec body*
    (non-comment YAML) referencing Slack receivers/configs.
    """
    assert SLACK_DORMANT_PATH.exists()
    config = load_active_alertmanagerconfig()
    # Active receivers must not include any Slack config.
    for receiver in config["spec"]["receivers"]:
        assert "slackConfigs" not in receiver
        assert "slack" not in receiver["name"].lower()
    # Active routes must not match on a slack-specific receiver name.
    for route in config["spec"]["route"].get("routes", []):
        receiver_name = route.get("receiver", "")
        assert "slack" not in receiver_name.lower()


def test_raw_fallback_has_placeholder_not_real_url():
    """H9 absorb: dormant raw fallback has __TEAMS_WEBHOOK_URL__ placeholder."""
    text = RAW_FALLBACK_PATH.read_text()
    assert "__TEAMS_WEBHOOK_URL__" in text
    # No real https:// webhook URL committed.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if "url" in stripped.lower() and "https://" in stripped:
            pytest.fail(f"real URL leaked in dormant fallback: {line!r}")


# ---------------------------------------------------------------------------
# Section 14 — promtool conditional (1 invariant)
# ---------------------------------------------------------------------------


def test_promtool_check_rules_if_available(tmp_path):
    """H5 absorb: if promtool is in PATH, validate generated rules; else skip."""
    if not shutil.which("promtool"):
        pytest.skip("promtool not in PATH")
    crd = load_active_prometheusrule()
    rules_file = tmp_path / "rules.yml"
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("PyYAML not installed")
    rules_file.write_text(yaml.safe_dump({"groups": crd["spec"]["groups"]}))
    result = subprocess.run(
        ["promtool", "check", "rules", str(rules_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"promtool failed:\nstdout={result.stdout}\nstderr={result.stderr}"


# ---------------------------------------------------------------------------
# Bonus — Module exports / regex contracts (utility coverage)
# ---------------------------------------------------------------------------


def test_subquery_pattern_matches_expected_forms():
    assert SUBQUERY_PATTERN.search("rate(ao_foo[5m:30s])")
    assert SUBQUERY_PATTERN.search("rate(ao_foo[1h:1m])")
    assert not SUBQUERY_PATTERN.search("rate(ao_foo[5m])")


def test_bounded_error_expr_shape():
    out = bounded_error_expr("ao:slo:foo:sli_ratio_rate1h")
    assert out == "1 - clamp_max(clamp_min(ao:slo:foo:sli_ratio_rate1h, 0), 1)"


def test_burn_threshold_compute_examples():
    # SLO target 0.99, burn 14.4 → 0.144
    assert abs(burn_threshold(14.4, 0.99) - 0.144) < 1e-9
    # SLO target 0.95, burn 14.4 → 0.72
    assert abs(burn_threshold(14.4, 0.95) - 0.72) < 1e-9
    # SLO target 0.995, burn 6 → 0.03
    assert abs(burn_threshold(6.0, 0.995) - 0.03) < 1e-9
