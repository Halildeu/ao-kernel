"""AO-MA-11E-2b issue body template invariants.

Pins:
- Strict 5-field anchor section in canonical order.
- Metadata section under separate `## ` heading (parser scope boundary).
- 11E-2a parser does NOT report anchor_schema_mismatch on V5 Metadata section.
- 11E-2a parser does NOT report anchor_sha_format_invalid on rendered SHA values.
- Rendered SHA values have NO display suffix `(manifest ...)`.
"""

from __future__ import annotations

from ao_kernel._internal.ao_ma.github_mirror_drift import parse_issue_anchor
from ao_kernel._internal.ao_ma.github_mirror_sync import render_issue_body


_VALID_ARTIFACT_SHA = "sha256:" + "0" * 64
_VALID_PLAN_DIGEST = "sha256:" + "f" * 64


def _make_body() -> str:
    return render_issue_body(
        anchor={
            "spm_anchor": "AO-MA-SPM-V5-EPIC-1",
            "slice_id": "V5-EPIC-1",
            "ao_authority_artifact": ".claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md",
            "artifact_sha256": _VALID_ARTIFACT_SHA,
            "plan_digest": _VALID_PLAN_DIGEST,
        },
        metadata={
            "risk_class_source": "computed_normal",
            "evidence_classes": ["follow_up_slices", "consensus_bundles"],
            "sub_issues_planned_ref": "E-1",
        },
        title="Test",
    )


def test_render_body_anchor_section_has_5_fields():
    body = _make_body()
    anchor_section = body.split("## V5 Metadata")[0]
    for field in ("spm_anchor", "slice_id", "ao_authority_artifact", "artifact_sha256", "plan_digest"):
        assert f"**{field}:**" in anchor_section, f"missing {field} in anchor"


def test_render_body_metadata_section_has_distinct_heading():
    body = _make_body()
    assert "## V5 Anchor" in body
    assert "## V5 Metadata" in body
    # Metadata must appear AFTER anchor
    assert body.index("## V5 Anchor") < body.index("## V5 Metadata")


def test_parser_does_not_drift_on_metadata_section():
    """Codex iter-2 §D: metadata section in V5 Metadata heading MUST NOT
    create anchor_schema_mismatch."""
    body = _make_body()
    result = parse_issue_anchor(body)
    assert result.unknown == [], f"parser should ignore V5 Metadata fields; got unknown={result.unknown}"
    assert "risk_class_source" not in result.fields
    assert "evidence_classes" not in result.fields


def test_parser_finds_all_5_anchor_fields():
    body = _make_body()
    result = parse_issue_anchor(body)
    assert result.missing == [], f"missing fields: {result.missing}"
    assert result.duplicates == []
    assert set(result.fields.keys()) == {
        "spm_anchor",
        "slice_id",
        "ao_authority_artifact",
        "artifact_sha256",
        "plan_digest",
    }


def test_parser_accepts_rendered_sha_values():
    body = _make_body()
    result = parse_issue_anchor(body)
    assert result.sha_format_invalid == [], (
        f"rendered SHA values must be format-valid; got invalid={result.sha_format_invalid}"
    )
    assert result.placeholders_unresolved == []


def test_rendered_anchor_values_have_no_display_suffix():
    """Codex iter-2 §G: pure sha256:<hex>, no `(manifest ...)` suffix."""
    body = _make_body()
    # Find plan_digest line
    plan_lines = [line for line in body.splitlines() if "**plan_digest:**" in line]
    assert plan_lines
    plan_line = plan_lines[0]
    # After the backtick-wrapped value, there should be nothing else (no parens)
    # Format: `- **plan_digest:** \`sha256:fff...\``
    assert "(" not in plan_line, f"plan_digest line has unexpected suffix: {plan_line!r}"


def test_parser_recovers_anchor_values_from_rendered_body():
    """End-to-end roundtrip: render → parse → values match input."""
    anchor = {
        "spm_anchor": "AO-MA-SPM-V5-EPIC-1",
        "slice_id": "V5-EPIC-1",
        "ao_authority_artifact": ".claude/plans/X.md",
        "artifact_sha256": _VALID_ARTIFACT_SHA,
        "plan_digest": _VALID_PLAN_DIGEST,
    }
    body = render_issue_body(anchor=anchor, metadata={}, title="x")
    parsed = parse_issue_anchor(body)
    for k, v in anchor.items():
        assert parsed.fields.get(k) == v, f"{k} mismatch: expected {v}, got {parsed.fields.get(k)}"
