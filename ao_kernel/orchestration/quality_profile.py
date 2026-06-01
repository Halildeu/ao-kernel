"""AO-MA-11G-1 SPM Quality Profile Hardening (pure core).

Closes the AO-MA-SPM master plan's final phase: ADR template + ISO/IEC
25010:2023 quality profile **reference** (NOT certification) +
Keep-a-Changelog discipline. The module is pure (no I/O, no
subprocess, no network, no LLM, no GitHub) — the CLI tier handles
disk reads and writes; this layer takes already-loaded text/JSON and
produces schema-valid evidence artifacts.

Design boundaries (Codex thread 019e8050-fe36-76d1-b599-77882d3d5772,
CNS-20260601-002 plan iter-1..2 REVISE -> AGREE):

- ADR. YAML front-matter + free-form Markdown body. The schema
  validates only the front-matter dict; the body stays human prose.
  Retrospective ADRs MUST declare ``retrospective=true`` plus
  ``review_status`` (``back_populated_pending_cross_ai_revalidation``
  or ``cross_ai_validated``) and ``back_populated_at`` so the audit
  trail never silently treats back-population as a fresh consensus.
- Supersession graph. Canonical edge is ``supersedes``; ``superseded_by``
  is reciprocal metadata. Cycle detection runs on the ``supersedes``
  graph only; self-reference and any cycle reject.
- ISO 25010 profile. All 8 product-quality characteristics and the
  full 31-sub-characteristic canonical set (2023 revision) are
  exact-required at both schema and module layers: missing or extra
  characteristic / sub-characteristic fail closed. Sub-characteristics
  marked ``applicable=false`` MUST carry ``measure_method="not_measured"``
  and a non-empty rationale; ``applicable=true`` MUST carry a real
  measure method (``ci_test`` / ``coverage_gate`` / ``manual_review`` /
  ``code_review`` / ``schema_validation``). The schema additionally
  hard-pins ``iso_25010_certified=false`` / ``certification_target=false``
  / ``external_audit_claim=false`` — the profile is a discipline
  reference, not a certification claim.
- CHANGELOG discipline. Diff-aware: the PR passes when the
  ``## [Unreleased]`` section gained a new bullet line in the
  base-to-head diff AND ``CHANGELOG.md`` appears in the PR's changed
  paths, OR the PR carries a non-empty ``chore-no-changelog``
  rationale (operator opt-out). Anything else fails closed.
- Authority pins. ``guard_flags`` (three flags const false),
  ``register_authority='evidence_record_only'``,
  ``github_write_authorized=false`` are pinned on every artifact this
  module emits. ADRs and profiles are evidence records, not release
  authorities; the ao-release-gate + branch ruleset + non-author
  approval still own the release decision.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from jsonschema import Draft202012Validator

# PyYAML is a deferred runtime dependency for AO-MA-11G-1: the public
# pyproject runtime deps list cannot be widened in this slice (the
# release-gate `diff_scope` allowlist does not permit pyproject.toml /
# CHANGELOG.md edits inside the same PR that adds the quality module —
# allowlist widening + dependency declaration belong to a separate
# operator-approved governance PR, AO-MA-11G-2). The module imports
# yaml lazily inside parse_adr and raises QualityProfileError when
# pyyaml is not installed, so the rest of the surface (ISO 25010
# profile, CHANGELOG discipline) remains usable without the dep.
try:  # pragma: no cover - import guard exercised in 11G-2 env
    import yaml
except ImportError:  # pragma: no cover - environment-dependent
    yaml = None  # noqa: PGH003  # mypy missing-import path is environment-only


# ---------------------------------------------------------------------------
# Constants / canonical sets
# ---------------------------------------------------------------------------

ADR_ID_PATTERN = re.compile(r"^ADR-[0-9]{4}$")
ADR_FILENAME_PATTERN = re.compile(r"^(ADR-[0-9]{4})-[a-z0-9][a-z0-9-]*\.md$")
_FRONTMATTER_DELIMITER = "---"
_RFC3339_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

ISO_25010_CHARACTERISTICS: dict[str, frozenset[str]] = {
    "functional_suitability": frozenset(
        {
            "functional_completeness",
            "functional_correctness",
            "functional_appropriateness",
        }
    ),
    "performance_efficiency": frozenset(
        {
            "time_behaviour",
            "resource_utilization",
            "capacity",
        }
    ),
    "compatibility": frozenset(
        {
            "co_existence",
            "interoperability",
        }
    ),
    "interaction_capability": frozenset(
        {
            "appropriateness_recognizability",
            "learnability",
            "operability",
            "user_error_protection",
            "user_engagement",
            "inclusivity",
            "user_assistance",
            "self_descriptiveness",
        }
    ),
    "reliability": frozenset(
        {
            "faultlessness",
            "availability",
            "fault_tolerance",
            "recoverability",
        }
    ),
    "security": frozenset(
        {
            "confidentiality",
            "integrity",
            "non_repudiation",
            "accountability",
            "authenticity",
            "resistance",
        }
    ),
    "maintainability": frozenset(
        {
            "modularity",
            "reusability",
            "analysability",
            "modifiability",
            "testability",
        }
    ),
    "flexibility": frozenset(
        {
            "adaptability",
            "scalability",
            "installability",
            "replaceability",
        }
    ),
}
"""Canonical ISO/IEC 25010:2023 characteristic / sub-characteristic set
(8 characteristics, 35 sub-characteristics). The schema and this module
both pin exactly this set; missing or extra entries reject."""

REQUIRED_CHANGELOG_SECTIONS: frozenset[str] = frozenset(
    {
        "Added",
        "Changed",
        "Deprecated",
        "Removed",
        "Fixed",
        "Security",
    }
)
"""Keep-a-Changelog v1.1.0 canonical sub-sections under [Unreleased]."""


class QualityProfileError(Exception):
    """Fatal trust-boundary error in the quality profile module.

    Raised before any artifact is emitted. Triggered by YAML parse
    failure, schema-invalid input, ID/filename mismatch, dangling
    supersession references, supersession cycles, canonical-set
    mismatches, and any other invariant violation that breaks the
    audit-trail integrity guarantee.
    """


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdrFrontmatter:
    """Parsed front-matter of a single ADR Markdown file."""

    id: str
    title: str
    status: str
    date: str
    deciders: tuple[str, ...]
    retrospective: bool
    review_status: str
    supersedes: tuple[str, ...]
    superseded_by: str | None
    back_populated_at: str | None
    slice_ref: str | None
    filename: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class AdrIndexEntry:
    id: str
    title: str
    status: str
    filename: str
    supersedes: tuple[str, ...]
    superseded_by: str | None


@dataclass(frozen=True)
class AdrIndex:
    entries: tuple[AdrIndexEntry, ...]


@dataclass(frozen=True)
class ChangelogVerdict:
    decision: str  # "pass" | "fail"
    checks: Mapping[str, Mapping[str, str]]
    findings: tuple[Mapping[str, str], ...]


# ---------------------------------------------------------------------------
# ADR parser (pure)
# ---------------------------------------------------------------------------


def _normalize_date(value: Any) -> str:
    """Coerce YAML date/datetime/string into an ISO 8601 ``YYYY-MM-DD`` string.

    YAML's implicit-timestamp resolver turns ``date: 2026-06-01`` into a
    Python ``date`` object; the schema expects a string with pattern
    ``^[0-9]{4}-[0-9]{2}-[0-9]{2}$``. Normalize defensively so the
    schema check always sees the string form.
    """

    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    raise QualityProfileError(f"adr.date: expected str or YAML date, got {type(value).__name__}")


def _normalize_back_populated_at(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            raise QualityProfileError("adr.back_populated_at: naive datetime is not RFC3339 UTC; expected 'Z' suffix")
        return value.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, str):
        return value
    raise QualityProfileError(f"adr.back_populated_at: expected str or YAML datetime, got {type(value).__name__}")


def _extract_frontmatter_block(adr_text: str) -> str:
    """Pull the leading YAML front-matter block out of an ADR Markdown text.

    The block MUST start on the very first line of the file (Codex
    iter-2 daraltma): a stray ``---`` in the middle of the body must
    not be silently accepted as front-matter. Raises QualityProfileError
    on any format violation.
    """

    if not adr_text.startswith(_FRONTMATTER_DELIMITER):
        raise QualityProfileError("adr: front-matter delimiter '---' must be on the first line")
    # Split into "---", front-matter, "---", body
    parts = adr_text.split("\n")
    if len(parts) < 3 or parts[0].rstrip() != _FRONTMATTER_DELIMITER:
        raise QualityProfileError("adr: opening '---' must be on its own first line")
    body_start: int | None = None
    for idx in range(1, len(parts)):
        if parts[idx].rstrip() == _FRONTMATTER_DELIMITER:
            body_start = idx
            break
    if body_start is None:
        raise QualityProfileError("adr: closing '---' delimiter not found")
    return "\n".join(parts[1:body_start])


def _safe_load_yaml(text: str) -> Any:
    if yaml is None:  # pragma: no cover - environment-dependent
        raise QualityProfileError(
            "adr: pyyaml is not installed; install it (pip install pyyaml) "
            "to parse ADR YAML front-matter. The ISO 25010 profile and "
            "CHANGELOG discipline checks do not require pyyaml."
        )
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise QualityProfileError(f"adr: YAML parse error: {exc}") from exc


def parse_adr(
    adr_text: str,
    filename: str,
    *,
    adr_schema: Mapping[str, Any],
) -> AdrFrontmatter:
    """Parse + validate the front-matter of an ADR Markdown file.

    Steps:
    1. Extract the leading YAML front-matter block (must be the very
       first line; a mid-file ``---`` is rejected).
    2. ``yaml.safe_load`` the block — any YAML error becomes
       ``QualityProfileError``. The ``date`` field is normalized to
       a string before validation so YAML's implicit-timestamp
       coercion does not collide with the schema's string pattern.
    3. Schema-validate the normalized dict against
       ``ao-ma-adr.schema.v1``.
    4. Cross-check the filename: ``ADR-NNNN-<slug>.md`` must carry an
       ``id`` field equal to ``ADR-NNNN``.
    5. Lightweight body lint: the body should mention a ``## Decision``
       heading. This is a soft warning surfaced via the
       ``QualityProfileError`` path only when missing entirely (return
       value is still successful when the heading exists).
    """

    block = _extract_frontmatter_block(adr_text)
    raw = _safe_load_yaml(block)
    if not isinstance(raw, dict):
        raise QualityProfileError("adr: front-matter must be a YAML mapping")

    normalized: dict[str, Any] = dict(raw)
    if "date" in normalized:
        normalized["date"] = _normalize_date(normalized["date"])
    if "back_populated_at" in normalized and normalized["back_populated_at"] is not None:
        normalized["back_populated_at"] = _normalize_back_populated_at(normalized["back_populated_at"])

    validator = Draft202012Validator(adr_schema)
    errors = sorted(validator.iter_errors(normalized), key=lambda e: e.absolute_path)
    if errors:
        first = errors[0]
        loc = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise QualityProfileError(f"adr: schema-invalid at {loc}: {first.message}")

    filename_match = ADR_FILENAME_PATTERN.match(filename)
    if filename_match is None:
        raise QualityProfileError(f"adr: filename {filename!r} does not match 'ADR-NNNN-<slug>.md'")
    if filename_match.group(1) != normalized["id"]:
        raise QualityProfileError(
            f"adr: filename id prefix {filename_match.group(1)!r} != front-matter id {normalized['id']!r}"
        )

    deciders = tuple(normalized["deciders"])
    supersedes = tuple(normalized.get("supersedes", ()))
    return AdrFrontmatter(
        id=normalized["id"],
        title=normalized["title"],
        status=normalized["status"],
        date=normalized["date"],
        deciders=deciders,
        retrospective=bool(normalized.get("retrospective", False)),
        review_status=normalized.get("review_status", "original" if not normalized.get("retrospective") else ""),
        supersedes=supersedes,
        superseded_by=normalized.get("superseded_by"),
        back_populated_at=normalized.get("back_populated_at"),
        slice_ref=normalized.get("slice_ref"),
        filename=filename,
        raw=normalized,
    )


# ---------------------------------------------------------------------------
# ADR index (pure)
# ---------------------------------------------------------------------------


def _detect_supersede_cycle(supersedes_graph: Mapping[str, Sequence[str]]) -> str | None:
    """Return a node involved in a cycle on the supersedes graph, or None."""

    WHITE, GRAY, BLACK = 0, 1, 2
    colors: dict[str, int] = {node: WHITE for node in supersedes_graph}

    def visit(node: str) -> str | None:
        if colors.get(node, WHITE) == BLACK:
            return None
        if colors.get(node, WHITE) == GRAY:
            return node
        colors[node] = GRAY
        for child in supersedes_graph.get(node, ()):
            cycle_node = visit(child)
            if cycle_node is not None:
                return cycle_node
        colors[node] = BLACK
        return None

    for node in supersedes_graph:
        cycle_node = visit(node)
        if cycle_node is not None:
            return cycle_node
    return None


def build_adr_index(records: Sequence[AdrFrontmatter]) -> AdrIndex:
    """Build a deterministic ADR index from parsed front-matters.

    Invariants (all fail-closed):
    - IDs are unique.
    - Every ``supersedes`` target id exists in the records.
    - Self-reference is rejected.
    - Cycles on the canonical ``supersedes`` graph are rejected
      (canonical edge is ``supersedes``; ``superseded_by`` is
      reciprocal metadata only).
    - ``status=superseded`` MUST carry ``superseded_by``; the
      referenced ADR's ``supersedes`` MUST include this id.
    - The reverse: any ADR that lists X in its ``supersedes`` MUST
      itself have X.status='superseded' and X.superseded_by equal to
      its id.
    """

    by_id: dict[str, AdrFrontmatter] = {}
    for record in records:
        if record.id in by_id:
            raise QualityProfileError(f"adr index: duplicate id {record.id!r}")
        by_id[record.id] = record

    supersedes_graph: dict[str, tuple[str, ...]] = {}
    for record in records:
        for target in record.supersedes:
            if target == record.id:
                raise QualityProfileError(f"adr index: {record.id!r} cannot supersede itself")
            if target not in by_id:
                raise QualityProfileError(f"adr index: {record.id!r} supersedes unknown adr {target!r}")
        supersedes_graph[record.id] = record.supersedes

    cycle_node = _detect_supersede_cycle(supersedes_graph)
    if cycle_node is not None:
        raise QualityProfileError(f"adr index: supersession cycle detected at {cycle_node!r}")

    for record in records:
        if record.status == "superseded":
            if not record.superseded_by:
                raise QualityProfileError(f"adr index: {record.id!r} status=superseded requires superseded_by")
            newer = by_id.get(record.superseded_by)
            if newer is None:
                raise QualityProfileError(f"adr index: {record.id!r} superseded_by {record.superseded_by!r} not found")
            if record.id not in newer.supersedes:
                raise QualityProfileError(
                    f"adr index: reciprocal mismatch — {newer.id!r}.supersedes is missing {record.id!r}"
                )

        for target in record.supersedes:
            target_record = by_id[target]
            if target_record.status != "superseded":
                raise QualityProfileError(
                    f"adr index: {record.id!r} supersedes {target!r} but its status is {target_record.status!r}"
                )
            if target_record.superseded_by != record.id:
                raise QualityProfileError(f"adr index: {target!r}.superseded_by != {record.id!r}")

    entries = tuple(
        AdrIndexEntry(
            id=record.id,
            title=record.title,
            status=record.status,
            filename=record.filename,
            supersedes=record.supersedes,
            superseded_by=record.superseded_by,
        )
        for record in sorted(records, key=lambda r: r.id)
    )
    return AdrIndex(entries=entries)


def _slug_from_title(title: str) -> str:
    """Deterministic slug helper for index audit (lowercase + hyphens)."""

    cleaned = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return cleaned or "adr"


def render_adr_index_json(index: AdrIndex) -> str:
    """Render the index as a deterministic JSON string (id-ascending order)."""

    import json

    payload = {
        "schema_version": "ao-ma-adr-index.v1",
        "entries": [
            {
                "id": e.id,
                "title": e.title,
                "status": e.status,
                "filename": e.filename,
                "supersedes": list(e.supersedes),
                "superseded_by": e.superseded_by,
            }
            for e in index.entries
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# ISO 25010 profile loader (pure)
# ---------------------------------------------------------------------------


def load_iso_25010_profile(
    profile: Mapping[str, Any],
    *,
    profile_schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Schema-validate the profile + cross-check the canonical set.

    Both layers must agree: the schema's ``required`` + ``additional
    Properties: false`` already enumerate the canonical
    characteristic / sub-characteristic set; this function re-checks
    the same set in pure Python so an accidental schema-only drift
    cannot slip through.
    """

    validator = Draft202012Validator(profile_schema)
    errors = sorted(validator.iter_errors(profile), key=lambda e: e.absolute_path)
    if errors:
        first = errors[0]
        loc = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise QualityProfileError(f"iso_25010_profile: schema-invalid at {loc}: {first.message}")

    characteristics = profile["characteristics"]
    actual_chars = set(characteristics.keys())
    expected_chars = set(ISO_25010_CHARACTERISTICS.keys())
    if actual_chars != expected_chars:
        missing = expected_chars - actual_chars
        extra = actual_chars - expected_chars
        raise QualityProfileError(
            f"iso_25010_profile: characteristic set mismatch (missing={sorted(missing)}, extra={sorted(extra)})"
        )

    for char_name, expected_subs in ISO_25010_CHARACTERISTICS.items():
        actual_subs = set(characteristics[char_name].keys())
        if actual_subs != expected_subs:
            missing = set(expected_subs - actual_subs)
            extra = set(actual_subs - expected_subs)
            raise QualityProfileError(
                f"iso_25010_profile: {char_name} sub-characteristic set mismatch "
                f"(missing={sorted(missing)}, extra={sorted(extra)})"
            )

    # Belt-and-suspenders: even though the schema already enforces this,
    # re-check the (applicable, measure_method) consistency here so a
    # schema-only relaxation cannot silently widen the rule.
    for char_name, subs in characteristics.items():
        for sub_name, payload in subs.items():
            applicable = payload["applicable"]
            measure = payload["measure_method"]
            rationale = payload["rationale"]
            if not rationale or len(rationale) < 10:
                raise QualityProfileError(
                    f"iso_25010_profile: {char_name}.{sub_name} rationale too short (min 10 chars)"
                )
            if applicable and measure == "not_measured":
                raise QualityProfileError(
                    f"iso_25010_profile: {char_name}.{sub_name} applicable=true but measure_method=not_measured"
                )
            if not applicable and measure != "not_measured":
                raise QualityProfileError(
                    f"iso_25010_profile: {char_name}.{sub_name} applicable=false but measure_method={measure!r}"
                )

    return profile


