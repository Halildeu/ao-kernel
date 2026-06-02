"""V5 Epic 1 E-1-6 invariants: ADR cross-AI revalidation.

Codex thread 019e874f AGREE on schema extension format. Independent
Anthropic Plan subagent revalidated ADR-0001..0004 with AGREE verdict.

Schema invariants:
- review_status enum expanded with cross_ai_revalidation_revise_required +
  cross_ai_revalidation_red_blocked
- cross_ai_revalidation block REQUIRED when review_status in {cross_ai_validated,
  cross_ai_revalidation_revise_required, cross_ai_revalidation_red_blocked}
- block REJECTED when review_status in {original, back_populated_pending_cross_ai_revalidation}

Instance invariants:
- All 4 ADRs (ADR-0001..0004) reach review_status=cross_ai_validated
- All 4 ADRs have cross_ai_revalidation block with 2 reviewers (openai + anthropic)
- All 4 ADRs preserve 3 guard_flags const false + register_authority +
  github_write_authorized const false
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-adr.schema.v1.json"
ADR_DIR = REPO_ROOT / ".claude" / "plans" / "adr"

EXPECTED_ADRS = (
    "ADR-0001-ao-ma-spm-program-adoption.md",
    "ADR-0002-fail-closed-recompute-not-trust.md",
    "ADR-0003-native-import-import-only.md",
    "ADR-0004-cross-ai-implementer-reviewer-distinct-provider.md",
)


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _normalize_yaml_dates(node):
    """Coerce PyYAML implicit-timestamp date/datetime objects back to ISO
    strings so they match the schema's `string` + pattern contract. This
    mirrors the parse-layer behavior the ADR validator already does in the
    codebase (AO-MA-11G-1)."""
    import datetime as _dt

    if isinstance(node, dict):
        return {k: _normalize_yaml_dates(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_normalize_yaml_dates(v) for v in node]
    if isinstance(node, _dt.datetime):
        return node.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(node, _dt.date):
        return node.strftime("%Y-%m-%d")
    return node


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a Markdown file."""
    if yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    lines = text.splitlines()
    assert lines[0] == "---", "ADR missing YAML frontmatter opener"
    end = None
    for i, line in enumerate(lines[1:], 1):
        if line == "---":
            end = i
            break
    assert end is not None, "ADR missing YAML frontmatter closer"
    raw = "\n".join(lines[1:end])
    return _normalize_yaml_dates(yaml.safe_load(raw))


def _load_adr(filename: str) -> dict:
    return _parse_frontmatter((ADR_DIR / filename).read_text())


# ---- 1. Schema validity (8) ----------------------------------------------


def test_schema_is_valid_draft_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(_load_schema())


def test_schema_review_status_enum_has_five_values() -> None:
    schema = _load_schema()
    enum = schema["properties"]["review_status"]["enum"]
    assert sorted(enum) == sorted(
        [
            "original",
            "back_populated_pending_cross_ai_revalidation",
            "cross_ai_validated",
            "cross_ai_revalidation_revise_required",
            "cross_ai_revalidation_red_blocked",
        ]
    )


def test_schema_has_cross_ai_revalidation_block() -> None:
    schema = _load_schema()
    block = schema["properties"]["cross_ai_revalidation"]
    assert block["additionalProperties"] is False
    required = block["required"]
    for field in ("schema_version", "revalidated_at", "scope", "decision_mutation", "reviewers", "consensus"):
        assert field in required, field


def test_schema_cross_ai_revalidation_consts() -> None:
    schema = _load_schema()
    block = schema["properties"]["cross_ai_revalidation"]["properties"]
    assert block["schema_version"]["const"] == "ao-ma-adr-cross-ai-revalidation.v1"
    assert block["scope"]["const"] == "retrospective_attestation_only"
    assert block["decision_mutation"]["const"] is False


def test_schema_reviewer_def_requires_provider_and_verdict() -> None:
    schema = _load_schema()
    reviewer = schema["$defs"]["cross_ai_reviewer"]
    assert "provider" in reviewer["required"]
    assert "verdict" in reviewer["required"]
    assert sorted(reviewer["properties"]["verdict"]["enum"]) == sorted(["AGREE", "REVISE", "RED"])


def test_schema_reviewers_min_two() -> None:
    schema = _load_schema()
    arr = schema["properties"]["cross_ai_revalidation"]["properties"]["reviewers"]
    assert arr["minItems"] == 2


def test_schema_consensus_enum_complete() -> None:
    schema = _load_schema()
    enum = schema["properties"]["cross_ai_revalidation"]["properties"]["consensus"]["enum"]
    assert sorted(enum) == sorted(
        [
            "cross_ai_validated",
            "cross_ai_revalidation_revise_required",
            "cross_ai_revalidation_red_blocked",
        ]
    )


def test_schema_guard_flags_unchanged_const_false() -> None:
    schema = _load_schema()
    flags = schema["properties"]["guard_flags"]["properties"]
    assert flags["support_widening"]["const"] is False
    assert flags["production_platform_claim"]["const"] is False
    assert flags["live_adapter_execution"]["const"] is False


# ---- 2. Schema negative (3) ----------------------------------------------


