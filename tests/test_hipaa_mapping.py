"""Invariant test suite for V5 Epic 6 E-6-3b: HIPAA control mapping.

Codex 019e84ee cross-AI plan-time AGREE (2 iters: REVISE → AGREE).

5 BLOCKER + 9 hardening absorbed:
- F1 citation grammar + stable control_id slug
- F2 Technical Safeguards out_of_scope (no ePHI claim) + 2 const pin
- F3 covered-entity discipline narrowed to self-claim forms
- F4 Markdown drift/parity (deterministic renderer + byte-equal)
- F5 Section-level applicability + section_status enum

~30 invariants across 10 sections.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "hipaa-control-mapping.schema.v1.json"
HIPAA_JSON_PATH = REPO_ROOT / "docs" / "compliance" / "hipaa-control-mapping.v1.json"
HIPAA_MD_PATH = REPO_ROOT / "docs" / "compliance" / "hipaa-control-mapping.v1.md"
COMPLIANCE_README_PATH = REPO_ROOT / "docs" / "compliance" / "README.md"
RENDERER_PATH = REPO_ROOT / "scripts" / "render_hipaa_mapping.py"

E63_CATALOG_PATH = REPO_ROOT / "docs" / "compliance" / "control-evidence-catalog.v1.json"
E63_SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "control-evidence-catalog.schema.v1.json"
E63_SOC2_MD = REPO_ROOT / "docs" / "compliance" / "soc2-trust-services-criteria-mapping.v1.md"
E63_ISO_MD = REPO_ROOT / "docs" / "compliance" / "iso-27001-controls-mapping.v1.md"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (6 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_schema_root_additional_properties_false():
    assert _load(SCHEMA_PATH).get("additionalProperties") is False


def test_schema_const_pins():
    schema = _load(SCHEMA_PATH)
    props = schema["properties"]
    assert props["schema_version"]["const"] == "hipaa-control-mapping.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["artifact_kind"]["const"] == "hipaa-control-mapping"
    assert props["framework_version"]["const"] == "HIPAA-2003-amended-2013"


def test_schema_guard_flags_const_false():
    schema = _load(SCHEMA_PATH)
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_schema_hipaa_disclaimer_6_const_true():
    """6 disclaimer const true (documentation_only added per Codex H1)."""
    schema = _load(SCHEMA_PATH)
    disc = schema["properties"]["hipaa_disclaimer"]["properties"]
    for key in (
        "not_certified",
        "not_audited",
        "documentation_only",
        "not_phi_processor",
        "not_baa_template",
        "operator_legal_counsel_required",
    ):
        assert disc[key]["const"] is True, f"hipaa_disclaimer.{key} must be const true"


def test_schema_phi_handling_disclosure_pins():
    schema = _load(SCHEMA_PATH)
    phi = schema["properties"]["phi_handling_disclosure"]["properties"]
    assert phi["ao_kernel_processes_phi"]["const"] is False
    assert phi["no_phi_in_repo"]["const"] is True
    assert phi["operator_phi_handler_decision"]["const"] is True


# ---------------------------------------------------------------------------
# Section 2 — Schema negative tests (4 invariants)
# ---------------------------------------------------------------------------


def _validate(instance: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(_load(SCHEMA_PATH)).validate(instance)


def test_schema_rejects_production_platform_claim_true():
    data = _load(HIPAA_JSON_PATH)
    data["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate(data)


def test_schema_rejects_ao_kernel_processes_phi_true():
    """Codex F2 absorb: PHI processing claim YASAK."""
    data = _load(HIPAA_JSON_PATH)
    data["phi_handling_disclosure"]["ao_kernel_processes_phi"] = True
    with pytest.raises(Exception):
        _validate(data)


def test_schema_rejects_ephi_control_owned_false():
    """Codex F2 absorb: every control.ephi_control_operator_owned const true."""
    data = _load(HIPAA_JSON_PATH)
    admin_section = next(s for s in data["sections"] if s["id"] == "administrative_safeguards")
    admin_section["controls"][0]["ephi_control_operator_owned"] = False
    with pytest.raises(Exception):
        _validate(data)


def test_schema_rejects_bad_citation_format():
    data = _load(HIPAA_JSON_PATH)
    admin_section = next(s for s in data["sections"] if s["id"] == "administrative_safeguards")
    admin_section["controls"][0]["citation"] = "not-a-citation"
    with pytest.raises(Exception):
        _validate(data)


# ---------------------------------------------------------------------------
# Section 3 — Section content (4 invariants)
# ---------------------------------------------------------------------------


def test_data_validates_against_schema():
    _validate(_load(HIPAA_JSON_PATH))


def test_exactly_five_sections():
    data = _load(HIPAA_JSON_PATH)
    section_ids = {s["id"] for s in data["sections"]}
    expected = {
        "administrative_safeguards",
        "physical_safeguards",
        "technical_safeguards",
        "privacy_rule",
        "breach_notification",
    }
    assert section_ids == expected


def test_privacy_rule_and_breach_notification_not_applicable():
    """Codex F5 absorb: Privacy Rule + Breach Notification section_status not_applicable."""
    data = _load(HIPAA_JSON_PATH)
    for sid in ("privacy_rule", "breach_notification"):
        section = next(s for s in data["sections"] if s["id"] == sid)
        assert section["section_status"] == "not_applicable"
        assert section["controls"] == []


def test_technical_safeguards_all_out_of_scope():
    """Codex F2 absorb: all Technical Safeguards out_of_scope (no ePHI claim)."""
    data = _load(HIPAA_JSON_PATH)
    tech = next(s for s in data["sections"] if s["id"] == "technical_safeguards")
    for control in tech["controls"]:
        assert control["ao_kernel_status"] == "out_of_scope", (
            f"Technical Safeguard {control['citation']} must be out_of_scope; got {control['ao_kernel_status']}"
        )


# ---------------------------------------------------------------------------
# Section 4 — Citation grammar (3 invariants — Codex F1 absorb)
# ---------------------------------------------------------------------------


CITATION_PATTERN = re.compile(r"^§164\.[0-9]{3}(\([a-z]\))?(\([0-9]+\))?([a-z])?(-([0-9]{3})?(-164\.[0-9]{3})?)?$")


def test_all_committed_citations_match_grammar():
    data = _load(HIPAA_JSON_PATH)
    for section in data["sections"]:
        for control in section["controls"]:
            assert CITATION_PATTERN.fullmatch(control["citation"]), f"bad citation: {control['citation']!r}"


@pytest.mark.parametrize(
    "citation",
    [
        "§164.308(a)(1)",
        "§164.310(b)",
        "§164.500-534",
        "§164.402-414",
    ],
)
def test_citation_grammar_positive_fixtures(citation):
    """Codex F1 absorb: 4 positive forms must match."""
    assert CITATION_PATTERN.fullmatch(citation), f"positive fixture failed: {citation}"


@pytest.mark.parametrize(
    "citation",
    [
        "164.308(a)(1)",  # missing §
        "§abc.308(a)(1)",  # non-numeric part
        "not-a-citation",
        "§164.30800a1",  # malformed parens
    ],
)
def test_citation_grammar_negative_fixtures(citation):
    assert not CITATION_PATTERN.fullmatch(citation), f"negative fixture matched: {citation}"


# ---------------------------------------------------------------------------
# Section 5 — Wording discipline (5 invariants)
# ---------------------------------------------------------------------------


_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_RE = re.compile(r"^(\s*)```")


def _iter_prose_lines(text: str):
    """Yield (line, prose) tuples for non-fenced lines with inline code stripped."""
    in_fence = False
    for line in text.splitlines():
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _INLINE_CODE_RE.sub("", line)
        yield line, prose


def _hipaa_prose_docs() -> list[Path]:
    """Prose documents only (Markdown). JSON SSOT is structured and lists
    prohibited tokens as data values inside `prohibited_claims`; running the
    text scanner over the JSON would flag its own discipline declarations.
    """
    return [HIPAA_MD_PATH]


HIPAA_PROHIBITED_TOKENS = (
    "hipaa compliant",
    "hipaa-compliant",
    "hipaa certified",
    "hipaa-certified",
    "phi-safe",
    "baa-ready",
    "we comply with hipaa",
    "hipaa-grade",
    "fully hipaa",
    "guaranteed phi protection",
)


def test_no_prohibited_hipaa_claim_language():
    """Codex F4/H2 absorb: hyphen-normalized, prose-only Markdown scanner.

    The Markdown disclaimer enumerates forbidden tokens inside inline code
    spans, which the prose iterator strips. The JSON SSOT lists the same
    tokens as data values under ``prohibited_claims``; that listing is
    enforced by ``test_prohibited_claims_list_matches_scanner_constants``
    rather than the prose scanner.
    """
    for path in _hipaa_prose_docs():
        text = path.read_text()
        for raw_line, prose in _iter_prose_lines(text):
            lowered_prose = prose.lower()
            lowered_raw = raw_line.lower()
            if "prohibited_claims" in lowered_raw or "scanner" in lowered_raw or "forbidden" in lowered_raw:
                continue
            for token in HIPAA_PROHIBITED_TOKENS:
                if token in lowered_prose:
                    pytest.fail(f"prohibited HIPAA claim in {path.name}: token={token!r}; line={raw_line!r}")


# Codex F3 absorb: covered-entity self-claim forms YASAK; generic legal use OK.
COVERED_ENTITY_FORBIDDEN = (
    re.compile(r"\bao-kernel\s+is\s+a\s+covered\s+entity\b", re.IGNORECASE),
    re.compile(r"\bwe\s+are\s+a\s+covered\s+entity\b", re.IGNORECASE),
    re.compile(r"\bcovered[\s-]entity\s+ready\b", re.IGNORECASE),
    re.compile(r"\bcovered[\s-]entity\s+(?:certified|approved|qualified)\b", re.IGNORECASE),
)


def test_no_self_claim_covered_entity_forms():
    """Codex F3 absorb: 4 self-claim form patterns YASAK across all artifacts."""
    for path in (HIPAA_JSON_PATH, HIPAA_MD_PATH):
        text = path.read_text()
        for pat in COVERED_ENTITY_FORBIDDEN:
            assert not pat.search(text), f"covered-entity self-claim in {path.name}: pattern={pat.pattern}"


# Codex H4 absorb. The HIPAA Security Rule § 164.308(b) standard is officially
# titled "Business Associate Contracts and Other Arrangements" so the noun
# "Business Associate Agreements (BAA)" appears in the regulatory context.
# The forbidden contract-construction patterns are imperatives ("shall...")
# that signal someone is drafting a BAA inside this repo.
BAA_FORBIDDEN_PATTERNS = (
    re.compile(r"\bcovered\s+entity\s+shall\b", re.IGNORECASE),
    re.compile(r"\bbusiness\s+associate\s+shall\b", re.IGNORECASE),
    re.compile(r"\bshall\s+notify\b", re.IGNORECASE),
    re.compile(r"\bthis\s+(?:agreement|baa)\s+(?:governs|covers|applies)\b", re.IGNORECASE),
)


def test_no_baa_template_language():
    """Codex H4 absorb: BAA contract-construction patterns YASAK in prose.

    Imperative contract phrases ("shall notify", "covered entity shall")
    signal that someone is drafting a BAA inside the repo. The regulatory
    title "Business Associate Contracts and Other Arrangements" remains
    permitted as a HIPAA Security Rule citation.
    """
    for path in (HIPAA_JSON_PATH, HIPAA_MD_PATH):
        text = path.read_text()
        for pat in BAA_FORBIDDEN_PATTERNS:
            assert not pat.search(text), f"BAA template language in {path.name}: pattern={pat.pattern}"


SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
MRN_PATTERN = re.compile(r"\bMRN[:\s-]\d{6,}", re.IGNORECASE)


def test_no_phi_sample_data():
    """No SSN or MRN-looking patterns in committed artifacts."""
    for path in (HIPAA_JSON_PATH, HIPAA_MD_PATH):
        text = path.read_text()
        assert not SSN_PATTERN.search(text), f"SSN-like pattern in {path.name}"
        assert not MRN_PATTERN.search(text), f"MRN-like pattern in {path.name}"


def test_prohibited_claims_list_matches_scanner_constants():
    """Catalog prohibited_claims must list all 10 scanner tokens."""
    data = _load(HIPAA_JSON_PATH)
    declared = {t.lower() for t in data["prohibited_claims"]}
    expected = set(HIPAA_PROHIBITED_TOKENS)
    assert declared == expected


# ---------------------------------------------------------------------------
# Section 6 — Drift / governance (4 invariants — F4 absorb)
# ---------------------------------------------------------------------------


def test_drift_committed_matches_generated(tmp_path):
    """Codex F4 absorb: deterministic renderer + byte-equal."""
    import sys as _sys

    _sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from render_hipaa_mapping import render_markdown  # noqa: E402

    data = _load(HIPAA_JSON_PATH)
    fresh = render_markdown(data)
    committed = HIPAA_MD_PATH.read_text()
    assert committed == fresh, (
        "DRIFT: committed Markdown differs from generator output. Run: python scripts/render_hipaa_mapping.py"
    )


def test_e63_catalog_file_unchanged():
    """Codex H9 absorb: SOC2/ISO catalog must remain untouched."""
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
    changed = set(result.stdout.splitlines())
    forbidden = {
        "docs/compliance/control-evidence-catalog.v1.json",
        "ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json",
        "docs/compliance/soc2-trust-services-criteria-mapping.v1.md",
        "docs/compliance/iso-27001-controls-mapping.v1.md",
    }
    for path in forbidden:
        assert path not in changed, f"E-6-3 catalog/render must remain ZERO TOUCH: {path}"


def test_no_github_workflow_change_in_pr_diff():
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
        assert not line.startswith(".github/workflows/"), f"E-6-3b must not touch workflows: {line}"


def test_e63_schema_unchanged():
    assert E63_SCHEMA_PATH.exists()
    # The E-6-3 schema content is fixed; we cannot diff without git on the
    # test runner. The other invariant `test_e63_catalog_file_unchanged`
    # covers the git-diff check; this assertion ensures the file is still
    # present (not accidentally deleted).


# ---------------------------------------------------------------------------
# Section 7 — Cross-validation (3 invariants)
# ---------------------------------------------------------------------------


def test_readme_section_3_5_hipaa_link_present():
    """Codex H8 absorb: README §3.5 HIPAA reference."""
    text = COMPLIANCE_README_PATH.read_text()
    assert "### 3.5 HIPAA Mapping Reference" in text
    assert "hipaa-control-mapping.v1.json" in text
    assert "hipaa-control-mapping.v1.md" in text


def test_documented_status_restricted():
    """Codex H7 absorb: 'documented' status conservatively bounded.

    The mapping ships three documented Administrative Safeguards entries that
    map directly to existing repo evidence surfaces (§164.308(a)(1) governance
    ADRs, §164.308(a)(6) E-6-6 incident playbook, §164.308(a)(8) cross-AI
    peer review). Every other control across all five sections is either
    `out_of_scope` or `not_applicable`. The cap stays at 3 so that adding a
    fourth `documented` row requires an explicit Codex follow-up review.
    """
    data = _load(HIPAA_JSON_PATH)
    documented = []
    for section in data["sections"]:
        for control in section["controls"]:
            if control["ao_kernel_status"] == "documented":
                documented.append(control["citation"])
    assert len(documented) <= 3, f"too many 'documented' statuses; HIPAA overclaim risk: {documented}"


def test_evidence_refs_pr_format():
    """Reused E-6-3 discipline: pr ref format `PR #\\d+`."""
    pr_pattern = re.compile(r"^PR #\d+$")
    data = _load(HIPAA_JSON_PATH)
    for section in data["sections"]:
        for control in section["controls"]:
            for ref in control["evidence_refs"]:
                if ref["type"] == "pr":
                    assert pr_pattern.fullmatch(ref["ref"]), f"bad PR ref: {ref['ref']!r}"


# ---------------------------------------------------------------------------
# Section 8 — Governance (3 invariants)
# ---------------------------------------------------------------------------


def test_guard_flags_const_false_in_instance():
    flags = _load(HIPAA_JSON_PATH)["guard_flags"]
    assert flags["support_widening_allowed"] is False
    assert flags["production_platform_claim_allowed"] is False
    assert flags["live_adapter_execution_allowed"] is False


def test_phi_handling_disclosure_pins():
    disc = _load(HIPAA_JSON_PATH)["phi_handling_disclosure"]
    assert disc["ao_kernel_processes_phi"] is False
    assert disc["no_phi_in_repo"] is True
    assert disc["operator_phi_handler_decision"] is True


def test_hipaa_disclaimer_pins():
    disc = _load(HIPAA_JSON_PATH)["hipaa_disclaimer"]
    for key in (
        "not_certified",
        "not_audited",
        "documentation_only",
        "not_phi_processor",
        "not_baa_template",
        "operator_legal_counsel_required",
    ):
        assert disc[key] is True, f"hipaa_disclaimer.{key} must be true in instance"
