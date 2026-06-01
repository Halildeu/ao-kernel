"""V5 Epic 6 E-6-3c invariants: GDPR DPIA operator template.

Codex 019e84fb cross-AI plan-time AGREE (2 iters: REVISE -> AGREE +
must_close_findings:[]).

Test sections (~36 invariants):
1. Schema validity (8)
2. Schema negative (5)
3. Section content (4)
4. Placeholder discipline / no personal-data-like samples (5)
5. Wording discipline / prohibited tokens (5)
6. Drift / governance (4)
7. Cross-validation (3)
8. Governance (2)

H10: personal-data-like scanner walks BOTH JSON SSOT and Markdown
artifacts. GDPR public-claim scanner walks Markdown prose only (E-6-3
parallel).
H11: 22 prohibited tokens flattened to literal constants.
H12: applicable risk schema branch requires non-null minLength fields.
H13: contract scanner 6 patterns.
H14: Art. 36 boundary wording in runbook.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest


def _is_valid_ip(candidate: str) -> bool:
    """Helper used by the IP scanner; lifted out of test body so the test
    contains no bare ``except: pass`` (BLK-003 in conftest)."""
    with contextlib.suppress(ValueError):
        ipaddress.ip_address(candidate)
        return True
    return False


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "gdpr-dpia-template.schema.v1.json"
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "gdpr-dpia-template.v1.json"
MD_PATH = REPO_ROOT / "docs" / "compliance" / "gdpr-dpia-template.v1.md"
RUNBOOK_PATH = REPO_ROOT / "docs" / "compliance" / "gdpr-dpia-operator-runbook.v1.md"
RENDERER_PATH = REPO_ROOT / "scripts" / "render_gdpr_dpia_template.py"
README_PATH = REPO_ROOT / "docs" / "compliance" / "README.md"
E63_CATALOG = REPO_ROOT / "docs" / "compliance" / "control-evidence-catalog.v1.json"
E63_SCHEMA = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "control-evidence-catalog.schema.v1.json"

# H11 — flattened prohibited tokens (22 literal constants)
PROHIBITED_TOKENS = (
    "gdpr-compliant",
    "gdpr compliant",
    "gdpr-certified",
    "gdpr certified",
    "gdpr-ready",
    "gdpr ready",
    "fully gdpr",
    "we comply with gdpr",
    "article 35 ready",
    "article 35 compliant",
    "dpia-approved",
    "dpia approved",
    "dpia-ready",
    "dpia ready",
    "dpia compliant",
    "dpa-approved",
    "dpo approved",
    "ico approved",
    "cnil approved",
    "supervisory authority approved",
    "privacy compliant",
    "data subject rights guaranteed",
    "privacy rights guaranteed",
    "lawful basis established",
    "lawful processing confirmed",
    "consent obtained",
)

# H13 — contract-language patterns (6)
CONTRACT_FORBIDDEN_PATTERNS = (
    re.compile(r"\bagreement\s+shall\b", re.IGNORECASE),
    re.compile(r"\bcontroller\s+shall\b", re.IGNORECASE),
    re.compile(r"\bprocessor\s+shall\b", re.IGNORECASE),
    re.compile(r"\bthe\s+parties\s+agree\b", re.IGNORECASE),
    re.compile(r"\bdata\s+processing\s+agreement\b", re.IGNORECASE),
    re.compile(r"\bstandard\s+contractual\s+clauses\b", re.IGNORECASE),
)

# Personal-data-like patterns (H10 scope: BOTH JSON + Markdown)
EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
US_PHONE_PATTERN = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
IP_CANDIDATE_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
NAME_LIKE_PATTERN = re.compile(r"\b(?:John|Jane)\s+Doe\b", re.IGNORECASE)

EXPECTED_SECTION_IDS = (
    "section_0_metadata",
    "section_a_systematic_description",
    "section_b_necessity_proportionality",
    "section_c_risks",
    "section_d_mitigation",
    "section_e_consultation",
    "section_f_decision_approval",
)


# ---- helpers --------------------------------------------------------------


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _load_instance() -> dict:
    return json.loads(JSON_PATH.read_text())


def _strip_inline_code(line: str) -> str:
    # Strip both inline-code spans and fenced markers
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


def _walk_json_strings(node) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for v in node.values():
            out.extend(_walk_json_strings(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_walk_json_strings(v))
    elif isinstance(node, str):
        out.append(node)
    return out


def _gdpr_prose_markdown_docs() -> list[Path]:
    return [MD_PATH, RUNBOOK_PATH]


def _gdpr_personal_data_artifacts() -> list[Path]:
    return [JSON_PATH, MD_PATH, RUNBOOK_PATH]


# ---- 1. Schema validity (8) -----------------------------------------------


def test_schema_is_valid_draft_2020_12() -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_additional_properties_false_root() -> None:
    schema = _load_schema()
    assert schema["additionalProperties"] is False


def test_schema_has_six_disclaimer_const_true() -> None:
    schema = _load_schema()
    disclaimer = schema["properties"]["dpia_disclaimer"]["properties"]
    assert len(disclaimer) == 6
    for fld, spec in disclaimer.items():
        assert spec.get("const") is True, fld


def test_schema_has_five_personal_data_disclosure_pins() -> None:
    schema = _load_schema()
    disclosure = schema["properties"]["personal_data_disclosure"]["properties"]
    assert disclosure["ao_kernel_processes_personal_data"]["const"] is False
    assert disclosure["no_personal_data_in_repo"]["const"] is True
    assert disclosure["not_data_controller"]["const"] is True
    assert disclosure["not_data_processor_in_v1"]["const"] is True
    assert disclosure["operator_dpia_decision"]["const"] is True


def test_schema_has_six_guard_flags_const_false() -> None:
    schema = _load_schema()
    flags = schema["properties"]["guard_flags"]["properties"]
    assert len(flags) == 6
    for fld, spec in flags.items():
        assert spec.get("const") is False, fld


def test_schema_section_prefixitems_exact_seven() -> None:
    schema = _load_schema()
    sections = schema["properties"]["sections"]
    assert sections["minItems"] == 7
    assert sections["maxItems"] == 7
    assert len(sections["prefixItems"]) == 7


def test_schema_risk_status_enum_complete() -> None:
    schema = _load_schema()
    risk = schema["$defs"]["risk_item"]
    enum = risk["properties"]["risk_status"]["enum"]
    assert enum == [
        "not_applicable",
        "identified",
        "mitigated",
        "residual_high_risk_requires_art36_review",
    ]


def test_schema_section_e_consultation_enum_complete() -> None:
    schema = _load_schema()
    fields = schema["$defs"]["section_e_consultation"]["properties"]["fields"]["properties"]
    for fld_key in (
        "dpo_advice_status",
        "data_subject_views_status",
        "supervisory_authority_prior_consultation_status",
    ):
        enum = fields[fld_key]["enum"]
        assert enum == [
            "not_applicable_repo_baseline",
            "operator_to_determine",
            "completed_operator_reference",
            "not_required_operator_assessment",
        ]


# ---- 2. Schema negative (5) -----------------------------------------------


def test_schema_rejects_support_widening_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["support_widening_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_production_platform_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_live_adapter_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["live_adapter_execution_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_identified_risk_missing_likelihood() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["sections"][3]["risks"][0]["risk_status"] = "identified"
    # likelihood stays null -> must fail the applicable-branch contract
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_section_e_free_form_status() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["sections"][5]["fields"]["dpo_advice_status"] = "free_form_value"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


# ---- 3. Section content (4) -----------------------------------------------


def test_instance_validates_against_schema() -> None:
    jsonschema.validate(_load_instance(), _load_schema())


def test_instance_has_exactly_seven_section_ids_in_order() -> None:
    instance = _load_instance()
    ids = tuple(s["id"] for s in instance["sections"])
    assert ids == EXPECTED_SECTION_IDS


def test_instance_section_0_trigger_baseline_pins() -> None:
    instance = _load_instance()
    section0 = instance["sections"][0]
    trigger = section0["dpia_trigger_assessment"]
    assert trigger["repo_baseline_triggered"] is False
    assert trigger["operator_must_assess_art35_3"] is True
    assert trigger["operator_must_check_supervisory_authority_lists"] is True
    assert trigger["special_categories_or_art10_data_in_repo"] is False
    assert trigger["art35_3_a_systematic_profiling_in_repo"] is False
    assert trigger["art35_3_b_large_scale_special_categories_in_repo"] is False
    assert trigger["art35_3_c_systematic_monitoring_public_area_in_repo"] is False
    assert "article 36" in trigger["art36_residual_high_risk_prior_consultation_reminder"].lower()


def test_instance_section_c_all_risks_not_applicable_baseline() -> None:
    instance = _load_instance()
    section_c = instance["sections"][3]
    assert section_c["id"] == "section_c_risks"
    assert len(section_c["risks"]) >= 1
    for risk in section_c["risks"]:
        assert risk["risk_status"] == "not_applicable"
        assert risk["likelihood"] is None
        assert risk["severity"] is None
        assert risk["risk_score"] is None
        assert risk["mitigation"] is None


# ---- 4. Placeholder discipline (5) ---------------------------------------


@pytest.mark.parametrize("path", [JSON_PATH, MD_PATH, RUNBOOK_PATH])
def test_no_real_email_addresses(path: Path) -> None:
    """H10: scan JSON SSOT + Markdown artifacts for email patterns."""
    text = path.read_text()
    matches = EMAIL_PATTERN.findall(text)
    # The EDPB URL https://edpb.europa.eu/ contains no @, so it should not match.
    # Anything else is a violation.
    assert matches == [], f"{path.name}: real email pattern detected: {matches}"


@pytest.mark.parametrize("path", [JSON_PATH, MD_PATH, RUNBOOK_PATH])
def test_no_us_phone_numbers(path: Path) -> None:
    text = path.read_text()
    matches = US_PHONE_PATTERN.findall(text)
    assert matches == [], f"{path.name}: US phone pattern detected: {matches}"


@pytest.mark.parametrize("path", [JSON_PATH, MD_PATH, RUNBOOK_PATH])
def test_no_ssn_pattern(path: Path) -> None:
    text = path.read_text()
    matches = SSN_PATTERN.findall(text)
    assert matches == [], f"{path.name}: SSN pattern detected: {matches}"


@pytest.mark.parametrize("path", [JSON_PATH, MD_PATH, RUNBOOK_PATH])
def test_no_valid_ip_addresses(path: Path) -> None:
    """H7: regex-then-ipaddress validation; RFC 5737 also forbidden."""
    text = path.read_text()
    candidates = IP_CANDIDATE_PATTERN.findall(text)
    valid_ips = [cand for cand in candidates if _is_valid_ip(cand)]
    assert valid_ips == [], f"{path.name}: real/test-net IP detected: {valid_ips}"


@pytest.mark.parametrize("path", [JSON_PATH, MD_PATH, RUNBOOK_PATH])
def test_no_name_like_placeholders(path: Path) -> None:
    text = path.read_text()
    matches = NAME_LIKE_PATTERN.findall(text)
    assert matches == [], f"{path.name}: John/Jane Doe placeholder detected: {matches}"


# ---- 5. Wording discipline (5) -------------------------------------------


@pytest.mark.parametrize("path", _gdpr_prose_markdown_docs())
def test_no_prohibited_gdpr_claim_language(path: Path) -> None:
    """H6 + H11: Markdown-prose-only scan; fenced blocks + inline code stripped.

    JSON SSOT lists prohibited tokens as data values; that is parity-asserted
    by test_prohibited_claims_list_matches_scanner_constants and NOT scanned
    here for prohibited claims.
    """
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line).lower()
        for token in PROHIBITED_TOKENS:
            assert token not in bare, f"{path.name}: prohibited token '{token}' in prose line: {line!r}"


@pytest.mark.parametrize("path", _gdpr_prose_markdown_docs())
def test_no_contract_dpa_template_language(path: Path) -> None:
    """H13: 6 contract-construction patterns; Markdown prose only."""
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        for pat in CONTRACT_FORBIDDEN_PATTERNS:
            assert not pat.search(bare), f"{path.name}: contract pattern '{pat.pattern}' matched in: {line!r}"


def test_prohibited_claims_list_matches_scanner_constants() -> None:
    """H11 parity: JSON catalog tokens == scanner literal constants."""
    instance = _load_instance()
    listed = tuple(t.lower() for t in instance["prohibited_claims"])
    scanner = tuple(t.lower() for t in PROHIBITED_TOKENS)
    assert sorted(listed) == sorted(scanner)


def test_runbook_art36_boundary_wording_present() -> None:
    """H14: runbook must contain explicit Art. 36 operator-owned boundary."""
    raw = RUNBOOK_PATH.read_text().lower()
    # Flatten blockquote markers + collapsed whitespace so multi-line
    # disclaimer prose is matched as a single sentence.
    text = re.sub(r"[\s>]+", " ", raw)
    assert "article 36" in text
    assert "operator" in text
    # The explicit boundary sentence
    assert "remains operator and dpo/counsel responsibility" in text


def test_runbook_has_no_legal_advice_or_lawful_basis_determination() -> None:
    """H9: runbook must explicitly disclaim lawful basis determination."""
    text = RUNBOOK_PATH.read_text().lower()
    assert "does not determine lawful basis" in text


# ---- 6. Drift / governance (4) -------------------------------------------


def test_drift_committed_matches_generated() -> None:
    """H8: byte-equal Markdown drift from renderer."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_gdpr", RENDERER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = json.loads(JSON_PATH.read_text())
    expected = mod.render_markdown(data)
    actual = MD_PATH.read_text()
    assert actual == expected, "Markdown drift; regenerate via render_gdpr_dpia_template.py"


