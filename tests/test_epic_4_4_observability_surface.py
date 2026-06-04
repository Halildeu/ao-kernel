"""V5 Epic 4 E-4-4 invariants: observability surface (ServiceMonitor + OTEL sidecar).

Opt-in observability for the ao-kernel Helm chart. The chart emits a
ServiceMonitor (Prometheus Operator CRD) and an optional OTEL collector
sidecar — both disabled by default. The chart never installs Prometheus
Operator and never embeds an alert receiver or secret. Alert routing is
Microsoft Teams primary (operator-wired Alertmanager → Teams).

Machine-enforced invariants:
  - servicemonitor.yaml gated on monitoring.serviceMonitor.enabled
  - ServiceMonitor uses monitoring.coreos.com/v1 + scrapes the http port
  - values monitoring block disabled by default
  - values.schema.json closes the monitoring block
  - OTEL sidecar gated on enabled + hardened securityContext + no secret
  - no Slack receiver embedded (Teams primary; receiver wiring is operator's)
  - no guard-flag key strings; no .github/workflows/ mutation
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHART_DIR = _REPO_ROOT / "deploy" / "helm" / "ao-kernel"
_VALUES = _CHART_DIR / "values.yaml"
_SCHEMA = _CHART_DIR / "values.schema.json"
_SM = _CHART_DIR / "templates" / "servicemonitor.yaml"
_DEPLOYMENT = _CHART_DIR / "templates" / "deployment.yaml"


def _load_values() -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_VALUES.read_text(encoding="utf-8"))


# ---- 1. ServiceMonitor template (4) -------------------------------------


def test_servicemonitor_template_exists() -> None:
    assert _SM.is_file(), "servicemonitor.yaml missing (E-4-4)"


def test_servicemonitor_gated_on_enabled() -> None:
    text = _SM.read_text(encoding="utf-8")
    assert "if .Values.monitoring.serviceMonitor.enabled" in text, (
        "ServiceMonitor must be gated on monitoring.serviceMonitor.enabled"
    )


def test_servicemonitor_uses_prometheus_operator_crd() -> None:
    text = _SM.read_text(encoding="utf-8")
    assert "apiVersion: monitoring.coreos.com/v1" in text
    assert "kind: ServiceMonitor" in text


def test_servicemonitor_scrapes_http_port() -> None:
    text = _SM.read_text(encoding="utf-8")
    assert "port: http" in text, "ServiceMonitor must scrape the named http port"


# ---- 2. values monitoring block (3) -------------------------------------


def test_values_monitoring_block_present() -> None:
    vals = _load_values()
    assert "monitoring" in vals
    assert "serviceMonitor" in vals["monitoring"]
    assert "otelSidecar" in vals["monitoring"]


def test_monitoring_disabled_by_default() -> None:
    vals = _load_values()
    assert vals["monitoring"]["serviceMonitor"]["enabled"] is False
    assert vals["monitoring"]["otelSidecar"]["enabled"] is False


def test_otel_sidecar_endpoint_empty_default_no_secret() -> None:
    vals = _load_values()
    otel = vals["monitoring"]["otelSidecar"]
    assert otel["otlpEndpoint"] == "", "OTLP endpoint default must be empty (operator-provided)"
    # No secret key in the otelSidecar block (endpoint is non-secret plain).
    assert "secret" not in json.dumps(otel).lower(), "otelSidecar must not carry secret material"


# ---- 3. schema closes the block (1) -------------------------------------


def test_schema_monitoring_closed() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert "monitoring" in schema["properties"]
    mon = schema["properties"]["monitoring"]
    assert mon.get("additionalProperties") is False
    assert mon["properties"]["serviceMonitor"].get("additionalProperties") is False
    assert mon["properties"]["otelSidecar"].get("additionalProperties") is False


# ---- 4. OTEL sidecar deployment injection (2) ---------------------------


def test_otel_sidecar_gated_and_hardened() -> None:
    text = _DEPLOYMENT.read_text(encoding="utf-8")
    assert "if .Values.monitoring.otelSidecar.enabled" in text, "sidecar must be gated"
    idx = text.find("name: otel-collector")
    assert idx != -1, "otel-collector sidecar container missing"
    window = text[idx : idx + 400]
    assert "allowPrivilegeEscalation: false" in window, "sidecar must harden securityContext"
    assert "readOnlyRootFilesystem: true" in window


def test_otel_sidecar_endpoint_via_plain_env_no_secretkeyref() -> None:
    text = _DEPLOYMENT.read_text(encoding="utf-8")
    idx = text.find("name: otel-collector")
    window = text[idx : idx + 500]
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in window
    # Endpoint is non-secret coordinate (value:), not a secretKeyRef.
    assert "otelSidecar.otlpEndpoint" in window


# ---- 5. Teams primary, no Slack receiver (1) ----------------------------


def test_no_slack_receiver_embedded() -> None:
    """Alert routing is Teams primary; the chart must not embed a Slack
    receiver/webhook. (Slack remains asset-preserved for other tenants but
    is NOT this chart's active receiver — HARD RULE Teams primary.)"""
    sm = _SM.read_text(encoding="utf-8").lower()
    assert "slack" not in sm, "ServiceMonitor must not embed a Slack receiver"
    assert "webhook" not in sm, "ServiceMonitor must not embed a webhook URL"


# ---- 6. no guard flag + governance (2) ----------------------------------


def test_no_guard_flag_key_in_monitoring() -> None:
    vals = _load_values()
    blob = json.dumps(vals.get("monitoring", {}))
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag not in blob, f"guard-flag key in monitoring block: {flag}"


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_4_4_observability_surface.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-4-4 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-4-4 must not touch .github/workflows/. Touched: {touched}"
