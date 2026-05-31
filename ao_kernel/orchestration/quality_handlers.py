"""AO-MA-11G-1 ``quality`` CLI handlers (thin wrappers).

Top-level ``ao-kernel quality`` parser per Codex thread 019e8050
iter-2 daraltma (NOT under ``orchestration``). The actual logic lives
in :mod:`ao_kernel.orchestration.quality_profile` (pure module); the
handlers in this file own only argparse + disk reads + file writes +
exit codes.

Forbidden flag pin (RI-7.8c uyumu): the parser does NOT define
``--adapter`` / ``--prompt`` / ``--model`` / ``--api-key`` / ``--url`` /
``--pr-write``; argparse rejects unknown flags with ``SystemExit``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from ao_kernel.orchestration.quality_profile import (
    QualityProfileError,
    build_adr_index,
    build_changelog_verdict_artifact,
    check_changelog_compliance,
    load_iso_25010_profile,
    parse_adr,
    render_adr_index_json,
)


_ADR_SCHEMA_NAME = "ao-ma-adr.schema.v1.json"
_ISO_PROFILE_SCHEMA_NAME = "ao-ma-iso-25010-profile.schema.v1.json"
_CHANGELOG_VERDICT_SCHEMA_NAME = "ao-ma-changelog-discipline.schema.v1.json"


def _load_schema(name: str) -> dict[str, Any]:
    path = resources.files("ao_kernel.defaults.schemas").joinpath(name)
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def add_quality_subparser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the top-level ``quality`` subparser."""

    quality_p = sub.add_parser(
        "quality",
        help=(
            "AO-MA-11G SPM Quality Profile Hardening: validate ADRs, build "
            "the ADR index, validate the ISO/IEC 25010 quality profile, and "
            "check the CHANGELOG discipline. The profile is a reference; "
            "no certification claim, no support widening, no live adapter "
            "execution."
        ),
    )
    quality_sub = quality_p.add_subparsers(dest="quality_command")

    validate_adr_p = quality_sub.add_parser(
        "validate-adr",
        help="Parse + schema-validate a single ADR Markdown file.",
    )
    validate_adr_p.add_argument(
        "--file",
        required=True,
        help="Path to the ADR-NNNN-<slug>.md file",
    )

    build_index_p = quality_sub.add_parser(
        "build-index",
        help=("Parse every ADR-NNNN-*.md file in a directory and emit a deterministic id-ascending index JSON."),
    )
    build_index_p.add_argument(
        "--dir",
        required=True,
        help="Directory containing ADR-NNNN-*.md files (template.md is excluded)",
    )
    build_index_p.add_argument(
        "--out",
        required=True,
        help="Path to write the index JSON",
    )

    validate_iso_p = quality_sub.add_parser(
        "validate-iso-profile",
        help="Schema-validate + canonical-set-validate an ISO 25010 profile JSON.",
    )
    validate_iso_p.add_argument(
        "--file",
        required=True,
        help="Path to the iso-25010-profile JSON file",
    )

    check_changelog_p = quality_sub.add_parser(
        "check-changelog",
        help=(
            "Diff-aware Keep-a-Changelog discipline check. Pass when the "
            "[Unreleased] section gained a new bullet line in the PR diff, "
            "OR a non-empty chore-no-changelog rationale is supplied."
        ),
    )
    check_changelog_p.add_argument(
        "--base-changelog",
        required=True,
        help="Path to CHANGELOG.md at the PR base ref",
    )
    check_changelog_p.add_argument(
        "--head-changelog",
        required=True,
        help="Path to CHANGELOG.md at the PR head ref",
    )
    check_changelog_p.add_argument(
        "--diff-path",
        action="append",
        default=[],
        help="A path that the PR changed; repeat for each path (CHANGELOG.md must appear when not using --chore-no-changelog)",
    )
    check_changelog_p.add_argument(
        "--chore-no-changelog",
        action="store_true",
        help="Operator opt-out: declare this PR is a chore that needs no CHANGELOG entry",
    )
    check_changelog_p.add_argument(
        "--chore-rationale",
        default=None,
        help="Non-empty rationale (min 10 chars) when --chore-no-changelog is set",
    )
    check_changelog_p.add_argument(
        "--out",
        required=True,
        help="Path to write the changelog discipline verdict artifact",
    )
    check_changelog_p.add_argument(
        "--evaluated-at",
        default=None,
        help=(
            "RFC3339 UTC timestamp; default uses the current UTC clock at "
            "CLI invocation time (the pure module never reads the clock)."
        ),
    )


