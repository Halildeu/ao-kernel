"""AO-MA-11G-1 quality profile functional tests.

Codex thread 019e8050 AGREE contract (CNS-20260601-002 iter-1..2):
- ADR parse + supersession graph (canonical edge: supersedes; cycle/
  dangling/self-ref reject; reciprocal mismatch reject).
- ISO 25010 profile schema + canonical-set EXACT (35 sub-char); per
  sub-char applicable/measure_method consistency.
- CHANGELOG discipline diff-aware: base/head bullet set fark + chore
  opt-out path.
- All artifact authority fields const false (3 guard + register +
  github_write + iso_25010_certified + certification_target +
  external_audit_claim).
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

# pyyaml is a deferred runtime dep for AO-MA-11G-1 (the pyproject and
# CHANGELOG widening + dep declaration ships in 11G-2 under operator
# governance). Only ADR parse / index tests genuinely need yaml; ISO
# 25010 profile and CHANGELOG discipline tests work without it. Mark
# the yaml-bound tests via @requires_yaml so the no-yaml environment
# still exercises the other two surfaces.
try:
    import yaml as _yaml_module  # noqa: F401

    _HAS_YAML = True
except ImportError:  # pragma: no cover - environment-dependent
    _HAS_YAML = False

requires_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")

from ao_kernel.orchestration.quality_profile import (  # noqa: E402 after importorskip
    ADR_FILENAME_PATTERN,
    ADR_ID_PATTERN,
    ISO_25010_CHARACTERISTICS,
    QualityProfileError,
    build_adr_index,
    build_changelog_verdict_artifact,
    check_changelog_compliance,
    load_iso_25010_profile,
    parse_adr,
    render_adr_index_json,
)


# ---------------------------------------------------------------------------
# Schema loader
# ---------------------------------------------------------------------------


def _load(name: str) -> dict[str, Any]:
    path = resources.files("ao_kernel.defaults.schemas").joinpath(name)
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


ADR_SCHEMA: dict[str, Any] = _load("ao-ma-adr.schema.v1.json")
ISO_SCHEMA: dict[str, Any] = _load("ao-ma-iso-25010-profile.schema.v1.json")
CHANGELOG_SCHEMA: dict[str, Any] = _load("ao-ma-changelog-discipline.schema.v1.json")


# ---------------------------------------------------------------------------
# Constants / fixtures
# ---------------------------------------------------------------------------


def _bundled_profile() -> dict[str, Any]:
    path = resources.files("ao_kernel.defaults.quality").joinpath("iso-25010-profile.v1.json")
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _adr(
    *,
    id: str = "ADR-0001",
    title: str = "Test decision",
    status: str = "accepted",
    date: str = "2026-06-01",
    deciders: list[str] | None = None,
    retrospective: bool = False,
    review_status: str | None = None,
    back_populated_at: str | None = None,
    supersedes: list[str] | None = None,
    superseded_by: str | None = None,
    body: str = "\n# Test\n\n## Decision\n\nWe do X.\n",
) -> tuple[str, str]:
    """Return (adr_text, filename)."""

    fm: dict[str, Any] = {
        "id": id,
        "title": title,
        "status": status,
        "date": date,
        "deciders": deciders or ["Claude (Anthropic)"],
        "retrospective": retrospective,
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
    }
    if retrospective:
        fm["review_status"] = review_status or "back_populated_pending_cross_ai_revalidation"
        fm["back_populated_at"] = back_populated_at or "2026-06-01T03:00:00Z"
    else:
        fm["review_status"] = review_status or "original"
    if supersedes:
        fm["supersedes"] = supersedes
    if superseded_by:
        fm["superseded_by"] = superseded_by

    import yaml as _y

    fm_text = _y.safe_dump(fm, sort_keys=False).rstrip()
    text = f"---\n{fm_text}\n---\n{body}"
    filename = f"{id}-{title.lower().replace(' ', '-')}.md"
    # filename must match ADR-NNNN-<slug>.md pattern
    slug = "test-decision" if title == "Test decision" else title.lower().replace(" ", "-")
    filename = f"{id}-{slug}.md"
    return text, filename


# ---------------------------------------------------------------------------
# Layer 1 — constants / canonical sets
# ---------------------------------------------------------------------------


def test_constants_pinned() -> None:
    assert ADR_ID_PATTERN.match("ADR-0001")
    assert not ADR_ID_PATTERN.match("ADR-1")
    assert ADR_FILENAME_PATTERN.match("ADR-0001-some-slug.md")
    assert not ADR_FILENAME_PATTERN.match("notes.md")
    assert set(ISO_25010_CHARACTERISTICS.keys()) == {
        "functional_suitability",
        "performance_efficiency",
        "compatibility",
        "interaction_capability",
        "reliability",
        "security",
        "maintainability",
        "flexibility",
    }
    total_subs = sum(len(s) for s in ISO_25010_CHARACTERISTICS.values())
    assert total_subs == 35


# ---------------------------------------------------------------------------
# Layer 2 — parse_adr
# ---------------------------------------------------------------------------


@requires_yaml
def test_parse_adr_happy() -> None:
    text, name = _adr(id="ADR-0001", retrospective=False)
    rec = parse_adr(text, name, adr_schema=ADR_SCHEMA)
    assert rec.id == "ADR-0001"
    assert rec.retrospective is False
    assert rec.review_status == "original"
    assert rec.back_populated_at is None


@requires_yaml
def test_parse_adr_retrospective_happy() -> None:
    text, name = _adr(id="ADR-0002", retrospective=True)
    rec = parse_adr(text, name, adr_schema=ADR_SCHEMA)
    assert rec.retrospective is True
    assert rec.review_status == "back_populated_pending_cross_ai_revalidation"
    assert rec.back_populated_at == "2026-06-01T03:00:00Z"


@requires_yaml
def test_parse_adr_rejects_mid_file_frontmatter_delimiter() -> None:
    text = "# Random body\n\n---\nid: ADR-0001\n---\n"
    with pytest.raises(QualityProfileError, match="first line"):
        parse_adr(text, "ADR-0001-x.md", adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_rejects_id_filename_mismatch() -> None:
    text, _ = _adr(id="ADR-0001")
    with pytest.raises(QualityProfileError, match="filename id prefix"):
        parse_adr(text, "ADR-0099-different.md", adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_rejects_bad_filename_format() -> None:
    text, _ = _adr(id="ADR-0001")
    with pytest.raises(QualityProfileError, match="does not match"):
        parse_adr(text, "notes.md", adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_rejects_yaml_parse_error() -> None:
    text = "---\nid: ADR-0001\n  invalid: : :\n---\n"
    with pytest.raises(QualityProfileError, match="YAML parse error"):
        parse_adr(text, "ADR-0001-x.md", adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_rejects_retrospective_true_without_review_status() -> None:
    text, name = _adr(id="ADR-0001", retrospective=True, review_status="original")
    # review_status='original' is invalid when retrospective=true
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        parse_adr(text, name, adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_rejects_status_superseded_without_superseded_by() -> None:
    # status=superseded but no superseded_by; schema must reject
    import yaml as _y

    fm = {
        "id": "ADR-0001",
        "title": "X",
        "status": "superseded",
        "date": "2026-06-01",
        "deciders": ["Claude (Anthropic)"],
        "retrospective": False,
        "review_status": "original",
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
    }
    text = "---\n" + _y.safe_dump(fm, sort_keys=False).rstrip() + "\n---\n\n# X\n"
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        parse_adr(text, "ADR-0001-x.md", adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_rejects_open_guard_flag() -> None:
    import yaml as _y

    fm = {
        "id": "ADR-0001",
        "title": "X",
        "status": "accepted",
        "date": "2026-06-01",
        "deciders": ["x"],
        "retrospective": False,
        "review_status": "original",
        "guard_flags": {
            "support_widening": True,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
    }
    text = "---\n" + _y.safe_dump(fm, sort_keys=False).rstrip() + "\n---\n\n# X\n"
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        parse_adr(text, "ADR-0001-x.md", adr_schema=ADR_SCHEMA)


@requires_yaml
def test_parse_adr_yaml_date_implicit_coercion_normalized() -> None:
    # Write the date unquoted so YAML coerces it to a date object.
    text = (
        "---\n"
        "id: ADR-0001\n"
        "title: X\n"
        "status: accepted\n"
        "date: 2026-06-01\n"
        "deciders:\n"
        "  - x\n"
        "retrospective: false\n"
        "review_status: original\n"
        "guard_flags:\n"
        "  support_widening: false\n"
        "  production_platform_claim: false\n"
        "  live_adapter_execution: false\n"
        "register_authority: evidence_record_only\n"
        "github_write_authorized: false\n"
        "---\n\n# X\n"
    )
    rec = parse_adr(text, "ADR-0001-x.md", adr_schema=ADR_SCHEMA)
    assert rec.date == "2026-06-01"


# ---------------------------------------------------------------------------
# Layer 3 — build_adr_index (supersession graph)
# ---------------------------------------------------------------------------


def _make_records(specs: list[dict[str, Any]]) -> list:
    recs = []
    for spec in specs:
        text, name = _adr(**spec)
        recs.append(parse_adr(text, name, adr_schema=ADR_SCHEMA))
    return recs


@requires_yaml
def test_build_adr_index_happy_chain() -> None:
    recs = _make_records(
        [
            {"id": "ADR-0001", "status": "superseded", "superseded_by": "ADR-0002"},
            {"id": "ADR-0002", "status": "accepted", "supersedes": ["ADR-0001"]},
        ]
    )
    idx = build_adr_index(recs)
    assert len(idx.entries) == 2
    assert idx.entries[0].id == "ADR-0001"  # id-asc sort


@requires_yaml
def test_build_adr_index_rejects_duplicate_id() -> None:
    recs = _make_records(
        [
            {"id": "ADR-0001"},
            {"id": "ADR-0001"},
        ]
    )
    with pytest.raises(QualityProfileError, match="duplicate id"):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_rejects_dangling_supersede_target() -> None:
    recs = _make_records(
        [
            {"id": "ADR-0001", "supersedes": ["ADR-0099"]},
        ]
    )
    with pytest.raises(QualityProfileError, match="supersedes unknown"):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_rejects_self_supersede() -> None:
    recs = _make_records(
        [
            {"id": "ADR-0001", "supersedes": ["ADR-0001"]},
        ]
    )
    with pytest.raises(QualityProfileError, match="cannot supersede itself"):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_rejects_status_superseded_without_supersession_target() -> None:
    # status=superseded + superseded_by=ADR-0002 but ADR-0002.supersedes does NOT include ADR-0001
    recs = _make_records(
        [
            {"id": "ADR-0001", "status": "superseded", "superseded_by": "ADR-0002"},
            {"id": "ADR-0002", "status": "accepted"},  # missing supersedes
        ]
    )
    with pytest.raises(QualityProfileError, match="reciprocal mismatch"):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_rejects_supersedes_target_not_marked_superseded() -> None:
    # ADR-0002 supersedes ADR-0001, but ADR-0001 status is "accepted" (not superseded)
    recs = _make_records(
        [
            {"id": "ADR-0001", "status": "accepted"},
            {"id": "ADR-0002", "status": "accepted", "supersedes": ["ADR-0001"]},
        ]
    )
    with pytest.raises(QualityProfileError, match="status is"):
        build_adr_index(recs)


@requires_yaml
def test_render_adr_index_json_is_deterministic_and_id_sorted() -> None:
    recs = _make_records(
        [
            {"id": "ADR-0003"},
            {"id": "ADR-0001"},
            {"id": "ADR-0002"},
        ]
    )
    idx = build_adr_index(recs)
    payload = json.loads(render_adr_index_json(idx))
    ids = [e["id"] for e in payload["entries"]]
    assert ids == ["ADR-0001", "ADR-0002", "ADR-0003"]


@requires_yaml
def test_render_adr_index_no_wall_clock() -> None:
    recs = _make_records([{"id": "ADR-0001"}])
    idx = build_adr_index(recs)
    payload = json.loads(render_adr_index_json(idx))
    assert "generated_at" not in payload


# ---------------------------------------------------------------------------
# Layer 4 — ISO 25010 profile loader
# ---------------------------------------------------------------------------


def test_iso_profile_happy_bundled() -> None:
    profile = _bundled_profile()
    out = load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)
    assert out is profile


def test_iso_profile_rejects_missing_characteristic() -> None:
    profile = _bundled_profile()
    profile["characteristics"].pop("security")
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


def test_iso_profile_rejects_extra_sub_characteristic() -> None:
    profile = _bundled_profile()
    profile["characteristics"]["security"]["bogus_extra_sub"] = {
        "applicable": True,
        "rationale": "x" * 20,
        "measure_method": "ci_test",
    }
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


def test_iso_profile_rejects_applicable_true_with_not_measured() -> None:
    profile = _bundled_profile()
    profile["characteristics"]["security"]["confidentiality"]["measure_method"] = "not_measured"
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


def test_iso_profile_rejects_applicable_false_with_real_method() -> None:
    profile = _bundled_profile()
    sub = profile["characteristics"]["compatibility"]["co_existence"]
    sub["applicable"] = True
    sub["measure_method"] = "manual_review"
    sub["rationale"] = "applicable now (test edit)"
    # Now flip applicable=false but keep manual_review
    sub["applicable"] = False
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


def test_iso_profile_rejects_forged_certification_claim() -> None:
    profile = _bundled_profile()
    profile["iso_25010_certified"] = True
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


def test_iso_profile_rejects_short_rationale() -> None:
    profile = _bundled_profile()
    profile["characteristics"]["security"]["confidentiality"]["rationale"] = "short"
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


def test_iso_profile_module_layer_canonical_set_check() -> None:
    # Bypass schema check by passing a schema that allows additionalProperties;
    # the module's own canonical-set re-check must still catch the drift.
    # Use a minimal "always pass" schema. Drop a sub-characteristic so the
    # module-side canonical set check (independent of the schema) trips.
    permissive_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
    profile = _bundled_profile()
    del profile["characteristics"]["security"]["confidentiality"]
    with pytest.raises(QualityProfileError, match="sub-characteristic set mismatch"):
        load_iso_25010_profile(profile, profile_schema=permissive_schema)


# ---------------------------------------------------------------------------
# Layer 5 — CHANGELOG discipline
# ---------------------------------------------------------------------------


_BASE_CHANGELOG = """# Changelog