def test_e63_catalog_zero_touch() -> None:
    """E-6-3 SOC2/ISO catalog file must NOT be modified by this PR."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = set(proc.stdout.split())
    assert "docs/compliance/control-evidence-catalog.v1.json" not in changed
    assert "ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json" not in changed
    assert "docs/compliance/soc2-trust-services-criteria-mapping.v1.md" not in changed
    assert "docs/compliance/iso-27001-controls-mapping.v1.md" not in changed


def test_e63b_hipaa_zero_touch() -> None:
    """E-6-3b HIPAA artifacts (if present) must NOT be modified."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = set(proc.stdout.split())
    forbidden = {
        "docs/compliance/hipaa-control-mapping.v1.json",
        "ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json",
        "docs/compliance/hipaa-control-mapping.v1.md",
        "scripts/render_hipaa_mapping.py",
        "tests/test_hipaa_mapping.py",
    }
    overlap = forbidden & changed
    assert not overlap, f"HIPAA artifacts modified: {overlap}"


def test_no_workflows_modified() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = proc.stdout.split()
    for path in changed:
        assert not path.startswith(".github/workflows/"), f"Workflow modified by GDPR slice: {path}"


# ---- 7. Cross-validation (3) ---------------------------------------------


def test_readme_has_gdpr_dpia_reference() -> None:
    text = README_PATH.read_text()
    assert "GDPR DPIA Operator Template Reference" in text
    assert "[`gdpr-dpia-template.v1.json`]" in text
    assert "[`gdpr-dpia-template.v1.md`]" in text
    assert "[`gdpr-dpia-operator-runbook.v1.md`]" in text


