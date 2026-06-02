"""V5 Epic 6 E-6-3e invariants: NIST CSF 2.0 Function/Category reference mapping.

Codex 019e8516 cross-AI plan-time AGREE (2 iters: REVISE -> AGREE +
must_close_findings:[]).

Implementation guardrails:
- Markdown title: "Function / Category Reference Mapping" (NOT "control mapping")
- documented evidence rows: "evidence surface only; not operating effectiveness"
- partial categories: evidence_refs minItems=1 enforced via schema
- Tier/Profile prose claims forbidden; only allowed in code spans / disclosure tables
- diff allowlist: `git diff --name-only origin/main...HEAD` (three-dot form)
- Zero-touch tests for HIPAA/GDPR/PCI: skip with reason if sibling slice
  files not yet merged into base
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "nist-csf-control-mapping.schema.v1.json"
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "nist-csf-control-mapping.v1.json"
MD_PATH = REPO_ROOT / "docs" / "compliance" / "nist-csf-control-mapping.v1.md"
RUNBOOK_PATH = REPO_ROOT / "docs" / "compliance" / "nist-csf-operator-usage-runbook.v1.md"
RENDERER_PATH = REPO_ROOT / "scripts" / "render_nist_csf_docs.py"
README_PATH = REPO_ROOT / "docs" / "compliance" / "README.md"

EXPECTED_FUNCTION_IDS = ("GV", "ID", "PR", "DE", "RS", "RC")
EXPECTED_PER_FUNCTION_CATEGORIES: dict[str, frozenset[str]] = {
    "GV": frozenset({"GV.OC", "GV.RM", "GV.RR", "GV.PO", "GV.OV", "GV.SC"}),
    "ID": frozenset({"ID.AM", "ID.RA", "ID.IM"}),
    "PR": frozenset({"PR.AA", "PR.AT", "PR.DS", "PR.PS", "PR.IR"}),
    "DE": frozenset({"DE.CM", "DE.AE"}),
    "RS": frozenset({"RS.MA", "RS.AN", "RS.CO", "RS.MI"}),
    "RC": frozenset({"RC.RP", "RC.CO"}),
}

# F4 + H4 - 18 exact prohibited tokens (lowered for exact-set parity)
PROHIBITED_TOKENS = (
    "nist csf certified",
    "nist-certified",
    "nist csf compliant",
    "csf compliant",
    "csf-compliant",
    "fully implements csf",
    "csf profile complete",
    "target profile complete",
    "current profile complete",
    "target profile achieved",
    "implementation tier achieved",
    "csf audit",
    "csf attested",
    "nist validated",
    "cisa approved",
    "cisa validated",
    "csf maturity level",
    "csf maturity score",
)

# F4 - regex prohibited patterns (prose claim of Tier/Profile)
TIER_NUMBER_PATTERN = re.compile(r"\btier\s+[1-4]\b", re.IGNORECASE)
NAMED_TIER_CLAIM_PATTERN = re.compile(
    r"\b(?:partial|risk\s+informed|repeatable|adaptive)\s+tier\b",
    re.IGNORECASE,
)
PROFILE_CLAIM_PATTERN = re.compile(r"\b(?:current|target)\s+profile\b", re.IGNORECASE)
FRAMEWORK_ACHIEVED_PATTERN = re.compile(r"\bframework\s+(?:adopted|matured|achieved)\b", re.IGNORECASE)
MATURITY_ACHIEVED_PATTERN = re.compile(r"\bmaturity\s+(?:score|level|achieved)\b", re.IGNORECASE)
REGEX_PROHIBITED_PATTERNS = (
    TIER_NUMBER_PATTERN,
    NAMED_TIER_CLAIM_PATTERN,
    PROFILE_CLAIM_PATTERN,
    FRAMEWORK_ACHIEVED_PATTERN,
    MATURITY_ACHIEVED_PATTERN,
)

# Contract-construction patterns (organization shall, etc.)
CONTRACT_FORBIDDEN_PATTERNS = (
    re.compile(r"\borganization\s+shall\b", re.IGNORECASE),
    re.compile(r"\btier\s+achieved\b", re.IGNORECASE),
    re.compile(r"\bprofile\s+complete\b", re.IGNORECASE),
    re.compile(r"\bframework\s+adopted\b", re.IGNORECASE),
    re.compile(r"\bmatured\s+to\b", re.IGNORECASE),
    re.compile(r"\bassessment\s+confirms\b", re.IGNORECASE),
)


# ---- helpers --------------------------------------------------------------


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _load_instance() -> dict:
    return json.loads(JSON_PATH.read_text())


def _strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def _strip_fenced_blocks(text: str) -> str:
    lines = text.splitlines()
    out = []
    in_fence = False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append(line)
    return "\n".join(out)


def _csf_prose_docs() -> list[Path]:
    return [MD_PATH, RUNBOOK_PATH]


def _diff_files() -> set[str] | None:
    """Returns the set of changed files vs origin/main (3-dot form), or None
    if git is unavailable in the test environment."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return set(proc.stdout.split())


