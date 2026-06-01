"""Generate PrometheusRule YAML from docs/sli-catalog.v1.json (V5 Epic 5 E-5-5).

This generator is the source-of-truth artifact for E-5-5 (Alertmanager rule
templates). It reads the SLI/SLO catalog produced by E-5-4 and emits a
deterministic PrometheusRule CRD YAML file containing:

- Recording rules for each ratio SLO (4 windows: 5m, 30m, 1h, 6h) — both the
  raw SLI ratio and the bounded error ratio.
- MWMBR alert rule pairs for each ratio SLO (critical 14.4x over 1h/5m,
  warning 6x over 6h/30m).
- A single recording rule for the budget objective (recording-only; no active
  firing rule per Codex 019e83af absorb F2).
- Recording rules for advisory SLIs (recording-only; no active firing rule per
  F2 absorb — baseline_required pattern).

Codex 019e83af cross-AI plan-time AGREE (4 iters: REVISE/REVISE/REVISE/AGREE).

Out of scope: deployment, Sloth/Pyrra integration, Grafana SLO plugin, live
alert delivery evidence, tenant-bound routing, advisory spike firing rules.

Run: python scripts/generate_alert_rules.py
Drift test: tests/test_alertmanager_rule_templates.py::test_drift_committed_matches_generated
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# F6 absorb: label-selector aware regex (catalog has `{le="30"}` and
# `{final_state="completed"}` selectors).
RATE_5M_PATTERN = re.compile(
    r"rate\("
    r"(?P<metric>[a-zA-Z_:][a-zA-Z0-9_:]*"  # metric name
    r"(?:\{[^{}]*\})?)"  # optional {label="val"} selector
    r"\[5m\]"
    r"\)"
)

# F3 absorb: detect any range selector — used both for source pre-condition
# (must all be [5m]) and post-condition (must all be [target_window]).
RANGE_SELECTOR_PATTERN = re.compile(r"\[([0-9]+[smhdw])\]")

# F3 absorb: subqueries (e.g. [5m:30s]) are out of scope — fail-closed.
SUBQUERY_PATTERN = re.compile(r"\[\d+[smhdw]:[^\]]+\]")

# Codex 019e83af absorb: only these windows are supported by the v1 generator.
ALLOWED_WINDOWS: frozenset[str] = frozenset({"5m", "30m", "1h", "6h"})

# MWMBR pair (Google SRE Workbook §6). Pinned by E-5-4 catalog.
MWMBR_PAIR: tuple[dict[str, Any], dict[str, Any]] = (
    {"severity": "critical", "burn_rate": 14.4, "long_window": "1h", "short_window": "5m"},
    {"severity": "warning", "burn_rate": 6.0, "long_window": "6h", "short_window": "30m"},
)


def windowize(expr: str, target_window: str) -> str:
    """Replace rate(...[5m]) → rate(...[target_window]) in catalog SLI expressions.

    Fail-closed contract (Codex F3/F6/F7 absorb):

    - ``target_window`` must be in :data:`ALLOWED_WINDOWS` (includes ``"5m"``).
    - The source expression must not contain subquery range selectors.
    - Every source range selector must be ``[5m]`` (catalog canonical form).
    - At least one ``rate(...[5m])`` must be found in the source.
    - Post-condition: every range selector in the output is exactly
      ``[target_window]``. This holds for ``target_window == "5m"`` as well
      (idempotent identity — F7 absorb).
    - Post-condition: no subquery range selector may appear in the output.

    Raises :class:`ValueError` on any contract violation.
    """
    if target_window not in ALLOWED_WINDOWS:
        raise ValueError(
            f"unsupported target_window: {target_window!r}; "
            f"allowed: {sorted(ALLOWED_WINDOWS)}"
        )

    if SUBQUERY_PATTERN.search(expr):
        raise ValueError(f"subquery range selector unsupported in source: {expr!r}")

    # Pre-condition: every source range selector must be [5m].
    for m in RANGE_SELECTOR_PATTERN.finditer(expr):
        if m.group(1) != "5m":
            raise ValueError(
                f"non-canonical range selector [{m.group(1)}] in source: {expr!r}"
            )

    if not RATE_5M_PATTERN.search(expr):
        raise ValueError(f"no rate(...[5m]) selector found in source: {expr!r}")

    new_expr = RATE_5M_PATTERN.sub(
        lambda m: f"rate({m.group('metric')}[{target_window}])",
        expr,
    )

    # Post-condition: every generated range selector must be exactly [target_window].
    # Works for target_window == "5m" (idempotent identity).
    generated_ranges = [m.group(1) for m in RANGE_SELECTOR_PATTERN.finditer(new_expr)]
    if not generated_ranges:
        raise ValueError(
            f"no range selector after windowization to [{target_window}]: {new_expr!r}"
        )
    unexpected = [w for w in generated_ranges if w != target_window]
    if unexpected:
        raise ValueError(
            f"unexpected range selector(s) after windowization to "
            f"[{target_window}]: {unexpected}; expr={new_expr!r}"
        )

    if SUBQUERY_PATTERN.search(new_expr):
        raise ValueError(f"subquery produced unexpectedly: {new_expr!r}")

    return new_expr


def bounded_error_expr(sli_recording_rule: str) -> str:
    """Build a bounded error ratio expression from a recorded SLI ratio.

    Codex 019e83af absorb F4: production rules are cleaner with recorded
    error ratios, and bad scrape math cannot create negative burn:

        1 - clamp_max(clamp_min(<sli_recording_rule>, 0), 1)
    """
    return f"1 - clamp_max(clamp_min({sli_recording_rule}, 0), 1)"


def burn_threshold(burn_rate: float, slo_target: float) -> float:
    """Compute MWMBR burn threshold: burn_rate * (1 - slo_target).

    Catalog-derived numeric literal (Codex F4 absorb — no hardcoded thresholds
    in source code; literal appears in generated YAML only).
    """
    return burn_rate * (1.0 - slo_target)


def _sli_recording_name(indicator_name: str, window: str) -> str:
    return f"ao:slo:{indicator_name}:sli_ratio_rate{window}"


def _error_recording_name(indicator_name: str, window: str) -> str:
    return f"ao:slo:{indicator_name}:error_ratio_rate{window}"


def _alert_name(indicator_name: str, severity: str) -> str:
    """Build alert name from indicator + severity.

    Convention: PascalCase, prefixed AOSLO + indicator chunks + Burn + Severity.
    """
    # camel_snake_case → CamelCase
    pascal = "".join(part.capitalize() for part in indicator_name.split("_"))
    return f"AOSLO{pascal}BurnRate{severity.capitalize()}"


def build_recording_rules(indicator: dict[str, Any]) -> list[dict[str, str]]:
    """Build recording rules for one ratio SLO (4 windows × {sli, error})."""
    name = indicator["name"]
    src_expr = indicator["sli_expr"]
    rules: list[dict[str, str]] = []
    for window in sorted(ALLOWED_WINDOWS):
        sli_rec_name = _sli_recording_name(name, window)
        rules.append(
            {
                "record": sli_rec_name,
                "expr": windowize(src_expr, window),
            }
        )
        rules.append(
            {
                "record": _error_recording_name(name, window),
                "expr": bounded_error_expr(sli_rec_name),
            }
        )
    return rules


def build_alert_rules(indicator: dict[str, Any]) -> list[dict[str, Any]]:
    """Build MWMBR alert pair for one ratio SLO (critical + warning)."""
    name = indicator["name"]
    slo_target = indicator["slo_target"]
    alerts: list[dict[str, Any]] = []
    for alert_cfg in MWMBR_PAIR:
        sev: str = alert_cfg["severity"]
        burn: float = alert_cfg["burn_rate"]
        long_w: str = alert_cfg["long_window"]
        short_w: str = alert_cfg["short_window"]
        threshold = burn_threshold(burn, slo_target)
        # Format threshold to a stable decimal repr.
        threshold_str = f"{threshold:.6g}"
        long_rec = _error_recording_name(name, long_w)
        short_rec = _error_recording_name(name, short_w)
        alerts.append(
            {
                "alert": _alert_name(name, sev),
                "expr": (
                    f"{long_rec} > {threshold_str} "
                    f"and {short_rec} > {threshold_str}"
                ),
                "for": "2m",
                "labels": {
                    "severity": sev,
                    "ao_slo": name,
                    "burn_rate": str(burn),
                    "long_window": long_w,
                    "short_window": short_w,
                },
                "annotations": {
                    "summary": (
                        f"SLO {name} burning error budget at {burn}x rate "
                        f"({sev})"
                    ),
                    "description": (
                        f"Error ratio over {long_w} > {threshold_str} AND over "
                        f"{short_w} > {threshold_str}. SLO target {slo_target}, "
                        f"window {indicator['window']}. Not an SLA — "
                        "operator-tunable threshold."
                    ),
                    "runbook_url": (
                        "https://github.com/Halildeu/ao-kernel/blob/main/"
                        "docs/alertmanager/README.md"
                    ),
                },
            }
        )
    return alerts


def build_budget_recording_rule(indicator: dict[str, Any]) -> dict[str, str]:
    """Build the single recording rule for a budget objective.

    Codex F2 absorb: NO active firing alert. Dormant operator overlay lives
    in README only; this PR commits 0 active budget alerts.
    """
    return {
        "record": f"ao:slo:{indicator['name']}:projection_rate1h",
        "expr": indicator["sli_expr"],
    }


def build_advisory_recording_rule(indicator: dict[str, Any]) -> dict[str, str]:
    """Build the single recording rule for an advisory SLI.

    Codex absorb: advisory SLIs are recording-only in v1; firing rules
    require baseline measurement + operator decision.
    """
    return {
        "record": f"ao:slo:{indicator['name']}:rate1h",
        "expr": indicator["sli_expr"],
    }


def render_yaml(catalog: dict[str, Any], catalog_path: str) -> str:
    """Render the full PrometheusRule YAML string.

    Uses a stable, deterministic hand-rolled YAML emitter rather than PyYAML
    so that:

    - The output is identical across Python versions and PyYAML versions.
    - The drift test (byte-equal) is stable.
    - We do not pull in PyYAML as a runtime dep (catalog itself is JSON).
    """
    ratio_indicators = [
        ind for ind in catalog["indicators"] if ind["objective_kind"] == "ratio_slo"
    ]
    budget_indicators = [
        ind for ind in catalog["indicators"] if ind["objective_kind"] == "budget_objective"
    ]
    advisory_indicators = [
        ind for ind in catalog["indicators"] if ind["objective_kind"] == "advisory_sli"
    ]

    lines: list[str] = []
    # H8 absorb: complete header (auto-gen marker, catalog path, schema
    # version, generator path, regeneration command, "DO NOT EDIT").
    lines.extend(
        [
            "# AUTO-GENERATED by scripts/generate_alert_rules.py",
            f"# Source catalog: {catalog_path} (schema: {catalog['schema_version']})",
            "# Regenerate: python scripts/generate_alert_rules.py",
            "# DO NOT EDIT BY HAND — changes will be lost on next regeneration.",
            "# Codex 019e83af cross-AI plan-time AGREE (4 iters: REVISE/REVISE/REVISE/AGREE).",
            "# Not SLA. Not a production platform claim. Operator-tunable defaults.",
            "---",
            "apiVersion: monitoring.coreos.com/v1",
            "kind: PrometheusRule",
            "metadata:",
            "  name: ao-kernel-slo-rules",
            "  labels:",
            "    app.kubernetes.io/name: ao-kernel",
            "    app.kubernetes.io/component: slo",
            "spec:",
            "  groups:",
        ]
    )

    # Group 1: ratio SLO recording rules
    lines.append("    - name: ao-kernel-slo-recording")
    lines.append("      interval: 30s")
    lines.append("      rules:")
    for ind in ratio_indicators:
        for rule in build_recording_rules(ind):
            lines.append(f"        - record: {rule['record']}")
            lines.append(f"          expr: {_yaml_quote(rule['expr'])}")

    # Group 2: ratio SLO MWMBR alerts
    lines.append("    - name: ao-kernel-slo-alerts")
    lines.append("      interval: 30s")
    lines.append("      rules:")
    for ind in ratio_indicators:
        for alert in build_alert_rules(ind):
            lines.append(f"        - alert: {alert['alert']}")
            lines.append(f"          expr: {_yaml_quote(alert['expr'])}")
            lines.append(f"          for: {alert['for']}")
            lines.append("          labels:")
            for k, v in alert["labels"].items():
                lines.append(f"            {k}: {_yaml_quote(v)}")
            lines.append("          annotations:")
            for k, v in alert["annotations"].items():
                lines.append(f"            {k}: {_yaml_quote(v)}")

    # Group 3: budget + advisory recording rules (Codex F2 absorb: recording-only)
    lines.append("    - name: ao-kernel-budget-recording")
    lines.append("      interval: 1m")
    lines.append("      rules:")
    for ind in budget_indicators:
        rule = build_budget_recording_rule(ind)
        lines.append(f"        - record: {rule['record']}")
        lines.append(f"          expr: {_yaml_quote(rule['expr'])}")

    lines.append("    - name: ao-kernel-advisory-recording")
    lines.append("      interval: 1m")
    lines.append("      rules:")
    for ind in advisory_indicators:
        rule = build_advisory_recording_rule(ind)
        lines.append(f"        - record: {rule['record']}")
        lines.append(f"          expr: {_yaml_quote(rule['expr'])}")

    return "\n".join(lines) + "\n"


def _yaml_quote(value: str) -> str:
    """Quote a YAML string value safely.

    Always wraps in double quotes and escapes inner double quotes / backslashes.
    Catalog expressions contain `{le="30"}` etc. so escaping matters.
    """
    if not isinstance(value, str):  # pragma: no cover — defensive only
        return str(value)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def generate(catalog_path: Path, output_path: Path) -> str:
    """Read catalog → render YAML → write to output_path. Returns rendered text."""
    catalog = json.loads(catalog_path.read_text())
    rendered = render_yaml(catalog, str(catalog_path.relative_to(catalog_path.parents[1])))
    output_path.write_text(rendered)
    return rendered


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _repo_root()
    catalog_path = root / "docs" / "sli-catalog.v1.json"
    output_path = root / "docs" / "alertmanager" / "prometheus-rules.v1.yml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate(catalog_path, output_path)
    print(f"generated {output_path.relative_to(root)} from {catalog_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