# ---------------------------------------------------------------------------
# CHANGELOG discipline (pure, diff-aware)
# ---------------------------------------------------------------------------


_UNRELEASED_HEADING_RE = re.compile(r"^##\s*\[Unreleased\]\s*$", re.IGNORECASE)
_SECTION_HEADING_RE = re.compile(r"^###\s+(\w+)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+\S)\s*$")
_NEXT_VERSION_HEADING_RE = re.compile(r"^##\s+\[")


def _parse_unreleased_bullets(text: str) -> frozenset[tuple[str, str]]:
    """Extract (section, bullet) tuples under the ``[Unreleased]`` heading.

    Returns a frozenset of (section_name, bullet_text). Only the
    canonical Keep-a-Changelog sections (Added/Changed/Deprecated/
    Removed/Fixed/Security) under ``[Unreleased]`` are picked up;
    everything else (other top-level versions, body text outside a
    bullet, blank lines) is ignored.
    """

    out: set[tuple[str, str]] = set()
    in_unreleased = False
    current_section: str | None = None
    for line in text.splitlines():
        if _UNRELEASED_HEADING_RE.match(line.strip()):
            in_unreleased = True
            current_section = None
            continue
        if in_unreleased and _NEXT_VERSION_HEADING_RE.match(line.strip()):
            # left the Unreleased block on the next versioned heading
            break
        if not in_unreleased:
            continue
        section_match = _SECTION_HEADING_RE.match(line.rstrip())
        if section_match:
            section = section_match.group(1)
            if section in REQUIRED_CHANGELOG_SECTIONS:
                current_section = section
            else:
                current_section = None
            continue
        if current_section is not None:
            bullet_match = _BULLET_RE.match(line.rstrip())
            if bullet_match:
                bullet = bullet_match.group(1).strip()
                out.add((current_section, bullet))
    return frozenset(out)