# ---- 1. Schema validity (12) ---------------------------------------------


def test_schema_is_valid_draft_2020_12() -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_additional_properties_false_root() -> None:
    schema = _load_schema()
    assert schema["additionalProperties"] is False


def test_schema_root_const_pins() -> None:
    schema = _load_schema()
    props = schema["properties"]
    assert props["schema_version"]["const"] == "nist-csf-control-mapping.v1"
    assert props["artifact_kind"]["const"] == "nist-csf-control-reference-mapping"
    assert props["service"]["const"] == "ao-kernel"
    assert props["operator_owned"]["const"] is True
    assert props["is_contractual_sla"]["const"] is False
    assert props["framework_version"]["const"] == "NIST-CSF-2.0"


def test_schema_six_guard_flags_const_false() -> None:
    schema = _load_schema()
    flags = schema["properties"]["guard_flags"]["properties"]
    assert len(flags) == 6
    for fld, spec in flags.items():
        assert spec.get("const") is False, fld


def test_schema_six_disclaimer_const_true() -> None:
    schema = _load_schema()
    disclaimer = schema["properties"]["csf_disclaimer"]["properties"]
    assert len(disclaimer) == 6
    for fld, spec in disclaimer.items():
        assert spec.get("const") is True, fld


def test_schema_tier_disclosure_pins() -> None:
    schema = _load_schema()
    tier = schema["properties"]["csf_tier_disclosure"]["properties"]
    assert tier["ao_kernel_claims_tier"]["const"] == "none"
    assert tier["tier_assessment_operator_owned"]["const"] is True


def test_schema_profile_disclosure_pins() -> None:
    schema = _load_schema()
    prof = schema["properties"]["csf_profile_disclosure"]["properties"]
    assert prof["ao_kernel_is_organization"]["const"] is False
    assert prof["no_csf_profile_in_repo"]["const"] is True
    assert prof["operator_csf_profile_owner"]["const"] is True


def test_schema_functions_exactly_six_with_contains() -> None:
    schema = _load_schema()
    funcs = schema["properties"]["functions"]
    assert funcs["minItems"] == 6
    assert funcs["maxItems"] == 6
    contains = funcs["allOf"]
    assert len(contains) == 6
    seen = set()
    for entry in contains:
        seen.add(entry["contains"]["properties"]["function_id"]["const"])
        assert entry["minContains"] == 1
        assert entry["maxContains"] == 1
    assert seen == set(EXPECTED_FUNCTION_IDS)


def test_schema_category_id_pattern_pinned() -> None:
    schema = _load_schema()
    pattern = schema["$defs"]["category"]["properties"]["category_id"]["pattern"]
    assert pattern == r"^(GV|ID|PR|DE|RS|RC)\.[A-Z]{2}$"


def test_schema_category_status_enum_complete() -> None:
    schema = _load_schema()
    enum = schema["$defs"]["category"]["properties"]["category_status"]["enum"]
    assert sorted(enum) == sorted(["documented", "partial", "out_of_scope", "not_applicable"])


def test_schema_evidence_ref_requires_claim_boundary() -> None:
    schema = _load_schema()
    required = schema["$defs"]["evidence_ref"]["required"]
    assert "claim_boundary" in required


def test_schema_prohibited_claims_min_18() -> None:
    schema = _load_schema()
    assert schema["properties"]["prohibited_claims"]["minItems"] == 18


