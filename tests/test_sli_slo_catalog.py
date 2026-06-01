"""V5 Epic 5 E-5-4 SLI/SLO catalog invariants.

Pins (Codex 019e8394 absorb):

- Schema is Draft 2020-12 with ``additionalProperties: false`` at all
  object nodes (no silent field drift).
- Catalog validates against the schema.
- 3 objective_kind variants pinned: ratio_slo / budget_objective /
  advisory_sli.
- Ratio SLOs declare MWMBR alerts (≥ 2; severity + burn_rate +
  long/short windows pinned).
- Budget objective uses ``unit=usd_per_month`` +
  ``threshold_source=operator_configured`` + ``target_status=placeholder``.
- Advisory SLIs declare ``hard_slo: false`` + ``baseline_required: true``.
- PromQL expressions reference only known ao_* metric families.
- Forbidden label values (e.g. ``outcome="error"``) rejected — the
  v1 metric surface exposes ``outcome=allow|deny`` only.
- Guard flag invariant: 3 flags const false.
- ``uptime_status.in_scope`` const false (Codex absorb — no v1
  health/freshness metric).
- ``docs/SLI-SLO.md`` exists + carries non-SLA / non-production-claim
  / operator-owned discipline language + all indicator names referenced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schema_path() -> Path:
    return _repo_root() / "ao_kernel" / "defaults" / "schemas" / "sli-catalog.schema.v1.json"


def _catalog_path() -> Path:
    return _repo_root() / "docs" / "sli-catalog.v1.json"


def _doc_path() -> Path:
    return _repo_root() / "docs" / "SLI-SLO.md"


def _plan_doc_path() -> Path:
    return _repo_root() / ".claude" / "plans" / "EPIC-5-E5-4-SLI-SLO-DEFINITIONS.md"


def _schema() -> dict[str, Any]:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def _catalog() -> dict[str, Any]:
    return json.loads(_catalog_path().read_text(encoding="utf-8"))


# ── Schema invariants ───────────────────────────────────────────────


def test_schema_file_exists() -> None:
    assert _schema_path().exists()


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_schema())


def test_schema_root_has_additional_properties_false() -> None:
    schema = _schema()
    assert schema.get("additionalProperties") is False


def test_schema_defs_all_use_additional_properties_false() -> None:
    """Every nested object schema must close additionalProperties."""
    schema = _schema()
    defs = schema.get("$defs", {})

    def _walk(node: Any) -> list[str]:
        violations: list[str] = []
        if isinstance(node, dict):
            if node.get("type") == "object" and node.get("additionalProperties") is not False:
                violations.append(json.dumps(node, sort_keys=True)[:80])
            for v in node.values():
                violations.extend(_walk(v))
        elif isinstance(node, list):
            for v in node:
                violations.extend(_walk(v))
        return violations

    leaks = _walk(defs)
    assert not leaks, f"$defs object schemas missing additionalProperties:false: {leaks[:3]}"


# ── Catalog file shape ──────────────────────────────────────────────


def test_catalog_file_exists() -> None:
    assert _catalog_path().exists()


def test_catalog_validates_against_schema() -> None:
    errors = list(Draft202012Validator(_schema()).iter_errors(_catalog()))
    assert not errors, f"catalog schema errors: {[e.message for e in errors[:3]]}"


def test_catalog_schema_version_pinned() -> None:
    assert _catalog()["schema_version"] == "sli-catalog.v1"


def test_catalog_service_pinned() -> None:
    assert _catalog()["service"] == "ao-kernel"


def test_catalog_guard_flags_const_false() -> None:
    flags = _catalog()["guard_flags"]
    assert flags == {
        "support_widening_allowed": False,
        "production_platform_claim_allowed": False,
        "live_adapter_execution_allowed": False,
    }


def test_catalog_uptime_out_of_scope() -> None:
    """Codex 019e8394 absorb — uptime SLI requires a health/freshness
    metric absent from the v1 metric surface."""
    catalog = _catalog()
    assert catalog["uptime_status"]["in_scope"] is False
    assert len(catalog["uptime_status"]["reason"]) >= 16


def test_catalog_has_minimum_three_indicators() -> None:
    assert len(_catalog()["indicators"]) >= 3


# ── Objective kind discipline ───────────────────────────────────────


def _indicators_by_kind() -> dict[str, list[dict[str, Any]]]:
    indicators = _catalog()["indicators"]
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for ind in indicators:
        by_kind.setdefault(ind["objective_kind"], []).append(ind)
    return by_kind


def test_catalog_has_all_three_objective_kinds() -> None:
    by_kind = _indicators_by_kind()
    assert "ratio_slo" in by_kind, "catalog must declare at least one ratio_slo indicator"
    assert "budget_objective" in by_kind, "catalog must declare a budget_objective"
    assert "advisory_sli" in by_kind, "catalog must declare at least one advisory_sli"


def test_ratio_slo_indicators_have_mwmbr_alerts() -> None:
    """Codex 019e8394 absorb — every ratio SLO has ≥ 2 MWMBR alerts
    with critical + warning severity pinned."""
    for ind in _indicators_by_kind().get("ratio_slo", []):
        alerts = ind["error_budget_alerts"]
        assert len(alerts) >= 2, f"{ind['name']}: needs ≥ 2 MWMBR alerts"
        severities = {a["severity"] for a in alerts}
        assert severities == {"critical", "warning"}, (
            f"{ind['name']}: severities must be {{critical, warning}}, got {severities}"
        )
        for alert in alerts:
            assert alert["burn_rate"] > 0
            assert alert["long_window"] in {"5m", "30m", "1h", "6h"}
            assert alert["short_window"] in {"5m", "30m", "1h", "6h"}


def test_ratio_slo_targets_in_open_unit_interval() -> None:
    for ind in _indicators_by_kind().get("ratio_slo", []):
        target = ind["slo_target"]
        assert 0 < target < 1, f"{ind['name']}: slo_target must be (0, 1) exclusive"


def test_budget_objective_pinned_unit_threshold_target_status() -> None:
    for ind in _indicators_by_kind().get("budget_objective", []):
        assert ind["unit"] == "usd_per_month"
        assert ind["threshold_source"] == "operator_configured"
        assert ind["target_status"] == "placeholder"
        assert ind["alerting_kind"] == "budget_alarm"
        assert "slo_target" not in ind, f"{ind['name']}: budget_objective must NOT carry slo_target (Codex absorb)"


def test_advisory_sli_pinned_hard_slo_false_baseline_required_true() -> None:
    for ind in _indicators_by_kind().get("advisory_sli", []):
        assert ind["hard_slo"] is False
        assert ind["baseline_required"] is True
        assert ind["alerting_kind"] == "spike"
        assert "slo_target" not in ind


# ── Non-SLA / non-production-claim discipline ───────────────────────


def test_every_indicator_is_operator_owned_and_not_sla() -> None:
    for ind in _catalog()["indicators"]:
        assert ind["operator_owned"] is True, f"{ind['name']}: operator_owned must be const true"
        assert ind["is_contractual_sla"] is False, f"{ind['name']}: is_contractual_sla must be const false"


# ── PromQL label / metric discipline ────────────────────────────────


_ALLOWED_METRIC_FAMILIES = frozenset(
    {
        "ao_llm_call_duration_seconds",
        "ao_llm_tokens_used_total",
        "ao_llm_cost_usd_total",
        "ao_llm_usage_missing_total",
        "ao_policy_check_total",
        "ao_workflow_duration_seconds",
        "ao_claim_active_total",
        "ao_claim_takeover_total",
    }
)
_HISTOGRAM_SUFFIXES = ("_bucket", "_count", "_sum")
_ALLOWED_POLICY_OUTCOMES = frozenset({"allow", "deny"})


def _extract_ao_references(expr: str) -> list[str]:
    """Pull out ao_* token identifiers from a PromQL expression."""
    return re.findall(r"\bao_[a-zA-Z0-9_]+", expr)


def test_promql_expressions_reference_only_known_metric_families() -> None:
    for ind in _catalog()["indicators"]:
        refs = _extract_ao_references(ind["sli_expr"])
        assert refs, f"{ind['name']}: sli_expr must reference at least one ao_* metric"
        for ref in refs:
            base = ref
            for suffix in _HISTOGRAM_SUFFIXES:
                if ref.endswith(suffix):
                    base = ref[: -len(suffix)]
                    break
            assert base in _ALLOWED_METRIC_FAMILIES, (
                f"{ind['name']}: PromQL references unknown metric {ref!r} (base {base!r} not in v1 metric surface)"
            )


def test_no_indicator_uses_forbidden_outcome_error_label() -> None:
    """Codex 019e8394 absorb — outcome enum is {allow, deny} in v1.
    Any indicator referencing ``outcome="error"`` would be silently
    broken in the runtime."""
    for ind in _catalog()["indicators"]:
        expr = ind["sli_expr"]
        match = re.search(r'outcome="([^"]+)"', expr)
        if match:
            assert match.group(1) in _ALLOWED_POLICY_OUTCOMES, (
                f"{ind['name']}: outcome={match.group(1)!r} not in {_ALLOWED_POLICY_OUTCOMES}"
            )


# ── Indicator name uniqueness ───────────────────────────────────────


def test_indicator_names_are_unique() -> None:
    names = [ind["name"] for ind in _catalog()["indicators"]]
    assert len(names) == len(set(names)), f"duplicate names: {names}"


# ── Operator-facing doc invariants ──────────────────────────────────


def test_sli_slo_doc_exists() -> None:
    assert _doc_path().exists()


def test_sli_slo_doc_carries_non_sla_guard() -> None:
    text = _doc_path().read_text(encoding="utf-8")
    lower = text.lower()
    assert "not sla" in lower or "not a sla" in lower, "doc must say 'Not SLA'"
    assert (
        "not a production platform claim" in lower
        or "not production platform claim" in lower
        or "no production platform claim" in lower
    ), "doc must say 'not a production platform claim'"
    assert "operator-owned" in lower or "operator owned" in lower


def test_sli_slo_doc_records_guard_flag_invariants() -> None:
    text = _doc_path().read_text(encoding="utf-8")
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in text, f"doc must surface {flag} guard flag"


def test_sli_slo_doc_references_every_catalog_indicator() -> None:
    """Doc must mention every catalog SLI by canonical name so the two
    surfaces stay in sync (Codex 019e8394 absorb — generator-free
    invariant)."""
    doc_text = _doc_path().read_text(encoding="utf-8")
    missing = [ind["name"] for ind in _catalog()["indicators"] if ind["name"] not in doc_text]
    assert not missing, f"docs/SLI-SLO.md does not reference catalog SLIs: {missing}"


def test_sli_slo_doc_has_required_sections() -> None:
    text = _doc_path().read_text(encoding="utf-8")
    for section in (
        "## 1. Catalog Layout",
        "## 2. Targets",
        "## 3. Burn-rate Alerts",
        "## 4. Error Budget",
        "## 5. Operator Responsibilities",
        "## 6. Out of Scope",
    ):
        assert section in text, f"missing section: {section}"


# ── Plan doc public claim discipline ────────────────────────────────


def test_plan_doc_exists() -> None:
    assert _plan_doc_path().exists()


def test_plan_doc_records_codex_absorb_table() -> None:
    text = _plan_doc_path().read_text(encoding="utf-8")
    assert "019e8394" in text, "plan doc must reference Codex thread id"
    assert "ratio_slo" in text and "budget_objective" in text and "advisory_sli" in text


def test_plan_doc_pins_guard_flag_invariants() -> None:
    text = _plan_doc_path().read_text(encoding="utf-8")
    for flag in (
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
    ):
        assert flag in text


@pytest.mark.parametrize("phrase", ["not an SLA", "candidate", "operator-tunable"])
def test_plan_doc_uses_non_claim_language(phrase: str) -> None:
    text = _plan_doc_path().read_text(encoding="utf-8")
    assert phrase.lower() in text.lower(), f"plan doc must include phrase: {phrase!r}"
