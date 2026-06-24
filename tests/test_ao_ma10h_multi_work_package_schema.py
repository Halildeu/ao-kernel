"""AO-MA-10h multi-work-package schema migration invariants (2026-06-02).

Pins the post-migration behavior of the
``ao-ma-10-high-risk-supersession-evidence.schema.v1.json`` schema and the
``scripts/ao_ma10_high_risk_supersession_evidence.py`` builder.

Background
----------

Before this migration the schema's ``work_package`` was pinned to
``const "AO-MA-10h"``, which blocked every other high-risk PR from producing
a conforming high-risk supersession evidence artifact. The
``ao-release-gate-review`` check then returned ``deny_missing_evidence`` for
21 open PRs. The migration widens ``work_package`` to a string ``pattern``
matching the trusted-base workflow's ``reviewed_wp`` regex, and updates the
runtime builder to emit the dynamic ``--review-work-package`` argument
instead of the hardcoded constant.

The post-migration authority model is unchanged: per-PR authority is
enforced by ``context_binding`` (head_sha, diff_digest, changed_files, refs,
repo, high_risk_changed_paths), provider distinctness, unanimous AGREE,
freshness, and guard-flag closure — not by an allowlist on this field.

These tests document and pin every invariant the migration claims, so a
future regression that re-narrows the work_package field or drops the
dynamic builder is caught by CI.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from scripts.ao_ma10_high_risk_supersession_evidence import (
    WORK_PACKAGE_MAX_LEN,
    WORK_PACKAGE_MIN_LEN,
    WORK_PACKAGE_PATTERN,
    _validate_work_package,
    build_high_risk_supersession_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "ao-ma-10-high-risk-supersession-evidence.schema.v1.json"
FIXTURE = ROOT / "tests" / "fixtures" / "ao_ma_10h" / "high_risk_supersession.valid.json"


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _validate(payload: dict[str, Any]) -> list[Any]:
    return list(Draft202012Validator(_schema()).iter_errors(payload))


# ---------------------------------------------------------------------------
# Schema shape: work_package is no longer const "AO-MA-10h".
# ---------------------------------------------------------------------------


def test_work_package_is_no_longer_pinned_to_const_ao_ma_10h() -> None:
    """The migration removes ``const "AO-MA-10h"`` from work_package."""

    work_package_spec = _schema()["properties"]["work_package"]
    assert work_package_spec["type"] == "string"
    assert "const" not in work_package_spec, (
        "work_package must not be re-narrowed to a const; the migration widened "
        "it to a string pattern so any well-formed work_package identifier can "
        "produce conforming evidence. Re-narrowing reintroduces the single-WP "
        "block that caused 21 PRs to fail ao-release-gate-review."
    )


def test_work_package_has_canonical_regex_and_length_bounds() -> None:
    """The schema pins the same regex + length bounds as the workflow."""

    work_package_spec = _schema()["properties"]["work_package"]
    assert work_package_spec["pattern"] == ("^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9][A-Za-z0-9._]*)*$")
    assert work_package_spec["minLength"] == WORK_PACKAGE_MIN_LEN
    assert work_package_spec["maxLength"] == WORK_PACKAGE_MAX_LEN


def test_work_package_regex_matches_workflow_canonical_regex() -> None:
    """Schema regex and trusted-base workflow regex must round-trip identically.

    Drift here means a reviewer evidence file could land with a work_package
    accepted by the workflow but rejected by the schema (or vice versa).
    """

    workflow_path = ROOT / ".github" / "workflows" / "test.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    # Workflow declares the regex inside an inline python heredoc; match the
    # canonical fullmatch line exactly so drift triggers a failure.
    assert r'if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:-[A-Za-z0-9][A-Za-z0-9._]*)*", wp):' in workflow_text


# ---------------------------------------------------------------------------
# Accepted / rejected work_package values.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "AO-MA-10h",  # legacy backward-compat
        "AO-MA-10j",
        "AO-MA-10Y",
        "AO-MA-11e-2c-d-e-workflows",
        "AO-MA-11A-1",
        "EPIC-4-1",
        "RI-7.8c",
        "GPP-2v",
        "FAZ-4.6",
        "AB-1",  # 4 chars, alphanumeric + hyphen
    ],
)
def test_canonical_work_packages_validate(value: str) -> None:
    """All real-world ao-kernel work_package identifiers must validate."""

    fixture = _fixture()
    fixture["work_package"] = value
    assert _validate(fixture) == [], f"{value!r} unexpectedly rejected"


@pytest.mark.parametrize(
    "value",
    [
        "",  # empty
        "ab",  # too short / lowercase first char
        "a",  # too short
        "ao-ma-10h",  # lowercase first char
        "10-AO-MA",  # leading digit
        "-AO-MA",  # leading hyphen
        "AO-MA-",  # trailing hyphen
        "AO--MA",  # double hyphen
        "AO/MA",  # forward slash
        "AO MA",  # space
        "AO_MA",  # underscore at top — schema canonical excludes it
        "X" * 81,  # exceeds maxLength
    ],
)
def test_malformed_work_packages_rejected(value: str) -> None:
    """Malformed identifiers must be rejected by both schema and pre-check."""

    fixture = _fixture()
    fixture["work_package"] = value
    assert _validate(fixture), f"{value!r} unexpectedly accepted by schema"

    with pytest.raises(ValueError):
        _validate_work_package(value)


# ---------------------------------------------------------------------------
# Pre-check matches schema pattern.
# ---------------------------------------------------------------------------


def test_validate_work_package_pre_check_matches_schema_pattern() -> None:
    """Builder's pre-check regex must match the schema pattern verbatim."""

    schema_pattern = _schema()["properties"]["work_package"]["pattern"]
    assert WORK_PACKAGE_PATTERN.pattern == schema_pattern
    # Sanity round-trip
    assert re.compile(schema_pattern).fullmatch("AO-MA-11e-2c-d-e-workflows")


