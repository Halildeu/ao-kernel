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


def test_body_drift_same_heading_excluded(repo: Path) -> None:
    # Codex post-impl #1: heading (value_hash) stable but body changed ->
    # doc_hash differs -> item must be excluded by the file-integrity guard.
    ingest_docs(repo)
    _write(repo / "AGENTS.md", "# AGENTS - testrepo\n\nCOMPLETELY DIFFERENT BODY TEXT.\n")
    packet = render_context_packet(repo)
    assert "AGENTS - testrepo" not in packet


def test_source_replaced_by_symlink_excluded(repo: Path) -> None:
    # Codex post-impl #2: a source that becomes a symlink after ingest is
    # rejected at render under the same confinement as ingest.
    ingest_docs(repo)
    target = repo.parent / "evil_agents.md"
    target.write_text("# AGENTS - testrepo\n", encoding="utf-8")
    (repo / "AGENTS.md").unlink()
    (repo / "AGENTS.md").symlink_to(target)
    packet = render_context_packet(repo)
    assert "AGENTS - testrepo" not in packet


def _run_cli(argv: list[str]) -> int:
    from ao_kernel.cli import main

    return main(argv)


def test_cli_ingest_then_packet(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_cli(["context", "ingest", "--root", str(repo)]) == 0
    assert "ingested=" in capsys.readouterr().out
    assert _run_cli(["context", "packet", "--root", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "Context Packet" in out
    assert "AUTHORITY" in out


def test_cli_ingest_json_output(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_cli(["context", "ingest", "--root", str(repo), "--output", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ingested"] == 6
    assert data["by_type"] == {"rule": 2, "decision": 2, "fact": 2}


def test_cli_ingest_bad_root_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_cli(["context", "ingest", "--root", str(tmp_path / "missing")]) == 1
    assert "not found" in capsys.readouterr().err


def test_cli_context_no_subcommand_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run_cli(["context"]) == 1
    assert "Usage" in capsys.readouterr().err


def test_cli_packet_include_doc_claims(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _run_cli(["context", "ingest", "--root", str(repo)])
    capsys.readouterr()
    rc = _run_cli(["context", "packet", "--root", str(repo), "--include-doc-claims", "--min-conf", "0.5"])
    assert rc == 0
    assert "UNVERIFIED" in capsys.readouterr().out


def test_cli_ingest_reports_collisions_and_secrets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".ao").mkdir()
    _write(tmp_path / "a/one.md", "# One\n")
    _write(tmp_path / "b/two.md", "# Two\n")
    _write(tmp_path / "AGENTS.md", f"# token {_FAKE_SK}\n")
    mp = tmp_path / "m.json"
    mp.write_text(
        json.dumps(
            {
                "schema_version": "context-doc-bridge-mapping.v1",
                "rules": [
                    {
                        "mapping_id": "agents",
                        "glob": "AGENTS.md",
                        "type": "rule",
                        "tier": "repo_canonical",
                        "key_template": "rule.agents-md",
                        "value_strategy": "first_heading",
                        "confidence": 0.95,
                    },
                    {
                        "mapping_id": "fixed",
                        "glob": "*/*.md",
                        "type": "rule",
                        "tier": "repo_canonical",
                        "key_template": "rule.fixed",
                        "value_strategy": "first_heading",
                        "confidence": 0.9,
                        "collision_policy": "strict",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    rc = _run_cli(["context", "ingest", "--root", str(tmp_path), "--mapping", str(mp)])
    assert rc == 0
    err = capsys.readouterr().err
    assert "collision" in err
    assert "secret-like" in err


def test_cli_packet_failure_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    rc = _run_cli(["context", "packet", "--root", str(tmp_path), "--mapping", str(bad)])
    assert rc == 1
    assert "failed" in capsys.readouterr().err


def test_supersede_policy_overrides(tmp_path: Path) -> None:
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
                        "collision_policy": "supersede",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = ingest_docs(tmp_path, mapping_path=str(mp))
    # supersede: both sources are accepted (no collision skip); the later source
    # (b/two.md) wins the shared key and records supersedes.
    assert report.ingested == 2
    assert report.collisions == []
    stored = {i["key"]: i for i in cs.query(tmp_path, include_expired=True)}
    assert stored["rule.fixed"]["value"] == "Two"
    assert stored["rule.fixed"]["supersedes"] == "rule.fixed"


def test_ingest_no_matching_sources(tmp_path: Path) -> None:
    (tmp_path / ".ao").mkdir()
    report = ingest_docs(tmp_path)
    assert report.ingested == 0
    assert report.by_type == {}


def test_keygen_rejects_unknown_placeholder() -> None:
    from ao_kernel._internal.context_doc_bridge import keygen

    with pytest.raises(ValueError, match="unknown placeholder"):
        keygen.render_key("rule.{bogus}", stem="x")


def test_render_excludes_when_mapping_rule_removed(repo: Path, tmp_path: Path) -> None:
    # ingest with the default mapping, then render with a mapping that no longer
    # defines those mapping_ids -> every item's rule is gone -> all excluded.
    ingest_docs(repo)
    empty_map = tmp_path / "empty.json"
    empty_map.write_text(
        json.dumps(
            {
                "schema_version": "context-doc-bridge-mapping.v1",
                "rules": [
                    {
                        "mapping_id": "unrelated",
                        "glob": "NOPE.md",
                        "type": "rule",
                        "tier": "repo_canonical",
                        "key_template": "rule.nope",
                        "value_strategy": "first_heading",
                        "confidence": 0.9,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    packet = render_context_packet(repo, mapping_path=str(empty_map))
    assert "AGENTS - testrepo" not in packet
    assert "Use Postgres" not in packet


def test_cross_ingest_collision_does_not_overwrite(tmp_path: Path) -> None:
    # Codex post-impl #3: a different source claiming an existing key (strict)
    # is a collision against the live store, not a silent overwrite.
    (tmp_path / ".ao").mkdir()
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
    _write(tmp_path / "a/one.md", "# One\n")
    first = ingest_docs(tmp_path, mapping_path=str(mp))
    assert first.ingested == 1

    (tmp_path / "a/one.md").unlink()
    _write(tmp_path / "b/two.md", "# Two\n")
    second = ingest_docs(tmp_path, mapping_path=str(mp))
    assert second.ingested == 0
    assert len(second.collisions) == 1

    stored = {i["key"]: i for i in cs.query(tmp_path, include_expired=True)}
    assert stored["rule.fixed"]["value"] == "One"


def test_resolve_within_repo_rejections(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("# ok\n", encoding="utf-8")
    assert _mapping.resolve_within_repo(tmp_path, "") is None
    assert _mapping.resolve_within_repo(tmp_path, "../x.md") is None
    assert _mapping.resolve_within_repo(tmp_path, "/etc/hosts") is None
    assert _mapping.resolve_within_repo(tmp_path, "~/x.md") is None
    assert _mapping.resolve_within_repo(tmp_path, "missing.md") is None
    resolved = _mapping.resolve_within_repo(tmp_path, "ok.md")
    assert resolved is not None
    assert resolved.name == "ok.md"


def test_resolve_within_repo_oversize(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("# " + ("x" * 100), encoding="utf-8")
    assert _mapping.resolve_within_repo(tmp_path, "big.md", max_bytes=10) is None


def test_resolve_sources_max_files_cap(tmp_path: Path) -> None:
    for i in range(3):
        (tmp_path / f"d{i}.md").write_text(f"# {i}\n", encoding="utf-8")
    assert len(_mapping.resolve_sources(tmp_path, "*.md", max_files=1)) == 1


def test_parser_section_headings_limit() -> None:
    text = "# title\n\n## A\n\n## B\n\n## C\n"
    assert _parser.section_headings(text, 2) == ["A", "B"]


def test_parser_status_durum_and_inline_date() -> None:
    assert _parser.status_and_date("## Durum\n\n**Kabul** (2026-02-01)")[0] == "Kabul"
    status, date = _parser.status_and_date("# x\n\nSuperseded by ADR-9 on 2026-02-03\n")
    assert status == "Superseded"
    assert date == "2026-02-03"


def test_renderer_skips_non_bridge_decisions(tmp_path: Path) -> None:
    (tmp_path / ".ao").mkdir()
    cs.promote_decision(tmp_path, key="manual.x", value="hand-recorded value", confidence=0.95)
    packet = render_context_packet(tmp_path)
    assert "hand-recorded value" not in packet


def test_cli_ingest_failure_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".ao").mkdir()
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    rc = _run_cli(["context", "ingest", "--root", str(tmp_path), "--mapping", str(bad)])
    assert rc == 1
    assert "failed" in capsys.readouterr().err


def test_parser_first_heading_fallback() -> None:
    assert _parser.first_heading("no heading line here", "fallback-stem") == "fallback-stem"


def test_packet_per_section_cap(repo: Path) -> None:
    ingest_docs(repo)
    packet = render_context_packet(repo, max_items=1)
    # 2 rules + 2 decisions exist but each section is capped at 1
    assert packet.count("- AGENTS - testrepo") + packet.count("- Context Priority") == 1
    assert "over per-section cap" in packet


def test_packet_min_conf_excludes_everything(repo: Path) -> None:
    ingest_docs(repo)
    packet = render_context_packet(repo, min_conf=0.99)
    assert "0 item shown" in packet
    assert "## Rules" not in packet


def test_packet_low_threshold_shows_status_but_still_drops_doc_claims(repo: Path) -> None:
    # A Proposed ADR (conf 0.6) clears a low min_conf and renders WITH its status
    # tag; doc_claim facts (conf 0.55) clear the conf bar too but are still
    # dropped because doc-claims are opt-in.
    _write(repo / "docs/adr/0003-proposed.md", "# 0003 - Proposed Thing\n\n## Status\n\n**Proposed**\n")
    ingest_docs(repo)
    packet = render_context_packet(repo, min_conf=0.5)
    assert "Proposed Thing" in packet
    assert "Proposed]" in packet or "| Proposed>" in packet
    assert "Live Delta" not in packet


def test_render_value_strategy_change_excludes(repo: Path, tmp_path: Path) -> None:
    # Same file + same doc_hash, but render uses a mapping whose rule (same
    # mapping_id) extracts a DIFFERENT value -> value_hash no longer reproduces
    # -> excluded even though the bytes are unchanged.
    ingest_map = tmp_path / "ingest.json"
    base_rule = {
        "mapping_id": "agents",
        "glob": "AGENTS.md",
        "type": "rule",
        "tier": "repo_canonical",
        "key_template": "rule.agents-md",
        "value_strategy": "first_heading",
        "confidence": 0.95,
    }
    ingest_map.write_text(
        json.dumps({"schema_version": "context-doc-bridge-mapping.v1", "rules": [base_rule]}),
        encoding="utf-8",
    )
    ingest_docs(repo, mapping_path=str(ingest_map))
    assert "AGENTS - testrepo" in render_context_packet(repo, mapping_path=str(ingest_map))

    drift_rule = dict(base_rule, value_strategy="section_headings")
    drift_map = tmp_path / "drift.json"
    drift_map.write_text(
        json.dumps({"schema_version": "context-doc-bridge-mapping.v1", "rules": [drift_rule]}),
        encoding="utf-8",
    )
    assert "AGENTS - testrepo" not in render_context_packet(repo, mapping_path=str(drift_map))
