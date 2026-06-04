"""V5 Epic 4 E-4-5 invariants: NetworkPolicy + PodSecurityStandards baseline.

Opt-in default-deny NetworkPolicy (DNS-only egress until the operator widens)
+ a PodSecurityStandards 'restricted' affirmation. The chart's existing
container securityContext already satisfies 'restricted'; the operator applies
the namespace enforce label out-of-band (chart does not manage the namespace).

Machine-enforced invariants:
  - networkpolicy.yaml gated on networkPolicy.enabled (default false)
  - policyTypes include Ingress + Egress; egress allows DNS
  - egress CIDRs default empty (DNS-only baseline; operator widens)
  - values + schema carry networkPolicy + podSecurityStandards (closed)
  - PSS enforceProfile default 'restricted'
  - existing container securityContext already meets 'restricted'
  - no guard-flag key; no .github/workflows/ mutation
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
_NETPOL = _CHART_DIR / "templates" / "networkpolicy.yaml"


def _load_values() -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_VALUES.read_text(encoding="utf-8"))


# ---- 1. NetworkPolicy template (4) --------------------------------------


def test_networkpolicy_template_exists() -> None:
    assert _NETPOL.is_file(), "networkpolicy.yaml missing (E-4-5)"


def test_networkpolicy_gated_on_enabled() -> None:
    text = _NETPOL.read_text(encoding="utf-8")
    assert "if .Values.networkPolicy.enabled" in text


def test_networkpolicy_default_deny_both_directions() -> None:
    text = _NETPOL.read_text(encoding="utf-8")
    assert "policyTypes:" in text
    assert "- Ingress" in text and "- Egress" in text


def test_networkpolicy_egress_allows_dns() -> None:
    text = _NETPOL.read_text(encoding="utf-8")
    assert "port: 53" in text, "egress must allow DNS (required for any outbound)"


# ---- 2. values + schema (3) ---------------------------------------------


def test_values_have_networkpolicy_and_pss() -> None:
    vals = _load_values()
    assert "networkPolicy" in vals
    assert "podSecurityStandards" in vals


def test_networkpolicy_disabled_and_egress_empty_default() -> None:
    vals = _load_values()
    assert vals["networkPolicy"]["enabled"] is False
    assert vals["networkPolicy"]["egress"]["allowCidrs"] == [], (
        "default egress CIDRs must be empty (DNS-only baseline; operator widens)"
    )


def test_pss_enforce_profile_restricted_default() -> None:
    vals = _load_values()
    assert vals["podSecurityStandards"]["enforceProfile"] == "restricted"


# ---- 3. schema closes blocks (1) ----------------------------------------


def test_schema_closes_networkpolicy_and_pss() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["networkPolicy"].get("additionalProperties") is False
    pss = schema["properties"]["podSecurityStandards"]
    assert pss.get("additionalProperties") is False
    assert "restricted" in pss["properties"]["enforceProfile"]["enum"]


# ---- 4. existing securityContext already meets 'restricted' (1) ---------


def test_container_securitycontext_meets_restricted() -> None:
    vals = _load_values()
    csc = vals["containerSecurityContext"]
    assert csc["allowPrivilegeEscalation"] is False
    assert csc["readOnlyRootFilesystem"] is True
    assert csc["capabilities"]["drop"] == ["ALL"]
    psc = vals["podSecurityContext"]
    assert psc["runAsNonRoot"] is True


# ---- 5. governance (2) --------------------------------------------------


def test_no_guard_flag_key_in_new_blocks() -> None:
    vals = _load_values()
    blob = json.dumps({"n": vals.get("networkPolicy"), "p": vals.get("podSecurityStandards")})
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag not in blob, f"guard-flag key present: {flag}"


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_4_5_networkpolicy_pss.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-4-5 test not ADDED by this PR (introducer pattern); invariant N/A")
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
    assert not touched, f"E-4-5 must not touch .github/workflows/. Touched: {touched}"