def cmd_quality_validate_adr(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel quality validate-adr``."""

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"error: adr file not found: {file_path!s}", file=sys.stderr)
        return 1
    schema = _load_schema(_ADR_SCHEMA_NAME)
    try:
        record = parse_adr(file_path.read_text(encoding="utf-8"), file_path.name, adr_schema=schema)
    except QualityProfileError as exc:
        print(f"quality validate-adr failed: {exc}", file=sys.stderr)
        return 1
    print(f"ok: {record.id} status={record.status} retrospective={record.retrospective}")
    return 0


def cmd_quality_build_index(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel quality build-index``."""

    dir_path = Path(args.dir).resolve()
    if not dir_path.is_dir():
        print(f"error: adr dir not found: {dir_path!s}", file=sys.stderr)
        return 1
    out_path = Path(args.out).resolve()
    schema = _load_schema(_ADR_SCHEMA_NAME)
    records = []
    for entry in sorted(dir_path.iterdir()):
        if not entry.is_file():
            continue
        if entry.name == "template.md":
            continue
        if not entry.name.startswith("ADR-") or not entry.name.endswith(".md"):
            continue
        try:
            record = parse_adr(entry.read_text(encoding="utf-8"), entry.name, adr_schema=schema)
        except QualityProfileError as exc:
            print(f"quality build-index failed at {entry.name}: {exc}", file=sys.stderr)
            return 1
        records.append(record)
    try:
        index = build_adr_index(records)
    except QualityProfileError as exc:
        print(f"quality build-index failed: {exc}", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_adr_index_json(index), encoding="utf-8")
    print(f"ok: wrote {len(records)} ADR entries to {out_path!s}")
    return 0


def cmd_quality_validate_iso_profile(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel quality validate-iso-profile``."""

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(f"error: iso profile not found: {file_path!s}", file=sys.stderr)
        return 1
    schema = _load_schema(_ISO_PROFILE_SCHEMA_NAME)
    try:
        profile = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"quality validate-iso-profile failed: JSON parse error: {exc}", file=sys.stderr)
        return 1
    try:
        load_iso_25010_profile(profile, profile_schema=schema)
    except QualityProfileError as exc:
        print(f"quality validate-iso-profile failed: {exc}", file=sys.stderr)
        return 1
    print(f"ok: iso 25010 profile {profile.get('profile_id')} v{profile.get('profile_version')} valid")
    return 0


def cmd_quality_check_changelog(args: argparse.Namespace) -> int:
    """Handle ``ao-kernel quality check-changelog``."""

    base_path = Path(args.base_changelog).resolve()
    head_path = Path(args.head_changelog).resolve()
    if not base_path.exists():
        print(f"error: base changelog not found: {base_path!s}", file=sys.stderr)
        return 1
    if not head_path.exists():
        print(f"error: head changelog not found: {head_path!s}", file=sys.stderr)
        return 1

    if args.evaluated_at:
        evaluated_at = args.evaluated_at
    else:
        evaluated_at = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        verdict = check_changelog_compliance(
            base_changelog_text=base_path.read_text(encoding="utf-8"),
            head_changelog_text=head_path.read_text(encoding="utf-8"),
            pr_diff_paths=args.diff_path,
            chore_label_present=bool(args.chore_no_changelog),
            chore_rationale=args.chore_rationale,
        )
        verdict_schema = _load_schema(_CHANGELOG_VERDICT_SCHEMA_NAME)
        artifact = build_changelog_verdict_artifact(
            verdict,
            evaluated_at=evaluated_at,
            verdict_schema=verdict_schema,
        )
    except QualityProfileError as exc:
        print(f"quality check-changelog failed: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"changelog discipline: decision={verdict.decision}; artifact -> {out_path!s}", file=sys.stderr)
    return 0 if verdict.decision == "pass" else 1