def test_section_e_baseline_all_not_applicable_repo_baseline() -> None:
    instance = _load_instance()
    section_e = instance["sections"][5]
    assert section_e["id"] == "section_e_consultation"
    fields = section_e["fields"]
    assert fields["dpo_advice_status"] == "not_applicable_repo_baseline"
    assert fields["data_subject_views_status"] == "not_applicable_repo_baseline"
    assert fields["supervisory_authority_prior_consultation_status"] == "not_applicable_repo_baseline"


def test_section_a_baseline_uses_non_data_placeholders() -> None:
    """H4: Section A data fields must use non-data placeholder convention."""
    instance = _load_instance()
    section_a = instance["sections"][1]
    assert section_a["id"] == "section_a_systematic_description"
    data_fields = (
        "data_subjects",
        "personal_data_categories",
        "recipients",
        "transfers",
        "retention",
        "processors_subprocessors",
        "data_flow_summary",
    )
    for fld in data_fields:
        value = section_a["fields"][fld]
        # must look like an angle-bracketed placeholder, NOT real data
        assert value.startswith("<") and value.endswith(">"), f"Section A.{fld} not placeholder: {value!r}"
        # And must declare no-personal-data baseline
        assert "no-personal-data-in-repo-baseline" in value, (
            f"Section A.{fld} does not declare repo-baseline: {value!r}"
        )


# ---- 8. Governance (2) ---------------------------------------------------


def test_six_guard_flags_const_false_in_schema() -> None:
    schema = _load_schema()
    flags = schema["properties"]["guard_flags"]["properties"]
    expected_flags = (
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
        "regulatory_filing_claim_allowed",
        "legal_advice_claim_allowed",
        "contract_template_allowed",
    )
    for fld in expected_flags:
        assert flags[fld]["const"] is False, fld


def test_six_disclaimer_const_true_in_instance() -> None:
    instance = _load_instance()
    disclaimer = instance["dpia_disclaimer"]
    expected = (
        "not_gdpr_certification",
        "not_regulatory_approval",
        "not_actual_dpia_filing",
        "not_legal_advice",
        "documentation_only",
        "operator_legal_counsel_required",
    )
    for fld in expected:
        assert disclaimer[fld] is True, fld