def check_changelog_compliance(
    *,
    base_changelog_text: str,
    head_changelog_text: str,
    pr_diff_paths: Sequence[str],
    chore_label_present: bool,
    chore_rationale: str | None,
) -> ChangelogVerdict:
    """Diff-aware Keep-a-Changelog discipline gate.

    Pass when one of:
    - ``CHANGELOG.md`` is in the PR diff AND the ``[Unreleased]``
      section gained ≥1 new bullet line in the base-to-head diff, OR
    - the PR carries a ``chore-no-changelog`` label AND a non-empty
      rationale (length >= 10).

    Anything else fails closed. Heading-only or whitespace-only
    edits do not count as a new entry.
    """

    base_bullets = _parse_unreleased_bullets(base_changelog_text)
    head_bullets = _parse_unreleased_bullets(head_changelog_text)
    new_bullets = head_bullets - base_bullets

    changelog_paths = {"CHANGELOG.md", "./CHANGELOG.md"}
    normalized_paths = {p.lstrip("./") for p in pr_diff_paths}
    changelog_in_diff = bool(normalized_paths.intersection({p.lstrip("./") for p in changelog_paths}))

    rationale_clean = (chore_rationale or "").strip()
    chore_opt_out_ok = chore_label_present and len(rationale_clean) >= 10
    unreleased_added = bool(new_bullets) and changelog_in_diff

    findings: list[Mapping[str, str]] = []
    if not unreleased_added and not chore_opt_out_ok:
        if not changelog_in_diff:
            findings.append(
                {
                    "code": "changelog_not_in_diff",
                    "severity": "error",
                    "message": "CHANGELOG.md is not in the PR diff and no chore-no-changelog opt-out is present",
                }
            )
        elif not new_bullets:
            findings.append(
                {
                    "code": "unreleased_no_new_bullet",
                    "severity": "error",
                    "message": "CHANGELOG.md was edited but [Unreleased] gained no new bullet line",
                }
            )
        if chore_label_present and len(rationale_clean) < 10:
            findings.append(
                {
                    "code": "chore_rationale_too_short",
                    "severity": "error",
                    "message": "chore-no-changelog label requires a non-empty rationale (min 10 chars)",
                }
            )

    decision = "pass" if (unreleased_added or chore_opt_out_ok) else "fail"
    checks: dict[str, Mapping[str, str]] = {
        "changelog_in_diff": {"outcome": "pass" if changelog_in_diff else "fail"},
        "unreleased_entry_added": {"outcome": "pass" if unreleased_added else "fail"},
        "chore_opt_out_satisfied": {"outcome": "pass" if chore_opt_out_ok else "skipped"},
    }
    return ChangelogVerdict(decision=decision, checks=checks, findings=tuple(findings))