## [Unreleased]

### Fixed

- existing bullet from before this PR
"""

_HEAD_CHANGELOG_NEW_ADDED = """# Changelog

## [Unreleased]

### Added

- a new feature line introduced in this PR

### Fixed

- existing bullet from before this PR
"""


def test_changelog_pass_when_unreleased_gained_new_bullet() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_HEAD_CHANGELOG_NEW_ADDED,
        pr_diff_paths=["CHANGELOG.md", "ao_kernel/foo.py"],
        chore_label_present=False,
        chore_rationale=None,
    )
    assert verdict.decision == "pass"
    assert verdict.checks["unreleased_entry_added"]["outcome"] == "pass"
    assert verdict.checks["changelog_in_diff"]["outcome"] == "pass"


def test_changelog_fail_when_unreleased_unchanged_no_chore_opt_out() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_BASE_CHANGELOG,  # same -> no new bullet
        pr_diff_paths=["ao_kernel/foo.py"],
        chore_label_present=False,
        chore_rationale=None,
    )
    assert verdict.decision == "fail"
    codes = {f["code"] for f in verdict.findings}
    assert "changelog_not_in_diff" in codes


def test_changelog_fail_when_changelog_in_diff_but_no_new_bullet() -> None:
    head = _BASE_CHANGELOG + "\n\n<!-- whitespace-only edit -->\n"
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=head,
        pr_diff_paths=["CHANGELOG.md"],
        chore_label_present=False,
        chore_rationale=None,
    )
    assert verdict.decision == "fail"
    codes = {f["code"] for f in verdict.findings}
    assert "unreleased_no_new_bullet" in codes


def test_changelog_pass_via_chore_opt_out() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_BASE_CHANGELOG,
        pr_diff_paths=["ao_kernel/foo.py"],
        chore_label_present=True,
        chore_rationale="dependency bump only; no user-visible behavior change",
    )
    assert verdict.decision == "pass"
    assert verdict.checks["chore_opt_out_satisfied"]["outcome"] == "pass"


def test_changelog_fail_when_chore_opt_out_rationale_too_short() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_BASE_CHANGELOG,
        pr_diff_paths=["ao_kernel/foo.py"],
        chore_label_present=True,
        chore_rationale="x",  # too short
    )
    assert verdict.decision == "fail"
    codes = {f["code"] for f in verdict.findings}
    assert "chore_rationale_too_short" in codes


def test_changelog_heading_only_edit_does_not_pass() -> None:
    head = _BASE_CHANGELOG.replace("### Fixed", "### Fixed  ")
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=head,
        pr_diff_paths=["CHANGELOG.md"],
        chore_label_present=False,
        chore_rationale=None,
    )
    assert verdict.decision == "fail"


def test_changelog_handles_relative_path_normalization() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_HEAD_CHANGELOG_NEW_ADDED,
        pr_diff_paths=["./CHANGELOG.md"],
        chore_label_present=False,
        chore_rationale=None,
    )
    assert verdict.decision == "pass"


def test_changelog_verdict_artifact_schema_valid() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_HEAD_CHANGELOG_NEW_ADDED,
        pr_diff_paths=["CHANGELOG.md"],
        chore_label_present=False,
        chore_rationale=None,
    )
    artifact = build_changelog_verdict_artifact(
        verdict,
        evaluated_at="2026-06-01T03:30:00Z",
        verdict_schema=CHANGELOG_SCHEMA,
    )
    assert artifact["decision"] == "pass"
    assert artifact["guard_flags"]["live_adapter_execution"] is False
    assert artifact["register_authority"] == "evidence_record_only"


def test_changelog_verdict_artifact_rejects_bad_evaluated_at() -> None:
    verdict = check_changelog_compliance(
        base_changelog_text=_BASE_CHANGELOG,
        head_changelog_text=_HEAD_CHANGELOG_NEW_ADDED,
        pr_diff_paths=["CHANGELOG.md"],
        chore_label_present=False,
        chore_rationale=None,
    )
    with pytest.raises(QualityProfileError, match="RFC3339"):
        build_changelog_verdict_artifact(
            verdict,
            evaluated_at="not-a-timestamp",
            verdict_schema=CHANGELOG_SCHEMA,
        )


# ---------------------------------------------------------------------------
# Layer 6 — bundled assets dogfooding
# ---------------------------------------------------------------------------


def test_bundled_iso_profile_schema_valid() -> None:
    profile = _bundled_profile()
    load_iso_25010_profile(profile, profile_schema=ISO_SCHEMA)


@requires_yaml
def test_bundled_adrs_parse_and_index_valid() -> None:
    adr_dir = Path(__file__).resolve().parent.parent / ".claude" / "plans" / "adr"
    records = []
    for entry in sorted(adr_dir.glob("ADR-*.md")):
        records.append(parse_adr(entry.read_text(encoding="utf-8"), entry.name, adr_schema=ADR_SCHEMA))
    assert len(records) >= 5
    idx = build_adr_index(records)
    assert {e.id for e in idx.entries} >= {"ADR-0001", "ADR-0002", "ADR-0003", "ADR-0004", "ADR-0005"}


@requires_yaml
def test_bundled_adr_template_not_parsed_as_adr() -> None:
    # template.md uses placeholder ADR-NNNN which the schema's id pattern rejects.
    template = Path(__file__).resolve().parent.parent / ".claude" / "plans" / "adr" / "template.md"
    with pytest.raises(QualityProfileError, match="schema-invalid"):
        parse_adr(template.read_text(encoding="utf-8"), template.name, adr_schema=ADR_SCHEMA)


# ---------------------------------------------------------------------------
# Layer 7 — Codex iter-1 absorb: supersession adversarial pin
# ---------------------------------------------------------------------------


@requires_yaml
def test_build_adr_index_rejects_supersession_cycle() -> None:
    # ADR-0001 supersedes ADR-0002; ADR-0002 supersedes ADR-0001 (cycle).
    # Both also carry status=superseded + reciprocal superseded_by to pass
    # the reciprocal pin, so the cycle check is the binding rejection.
    recs = _make_records(
        [
            {"id": "ADR-0001", "status": "superseded", "supersedes": ["ADR-0002"], "superseded_by": "ADR-0002"},
            {"id": "ADR-0002", "status": "superseded", "supersedes": ["ADR-0001"], "superseded_by": "ADR-0001"},
        ]
    )
    with pytest.raises(QualityProfileError, match="supersession cycle"):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_rejects_superseded_by_unknown_target() -> None:
    recs = _make_records(
        [
            {"id": "ADR-0001", "status": "superseded", "superseded_by": "ADR-0099"},
        ]
    )
    with pytest.raises(QualityProfileError, match="superseded_by"):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_rejects_wrong_reciprocal_superseded_by() -> None:
    # ADR-0002 supersedes ADR-0001 (with status=superseded), but
    # ADR-0001.superseded_by points to ADR-0099 instead of ADR-0002.
    recs = _make_records(
        [
            {"id": "ADR-0001", "status": "superseded", "superseded_by": "ADR-0099"},
            {"id": "ADR-0002", "status": "accepted", "supersedes": ["ADR-0001"]},
        ]
    )
    with pytest.raises(QualityProfileError):
        build_adr_index(recs)


@requires_yaml
def test_build_adr_index_preserves_real_filename() -> None:
    """Codex iter-1 absorb: index filename MUST be the actual on-disk
    filename (not a re-derived title slug)."""

    text, _ = _adr(id="ADR-0001", title="X")
    rec = parse_adr(text, "ADR-0001-custom-on-disk-name.md", adr_schema=ADR_SCHEMA)
    idx = build_adr_index([rec])
    assert idx.entries[0].filename == "ADR-0001-custom-on-disk-name.md"
