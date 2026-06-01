"""Invariant test suite for V5 Epic 6 E-6-6b: Vendor escalation matrix.

Follow-up slice to E-6-6 incident response playbook (PR #801 MERGED).
Cross-validates with E-6-6 severity-matrix.v1.json tier IDs.

~25 invariants across 8 sections.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "vendor-escalation-matrix.schema.v1.json"
MATRIX_PATH = REPO_ROOT / "docs" / "incident-response" / "vendor-escalation-matrix.v1.json"
RUNBOOK_PATH = REPO_ROOT / "docs" / "incident-response" / "vendor-escalation-runbook.v1.md"
SEVERITY_MATRIX_PATH = REPO_ROOT / "docs" / "incident-response" / "severity-matrix.v1.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (5 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_schema_additional_properties_false_root():
    assert _load(SCHEMA_PATH).get("additionalProperties") is False


def test_schema_const_pins():
    schema = _load(SCHEMA_PATH)
    props = schema["properties"]
    assert props["schema_version"]["const"] == "vendor-escalation-matrix.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["artifact_kind"]["const"] == "vendor-escalation-matrix"


def test_schema_guard_flags_const_false():
    schema = _load(SCHEMA_PATH)
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_schema_matrix_disclaimer_5_const_true():
    """5 disclaimer const true (operator-owned external handoff discipline)."""
    schema = _load(SCHEMA_PATH)
    disc = schema["properties"]["matrix_disclaimer"]["properties"]
    for key in (
        "operator_owned_external_handoff",
        "no_vendor_sla_promise",
        "no_customer_notification_authority",
        "no_pii_in_repo",
        "operator_legal_counsel_required",
    ):
        assert disc[key]["const"] is True, f"matrix_disclaimer.{key} must be const true"


# ---------------------------------------------------------------------------
# Section 2 — Schema negative (3 invariants)
# ---------------------------------------------------------------------------


def _validate(instance: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(_load(SCHEMA_PATH)).validate(instance)


def test_schema_rejects_production_platform_claim_true():
    matrix = _load(MATRIX_PATH)
    matrix["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate(matrix)


def test_schema_rejects_no_pii_committed_false():
    """no_pii_committed const true; setting false rejects."""
    matrix = _load(MATRIX_PATH)
    matrix["vendors"][0]["no_pii_committed"] = False
    with pytest.raises(Exception):
        _validate(matrix)


def test_schema_rejects_account_manager_contact_literal():
    """account_manager_contact const operator_provisioned only."""
    matrix = _load(MATRIX_PATH)
    matrix["vendors"][0]["account_manager_contact"] = "alice@example.com"
    with pytest.raises(Exception):
        _validate(matrix)


# ---------------------------------------------------------------------------
# Section 3 — Matrix content (5 invariants)
# ---------------------------------------------------------------------------


def test_matrix_validates_against_schema():
    _validate(_load(MATRIX_PATH))


def test_matrix_has_at_least_three_vendors():
    """Schema requires minItems 3; matrix ships 8."""
    vendors = _load(MATRIX_PATH)["vendors"]
    assert len(vendors) >= 3


def test_matrix_vendor_ids_unique():
    vendors = _load(MATRIX_PATH)["vendors"]
    ids = [v["id"] for v in vendors]
    assert len(ids) == len(set(ids))


def test_matrix_all_llm_providers_present():
    """6 LLM provider entries (Anthropic, OpenAI, Gemini, xAI, DeepSeek, Qwen)."""
    vendors = _load(MATRIX_PATH)["vendors"]
    llm_ids = {v["id"] for v in vendors if v["category"] == "llm_provider"}
    expected = {"anthropic-claude", "openai", "google-gemini", "xai-grok", "deepseek", "qwen"}
    assert expected.issubset(llm_ids), f"missing LLM providers: {expected - llm_ids}"


def test_matrix_workflow_step_count_per_vendor():
    """Schema bounds: minItems 3, maxItems 7 per vendor."""
    vendors = _load(MATRIX_PATH)["vendors"]
    for v in vendors:
        steps = v["operator_workflow_steps"]
        assert 3 <= len(steps) <= 7, f"{v['id']}: workflow steps out of bounds {len(steps)}"


# ---------------------------------------------------------------------------
# Section 4 — Severity matrix cross-validation (3 invariants)
# ---------------------------------------------------------------------------


def test_severity_matrix_present_in_repo():
    """E-6-6 severity matrix exists (MERGED PR #801)."""
    assert SEVERITY_MATRIX_PATH.exists(), "E-6-6 severity-matrix.v1.json missing"


def test_every_vendor_applicable_severity_subset_of_sev_matrix():
    """vendor.applicable_severity ⊆ E-6-6 tier IDs."""
    severity_matrix = _load(SEVERITY_MATRIX_PATH)
    severity_tier_ids = {t["id"] for t in severity_matrix["tiers"]}
    vendors = _load(MATRIX_PATH)["vendors"]
    for v in vendors:
        for sev in v["applicable_severity"]:
            assert sev in severity_tier_ids, f"{v['id']}: applicable_severity {sev!r} not in severity-matrix"


def test_no_vendor_maps_to_sev3():
    """v1 conservatism: vendor handoff only for SEV-1/SEV-2; SEV-3 is internal."""
    vendors = _load(MATRIX_PATH)["vendors"]
    for v in vendors:
        assert "SEV-3" not in v["applicable_severity"], f"{v['id']}: maps to SEV-3 (v1 expects internal-only)"


# ---------------------------------------------------------------------------
# Section 5 — PII / credential discipline (3 invariants)
# ---------------------------------------------------------------------------


# Token-prefix-only secret patterns (Codex 019e84c6 absorb R2).
SECRET_PATTERNS = (
    re.compile(r"\bghp_[A-Za-z0-9]{36,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.|redacted\.|placeholder\.)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def test_no_secret_committed_in_matrix_or_runbook():
    for path in (MATRIX_PATH, RUNBOOK_PATH):
        text = path.read_text()
        for pat in SECRET_PATTERNS:
            assert not pat.search(text), f"secret-like pattern in {path.name}: {pat.pattern}"


def test_no_personal_email_committed():
    """Codex matrix_disclaimer.no_pii_in_repo absorb."""
    for path in (MATRIX_PATH, RUNBOOK_PATH):
        text = path.read_text()
        # Skip lines that are explicit disclaimers / discipline documentation
        for line in text.splitlines():
            lowered = line.lower()
            if "example" in lowered or "redacted" in lowered or "placeholder" in lowered:
                continue
            assert not EMAIL_PATTERN.search(line), f"personal email in {path.name}: {line!r}"


def test_all_account_manager_contacts_operator_provisioned():
    vendors = _load(MATRIX_PATH)["vendors"]
    for v in vendors:
        assert v["account_manager_contact"] == "operator_provisioned"


# ---------------------------------------------------------------------------
# Section 6 — URL pattern discipline (2 invariants)
# ---------------------------------------------------------------------------


def test_status_page_url_https():
    vendors = _load(MATRIX_PATH)["vendors"]
    for v in vendors:
        assert v["status_page_url"].startswith("https://"), f"{v['id']}: status page URL must be https"


def test_support_portal_url_https():
    vendors = _load(MATRIX_PATH)["vendors"]
    for v in vendors:
        assert v["support_portal_url"].startswith("https://"), f"{v['id']}: support portal URL must be https"


# ---------------------------------------------------------------------------
# Section 7 — Runbook structure (3 invariants)
# ---------------------------------------------------------------------------


def test_runbook_has_required_sections():
    text = RUNBOOK_PATH.read_text()
    required = (
        "## 1. Source of Truth",
        "## 2. Vendor Categories",
        "## 3. Standard Workflow",
        "## 4. Severity Mapping",
        "## 5. PII Boundary",
        "## 6. Stop and contact owner if",
        "## 7. References",
    )
    for section in required:
        assert section in text, f"runbook missing section: {section}"


def test_runbook_mentions_no_vendor_sla_promise():
    text = RUNBOOK_PATH.read_text().lower()
    assert "no vendor sla promise" in text or "do not promise vendor sla" in text


def test_runbook_mentions_legal_counsel_before_disclosure():
    text = RUNBOOK_PATH.read_text().lower()
    assert "legal counsel" in text or "legal-counsel" in text


# ---------------------------------------------------------------------------
# Section 8 — Governance (2 invariants)
# ---------------------------------------------------------------------------


def test_matrix_guard_flags_const_false():
    flags = _load(MATRIX_PATH)["guard_flags"]
    assert flags["support_widening_allowed"] is False
    assert flags["production_platform_claim_allowed"] is False
    assert flags["live_adapter_execution_allowed"] is False


def test_no_github_workflow_change_in_pr_diff():
    """E-6-6b is docs/schema/tests only; no workflow mutation."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("git not available or origin/main not fetched")
    if result.returncode != 0:
        pytest.skip(f"git diff failed: {result.stderr}")
    for line in result.stdout.splitlines():
        assert not line.startswith(".github/workflows/"), f"E-6-6b must not touch workflows: {line}"