def test_schema_rejects_cross_ai_validated_without_block() -> None:
    schema = _load_schema()
    instance = {
        "id": "ADR-9999",
        "title": "test",
        "status": "accepted",
        "date": "2026-06-02",
        "deciders": ["A"],
        "retrospective": True,
        "review_status": "cross_ai_validated",
        "back_populated_at": "2026-06-01T03:00:00Z",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_block_when_review_status_pending() -> None:
    schema = _load_schema()
    instance = {
        "id": "ADR-9999",
        "title": "test",
        "status": "accepted",
        "date": "2026-06-02",
        "deciders": ["A"],
        "retrospective": True,
        "review_status": "back_populated_pending_cross_ai_revalidation",
        "back_populated_at": "2026-06-01T03:00:00Z",
        "cross_ai_revalidation": {
            "schema_version": "ao-ma-adr-cross-ai-revalidation.v1",
            "revalidated_at": "2026-06-02T00:00:00Z",
            "scope": "retrospective_attestation_only",
            "decision_mutation": False,
            "reviewers": [
                {
                    "provider": "openai",
                    "agent": "codex",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                    "verdict": "AGREE",
                    "rationale": "x" * 30,
                },
                {
                    "provider": "anthropic",
                    "agent": "claude",
                    "reviewed_at": "2026-06-02T00:00:00Z",
                    "verdict": "AGREE",
                    "rationale": "x" * 30,
                },
            ],
            "consensus": "cross_ai_validated",
        },
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance, schema)


def test_schema_rejects_reviewer_with_invalid_verdict() -> None:
    schema = _load_schema()
    reviewer_schema = schema["$defs"]["cross_ai_reviewer"]
    bad = {
        "provider": "openai",
        "agent": "codex",
        "reviewed_at": "2026-06-02T00:00:00Z",
        "verdict": "MAYBE",
        "rationale": "x" * 30,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, reviewer_schema)


# ---- 3. ADR instance content (5) ----------------------------------------


@pytest.mark.parametrize("filename", EXPECTED_ADRS)
def test_adr_review_status_is_cross_ai_validated(filename: str) -> None:
    fm = _load_adr(filename)
    assert fm["review_status"] == "cross_ai_validated", (
        f"{filename}: review_status={fm['review_status']}, expected cross_ai_validated"
    )


@pytest.mark.parametrize("filename", EXPECTED_ADRS)
def test_adr_has_two_reviewers_distinct_provider(filename: str) -> None:
    fm = _load_adr(filename)
    revalidation = fm["cross_ai_revalidation"]
    reviewers = revalidation["reviewers"]
    assert len(reviewers) >= 2
    providers = {r["provider"] for r in reviewers}
    assert "openai" in providers
    assert "anthropic" in providers
    # Cross-AI HARD RULE: implementer ≠ reviewer providers; here both AGREE
    for r in reviewers:
        assert r["verdict"] == "AGREE"


@pytest.mark.parametrize("filename", EXPECTED_ADRS)
def test_adr_validates_against_schema(filename: str) -> None:
    schema = _load_schema()
    instance = _load_adr(filename)
    jsonschema.validate(instance, schema)


@pytest.mark.parametrize("filename", EXPECTED_ADRS)
def test_adr_guard_flags_const_false_preserved(filename: str) -> None:
    fm = _load_adr(filename)
    flags = fm["guard_flags"]
    assert flags["support_widening"] is False
    assert flags["production_platform_claim"] is False
    assert flags["live_adapter_execution"] is False


@pytest.mark.parametrize("filename", EXPECTED_ADRS)
def test_adr_consensus_matches_reviewers(filename: str) -> None:
    """Recompute-not-trust per ADR-0002: consensus must be re-derivable from verdicts."""
    fm = _load_adr(filename)
    revalidation = fm["cross_ai_revalidation"]
    verdicts = [r["verdict"] for r in revalidation["reviewers"]]
    if "RED" in verdicts:
        expected = "cross_ai_revalidation_red_blocked"
    elif "REVISE" in verdicts:
        expected = "cross_ai_revalidation_revise_required"
    else:
        expected = "cross_ai_validated"
    assert revalidation["consensus"] == expected, (
        f"{filename}: stored consensus={revalidation['consensus']}, recomputed={expected} from verdicts={verdicts}"
    )


# ---- 4. Governance ZERO TOUCH (2) ---------------------------------------


def test_no_adr_decision_section_mutation() -> None:
    """E-1-6 is revalidation-only; ADR decision body sections MUST NOT be edited.

    The frontmatter (between --- markers) may change; everything below MUST
    stay byte-identical to the version on main.
    """
    import subprocess

    proc = subprocess.run(
        ["git", "diff", "origin/main...HEAD", "--", ".claude/plans/adr/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    diff = proc.stdout
    # Every removed/added line outside the frontmatter is a violation
    in_frontmatter = False
    frontmatter_closes_seen = 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git"):
            in_frontmatter = False
            frontmatter_closes_seen = 0
            continue
        if raw.startswith("@@"):
            in_frontmatter = False
            continue
        # Hunk lines: ' ', '+', '-'
        if not raw or raw[0] not in " +-":
            continue
        content = raw[1:]
        if content == "---":
            if not in_frontmatter and frontmatter_closes_seen == 0:
                in_frontmatter = True
            elif in_frontmatter:
                in_frontmatter = False
                frontmatter_closes_seen += 1
            continue
        if raw[0] in "+-" and not in_frontmatter:
            # An added or removed line outside frontmatter — violation
            assert False, f"E-1-6 must edit only ADR frontmatter, not body: {raw!r}"