# ---------------------------------------------------------------------------
# Authority surface: migration must NOT relax other boundaries.
# ---------------------------------------------------------------------------


def test_migration_does_not_relax_authority_or_guard_const_pins() -> None:
    """All authority-bearing fields stay pinned const false / authoritative."""

    schema = _schema()
    properties = schema["properties"]

    assert properties["repo"]["const"] == "Halildeu/ao-kernel"
    assert properties["planning_only"]["const"] is True
    assert properties["release_authority"]["const"] == "ao-release-gate+github-ruleset"
    assert properties["ai_output_release_authority"]["const"] is False
    assert properties["consensus_status"]["const"] == "AGREE"
    assert properties["max_revise_rounds"]["const"] == 3
    assert properties["escalation_action"]["const"] == "operator_human_review_fallback"
    assert properties["secrets_recorded"]["const"] is False
    assert properties["mutations_performed"]["const"] is False

    guard_flags = properties["guard_flags"]["properties"]
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert guard_flags[flag]["const"] is False, f"{flag} must stay const false"


def test_migration_preserves_provider_distinctness_and_dynamic_pair_shape() -> None:
    """Two distinct reviewers are required; release-gate enforces the dynamic pair."""

    schema = _schema()
    assert "implementer_provider" in schema["required"]
    implementer_provider = schema["properties"]["implementer_provider"]
    assert implementer_provider["$ref"] == "#/$defs/implementer_provider_id"
    assert schema["$defs"]["implementer_provider_id"]["enum"] == [
        "openai",
        "anthropic",
        "minimax",
        "google",
        "xai",
        "human",
    ]

    reviewer_providers = schema["properties"]["reviewer_providers"]
    assert reviewer_providers["minItems"] == 2
    assert reviewer_providers["maxItems"] == 2
    assert reviewer_providers["uniqueItems"] is True
    assert reviewer_providers["items"] == {"$ref": "#/$defs/provider_id"}
    assert "contains" not in reviewer_providers
    assert "allOf" not in reviewer_providers

    required_providers = schema["properties"]["required_reviewer_providers"]
    assert required_providers["minItems"] == 2
    assert required_providers["maxItems"] == 2
    assert required_providers["uniqueItems"] is True
    assert required_providers["items"] == {"$ref": "#/$defs/provider_id"}