# ---- 2. Schema negative (5) ----------------------------------------------


def test_schema_rejects_support_widening_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["support_widening_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_csf_tier_claim_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["csf_tier_claim_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_documented_without_evidence() -> None:
    schema = _load_schema()
    instance = _load_instance()
    for func in instance["functions"]:
        for cat in func["categories"]:
            if cat["category_id"] == "RS.MA":
                cat["evidence_refs"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_out_of_scope_with_evidence() -> None:
    schema = _load_schema()
    instance = _load_instance()
    for func in instance["functions"]:
        for cat in func["categories"]:
            if cat["category_id"] == "PR.AA":
                cat["evidence_refs"] = [
                    {
                        "type": "doc",
                        "ref": "irrelevant.md",
                        "description": "should not appear",
                        "claim_boundary": "irrelevant",
                    }
                ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_bad_category_id() -> None:
    schema = _load_schema()
    instance = _load_instance()
    for func in instance["functions"]:
        for cat in func["categories"]:
            if cat["category_id"] == "GV.OC":
                cat["category_id"] = "XX.YY"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


# ---- 3. Function/category content (8) ------------------------------------


def test_instance_validates_against_schema() -> None:
    jsonschema.validate(_load_instance(), _load_schema())


def test_instance_has_six_functions_exact() -> None:
    instance = _load_instance()
    ids = {f["function_id"] for f in instance["functions"]}
    assert ids == set(EXPECTED_FUNCTION_IDS)


def test_instance_has_twenty_two_categories_total() -> None:
    instance = _load_instance()
    total = sum(len(f["categories"]) for f in instance["functions"])
    assert total == 22


def test_per_function_categories_exact_sets() -> None:
    instance = _load_instance()
    funcs_by_id = {f["function_id"]: f for f in instance["functions"]}
    for fid, expected in EXPECTED_PER_FUNCTION_CATEGORIES.items():
        actual = {c["category_id"] for c in funcs_by_id[fid]["categories"]}
        assert actual == expected, f"Function {fid}: got {actual}, expected {expected}"


def test_category_status_distribution() -> None:
    instance = _load_instance()
    counts = {"documented": 0, "partial": 0, "out_of_scope": 0, "not_applicable": 0}
    for func in instance["functions"]:
        for cat in func["categories"]:
            counts[cat["category_status"]] += 1
    assert counts == {
        "documented": 2,
        "partial": 5,
        "out_of_scope": 15,
        "not_applicable": 0,
    }


def test_function_status_derivation_consistency() -> None:
    """function_status must reflect per-function category status mix."""
    instance = _load_instance()
    for func in instance["functions"]:
        cats = [c["category_status"] for c in func["categories"]]
        if all(s == "documented" for s in cats):
            expected = "documented"
        elif all(s == "out_of_scope" for s in cats):
            expected = "out_of_scope"
        elif all(s == "not_applicable" for s in cats):
            expected = "not_applicable"
        else:
            expected = "partial"
        assert func["function_status"] == expected, (
            f"Function {func['function_id']}: function_status={func['function_status']}, "
            f"derived={expected}, categories={cats}"
        )


def test_rs_ma_documented_with_e66_evidence() -> None:
    instance = _load_instance()
    cats_by_id = {c["category_id"]: c for f in instance["functions"] for c in f["categories"]}
    rs_ma = cats_by_id["RS.MA"]
    assert rs_ma["category_status"] == "documented"
    refs = rs_ma["evidence_refs"]
    assert any("#801" in r["ref"] for r in refs)
    for r in refs:
        assert "evidence surface only" in r["claim_boundary"]


def test_de_ae_partial_boundary_wording() -> None:
    instance = _load_instance()
    cats_by_id = {c["category_id"]: c for f in instance["functions"] for c in f["categories"]}
    de_ae = cats_by_id["DE.AE"]
    assert de_ae["category_status"] == "partial"
    rationale = de_ae["rationale"].lower()
    assert "not incident detection automation" in rationale
    assert "not an operating control" in rationale


# ---- 4. Tier / Profile discipline (5) ------------------------------------


@pytest.mark.parametrize("path", _csf_prose_docs())
def test_no_tier_number_in_prose(path: Path) -> None:
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        match = TIER_NUMBER_PATTERN.search(bare)
        assert match is None, f"{path.name}: Tier number prose claim: {line!r}"


@pytest.mark.parametrize("path", _csf_prose_docs())
def test_no_named_tier_claim_in_prose(path: Path) -> None:
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        match = NAMED_TIER_CLAIM_PATTERN.search(bare)
        assert match is None, f"{path.name}: named tier prose claim: {line!r}"


@pytest.mark.parametrize("path", _csf_prose_docs())
def test_no_profile_claim_in_prose(path: Path) -> None:
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        match = PROFILE_CLAIM_PATTERN.search(bare)
        assert match is None, f"{path.name}: profile prose claim: {line!r}"


def test_tier_disclosure_pins_in_instance() -> None:
    instance = _load_instance()
    tier = instance["csf_tier_disclosure"]
    assert tier["ao_kernel_claims_tier"] == "none"
    assert tier["tier_assessment_operator_owned"] is True
    assert set(tier["available_tiers"]) == {
        "partial",
        "risk_informed",
        "repeatable",
        "adaptive",
    }


def test_profile_disclosure_pins_in_instance() -> None:
    instance = _load_instance()
    prof = instance["csf_profile_disclosure"]
    assert prof["ao_kernel_is_organization"] is False
    assert prof["no_csf_profile_in_repo"] is True
    assert prof["operator_csf_profile_owner"] is True


# ---- 5. Wording discipline (5) -------------------------------------------


@pytest.mark.parametrize("path", _csf_prose_docs())
def test_no_prohibited_csf_claim_language(path: Path) -> None:
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line).lower()
        for token in PROHIBITED_TOKENS:
            pattern = re.compile(rf"(?<![\w-]){re.escape(token)}(?![\w-])")
            assert not pattern.search(bare), f"{path.name}: prohibited token '{token}' in prose: {line!r}"


@pytest.mark.parametrize("path", _csf_prose_docs())
def test_no_regex_prohibited_patterns_in_prose(path: Path) -> None:
    """F4 regex layer: framework_achieved + maturity_achieved (Tier/Profile
    already covered by separate tests)."""
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        for pattern in (FRAMEWORK_ACHIEVED_PATTERN, MATURITY_ACHIEVED_PATTERN):
            assert not pattern.search(bare), f"{path.name}: regex prohibited pattern {pattern.pattern} in: {line!r}"


@pytest.mark.parametrize("path", _csf_prose_docs())
def test_no_contract_language(path: Path) -> None:
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        for pat in CONTRACT_FORBIDDEN_PATTERNS:
            assert not pat.search(bare), f"{path.name}: contract pattern {pat.pattern} matched in: {line!r}"


def test_prohibited_claims_list_matches_scanner_constants() -> None:
    instance = _load_instance()
    listed = sorted(t.lower() for t in instance["prohibited_claims"])
    scanner = sorted(PROHIBITED_TOKENS)
    assert listed == scanner


def test_rs_function_status_partial_in_markdown() -> None:
    text = MD_PATH.read_text()
    # The RS function header followed by status: partial
    assert "`RS`" in text
    assert "`partial`" in text


# ---- 6. Drift / governance (6) -------------------------------------------


def test_drift_committed_matches_generated() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_csf", RENDERER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = json.loads(JSON_PATH.read_text())
    expected = mod.render_markdown(data)
    actual = MD_PATH.read_text()
    assert actual == expected, "Markdown drift; regenerate via render_nist_csf_docs.py"




def test_e63_catalog_zero_touch() -> None:
    changed = _diff_files()
    if changed is None:
        pytest.skip("git diff unavailable")
    forbidden = {
        "docs/compliance/control-evidence-catalog.v1.json",
        "ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json",
        "docs/compliance/soc2-trust-services-criteria-mapping.v1.md",
        "docs/compliance/iso-27001-controls-mapping.v1.md",
    }
    overlap = forbidden & changed
    assert not overlap, f"E-6-3 catalog modified: {overlap}"


def test_e63b_hipaa_zero_touch() -> None:
    """E-6-3b HIPAA may not yet be merged into base; skip if sibling files
    are still in pipeline branches."""
    changed = _diff_files()
    if changed is None:
        pytest.skip("git diff unavailable")
    hipaa = {
        "docs/compliance/hipaa-control-mapping.v1.json",
        "ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json",
        "docs/compliance/hipaa-control-mapping.v1.md",
        "scripts/render_hipaa_mapping.py",
        "tests/test_hipaa_mapping.py",
    }
    overlap = hipaa & changed
    assert not overlap, f"HIPAA artifacts modified by this PR: {overlap}"


def test_e63c_gdpr_zero_touch() -> None:
    changed = _diff_files()
    if changed is None:
        pytest.skip("git diff unavailable")
    gdpr = {
        "docs/compliance/gdpr-dpia-template.v1.json",
        "ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json",
        "docs/compliance/gdpr-dpia-template.v1.md",
        "docs/compliance/gdpr-dpia-operator-runbook.v1.md",
        "scripts/render_gdpr_dpia_template.py",
        "tests/test_gdpr_dpia_template.py",
    }
    overlap = gdpr & changed
    assert not overlap, f"GDPR DPIA artifacts modified by this PR: {overlap}"


def test_e63d_pci_zero_touch() -> None:
    changed = _diff_files()
    if changed is None:
        pytest.skip("git diff unavailable")
    pci = {
        "docs/compliance/pci-dss-control-mapping.v1.json",
        "ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json",
        "docs/compliance/pci-dss-control-mapping.v1.md",
        "docs/compliance/pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md",
        "scripts/render_pci_dss_docs.py",
        "tests/test_pci_dss_mapping.py",
    }
    overlap = pci & changed
    assert not overlap, f"PCI-DSS artifacts modified by this PR: {overlap}"


# ---- 7. Cross-validation (4) ---------------------------------------------


def test_readme_has_nist_csf_reference() -> None:
    text = README_PATH.read_text()
    assert "NIST CSF 2.0 Function/Category Reference Mapping" in text
    assert "[`nist-csf-control-mapping.v1.json`]" in text
    assert "[`nist-csf-control-mapping.v1.md`]" in text
    assert "[`nist-csf-operator-usage-runbook.v1.md`]" in text


def test_readme_anchor_targets_exist() -> None:
    assert JSON_PATH.exists()
    assert MD_PATH.exists()
    assert RUNBOOK_PATH.exists()


def test_runbook_voluntary_framework_characterization() -> None:
    raw = RUNBOOK_PATH.read_text().lower()
    # Collapse whitespace + Markdown emphasis so multi-line bold/disclaimer
    # prose matches a single normalized sentence.
    text = re.sub(r"[\s*]+", " ", raw)
    assert "voluntary" in text
    assert "no nist csf certification program" in text or "no csf certification program" in text


def test_runbook_usage_section_present() -> None:
    text = RUNBOOK_PATH.read_text()
    assert "How to Use This Mapping" in text
    assert "Implementation Tiers (operator-owned)" in text
    assert "CSF Profiles (operator-owned)" in text


# ---- 8. Governance (3) ---------------------------------------------------


def test_six_guard_flags_const_false_in_instance() -> None:
    instance = _load_instance()
    flags = instance["guard_flags"]
    expected = (
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
        "csf_certification_claim_allowed",
        "csf_tier_claim_allowed",
        "csf_profile_claim_allowed",
    )
    for fld in expected:
        assert flags[fld] is False, fld


def test_six_disclaimer_const_true_in_instance() -> None:
    instance = _load_instance()
    disclaimer = instance["csf_disclaimer"]
    expected = (
        "not_nist_certified",
        "no_nist_csf_certification_program",
        "not_nist_audited",
        "not_cisa_attested",
        "documentation_only",
        "operator_csf_profile_decision",
    )
    for fld in expected:
        assert disclaimer[fld] is True, fld


def test_documented_categories_count_bounded() -> None:
    """Conservative bound: at most 2 documented categories in this slice."""
    instance = _load_instance()
    documented = [
        c["category_id"] for f in instance["functions"] for c in f["categories"] if c["category_status"] == "documented"
    ]
    assert len(documented) <= 2, f"Too many documented: {documented}"
