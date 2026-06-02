"""V5 Epic 6 E-6-3d invariants: PCI-DSS v4.0.1 control reference mapping.

Codex 019e850a cross-AI plan-time AGREE (2 iters: REVISE -> AGREE +
must_close_findings:[]).

H11: PAN/SAD scanner walks raw text (no inline-code/fenced-code exemption);
public-claim scanner does prose-only with code exemption.
H12: Known test PAN literals live ONLY in this test file; they MUST NOT
appear in JSON/Markdown/runbook.
H13: Word-boundary regex for token scanner.
H14: req_id numeric sort `sorted(map(int, ids)) == list(range(1, 13))`.
H15: SAQ display-label source_note in runbook (not pinned in schema).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "pci-dss-control-mapping.schema.v1.json"
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "pci-dss-control-mapping.v1.json"
MD_PATH = REPO_ROOT / "docs" / "compliance" / "pci-dss-control-mapping.v1.md"
RUNBOOK_PATH = REPO_ROOT / "docs" / "compliance" / "pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md"
RENDERER_PATH = REPO_ROOT / "scripts" / "render_pci_dss_docs.py"
README_PATH = REPO_ROOT / "docs" / "compliance" / "README.md"

# F1 + H13 - 32 prohibited tokens flattened (lowered for exact-set parity)
PROHIBITED_TOKENS = (
    "pci-compliant",
    "pci compliant",
    "pci-dss compliant",
    "pci dss compliant",
    "pci-dss-compliant",
    "pci certified",
    "pci-certified",
    "pci-dss certified",
    "pci-dss-certified",
    "pci validated",
    "pci-validated",
    "pci-dss validated",
    "fully pci-dss",
    "fully pci",
    "we comply with pci-dss",
    "we comply with pci",
    "pci compliance",
    "pci-dss compliance",
    "pci-dss level 1",
    "pci-dss level 2",
    "pci-dss-approved",
    "pa-dss compliant",
    "qsa-approved",
    "qsa validated",
    "aoc-ready",
    "roc-ready",
    "saq-a ready",
    "saq-d ready",
    "saq eligible",
    "eligible for saq a",
    "pci ready",
    "pci-ready",
)

# H6 - 10 contract patterns (case-insensitive word-boundary)
CONTRACT_FORBIDDEN_PATTERNS = (
    re.compile(r"\bmerchant\s+shall\b", re.IGNORECASE),
    re.compile(r"\bservice\s+provider\s+shall\b", re.IGNORECASE),
    re.compile(r"\baoc\s+shall\b", re.IGNORECASE),
    re.compile(r"\bassessor\s+shall\b", re.IGNORECASE),
    re.compile(r"\bqsa\s+shall\b", re.IGNORECASE),
    re.compile(r"\bwe\s+have\s+completed\b", re.IGNORECASE),
    re.compile(r"\bhas\s+been\s+assessed\b", re.IGNORECASE),
    re.compile(r"\bvalidated\s+by\b", re.IGNORECASE),
    re.compile(r"\bthe\s+parties\s+agree\b", re.IGNORECASE),
    re.compile(r"\bassessment\s+confirms\b", re.IGNORECASE),
)

# F2 - PAN/SAD scanner patterns (raw text; no code exemption)
PAN_CANDIDATE_PATTERN = re.compile(r"\d[\d\s-]{11,21}\d")
# H12 - Known public test PAN list (test sabiti; YASAK in any artifact)
KNOWN_TEST_PAN_DIGITS = (
    "4242424242424242",
    "4111111111111111",
    "5555555555554444",
    "378282246310005",
    "6011000990139424",
)
TRACK1_PATTERN = re.compile(r"%B\d+\^[A-Z/\s.]+\^\d+")
TRACK2_PATTERN = re.compile(r";\d+=\d+\?")
CVV_CONTEXT_PATTERN = re.compile(r"(?:cvv2?|cvc2?|cid)[\s:]*\d{3,4}", re.IGNORECASE)
PIN_CONTEXT_PATTERN = re.compile(r"\bpin\s*block\b|\bpin[\s:]?\d{4,}", re.IGNORECASE)
EXPIRY_CONTEXT_PATTERN = re.compile(r"(?:exp|expiry|expiration)[\s:]*\d{1,2}/\d{2,4}", re.IGNORECASE)


EXPECTED_REQ_IDS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12")


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


def _luhn_valid(digits: str) -> bool:
    digits_only = re.sub(r"\D", "", digits)
    if not 13 <= len(digits_only) <= 19:
        return False
    total = 0
    parity = len(digits_only) % 2
    for i, ch in enumerate(digits_only):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _pci_prose_docs() -> list[Path]:
    return [MD_PATH, RUNBOOK_PATH]


def _pci_personal_data_artifacts() -> list[Path]:
    return [JSON_PATH, MD_PATH, RUNBOOK_PATH]


# ---- 1. Schema validity (10) ---------------------------------------------


def test_schema_is_valid_draft_2020_12() -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


def test_schema_additional_properties_false_root() -> None:
    schema = _load_schema()
    assert schema["additionalProperties"] is False


def test_schema_root_const_pins() -> None:
    schema = _load_schema()
    props = schema["properties"]
    assert props["schema_version"]["const"] == "pci-dss-control-mapping.v1"
    assert props["artifact_kind"]["const"] == "pci-dss-control-reference-mapping"
    assert props["service"]["const"] == "ao-kernel"
    assert props["operator_owned"]["const"] is True
    assert props["is_contractual_sla"]["const"] is False
    assert props["framework_version"]["const"] == "PCI-DSS-v4.0.1"


def test_schema_six_guard_flags_const_false() -> None:
    schema = _load_schema()
    flags = schema["properties"]["guard_flags"]["properties"]
    assert len(flags) == 6
    for fld, spec in flags.items():
        assert spec.get("const") is False, fld


def test_schema_seven_disclaimer_const_true() -> None:
    schema = _load_schema()
    disclaimer = schema["properties"]["pci_disclaimer"]["properties"]
    assert len(disclaimer) == 7
    for fld, spec in disclaimer.items():
        assert spec.get("const") is True, fld


def test_schema_five_chd_disclosure_pins() -> None:
    schema = _load_schema()
    disclosure = schema["properties"]["chd_handling_disclosure"]["properties"]
    assert disclosure["ao_kernel_processes_chd"]["const"] is False
    assert disclosure["ao_kernel_processes_sad"]["const"] is False
    assert disclosure["no_pan_in_repo"]["const"] is True
    assert disclosure["no_cde_in_repo"]["const"] is True
    assert disclosure["operator_cde_decision"]["const"] is True


def test_schema_saq_applicability_const_pins() -> None:
    schema = _load_schema()
    saq = schema["properties"]["saq_applicability"]["properties"]
    assert saq["repo_baseline_saq"]["const"] == "none"
    assert saq["operator_determines"]["const"] is True


def test_schema_requirements_exactly_twelve_with_contains() -> None:
    schema = _load_schema()
    reqs = schema["properties"]["requirements"]
    assert reqs["minItems"] == 12
    assert reqs["maxItems"] == 12
    contains_entries = reqs["allOf"]
    assert len(contains_entries) == 12
    seen = set()
    for entry in contains_entries:
        const_id = entry["contains"]["properties"]["req_id"]["const"]
        assert entry["minContains"] == 1
        assert entry["maxContains"] == 1
        seen.add(const_id)
    assert seen == set(EXPECTED_REQ_IDS)


def test_schema_req_status_enum_complete() -> None:
    schema = _load_schema()
    enum = schema["$defs"]["requirement"]["properties"]["req_status"]["enum"]
    assert sorted(enum) == sorted(
        [
            "documented",
            "partial",
            "out_of_scope",
            "not_applicable",
        ]
    )


def test_schema_req_id_pattern_pinned() -> None:
    schema = _load_schema()
    pattern = schema["$defs"]["requirement"]["properties"]["req_id"]["pattern"]
    assert pattern == r"^(?:[1-9]|1[0-2])$"


# ---- 2. Schema negative (5) ----------------------------------------------


def test_schema_rejects_support_widening_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["support_widening_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_cde_claim_flip() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["guard_flags"]["cde_claim_allowed"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_partial_without_evidence() -> None:
    schema = _load_schema()
    instance = _load_instance()
    # Req 6 is partial in baseline; clear its evidence_refs to violate
    for req in instance["requirements"]:
        if req["req_id"] == "6":
            req["evidence_refs"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_out_of_scope_with_evidence() -> None:
    schema = _load_schema()
    instance = _load_instance()
    for req in instance["requirements"]:
        if req["req_id"] == "1":
            req["evidence_refs"] = [{"type": "doc", "ref": "irrelevant.md", "description": "should not appear"}]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_req_id_out_of_range() -> None:
    schema = _load_schema()
    instance = _load_instance()
    instance["requirements"][0]["req_id"] = "13"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


# ---- 3. Section content (5) ----------------------------------------------


def test_instance_validates_against_schema() -> None:
    jsonschema.validate(_load_instance(), _load_schema())


def test_instance_has_exact_twelve_req_ids() -> None:
    instance = _load_instance()
    ids = [r["req_id"] for r in instance["requirements"]]
    assert sorted(map(int, ids)) == list(range(1, 13))


def test_instance_status_distribution() -> None:
    instance = _load_instance()
    counts = {"documented": 0, "partial": 0, "out_of_scope": 0, "not_applicable": 0}
    for req in instance["requirements"]:
        counts[req["req_status"]] += 1
    assert counts == {"documented": 0, "partial": 3, "out_of_scope": 7, "not_applicable": 2}


def test_req_10_partial_boundary_wording() -> None:
    instance = _load_instance()
    req10 = next(r for r in instance["requirements"] if r["req_id"] == "10")
    rationale = req10["req_rationale"].lower()
    assert "not cde logging" in rationale
    assert "not a pci control operation" in rationale


def test_req_11_partial_boundary_wording() -> None:
    instance = _load_instance()
    req11 = next(r for r in instance["requirements"] if r["req_id"] == "11")
    rationale = req11["req_rationale"].lower()
    assert "not asv scan" in rationale
    assert "not penetration test" in rationale
    assert "not a pci control operation" in rationale


# ---- 4. PAN/SAD discipline (6) -------------------------------------------


@pytest.mark.parametrize("path", _pci_personal_data_artifacts())
def test_no_luhn_valid_pan_in_raw_text(path: Path) -> None:
    """H11: scan raw text (no code exemption)."""
    text = path.read_text()
    candidates = PAN_CANDIDATE_PATTERN.findall(text)
    luhn_hits = [c for c in candidates if _luhn_valid(c)]
    assert luhn_hits == [], f"{path.name}: Luhn-valid PAN detected: {luhn_hits}"


@pytest.mark.parametrize("path", _pci_personal_data_artifacts())
def test_no_known_test_pan(path: Path) -> None:
    """H12: known public test PAN literals MUST NOT appear in artifacts."""
    text = re.sub(r"\D", "", path.read_text())
    for pan in KNOWN_TEST_PAN_DIGITS:
        assert pan not in text, f"{path.name}: known test PAN {pan[:4]}... detected"


@pytest.mark.parametrize("path", _pci_personal_data_artifacts())
def test_no_track1_data(path: Path) -> None:
    text = path.read_text()
    matches = TRACK1_PATTERN.findall(text)
    assert matches == [], f"{path.name}: Track 1 data detected: {matches}"


@pytest.mark.parametrize("path", _pci_personal_data_artifacts())
def test_no_track2_data(path: Path) -> None:
    text = path.read_text()
    matches = TRACK2_PATTERN.findall(text)
    assert matches == [], f"{path.name}: Track 2 data detected: {matches}"


@pytest.mark.parametrize("path", _pci_personal_data_artifacts())
def test_no_cvv_context(path: Path) -> None:
    text = path.read_text()
    matches = CVV_CONTEXT_PATTERN.findall(text)
    assert matches == [], f"{path.name}: CVV/CVC/CID context: {matches}"


@pytest.mark.parametrize("path", _pci_personal_data_artifacts())
def test_no_pin_block_or_pin_digits(path: Path) -> None:
    text = path.read_text()
    matches = PIN_CONTEXT_PATTERN.findall(text)
    assert matches == [], f"{path.name}: PIN context: {matches}"


# ---- 5. Wording discipline (5) -------------------------------------------


@pytest.mark.parametrize("path", _pci_prose_docs())
def test_no_prohibited_pci_claim_language(path: Path) -> None:
    """H13: word-boundary scanner; fenced + inline code exempted for prose only."""
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line).lower()
        for token in PROHIBITED_TOKENS:
            pattern = re.compile(rf"(?<![\w-]){re.escape(token)}(?![\w-])")
            assert not pattern.search(bare), f"{path.name}: prohibited token '{token}' in prose line: {line!r}"


@pytest.mark.parametrize("path", _pci_prose_docs())
def test_no_contract_language(path: Path) -> None:
    text = _strip_fenced_blocks(path.read_text())
    for line in text.splitlines():
        bare = _strip_inline_code(line)
        for pat in CONTRACT_FORBIDDEN_PATTERNS:
            assert not pat.search(bare), f"{path.name}: contract pattern '{pat.pattern}' matched in: {line!r}"


def test_prohibited_claims_list_matches_scanner_constants() -> None:
    """Exact-set parity: JSON catalog tokens == scanner literals."""
    instance = _load_instance()
    listed = sorted(t.lower() for t in instance["prohibited_claims"])
    scanner = sorted(PROHIBITED_TOKENS)
    assert listed == scanner


def test_req_10_and_11_boundary_appears_in_markdown() -> None:
    """Boundary wording must be present in generated Markdown too."""
    text = MD_PATH.read_text().lower()
    # Req 10: "NOT CDE logging"
    assert "not cde logging" in text
    # Req 11: "NOT ASV scan" + "NOT penetration test"
    assert "not asv scan" in text
    assert "not penetration test" in text


def test_runbook_qsa_engagement_workflow_section_present() -> None:
    text = RUNBOOK_PATH.read_text().lower()
    assert "qualified security assessor" in text or "qsa" in text
    assert "asv scan" in text
    assert "penetration testing" in text


# ---- 6. Drift / governance (5) -------------------------------------------


def test_drift_committed_matches_generated() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_pci", RENDERER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = json.loads(JSON_PATH.read_text())
    expected = mod.render_markdown(data)
    actual = MD_PATH.read_text()
    assert actual == expected, "Markdown drift; regenerate via render_pci_dss_docs.py"


def test_e63_catalog_zero_touch() -> None:
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
        "docs/compliance/control-evidence-catalog.v1.json",
        "ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json",
        "docs/compliance/soc2-trust-services-criteria-mapping.v1.md",
        "docs/compliance/iso-27001-controls-mapping.v1.md",
    }
    overlap = forbidden & changed
    assert not overlap, f"E-6-3 catalog modified: {overlap}"


def test_e63b_hipaa_zero_touch() -> None:
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
    hipaa = {
        "docs/compliance/hipaa-control-mapping.v1.json",
        "ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json",
        "docs/compliance/hipaa-control-mapping.v1.md",
        "scripts/render_hipaa_mapping.py",
        "tests/test_hipaa_mapping.py",
    }
    overlap = hipaa & changed
    assert not overlap, f"HIPAA artifacts modified: {overlap}"


def test_e63c_gdpr_zero_touch() -> None:
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
    gdpr = {
        "docs/compliance/gdpr-dpia-template.v1.json",
        "ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json",
        "docs/compliance/gdpr-dpia-template.v1.md",
        "docs/compliance/gdpr-dpia-operator-runbook.v1.md",
        "scripts/render_gdpr_dpia_template.py",
        "tests/test_gdpr_dpia_template.py",
    }
    overlap = gdpr & changed
    assert not overlap, f"GDPR DPIA artifacts modified: {overlap}"


# ---- 7. Cross-validation (3) ---------------------------------------------


def test_readme_has_pci_dss_reference() -> None:
    text = README_PATH.read_text()
    assert "PCI-DSS Control Reference Mapping" in text
    assert "[`pci-dss-control-mapping.v1.json`]" in text
    assert "[`pci-dss-control-mapping.v1.md`]" in text
    assert "[`pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md`]" in text


def test_runbook_saq_source_note_present() -> None:
    """H15: SAQ display labels are operator-updatable; runbook source note."""
    text = RUNBOOK_PATH.read_text().lower()
    assert "saq source note" in text
    assert "operator should re-confirm display labels" in text


def test_saq_applicability_in_instance_baseline_none() -> None:
    instance = _load_instance()
    saq = instance["saq_applicability"]
    assert saq["repo_baseline_saq"] == "none"
    assert saq["operator_determines"] is True
    assert len(saq["available_saq_types"]) == 9


# ---- 8. Governance (2) ---------------------------------------------------


def test_six_guard_flags_const_false_in_instance() -> None:
    instance = _load_instance()
    flags = instance["guard_flags"]
    expected = (
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
        "cde_claim_allowed",
        "qsa_assessment_claim_allowed",
        "saq_filing_claim_allowed",
    )
    for fld in expected:
        assert flags[fld] is False, fld


def test_seven_disclaimer_const_true_in_instance() -> None:
    instance = _load_instance()
    disclaimer = instance["pci_disclaimer"]
    expected = (
        "not_pci_certified",
        "not_aoc_holder",
        "not_roc_holder",
        "not_saq_filed",
        "not_asv_scanned",
        "documentation_only",
        "operator_qsa_engagement_required",
    )
    for fld in expected:
        assert disclaimer[fld] is True, fld