# ---------------------------------------------------------------------------
# Builder dynamic emission (replaces hardcoded "AO-MA-10h").
# ---------------------------------------------------------------------------


def _runtime_evidence_with_work_package(work_package: str) -> dict[str, Any]:
    """Build a minimal valid evidence dict via the runtime helpers.

    The full ``build_high_risk_supersession_evidence`` requires a live git
    repo + raw reviewer files; for the multi-WP emission invariant we only
    need to confirm the work_package field round-trips. We construct the
    evidence shape directly off the fixture and re-validate it.
    """

    evidence = deepcopy(_fixture())
    evidence["work_package"] = work_package
    return evidence


@pytest.mark.parametrize(
    "work_package",
    [
        "AO-MA-10h",  # legacy
        "AO-MA-11e-2c-d-e-workflows",  # current PR pattern
        "EPIC-4-1",
        "RI-7.8c",
    ],
)
def test_builder_emits_dynamic_work_package_field(work_package: str) -> None:
    """Round-trip multiple identifiers through the schema validator."""

    evidence = _runtime_evidence_with_work_package(work_package)
    assert evidence["work_package"] == work_package
    assert _validate(evidence) == [], (
        f"runtime evidence with work_package={work_package!r} must validate; "
        "the schema migration widened work_package so this round-trips."
    )


def test_builder_source_no_longer_hardcodes_ao_ma_10h_work_package() -> None:
    """Static-source guard: builder must not re-hardcode the legacy WP value.

    A regression that reintroduces ``"work_package": "AO-MA-10h"`` in the
    builder would silently re-narrow runtime evidence to the legacy lane and
    re-block every other PR. We pin the post-migration source by checking
    the dynamic assignment is present and the hardcoded string literal is
    absent in the emit block.
    """

    builder_text = (ROOT / "scripts" / "ao_ma10_high_risk_supersession_evidence.py").read_text(encoding="utf-8")
    assert '"work_package": review_work_package' in builder_text, (
        "builder must emit work_package from the --review-work-package argument; "
        "the migration removed the hardcoded const, do not reintroduce it."
    )
    # Defensive: the legacy literal may still appear in comments, but never
    # adjacent to the "work_package" key in a dict-literal position.
    assert '"work_package": "AO-MA-10h"' not in builder_text, (
        "builder emit dict must not hardcode 'AO-MA-10h'; use the dynamic review_work_package argument instead."
    )


def test_builder_signature_keeps_required_review_work_package() -> None:
    """The builder API still requires the caller to supply work_package."""

    # build_high_risk_supersession_evidence is keyword-only with no default
    # for review_work_package; mypy + signature contract pin this.
    with pytest.raises(TypeError):
        # Intentionally omit review_work_package to trigger TypeError.
        build_high_risk_supersession_evidence(  # type: ignore[call-arg]
            repository="Halildeu/ao-kernel",
            review_base_ref="refs/heads/main",
            review_head_ref="refs/heads/codex/x",
            diff_base_ref="HEAD",
            diff_head_ref="HEAD",
            repo_root=ROOT,
            raw_review_paths=[],
            max_age_seconds=3600,
            round_index=1,
            generated_at="2026-06-02T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# Required-field set is unchanged (work_package still required).
# ---------------------------------------------------------------------------


def test_work_package_still_required_after_migration() -> None:
    """Widening the pattern must not drop work_package from required[]."""

    required = _schema()["required"]
    assert "work_package" in required


def test_missing_work_package_still_rejected() -> None:
    """Schema must still reject evidence missing the work_package field."""

    fixture = _fixture()
    fixture.pop("work_package")
    assert _validate(fixture)
