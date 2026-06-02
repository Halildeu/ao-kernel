"""Invariant test suite for V5 Epic 6 E-6-4: License compliance.

Codex 019e83df cross-AI plan-time AGREE (2 iters: REVISE → AGREE).

6 must-close findings closed + 14 hardening + 4 non-blocking tweaks:
- F1 SPDX expression handling simple_identifier_only; composite/exception
  → review_required (no false pass)
- F2 unknown_handling = review (fail-closed review, not deny)
- F3 Mutually exclusive tier membership
- F4 Distinct naming from runtime policy_license.v1.json (no collision)
- F5 Source provenance + deterministic (no wall-clock)
- F6 (preflight rerun documented at impl time)
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPLIANCE_DIR = REPO_ROOT / "docs" / "license-compliance"
POLICY_PATH = COMPLIANCE_DIR / "license-compliance-policy.v1.json"
INVENTORY_PATH = COMPLIANCE_DIR / "dependency-license-inventory.v1.json"
INVENTORY_MD_PATH = COMPLIANCE_DIR / "dependency-license-inventory.v1.md"
README_PATH = COMPLIANCE_DIR / "README.md"
POLICY_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "license-compliance-policy.schema.v1.json"
INVENTORY_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "dependency-license-inventory.schema.v1.json"
SBOM_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "sample-sbom.cdx.json"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_license_inventory.py"
LICENSE_PATH = REPO_ROOT / "LICENSE"
RUNTIME_POLICY_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "policies" / "policy_license.v1.json"
RUNTIME_POLICY_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "policy-license.schema.json"


sys.path.insert(0, str(REPO_ROOT / "scripts"))


def load_policy_schema() -> dict[str, Any]:
    return json.loads(POLICY_SCHEMA_PATH.read_text())


def load_inventory_schema() -> dict[str, Any]:
    return json.loads(INVENTORY_SCHEMA_PATH.read_text())


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text())


def load_inventory() -> dict[str, Any]:
    return json.loads(INVENTORY_PATH.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (8 invariants)
# ---------------------------------------------------------------------------


def test_policy_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(load_policy_schema())


def test_inventory_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(load_inventory_schema())


def test_policy_schema_additional_properties_false_at_root():
    assert load_policy_schema().get("additionalProperties") is False


def test_inventory_schema_additional_properties_false_at_root():
    assert load_inventory_schema().get("additionalProperties") is False


def test_policy_schema_const_pins():
    schema = load_policy_schema()
    props = schema["properties"]
    assert props["schema_version"]["const"] == "license-compliance-policy.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["operator_owned"]["const"] is True
    assert props["is_contractual_sla"]["const"] is False
    assert props["ao_kernel_license"]["const"] == "MIT"
    assert props["spdx_expression_handling"]["const"] == "simple_identifier_only"
    assert props["composite_expression_handling"]["const"] == "review_required"
    assert props["license_exception_handling"]["const"] == "review_required"


def test_policy_schema_guard_flags_const_false():
    schema = load_policy_schema()
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_policy_schema_disclaimer_const_true():
    schema = load_policy_schema()
    disc = schema["properties"]["policy_disclaimer"]["properties"]
    assert disc["not_legal_counsel"]["const"] is True
    assert disc["not_legal_advice"]["const"] is True
    assert disc["operator_responsibility"]["const"] is True


def test_inventory_schema_const_generator_name():
    schema = load_inventory_schema()
    props = schema["properties"]
    assert props["generator_name"]["const"] == "scripts/generate_license_inventory.py"
    assert props["schema_version"]["const"] == "dependency-license-inventory.v1"
    assert props["source_sbom_bom_format"]["const"] == "CycloneDX"


# ---------------------------------------------------------------------------
# Section 2 — Schema negative tests (4 invariants)
# ---------------------------------------------------------------------------


def _validate_policy(instance: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(load_policy_schema()).validate(instance)


def _validate_inventory(instance: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(load_inventory_schema()).validate(instance)


def test_policy_rejects_production_platform_claim_true():
    policy = load_policy()
    policy["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate_policy(policy)


def test_policy_rejects_is_contractual_sla_true():
    policy = load_policy()
    policy["is_contractual_sla"] = True
    with pytest.raises(Exception):
        _validate_policy(policy)


def test_policy_rejects_bad_unknown_handling():
    policy = load_policy()
    policy["unknown_handling"] = "allow"
    with pytest.raises(Exception):
        _validate_policy(policy)


def test_inventory_rejects_bad_report_status():
    inv = load_inventory()
    inv["report_status"] = "allowed"
    with pytest.raises(Exception):
        _validate_inventory(inv)


# ---------------------------------------------------------------------------
# Section 3 — Policy content (5 invariants)
# ---------------------------------------------------------------------------


def test_policy_validates_against_schema():
    _validate_policy(load_policy())


def test_policy_three_tiers_non_empty():
    tiers = load_policy()["tiers"]
    assert len(tiers["allow"]) >= 1
    assert len(tiers["review"]) >= 1
    assert len(tiers["deny"]) >= 1


def test_tiers_mutually_exclusive():
    """F3 absorb: no SPDX identifier may appear in more than one tier."""
    policy = load_policy()
    seen: dict[str, str] = {}
    for tier_name, ids in policy["tiers"].items():
        for spdx_id in ids:
            if spdx_id in seen:
                pytest.fail(f"{spdx_id!r} in both {seen[spdx_id]!r} and {tier_name!r}")
            seen[spdx_id] = tier_name


def test_policy_unknown_handling_review():
    """F2 absorb: v1 fail-closed review (not deny, not allow)."""
    assert load_policy()["unknown_handling"] == "review"


def test_policy_spdx_handling_const_review_required():
    """F1 absorb: composite/exception/ref all review_required."""
    policy = load_policy()
    assert policy["spdx_expression_handling"] == "simple_identifier_only"
    assert policy["composite_expression_handling"] == "review_required"
    assert policy["license_exception_handling"] == "review_required"
    assert policy["license_ref_handling"] == "review_required"


# ---------------------------------------------------------------------------
# Section 4 — Naming / authority collision (3 invariants — F4 absorb)
# ---------------------------------------------------------------------------


def test_runtime_policy_preserved():
    """F4 absorb: existing runtime policy_license.v1.json NOT touched."""
    assert RUNTIME_POLICY_PATH.exists()
    assert RUNTIME_POLICY_SCHEMA_PATH.exists()


def test_compliance_policy_distinct_naming():
    """E-6-4 uses distinct naming from runtime policy."""
    assert POLICY_PATH.exists()
    assert POLICY_SCHEMA_PATH.exists()
    # Different files, different names
    assert POLICY_PATH.name == "license-compliance-policy.v1.json"
    assert POLICY_SCHEMA_PATH.name == "license-compliance-policy.schema.v1.json"


def test_compliance_policy_schema_version_distinct():
    """Distinct schema_version vs runtime policy v1."""
    compliance = load_policy()
    runtime = json.loads(RUNTIME_POLICY_PATH.read_text())
    assert compliance["schema_version"] == "license-compliance-policy.v1"
    assert runtime.get("version") == "v1"  # different field name + namespace
    # No accidental schema_version collision
    assert "schema_version" not in runtime or runtime.get("schema_version") != compliance["schema_version"]


# ---------------------------------------------------------------------------
# Section 5 — Generator + provenance (6 invariants — F5 absorb)
# ---------------------------------------------------------------------------


def test_generator_idempotent(tmp_path):
    from generate_license_inventory import generate_inventory

    _inv_a, text_a = generate_inventory(POLICY_PATH, SBOM_FIXTURE_PATH)
    _inv_b, text_b = generate_inventory(POLICY_PATH, SBOM_FIXTURE_PATH)
    assert text_a == text_b


def test_inventory_drift_byte_equal():
    """F5 absorb: committed inventory must equal fresh generation byte-equal."""
    from generate_license_inventory import generate_inventory

    _inv, fresh_text = generate_inventory(POLICY_PATH, SBOM_FIXTURE_PATH)
    committed_text = INVENTORY_PATH.read_text()
    assert committed_text == fresh_text, (
        "DRIFT: committed inventory differs from generator output. "
        "Run: python scripts/generate_license_inventory.py --policy ... --sbom ... --output ..."
    )


def test_inventory_markdown_drift_byte_equal():
    """H11 absorb: Markdown render also byte-equal drift tested."""
    from generate_license_inventory import generate_inventory, render_markdown_summary

    inv, _ = generate_inventory(POLICY_PATH, SBOM_FIXTURE_PATH)
    fresh_md = render_markdown_summary(inv)
    committed_md = INVENTORY_MD_PATH.read_text()
    assert committed_md == fresh_md


def test_inventory_has_no_wall_clock_timestamp():
    """F5 absorb: no wall-clock timestamp fields."""
    inv = load_inventory()
    forbidden_keys = ("generated_at", "timestamp", "created_at", "report_time")
    for key in forbidden_keys:
        assert key not in inv, f"wall-clock field leaked: {key}"


def test_inventory_components_sorted_stably():
    """F5 absorb: components sorted by (name, version, purl, bom_ref)."""
    inv = load_inventory()
    sort_keys = [(c["name"], c["version"], c.get("purl") or "", c.get("bom_ref") or "") for c in inv["components"]]
    assert sort_keys == sorted(sort_keys)


def test_inventory_source_provenance_present():
    """F5 absorb: source SHA256 + bom_format + spec_version recorded."""
    inv = load_inventory()
    assert re.fullmatch(r"[a-f0-9]{64}", inv["source_sbom_sha256"])
    assert re.fullmatch(r"[a-f0-9]{64}", inv["source_policy_sha256"])
    assert inv["source_sbom_bom_format"] == "CycloneDX"
    assert inv["source_sbom_spec_version"].startswith("1.")
    # Verify SHA256s match actual files
    expected_sbom = hashlib.sha256(SBOM_FIXTURE_PATH.read_bytes()).hexdigest()
    expected_policy = hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()
    assert inv["source_sbom_sha256"] == expected_sbom
    assert inv["source_policy_sha256"] == expected_policy


# ---------------------------------------------------------------------------
# Section 6 — CycloneDX shape handling (5 invariants — H2 + H3 absorb)
# ---------------------------------------------------------------------------


def test_inventory_simple_id_match_to_allow_tier():
    """license.id MIT → policy_tier 'allow' + policy_decision 'pass'."""
    inv = load_inventory()
    mit_record = next((c for c in inv["components"] if c["name"] == "jsonschema"), None)
    assert mit_record is not None
    assert mit_record["license_id"] == "MIT"
    assert mit_record["policy_tier"] == "allow"
    assert mit_record["policy_decision"] == "pass"
    assert mit_record["review_reason"] is None


def test_inventory_review_tier_match():
    """license.id LGPL → policy_tier 'review' + reason 'policy_review_tier'."""
    inv = load_inventory()
    lgpl_record = next((c for c in inv["components"] if c["name"] == "psycopg2-binary"), None)
    assert lgpl_record is not None
    assert lgpl_record["license_id"] == "LGPL-3.0-or-later"
    assert lgpl_record["policy_tier"] == "review"
    assert lgpl_record["policy_decision"] == "review"
    assert lgpl_record["review_reason"] == "policy_review_tier"


def test_inventory_expression_falls_to_review():
    """F1 absorb: license.expression → review with 'unsupported_expression'."""
    inv = load_inventory()
    expr_record = next((c for c in inv["components"] if c["name"] == "example-dual-license"), None)
    assert expr_record is not None
    assert expr_record["license_expression"] == "MIT OR Apache-2.0"
    assert expr_record["policy_decision"] == "review"
    assert expr_record["review_reason"] == "unsupported_expression"


def test_inventory_name_only_falls_to_review():
    """H2 absorb: license.name only → review with 'unresolved_name'."""
    inv = load_inventory()
    name_record = next((c for c in inv["components"] if c["name"] == "example-name-only"), None)
    assert name_record is not None
    assert name_record["license_name"] == "Custom Permissive License"
    assert name_record["policy_decision"] == "review"
    assert name_record["review_reason"] == "unresolved_name"


def test_inventory_review_reason_enum_values():
    """H14 absorb: review_reason must use enumerated values."""
    valid_reasons = {
        None,
        "policy_review_tier",
        "unsupported_expression",
        "unsupported_exception",
        "license_ref",
        "noassertion",
        "none_declared",
        "unresolved_name",
        "unresolved_url",
        "missing_license",
        "unknown_identifier",
    }
    inv = load_inventory()
    for c in inv["components"]:
        assert c["review_reason"] in valid_reasons, f"unknown review_reason: {c['review_reason']!r} in {c['name']}"


# ---------------------------------------------------------------------------
# Section 7 — Wording discipline (3 invariants — H4 absorb)
# ---------------------------------------------------------------------------


_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_RE = re.compile(r"^(\s*)```")


def _iter_prose_lines(text: str):
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _INLINE_CODE_RE.sub("", line)
        yield line_no, line, prose


FORBIDDEN_WORDING_TOKENS = (
    "legally compliant",
    "license-safe",
    "legal approved",
    "fully compliant",
    "we comply with",
)
NEGATION_MARKERS = ("not ", "never ", "no ", "without ", "non-")


def test_no_legal_compliance_claim_language():
    """H4 absorb: scan compliance docs for forbidden legal-claim tokens."""
    for path in (README_PATH, INVENTORY_MD_PATH):
        text = path.read_text()
        for _no, line, prose in _iter_prose_lines(text):
            lowered = prose.lower()
            # Allow lines that are documenting the forbidden tokens
            if any(marker in lowered for marker in ("forbidden", "prohibited", "discipline", "yasak")):
                continue
            for token in FORBIDDEN_WORDING_TOKENS:
                if token in lowered:
                    if any(neg + token in lowered for neg in NEGATION_MARKERS):
                        continue
                    pytest.fail(
                        f"legal-claim language leak in {path.relative_to(REPO_ROOT)}: token={token!r}; line={line!r}"
                    )


def test_readme_disclaimer_present():
    text = README_PATH.read_text().lower()
    assert "not legal counsel" in text
    assert "not legal advice" in text
    assert "operator responsibility" in text


def test_readme_mentions_guard_flags():
    text = README_PATH.read_text().lower()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text


# ---------------------------------------------------------------------------
# Section 8 — Summary + report_status (3 invariants — H13 absorb)
# ---------------------------------------------------------------------------


def test_inventory_summary_counts_match_components():
    inv = load_inventory()
    summary = inv["summary"]
    assert summary["component_count"] == len(inv["components"])
    pass_n = sum(1 for c in inv["components"] if c["policy_decision"] == "pass")
    review_n = sum(1 for c in inv["components"] if c["policy_decision"] == "review")
    deny_n = sum(1 for c in inv["components"] if c["policy_decision"] == "deny")
    assert summary["pass_count"] == pass_n
    assert summary["review_count"] == review_n
    assert summary["deny_count"] == deny_n


def test_inventory_report_status_consistent_with_summary():
    inv = load_inventory()
    summary = inv["summary"]
    status = inv["report_status"]
    if summary["deny_count"] > 0:
        assert status == "blocked_by_deny_license"
    elif summary["review_count"] > 0:
        assert status == "review_required"
    else:
        assert status == "pass_no_deny_matches"


def test_inventory_validates_against_schema():
    _validate_inventory(load_inventory())


# ---------------------------------------------------------------------------
# Section 9 — LICENSE file parity (2 invariants)
# ---------------------------------------------------------------------------


def test_license_file_exists_in_repo_root():
    assert LICENSE_PATH.exists(), "LICENSE file missing in repo root"


def test_policy_ao_kernel_license_matches_license_file():
    """Policy.ao_kernel_license == MIT must match LICENSE file content."""
    policy = load_policy()
    license_text = LICENSE_PATH.read_text()
    assert policy["ao_kernel_license"] == "MIT"
    # Quick assertion: LICENSE file mentions MIT
    assert "MIT" in license_text


# ---------------------------------------------------------------------------
# Section 10 — Governance (2 invariants)
# ---------------------------------------------------------------------------


def test_policy_guard_flags_const_false():
    policy = load_policy()
    flags = policy["guard_flags"]
    assert flags["support_widening_allowed"] is False
    assert flags["production_platform_claim_allowed"] is False
    assert flags["live_adapter_execution_allowed"] is False


def test_no_github_workflow_change_in_pr_diff():
    """Conservative low-risk lane: PR must not touch .github/workflows/."""
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
        assert not line.startswith(".github/workflows/"), f"compliance docs PR must not touch workflows: {line}"
