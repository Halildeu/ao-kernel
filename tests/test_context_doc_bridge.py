"""Tests for the context doc-bridge (ingest + render + provenance + guards).

Covers the Codex plan-time acceptance criteria: provenance in canonical items,
single-revision CAS batch, fail-closed stale/drift/deleted source exclusion,
doc_claim opt-in, secret skip-not-redact, mapping bounds (traversal/symlink/
malformed), key collision, idempotency, and the no-touch guards on
``compile_context`` / MCP surface / guard flags.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from ao_kernel._internal.context_doc_bridge import mapping as _mapping
from ao_kernel._internal.context_doc_bridge import parser as _parser
from ao_kernel.context import canonical_store as cs
from ao_kernel.context.doc_bridge import ingest_docs, render_context_packet

_GUARD_FLAGS = ("live_adapter_execution", "support_widening", "production_platform_claim")

# Synthetic secret-like tokens assembled at runtime so the literal never appears
# contiguously in source (repo .githooks/pre-commit secret scanner) while still
# triggering looks_like_secret() at runtime. NOT real credentials.
_FAKE_SK = "sk-" + "abcdefghijklmnop12345"
_FAKE_GHP = "ghp_" + "0123456789abcdefghij0123456789"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".ao").mkdir()
    _write(tmp_path / "AGENTS.md", "# AGENTS - testrepo\n\nentry surface.\n")
    _write(tmp_path / "docs/context-priority-rules.md", "# Context Priority Rules\n\nrules.\n")
    _write(
        tmp_path / "docs/adr/0001-use-pg.md",
        "# 0001 - Use Postgres\n\n## Status\n\n**Accepted** (2026-01-02)\n\nctx.\n",
    )
    _write(
        tmp_path / "docs/adr/0002-no-mesh.md",
        "# 0002 - No Mesh\n\n## Status\n\n**Rejected** (2026-01-03)\n\nctx.\n",
    )
    _write(tmp_path / "docs/adr/README.md", "# ADR index\n")  # excluded by [0-9]* glob
    _write(tmp_path / "docs/state/current-state.md", "# Current State\n\n## Live Delta A\n\n## Live Delta B\n")
    return tmp_path


def test_ingest_happy_path_writes_items_with_provenance(repo: Path) -> None:
    report = ingest_docs(repo)
    assert report.ingested == 6
    assert report.by_type == {"rule": 2, "decision": 2, "fact": 2}
    items = {i["key"]: i for i in cs.query(repo)}
    prov = items["rule.agents-md"]["provenance"]["doc_bridge"]
    assert prov["src"] == "AGENTS.md"
    assert prov["type"] == "rule"
    assert prov["doc_hash"].startswith("sha256:")
    assert prov["value_hash"].startswith("sha256:")
    assert prov["schema_version"] == "doc-bridge-provenance.v1"


def test_adr_status_drives_confidence(repo: Path) -> None:
    ingest_docs(repo)
    items = {i["key"]: i for i in cs.query(repo, include_expired=True)}
    assert items["decision.adr.0001-use-pg"]["confidence"] == 0.9
    assert items["decision.adr.0002-no-mesh"]["confidence"] == 0.45


def test_readme_excluded_by_glob(repo: Path) -> None:
    ingest_docs(repo)
    keys = {i["key"] for i in cs.query(repo, include_expired=True)}
    assert not any("readme" in k.lower() for k in keys)


def test_packet_default_excludes_doc_claims_and_low_conf(repo: Path) -> None:
    ingest_docs(repo)
    packet = render_context_packet(repo)
    assert "AGENTS - testrepo" in packet
    assert "Use Postgres" in packet
    assert "No Mesh" not in packet
    assert "Live Delta A" not in packet
    assert "AUTHORITY" in packet


def test_packet_include_doc_claims_labels_unverified(repo: Path) -> None:
    ingest_docs(repo)
    packet = render_context_packet(repo, include_doc_claims=True, min_conf=0.5)
    assert "Live Delta A" in packet
    assert "UNVERIFIED" in packet


def test_authority_header_names_all_guard_flags(repo: Path) -> None:
    ingest_docs(repo)
    packet = render_context_packet(repo)
    for flag in _GUARD_FLAGS:
        assert flag in packet


def test_stale_source_deleted_excluded(repo: Path) -> None:
    ingest_docs(repo)
    (repo / "AGENTS.md").unlink()
    packet = render_context_packet(repo)
    assert "AGENTS - testrepo" not in packet


def test_source_drift_excluded(repo: Path) -> None:
    ingest_docs(repo)
    _write(repo / "AGENTS.md", "# AGENTS - DRIFTED\n")
    packet = render_context_packet(repo)
    assert "AGENTS - testrepo" not in packet
    assert "DRIFTED" not in packet


def test_idempotent_ingest_no_duplicate_keys(repo: Path) -> None:
    report1 = ingest_docs(repo)
    count1 = len(cs.query(repo, include_expired=True))
    report2 = ingest_docs(repo)
    count2 = len(cs.query(repo, include_expired=True))
    assert count1 == count2
    assert report2.ingested == report1.ingested


def test_cas_single_revision_batch(repo: Path) -> None:
    before = cs.store_revision(cs.load_store(repo))
    report = ingest_docs(repo)
    after = cs.store_revision(cs.load_store(repo))
    assert report.revision == after
    assert after != before


def test_secret_like_value_skipped_not_stored(tmp_path: Path) -> None:
    (tmp_path / ".ao").mkdir()
    _write(tmp_path / "AGENTS.md", f"# token {_FAKE_SK}\n")
    report = ingest_docs(tmp_path)
    assert any("AGENTS.md" in entry for entry in report.secrets_skipped)
    keys = {i["key"] for i in cs.query(tmp_path, include_expired=True)}
    assert "rule.agents-md" not in keys


def test_no_ingested_key_is_a_guard_flag(repo: Path) -> None:
    ingest_docs(repo)
    keys = {i["key"] for i in cs.query(repo, include_expired=True)}
    for flag in _GUARD_FLAGS:
        assert flag not in keys


def test_path_traversal_pattern_rejected(tmp_path: Path) -> None:
    assert _mapping.resolve_sources(tmp_path, "../escape/*.md") == []
    assert _mapping.resolve_sources(tmp_path, "/etc/*.conf") == []
    assert _mapping.resolve_sources(tmp_path, "~/secret.md") == []


def test_symlink_escape_skipped(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_secret.md"
    outside.write_text("# secret outside repo\n", encoding="utf-8")
    link = tmp_path / "AGENTS.md"
    link.symlink_to(outside)
    assert _mapping.resolve_sources(tmp_path, "AGENTS.md") == []


def test_oversize_file_skipped(tmp_path: Path) -> None:
    big = tmp_path / "BIG.md"
    big.write_text("# big\n" + ("x" * 100), encoding="utf-8")
    found = _mapping.resolve_sources(tmp_path, "BIG.md", max_bytes=10)
    assert found == []


def test_malformed_mapping_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": "wrong", "rules": []}), encoding="utf-8")
    with pytest.raises(Exception):  # noqa: B017 — jsonschema ValidationError surface
        _mapping.load_mapping(str(bad))


def test_default_mapping_is_schema_valid() -> None:
    spec = _mapping.load_mapping(None)
    assert spec["schema_version"] == "context-doc-bridge-mapping.v1"
    assert len(spec["rules"]) >= 1


def test_key_collision_strict_reported_and_skipped(tmp_path: Path) -> None:
    (tmp_path / ".ao").mkdir()
    _write(tmp_path / "a/one.md", "# One\n")
    _write(tmp_path / "b/two.md", "# Two\n")
    mp = tmp_path / "m.json"
    mp.write_text(
        json.dumps(
            {
                "schema_version": "context-doc-bridge-mapping.v1",
                "rules": [
                    {
                        "mapping_id": "x",
                        "glob": "*/*.md",
                        "type": "rule",
                        "tier": "repo_canonical",
                        "key_template": "rule.fixed",
                        "value_strategy": "first_heading",
                        "confidence": 0.9,
                        "collision_policy": "strict",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = ingest_docs(tmp_path, mapping_path=str(mp))
    assert report.ingested == 1
    assert len(report.collisions) == 1


def test_compile_context_signature_unchanged() -> None:
    from ao_kernel.context.context_compiler import compile_context

    params = set(inspect.signature(compile_context).parameters)
    assert "doc_bridge" not in params
    assert "context_packet" not in params


def test_mcp_server_does_not_wire_doc_bridge() -> None:
    from ao_kernel import mcp_server

    source = Path(mcp_server.__file__).read_text(encoding="utf-8")
    assert "doc_bridge" not in source
    assert "context_doc_bridge" not in source


def test_parser_status_variants() -> None:
    assert _parser.status_and_date("## Status\n\n**Accepted** (2026-01-02)")[0] == "Accepted"
    assert _parser.status_and_date("Status: Rejected")[0] == "Rejected"
    assert _parser.status_and_date("# no status here")[0] == "Unknown"


def test_parser_secret_detection() -> None:
    assert _parser.looks_like_secret("api_key = abcdef123456")
    assert _parser.looks_like_secret(_FAKE_GHP)
    assert not _parser.looks_like_secret("a normal architecture decision heading")
