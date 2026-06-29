"""GPP-2B-2 drift guard for the ao-release-gate / local gate evidence mapping.

The §3.1 check-correspondence table in
``.claude/plans/GPP-2B-AO-RELEASE-GATE-REQUIRED-CHECK-MAPPING.md`` maps the
local AI review gate's checks onto the ao-release-gate's checks. These tests
pin that table to both gates' *actual* check sets so the mapping cannot
silently drift:

- the 8 local-gate checks declared in ``local-gpp-gate-evidence.schema.v1.json``
- the 34 ao-release-gate checks produced by ``build_ao_release_gate_decision``
  (GPP-2D-2b added ``review_evidence`` and ``review_evidence_context_bound``;
  AO-MA-10b added six ``ao_ma10_*`` checks; the PR metadata productization
  slice added ``pr_delivery_metadata_diagnostic``)

If either gate gains, loses, or renames a check without the table being
updated, these tests fail. This is a documentation-integrity test only: it
reads no runtime state, posts no check-run, and changes no branch protection.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from ao_kernel.ao_release_gate import build_ao_release_gate_decision

_MAPPING_DOC = ".claude/plans/GPP-2B-AO-RELEASE-GATE-REQUIRED-CHECK-MAPPING.md"
_SECTION_HEADING = "### 3.1 Check correspondence"
_NONE_MARKER = "*(none)*"
_BACKTICK = re.compile(r"`([^`]+)`")
_COUNT = re.compile(r"\((\d+)\)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _schema_local_check_names() -> list[str]:
    """The canonical local-gate check set: the artifact contract itself."""
    schema_path = _repo_root() / "ao_kernel" / "defaults" / "schemas" / "local-gpp-gate-evidence.schema.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return list(schema["properties"]["checks"]["required"])


def _runtime_ao_release_gate_check_names() -> list[str]:
    """The ao-release-gate check set, enumerated from the decision core.

    Any payload yields the full check list; an empty dict is enough and
    keeps the call side-effect-free (no check-run is posted).
    """
    decision = build_ao_release_gate_decision({}, {})
    return [check["name"] for check in decision["checks"]]


class MappingRow(NamedTuple):
    """One parsed data row of the §3.1 check-correspondence table."""

    local_tokens: list[str]
    ao_tokens: list[str]
    category: str
    local_is_none: bool
    ao_is_none: bool


class ParsedTable(NamedTuple):
    """The parsed §3.1 table plus enough structure to anchor-check it."""

    section_found: bool
    header_found: bool
    rows: list[MappingRow]
    local_header_count: int | None
    ao_header_count: int | None


def _split_row(line: str) -> list[str]:
    """Split a Markdown table row on pipes, dropping the outer empties."""
    return [cell.strip() for cell in line.split("|")[1:-1]]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(bool(cell) and set(cell) <= {"-", ":"} for cell in cells)


def _extract_count(cell: str) -> int | None:
    match = _COUNT.search(cell)
    return int(match.group(1)) if match else None


def _parse_section_3_1() -> ParsedTable:
    """Parse the §3.1 check-correspondence table.

    Backtick tokens are read only from column 1 (local-gate check) and
    column 2 (ao-release-gate check); column 3 carries category prose that
    itself contains backticked words and must never feed the token sets.
    """
    lines = (_repo_root() / _MAPPING_DOC).read_text(encoding="utf-8").splitlines()

    section_idx = next(
        (i for i, line in enumerate(lines) if line.strip() == _SECTION_HEADING),
        None,
    )
    if section_idx is None:
        return ParsedTable(False, False, [], None, None)

    section_lines: list[str] = []
    for line in lines[section_idx + 1 :]:
        if line.startswith(("### ", "## ")):
            break
        section_lines.append(line)

    header_idx = next(
        (i for i, line in enumerate(section_lines) if line.lstrip().startswith("|") and "Local gate check" in line),
        None,
    )
    if header_idx is None:
        return ParsedTable(True, False, [], None, None)

    header_cells = _split_row(section_lines[header_idx])
    local_count = _extract_count(header_cells[0]) if len(header_cells) > 0 else None
    ao_count = _extract_count(header_cells[1]) if len(header_cells) > 1 else None

    rows: list[MappingRow] = []
    for line in section_lines[header_idx + 1 :]:
        if not line.lstrip().startswith("|"):
            break
        cells = _split_row(line)
        if _is_separator(cells) or len(cells) < 3:
            continue
        col1, col2, col3 = cells[0], cells[1], cells[2]
        local_tokens = _BACKTICK.findall(col1)
        ao_tokens = _BACKTICK.findall(col2)
        rows.append(
            MappingRow(
                local_tokens=local_tokens,
                ao_tokens=ao_tokens,
                category=col3,
                local_is_none=not local_tokens and _NONE_MARKER in col1,
                ao_is_none=not ao_tokens and _NONE_MARKER in col2,
            )
        )
    return ParsedTable(True, True, rows, local_count, ao_count)


def test_section_3_1_table_anchor() -> None:
    """The §3.1 check-correspondence table is present and parses to rows."""
    table = _parse_section_3_1()
    assert table.section_found, f"'{_SECTION_HEADING}' heading missing from {_MAPPING_DOC}"
    assert table.header_found, "§3.1 check-correspondence table header not found"
    # 8 local-gate checks may share rows (GPP-2D-2b merged reviewer_agree +
    # cross_provider_verified into one ao-counterpart row), but the table
    # always carries every local-gate check plus the single ao-only row.
    assert len(table.rows) >= 8, (
        f"§3.1 table parsed to {len(table.rows)} data rows; "
        "expected >= 8 (every local-gate check is represented, plus 1 ao-release-gate-only row)"
    )


def test_section_3_1_header_counts_match_actual_check_sets() -> None:
    """The table header counts match the live gates."""
    table = _parse_section_3_1()
    local_total = len(_schema_local_check_names())
    ao_total = len(_runtime_ao_release_gate_check_names())
    assert table.local_header_count == local_total, (
        f"§3.1 header claims ({table.local_header_count}) local-gate checks; the schema declares {local_total}"
    )
    assert table.ao_header_count == ao_total, (
        f"§3.1 header claims ({table.ao_header_count}) ao-release-gate checks; "
        f"build_ao_release_gate_decision produces {ao_total}"
    )


def test_local_gate_check_names_match_schema() -> None:
    """Every schema local-gate check is in the table, and vice versa."""
    table = _parse_section_3_1()
    table_local = {token for row in table.rows for token in row.local_tokens}
    schema_local = set(_schema_local_check_names())
    assert table_local == schema_local, (
        "§3.1 local-gate column drifted from local-gpp-gate-evidence.schema.v1.json — "
        f"missing from table: {sorted(schema_local - table_local)}; "
        f"stale in table: {sorted(table_local - schema_local)}"
    )


def test_mapping_table_covers_current_ao_release_gate_checks() -> None:
    """Every ao-release-gate check is in the table, and vice versa."""
    table = _parse_section_3_1()
    table_ao = {token for row in table.rows for token in row.ao_tokens}
    runtime_ao = set(_runtime_ao_release_gate_check_names())
    assert table_ao == runtime_ao, (
        "§3.1 ao-release-gate column drifted from build_ao_release_gate_decision — "
        f"missing from table: {sorted(runtime_ao - table_ao)}; "
        f"stale in table: {sorted(table_ao - runtime_ao)}"
    )


def test_each_local_check_row_has_counterpart_or_local_only_marker() -> None:
    """A local-gate check row is either Category A with an ao-release-gate
    counterpart, or Category C with an explicit 'local-only' marker."""
    table = _parse_section_3_1()
    local_rows = [row for row in table.rows if row.local_tokens]
    assert local_rows, "§3.1 table has no rows carrying a local-gate check"
    for row in local_rows:
        label = ", ".join(row.local_tokens)
        if row.ao_tokens:
            assert row.category.startswith("A"), (
                f"row '{label}' documents an ao-release-gate counterpart but "
                f"its category is '{row.category}' (expected Category A)"
            )
        elif row.ao_is_none:
            assert row.category.startswith("C") and "local-only" in row.category, (
                f"row '{label}' has no counterpart; category '{row.category}' "
                "must be Category C and carry an explicit 'local-only' marker"
            )
        else:
            raise AssertionError(
                f"row '{label}' has neither an ao-release-gate counterpart "
                f"nor an explicit '{_NONE_MARKER}' local-only marker"
            )


def test_category_b_row_is_ao_release_gate_only() -> None:
    """Exactly one row carries no local-gate check: the ao-release-gate-only
    row (Category B)."""
    table = _parse_section_3_1()
    b_rows = [row for row in table.rows if row.local_is_none]
    assert len(b_rows) == 1, (
        f"expected exactly 1 ao-release-gate-only row (local column '{_NONE_MARKER}'), found {len(b_rows)}"
    )
    row = b_rows[0]
    assert row.ao_tokens, "the ao-release-gate-only row lists no ao-release-gate checks"
    assert row.category.startswith("B"), (
        f"the ao-release-gate-only row has category '{row.category}' (expected Category B)"
    )


def test_no_duplicate_tokens_in_mapping_table() -> None:
    """No check name appears twice in either column — a duplicate would make
    the mapping ambiguous."""
    table = _parse_section_3_1()
    ao_flat = [token for row in table.rows for token in row.ao_tokens]
    local_flat = [token for row in table.rows for token in row.local_tokens]
    ao_dupes = sorted({token for token in ao_flat if ao_flat.count(token) > 1})
    local_dupes = sorted({token for token in local_flat if local_flat.count(token) > 1})
    assert not ao_dupes, f"ao-release-gate checks listed more than once in §3.1: {ao_dupes}"
    assert not local_dupes, f"local-gate checks listed more than once in §3.1: {local_dupes}"
