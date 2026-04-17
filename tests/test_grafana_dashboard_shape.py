"""Shape test for the bundled Grafana dashboard (PR-B5 C4).

Pins the panel → metric matrix declared in `docs/grafana/README.md`
so that an operator-facing dashboard edit cannot silently drop a
metric from the matrix without breaking the test. Also covers:

- Valid JSON + schema version compatibility.
- Eight panels (seven visible panels in the default + one that was
  merged but we count based on plan v4 §2.8).
- Each panel's first target expression references the expected
  metric name from the plan.
- Datasource template variable present for portable import.
"""

from __future__ import annotations

import json
from pathlib import Path


_DASHBOARD_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "grafana"
    / "ao_kernel_default.v1.json"
)


# Panel title → metric family substring that must appear in the
# first target's ``expr``. Derived from plan v4 §2.8 panel-matrix.
_EXPECTED_PANELS: dict[str, str] = {
    "LLM call duration p95 (by provider)": "ao_llm_call_duration_seconds",
    "LLM tokens/s (by provider + direction)": "ao_llm_tokens_used_total",
    "LLM cost (USD/hour, by provider)": "ao_llm_cost_usd_total",
    "LLM usage-missing rate (by provider)": "ao_llm_usage_missing_total",
    "Policy deny rate": "ao_policy_check_total",
    "Workflow duration p95 (by final_state)": "ao_workflow_duration_seconds",
    "Active coordination claims": "ao_claim_active_total",
    "Claim takeovers (last 1h)": "ao_claim_takeover_total",
}


def _load_dashboard() -> dict:
    return json.loads(_DASHBOARD_PATH.read_text(encoding="utf-8"))


class TestStructure:
    def test_dashboard_file_exists(self) -> None:
        assert _DASHBOARD_PATH.is_file(), (
            f"bundled dashboard missing at {_DASHBOARD_PATH}"
        )

    def test_dashboard_is_valid_json(self) -> None:
        # Raises JSONDecodeError on failure.
        doc = _load_dashboard()
        assert isinstance(doc, dict)

    def test_schema_version_recent(self) -> None:
        """Grafana 10+ ships schemaVersion 38; older versions still
        import but with warnings."""
        doc = _load_dashboard()
        assert doc["schemaVersion"] >= 30


class TestPanels:
    def test_eight_panels_present(self) -> None:
        doc = _load_dashboard()
        assert len(doc["panels"]) == 8

    def test_panel_title_to_metric_matrix(self) -> None:
        """Every panel's first target must reference the metric family
        declared in plan v4 §2.8. Drift between dashboard and
        runtime (e.g., a renamed metric) fails this test."""
        doc = _load_dashboard()
        seen: dict[str, str] = {}
        for panel in doc["panels"]:
            title = panel["title"]
            expr = panel["targets"][0]["expr"]
            seen[title] = expr

        missing_titles = set(_EXPECTED_PANELS.keys()) - set(seen.keys())
        assert not missing_titles, (
            f"dashboard missing expected panels: {sorted(missing_titles)}"
        )
        for title, metric_fragment in _EXPECTED_PANELS.items():
            assert metric_fragment in seen[title], (
                f"panel {title!r} expr does not reference {metric_fragment!r}; "
                f"got: {seen[title]!r}"
            )

    def test_every_panel_has_gridpos(self) -> None:
        """Layout drift — missing gridPos breaks auto-arrangement."""
        doc = _load_dashboard()
        for panel in doc["panels"]:
            assert "gridPos" in panel, (
                f"panel {panel.get('title')!r} missing gridPos"
            )


class TestTemplating:
    def test_datasource_variable_present(self) -> None:
        """Importable dashboards must expose a datasource template so
        operators can bind Prometheus without editing the JSON."""
        doc = _load_dashboard()
        names = {v["name"] for v in doc["templating"]["list"]}
        assert "DS_PROMETHEUS" in names


class TestDocsParity:
    def test_readme_mentions_each_expected_panel(self) -> None:
        """The Grafana README panel-matrix table must list every
        expected title so operators can trace panels back to metric
        families."""
        readme_path = _DASHBOARD_PATH.parent / "README.md"
        text = readme_path.read_text(encoding="utf-8")
        for metric in _EXPECTED_PANELS.values():
            assert metric in text, (
                f"README.md does not document metric {metric!r}"
            )
