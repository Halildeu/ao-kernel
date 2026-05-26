"""Doc invariant test for RI-7.2 guardrail hardening matrix.

This test pins the canonical RI-7.2 matrix document so the hardening
inventory cannot silently drift. It is a docs invariant only; it does not
execute repo-intelligence code paths.
"""

from __future__ import annotations

from pathlib import Path


_MATRIX_PATH = (
    Path(__file__).resolve().parents[1] / ".claude" / "plans" / "RI-7.2-REPO-INTELLIGENCE-GUARDRAIL-HARDENING-MATRIX.md"
)


def _matrix_text() -> str:
    assert _MATRIX_PATH.exists(), f"matrix doc missing: {_MATRIX_PATH}"
    return _MATRIX_PATH.read_text(encoding="utf-8")


def test_ri72_matrix_doc_exists_and_records_six_guardrail_rows() -> None:
    text = _matrix_text()
    assert "# RI-7.2 — Repo-Intelligence Guardrail Hardening Matrix" in text
    # The six guardrail headings the readiness gate requires.
    assert "### 3.1 AST / chunk edge cases" in text
    assert "### 3.2 Namespace isolation" in text
    assert "### 3.3 Stale vector cleanup" in text
    assert "### 3.4 No implicit / unconfirmed root authority write" in text
    assert "### 3.5 No auto-feed (no hidden context compiler injection)" in text
    assert "### 3.6 No MCP exposure" in text


def test_ri72_matrix_doc_records_exit_decision_and_no_promotion_dilution() -> None:
    text = _matrix_text()
    # Whitespace-collapsed view tolerates Markdown line wraps in the doc.
    flat = " ".join(text.split())
    # Exit decision string for this slice.
    assert "ri7_guardrail_hardening_matrix_ready" in flat
    # Promotion-bound guard flags must remain stated as closed in this slice.
    assert "Support widening: false" in flat or "support_widening=false" in flat
    assert "Production platform claim: false" in flat or "production_platform_claim=false" in flat
    assert "Live adapter execution: false" in flat or "live_adapter_execution=false" in flat
    # The slice must not be presented as a production claim or tier promotion.
    assert "No production platform claim" in flat
    assert "No live adapter execution" in flat


def test_ri72_matrix_doc_records_forbidden_change_audit() -> None:
    text = _matrix_text()
    # The forbidden-change audit must be present so future drift is auditable.
    assert "Forbidden-Change Audit" in text
    # Key untouched surfaces must be named explicitly.
    assert "gpp_status.v1.json" in text
    assert "scripts/gp5_platform_claim_decision.py" in text
    assert ".github/workflows/" in text
    assert "mcp_server" in text or "MCP" in text


def test_ri72_matrix_doc_pins_regression_test_references() -> None:
    text = _matrix_text()
    # The two RI-7.2 regression tests added in this slice must be cited
    # in the matrix so the doc-to-test binding is enforceable.
    assert "test_build_python_ast_indexes_skips_repo_map_path_escape_without_reading_outside_root" in text
    assert "test_write_repo_vectors_rejects_delete_key_outside_namespace_without_mutation" in text
    # No-MCP regression refs must name tests that actually exist; this guards
    # against stale or invented function names slipping into the matrix doc.
    assert "test_repo_intelligence_is_not_exposed_as_mcp_tool" in text
    assert "test_repo_intelligence_is_not_registered_in_mcp_tool_gateway" in text


def test_ri72_matrix_no_mcp_regression_refs_match_real_test_functions() -> None:
    """The matrix's no-MCP regression refs must correspond to defined test
    functions in the no-MCP guard file. This catches doc drift where a
    matrix cites a function name that does not exist.
    """
    matrix_text = _matrix_text()
    guard_path = Path(__file__).resolve().parent / "test_repo_intelligence_no_mcp_root_export_guard.py"
    assert guard_path.exists(), f"no-MCP guard test file missing: {guard_path}"
    guard_text = guard_path.read_text(encoding="utf-8")

    cited_no_mcp_names = (
        "test_repo_intelligence_is_not_exposed_as_mcp_tool",
        "test_repo_intelligence_is_not_registered_in_mcp_tool_gateway",
        "test_repo_cli_has_no_root_export_or_mcp_subcommand",
        "test_repo_cli_help_does_not_advertise_root_export_or_mcp_flags",
    )
    for name in cited_no_mcp_names:
        # Matrix cites this name as no-MCP regression evidence.
        assert name in matrix_text, f"matrix doc must cite {name}"
        # The actual test function must exist in the guard file.
        assert f"def {name}(" in guard_text, f"no-MCP guard file must define {name}"