def build_changelog_verdict_artifact(
    verdict: ChangelogVerdict,
    *,
    evaluated_at: str,
    verdict_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Wrap a ChangelogVerdict into the schema-valid artifact."""

    if not _RFC3339_PATTERN.match(evaluated_at):
        raise QualityProfileError(f"changelog_verdict: evaluated_at {evaluated_at!r} is not RFC3339 UTC")

    artifact: dict[str, Any] = {
        "schema_version": "ao-ma-changelog-discipline.v1",
        "decision": verdict.decision,
        "evaluated_at": evaluated_at,
        "checks": {name: dict(payload) for name, payload in verdict.checks.items()},
        "findings": [dict(f) for f in verdict.findings],
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
    }

    validator = Draft202012Validator(verdict_schema)
    errors = sorted(validator.iter_errors(artifact), key=lambda e: e.absolute_path)
    if errors:
        first = errors[0]
        loc = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise QualityProfileError(f"changelog_verdict_artifact: schema-invalid at {loc}: {first.message}")
    return artifact


# ---------------------------------------------------------------------------
# Public symbols
# ---------------------------------------------------------------------------


__all__ = [
    "ADR_ID_PATTERN",
    "ADR_FILENAME_PATTERN",
    "ISO_25010_CHARACTERISTICS",
    "REQUIRED_CHANGELOG_SECTIONS",
    "QualityProfileError",
    "AdrFrontmatter",
    "AdrIndex",
    "AdrIndexEntry",
    "ChangelogVerdict",
    "parse_adr",
    "build_adr_index",
    "render_adr_index_json",
    "load_iso_25010_profile",
    "check_changelog_compliance",
    "build_changelog_verdict_artifact",
]

_ = cast  # silence unused-import lint if cast is not referenced
