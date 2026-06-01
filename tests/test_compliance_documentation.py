"""Invariant test suite for V5 Epic 6 E-6-3: SOC2/ISO compliance documentation.

Codex 019e83d1 cross-AI plan-time AGREE (2 iters: REVISE → AGREE).

6 must-close findings closed + 9 hardening + 2 implementation guardrails:
- F1 SOC2 CC1/CC3/CC4 explicit rows (no silent omission)
- F2 CC5 = Control Activities (not Risk Mitigation); CC9 = Risk Mitigation
- F3 Wording discipline (covered/control implemented banned; documented preferred)
- F4 Availability `partial` + explicit gaps (not out_of_scope)
- F5 ISO A.16 `partial` (not covered)
- F6 "audit-ready" forbidden
- Guardrail 1: claim negation scope narrowed to {certified, audited} only
- Guardrail 2: local-ai-review-evidence.v1.json post-impl freshness
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPLIANCE_DIR = REPO_ROOT / "docs" / "compliance"
CATALOG_PATH = COMPLIANCE_DIR / "control-evidence-catalog.v1.json"
SOC2_MD_PATH = COMPLIANCE_DIR / "soc2-trust-services-criteria-mapping.v1.md"
ISO_MD_PATH = COMPLIANCE_DIR / "iso-27001-controls-mapping.v1.md"
README_PATH = COMPLIANCE_DIR / "README.md"
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "control-evidence-catalog.schema.v1.json"
GENERATOR_PATH = REPO_ROOT / "scripts" / "render_compliance_docs.py"

COMPLIANCE_FILES = [README_PATH, SOC2_MD_PATH, ISO_MD_PATH]
ALL_ARTIFACTS = COMPLIANCE_FILES + [CATALOG_PATH]


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (8 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = load_schema()
    Draft202012Validator.check_schema(schema)


def test_schema_root_additional_properties_false():
    schema = load_schema()
    assert schema.get("additionalProperties") is False


def test_schema_root_const_pins():
    schema = load_schema()
    props = schema["properties"]
    assert props["schema_version"]["const"] == "control-evidence-catalog.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["artifact_kind"]["const"] == "compliance-posture-documentation"
    assert props["operator_owned"]["const"] is True
    assert props["is_contractual_sla"]["const"] is False


def test_schema_guard_flags_const_false():
    schema = load_schema()
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_schema_compliance_disclaimer_const_true():
    schema = load_schema()
    disc = schema["properties"]["compliance_disclaimer"]["properties"]
    assert disc["not_certified"]["const"] is True
    assert disc["not_audited"]["const"] is True
    assert disc["documentation_only"]["const"] is True


def test_schema_frameworks_exactly_two():
    schema = load_schema()
    fw = schema["properties"]["frameworks"]
    assert fw["minItems"] == 2 and fw["maxItems"] == 2


def test_schema_control_status_enum():
    schema = load_schema()
    statuses = schema["$defs"]["control"]["properties"]["ao_kernel_status"]["enum"]
    assert set(statuses) == {"documented", "partial", "out_of_scope", "not_applicable"}


def test_schema_evidence_ref_type_enum():
    schema = load_schema()
    types = schema["$defs"]["evidence_ref"]["properties"]["type"]["enum"]
    assert set(types) == {"pr", "adr", "hard_rule", "doc", "test", "source"}


# ---------------------------------------------------------------------------
# Section 2 — Schema negative tests (4 invariants)
# ---------------------------------------------------------------------------


def _validate(instance: dict, schema: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(schema).validate(instance)


def test_schema_rejects_production_platform_claim_true():
    cat = load_catalog()
    cat["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate(cat, load_schema())


def test_schema_rejects_is_contractual_sla_true():
    cat = load_catalog()
    cat["is_contractual_sla"] = True
    with pytest.raises(Exception):
        _validate(cat, load_schema())


def test_schema_rejects_bad_status_enum():
    cat = load_catalog()
    cat["frameworks"][0]["controls"][0]["ao_kernel_status"] = "implemented"
    with pytest.raises(Exception):
        _validate(cat, load_schema())


def test_schema_rejects_bad_evidence_ref_type():
    cat = load_catalog()
    # Find a control with evidence_refs and corrupt the type
    for fw in cat["frameworks"]:
        for ctrl in fw["controls"]:
            if ctrl["evidence_refs"]:
                ctrl["evidence_refs"][0]["type"] = "blog_post"
                with pytest.raises(Exception):
                    _validate(cat, load_schema())
                return
    pytest.skip("no control with evidence_refs to corrupt")


# ---------------------------------------------------------------------------
# Section 3 — Catalog content (6 invariants)
# ---------------------------------------------------------------------------


def test_catalog_validates_against_schema():
    _validate(load_catalog(), load_schema())


def test_catalog_two_frameworks():
    cat = load_catalog()
    fw_ids = [fw["id"] for fw in cat["frameworks"]]
    assert set(fw_ids) == {"SOC2-TSC", "ISO-27001-Annex-A"}


def test_soc2_thirteen_controls():
    """F1 absorb: CC1, CC3, CC4 explicit; no silent omission."""
    cat = load_catalog()
    soc2 = next(fw for fw in cat["frameworks"] if fw["id"] == "SOC2-TSC")
    ids = {c["control_id"] for c in soc2["controls"]}
    expected = {"CC1", "CC2", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "CC9", "A", "C", "PI", "P"}
    assert ids == expected, f"SOC2 missing: {expected - ids}; extra: {ids - expected}"


def test_iso_fourteen_areas():
    cat = load_catalog()
    iso = next(fw for fw in cat["frameworks"] if fw["id"] == "ISO-27001-Annex-A")
    ids = {c["control_id"] for c in iso["controls"]}
    expected = {f"A.{n}" for n in range(5, 19)}
    assert ids == expected


def test_cc5_label_is_control_activities():
    """F2 absorb: CC5 must be Control Activities, not Risk Mitigation."""
    cat = load_catalog()
    soc2 = next(fw for fw in cat["frameworks"] if fw["id"] == "SOC2-TSC")
    cc5 = next(c for c in soc2["controls"] if c["control_id"] == "CC5")
    assert "Control Activities" in cc5["name"]
    assert "Risk Mitigation" not in cc5["name"]


def test_cc9_label_is_risk_mitigation():
    """F2 absorb: CC9 must be Risk Mitigation."""
    cat = load_catalog()
    soc2 = next(fw for fw in cat["frameworks"] if fw["id"] == "SOC2-TSC")
    cc9 = next(c for c in soc2["controls"] if c["control_id"] == "CC9")
    assert "Risk Mitigation" in cc9["name"]


# ---------------------------------------------------------------------------
# Section 4 — Status-specific F4/F5 invariants (3)
# ---------------------------------------------------------------------------


def test_availability_status_partial_not_out_of_scope():
    """F4 absorb: A category must be `partial` (not `out_of_scope`)."""
    cat = load_catalog()
    soc2 = next(fw for fw in cat["frameworks"] if fw["id"] == "SOC2-TSC")
    a = next(c for c in soc2["controls"] if c["control_id"] == "A")
    assert a["ao_kernel_status"] == "partial"
    # Rationale must mention uptime out-of-scope explicitly
    assert "uptime" in a["status_rationale"].lower() or "uptime" in a["operator_boundary"].lower()


def test_iso_a16_status_partial_not_covered():
    """F5 absorb: A.16 must be `partial` (not `covered` or `documented`)."""
    cat = load_catalog()
    iso = next(fw for fw in cat["frameworks"] if fw["id"] == "ISO-27001-Annex-A")
    a16 = next(c for c in iso["controls"] if c["control_id"] == "A.16")
    assert a16["ao_kernel_status"] == "partial"


def test_privacy_status_out_of_scope():
    cat = load_catalog()
    soc2 = next(fw for fw in cat["frameworks"] if fw["id"] == "SOC2-TSC")
    p = next(c for c in soc2["controls"] if c["control_id"] == "P")
    assert p["ao_kernel_status"] == "out_of_scope"


# ---------------------------------------------------------------------------
# Section 5 — JSON ↔ Markdown parity (4 invariants)
# ---------------------------------------------------------------------------


def test_drift_committed_matches_generated(tmp_path):
    """Option C absorb: byte-equal drift test."""
    # Import generator
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from render_compliance_docs import generate  # noqa: E402

    soc2_tmp = tmp_path / "soc2.md"
    iso_tmp = tmp_path / "iso.md"
    soc2_md, iso_md = generate(CATALOG_PATH, soc2_tmp, iso_tmp)
    assert SOC2_MD_PATH.read_text() == soc2_md, "DRIFT: SOC2 Markdown differs from generator output"
    assert ISO_MD_PATH.read_text() == iso_md, "DRIFT: ISO Markdown differs from generator output"


def test_soc2_markdown_contains_all_control_ids():
    cat = load_catalog()
    soc2_text = SOC2_MD_PATH.read_text()
    soc2 = next(fw for fw in cat["frameworks"] if fw["id"] == "SOC2-TSC")
    for control in soc2["controls"]:
        assert f"`{control['control_id']}`" in soc2_text, f"SOC2 Markdown missing control {control['control_id']}"


def test_iso_markdown_contains_all_control_ids():
    cat = load_catalog()
    iso_text = ISO_MD_PATH.read_text()
    iso = next(fw for fw in cat["frameworks"] if fw["id"] == "ISO-27001-Annex-A")
    for control in iso["controls"]:
        assert f"`{control['control_id']}`" in iso_text, f"ISO Markdown missing control {control['control_id']}"


def test_markdown_status_values_rendered():
    """All status values in catalog appear in respective Markdown."""
    cat = load_catalog()
    soc2_text = SOC2_MD_PATH.read_text()
    iso_text = ISO_MD_PATH.read_text()
    for fw in cat["frameworks"]:
        target = soc2_text if fw["id"] == "SOC2-TSC" else iso_text
        for control in fw["controls"]:
            status = control["ao_kernel_status"]
            assert f"`{status}`" in target, f"{fw['id']}/{control['control_id']}: status `{status}` not in Markdown"


# ---------------------------------------------------------------------------
# Section 6 — Wording discipline (5 invariants)
# ---------------------------------------------------------------------------


# F6 absorb + Codex guardrail-1: narrow negation scope.
NEGATION_ALLOWED_TOKENS = {"certified", "audited"}

# Codex absorb: all forbidden tokens (10).
FORBIDDEN_CLAIM_TOKENS = (
    "we comply with",
    "soc2 compliant",
    "iso compliant",
    "meets soc2",
    "meets iso 27001",
    "certification-ready",
    "audit-ready",
    "certified",
    "audited",
    "control implemented",
)


_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_RE = re.compile(r"^(\s*)```")


def _strip_inline_code(line: str) -> str:
    """Strip Markdown inline `code spans` so quoted forbidden tokens are ignored.

    Forbidden tokens shown as `` `audit-ready` `` are documentation of the
    discipline, not a public claim. The scanner ignores anything inside
    backtick code spans (HARD RULE Long-term: kalıcı, machine-enforced).
    """
    return _INLINE_CODE_RE.sub("", line)


def _iter_prose_lines(text: str):
    """Yield (line_no, line, prose) for non-fenced-code lines.

    Fenced code blocks (``` ... ```) carry quoted token examples only and
    are skipped entirely; inline code spans are stripped per line.
    """
    in_fence = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _strip_inline_code(line)
        yield line_no, line, prose


def _is_negated(line_lower: str, token: str) -> bool:
    """Codex guardrail-1: negation only valid for certified/audited."""
    if token not in NEGATION_ALLOWED_TOKENS:
        return False
    return (
        f"not {token}" in line_lower
        or f"never {token}" in line_lower
        or f"without being {token}" in line_lower
        or f"non-{token}" in line_lower
    )


def _line_is_token_listing(line_lower: str) -> bool:
    """Return True if the line is enumerating forbidden tokens by name.

    Such lines (e.g. README disclaimer "does NOT contain" section, mapping
    of forbidden -> replacement wording) document the discipline. The
    scanner skips them only when they explicitly mark themselves as such.
    """
    markers = (
        "prohibited",
        "forbidden",
        "yasak",
        "claim language scanner",
        "wording discipline",
        "wording dictionary",
        "negation",
        "does not contain",
        'does not contain "',
        "this package does not",
    )
    return any(marker in line_lower for marker in markers)


def test_no_compliance_claim_language():
    """F3 + F6 absorb: scan compliance docs for forbidden public-claim tokens.

    Discipline:
    - Fenced code blocks (``` ... ```) are skipped entirely.
    - Inline backtick code spans (`token`) are stripped from each prose line.
    - Lines that explicitly mark themselves as discipline-documentation
      (prohibited / forbidden / yasak / negation / "does not contain")
      are skipped — they enumerate forbidden tokens by design.
    - Otherwise, prose containing a forbidden token fails unless the token
      is `certified` or `audited` and the line carries an explicit negation.
    """
    for path in COMPLIANCE_FILES:
        text = path.read_text()
        for _line_no, line, prose in _iter_prose_lines(text):
            lowered_prose = prose.lower()
            if _line_is_token_listing(line.lower()):
                continue
            for token in FORBIDDEN_CLAIM_TOKENS:
                if token in lowered_prose:
                    if _is_negated(lowered_prose, token):
                        continue
                    pytest.fail(f"claim language leak in {path.relative_to(REPO_ROOT)}: token={token!r}; line={line!r}")


def test_no_audit_ready_token_anywhere():
    """F6 absorb: 'audit-ready' explicitly forbidden (not negatable).

    Same discipline as test_no_compliance_claim_language: fenced code +
    inline backticks + explicit discipline-documentation lines are skipped.
    """
    for path in COMPLIANCE_FILES:
        text = path.read_text()
        for _line_no, line, prose in _iter_prose_lines(text):
            if "audit-ready" in prose.lower():
                if _line_is_token_listing(line.lower()):
                    continue
                # Allow README §6 explanation (e.g. listing forbidden tokens)
                if line.startswith('- "audit-ready"'):
                    continue
                pytest.fail(f"'audit-ready' found in {path.relative_to(REPO_ROOT)}: {line!r}")


def test_certified_audited_only_in_negation():
    """F3 absorb: 'certified' / 'audited' valid only in negation context.

    Uses the same prose/code-stripping discipline so quoted token examples
    are not flagged.
    """
    for path in COMPLIANCE_FILES:
        text = path.read_text()
        for _line_no, line, prose in _iter_prose_lines(text):
            lowered_prose = prose.lower()
            if _line_is_token_listing(line.lower()):
                continue
            for token in ("certified", "audited"):
                if token in lowered_prose:
                    if _is_negated(lowered_prose, token):
                        continue
                    pytest.fail(f"{token!r} without negation in {path.relative_to(REPO_ROOT)}: {line!r}")


def test_prohibited_claims_list_in_catalog():
    """Catalog must list all forbidden claim tokens."""
    cat = load_catalog()
    assert "prohibited_claims" in cat
    declared = {t.lower() for t in cat["prohibited_claims"]}
    expected = set(FORBIDDEN_CLAIM_TOKENS)
    assert declared == expected, (
        f"prohibited_claims mismatch: missing {expected - declared}; extra {declared - expected}"
    )


def test_no_audit_report_template_language():
    """No audit report template structure leaks into compliance docs."""
    forbidden_phrases = (
        "auditor's report",
        "report of independent",
        "we examined",
        "in our opinion",
    )
    for path in COMPLIANCE_FILES:
        text = path.read_text().lower()
        for phrase in forbidden_phrases:
            assert phrase not in text, f"audit report template language in {path.relative_to(REPO_ROOT)}: {phrase!r}"


# ---------------------------------------------------------------------------
# Section 7 — Evidence refs (3 invariants)
# ---------------------------------------------------------------------------


PR_REF_PATTERN = re.compile(r"^PR #\d+$")
HARD_RULE_REF_PATTERN = re.compile(r"^.+\(\d{4}-\d{2}-\d{2}\)$")


def test_evidence_refs_paths_exist():
    """Codex H7 absorb: doc/test/source refs must resolve on disk."""
    cat = load_catalog()
    for fw in cat["frameworks"]:
        for control in fw["controls"]:
            for ref in control["evidence_refs"]:
                if ref["type"] in {"doc", "test", "source"} and "path" in ref:
                    target = REPO_ROOT / ref["path"]
                    assert target.exists(), f"{fw['id']}/{control['control_id']}: evidence path missing: {ref['path']}"


def test_evidence_refs_pr_format():
    cat = load_catalog()
    for fw in cat["frameworks"]:
        for control in fw["controls"]:
            for ref in control["evidence_refs"]:
                if ref["type"] == "pr":
                    assert PR_REF_PATTERN.fullmatch(ref["ref"]), (
                        f"{fw['id']}/{control['control_id']}: bad PR ref: {ref['ref']!r}"
                    )


def test_evidence_refs_hard_rule_has_date():
    cat = load_catalog()
    for fw in cat["frameworks"]:
        for control in fw["controls"]:
            for ref in control["evidence_refs"]:
                if ref["type"] == "hard_rule":
                    assert HARD_RULE_REF_PATTERN.fullmatch(ref["ref"]), (
                        f"{fw['id']}/{control['control_id']}: hard_rule missing date: {ref['ref']!r}"
                    )


# ---------------------------------------------------------------------------
# Section 8 — Disclaimer parity (3 invariants)
# ---------------------------------------------------------------------------


def test_disclaimer_parity_not_certified_not_audited():
    for path in COMPLIANCE_FILES:
        text = path.read_text().lower()
        assert "not certified" in text, f"'Not certified' missing in {path.name}"
        assert "not audited" in text, f"'Not audited' missing in {path.name}"


def test_disclaimer_parity_documentation_only():
    for path in COMPLIANCE_FILES:
        text = path.read_text().lower()
        assert "documentation only" in text, f"'documentation only' missing in {path.name}"


def test_disclaimer_parity_guard_flags_mention():
    for path in COMPLIANCE_FILES:
        text = path.read_text().lower()
        assert "support_widening" in text
        assert "production_platform_claim" in text
        assert "live_adapter_execution" in text


# ---------------------------------------------------------------------------
# Section 9 — Governance (3 invariants)
# ---------------------------------------------------------------------------


def test_catalog_guard_flags_const_false():
    cat = load_catalog()
    gf = cat["guard_flags"]
    assert gf["support_widening_allowed"] is False
    assert gf["production_platform_claim_allowed"] is False
    assert gf["live_adapter_execution_allowed"] is False


def test_catalog_compliance_disclaimer_const_true():
    cat = load_catalog()
    disc = cat["compliance_disclaimer"]
    assert disc["not_certified"] is True
    assert disc["not_audited"] is True
    assert disc["documentation_only"] is True


def test_no_github_workflow_change_in_pr_diff():
    """Conservative low-risk lane: PR must not touch .github/workflows/."""
    # Check committed changes against origin/main
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
