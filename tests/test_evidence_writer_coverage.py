"""Coverage tests for _internal/evidence/writer.py.

Targets PR-C3: bring writer.py branch coverage from ~26% toward 85%.
The module is a data-writer: tests build a temporary workspace +
run_dir and assert that every write_* helper produces the expected
file / JSONL line / manifest.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ao_kernel._internal.evidence.writer import (
    EvidenceWriter,
    _git_commit_and_dirty,
    _hash_json_dir,
    _sha256_concat_files,
    _sha256_file,
)


# ── _sha256_file / _sha256_concat_files ────────────────────────────


class TestShaHelpers:
    def test_sha256_file_roundtrip(self, tmp_path: Path):
        p = tmp_path / "a.bin"
        p.write_bytes(b"ao-kernel")
        digest = _sha256_file(p)
        assert len(digest) == 64
        # Same content → same digest
        p2 = tmp_path / "b.bin"
        p2.write_bytes(b"ao-kernel")
        assert _sha256_file(p) == _sha256_file(p2)

    def test_sha256_concat_files_order_sensitive(self, tmp_path: Path):
        a = tmp_path / "a.bin"
        b = tmp_path / "b.bin"
        a.write_bytes(b"alpha")
        b.write_bytes(b"beta")
        assert _sha256_concat_files([a, b]) != _sha256_concat_files([b, a])


# ── _hash_json_dir ─────────────────────────────────────────────────


class TestHashJsonDir:
    def test_missing_dir_returns_empty_hash(self, tmp_path: Path):
        # Nonexistent directory yields the sha256 of the empty byte stream
        digest = _hash_json_dir(tmp_path, "does_not_exist")
        assert len(digest) == 64

    def test_hashes_all_json_files_sorted(self, tmp_path: Path):
        policies = tmp_path / "policies"
        policies.mkdir()
        (policies / "zeta.json").write_text("{\"version\": 1}", encoding="utf-8")
        (policies / "alpha.json").write_text("{\"version\": 2}", encoding="utf-8")
        digest1 = _hash_json_dir(tmp_path, "policies")
        assert len(digest1) == 64
        # Deterministic
        assert _hash_json_dir(tmp_path, "policies") == digest1


# ── _git_commit_and_dirty ─────────────────────────────────────────


class TestGitCommitAndDirty:
    def test_non_git_workspace_returns_unknown(self, tmp_path: Path):
        commit, dirty = _git_commit_and_dirty(tmp_path)
        assert commit == "unknown"
        assert dirty is False

    def test_git_missing_binary_falls_back(self, tmp_path: Path, monkeypatch):
        def _raise(*_a, **_kw):
            raise FileNotFoundError("git not found")
        monkeypatch.setattr(subprocess, "run", _raise)
        commit, dirty = _git_commit_and_dirty(tmp_path)
        assert commit == "unknown"
        assert dirty is False


# ── EvidenceWriter writes ─────────────────────────────────────────


class TestEvidenceWriterWrites:
    @pytest.fixture
    def writer(self, tmp_path: Path) -> EvidenceWriter:
        return EvidenceWriter(out_dir=tmp_path / "evidence", run_id="run-42")

    def test_run_dir_is_out_dir_plus_run_id(self, writer: EvidenceWriter):
        assert writer.run_dir.name == "run-42"
        assert writer.run_dir.parent == writer.out_dir

    def test_write_request_persists_envelope(self, writer: EvidenceWriter):
        writer.write_request({"intent": "FAST_TEXT", "messages": []})
        saved = json.loads((writer.run_dir / "request.json").read_text(encoding="utf-8"))
        assert saved["intent"] == "FAST_TEXT"

    def test_write_summary_persists_summary(self, writer: EvidenceWriter):
        writer.write_summary({"ok": True, "duration_ms": 42})
        saved = json.loads((writer.run_dir / "summary.json").read_text(encoding="utf-8"))
        assert saved["ok"] is True

    def test_write_closeout_persists(self, writer: EvidenceWriter):
        writer.write_closeout({"status": "completed"})
        saved = json.loads((writer.run_dir / "closeout.v1.json").read_text(encoding="utf-8"))
        assert saved["status"] == "completed"

    def test_write_suspend_persists(self, writer: EvidenceWriter):
        writer.write_suspend({"reason": "rate_limit"})
        saved = json.loads((writer.run_dir / "suspend.json").read_text(encoding="utf-8"))
        assert saved["reason"] == "rate_limit"

    def test_write_resume_log_appends_newline(self, writer: EvidenceWriter):
        writer.write_resume_log("resumed without trailing newline")
        body = (writer.run_dir / "resume.log").read_text(encoding="utf-8")
        assert body.endswith("\n")

    def test_write_resume_log_preserves_existing_newline(self, writer: EvidenceWriter):
        writer.write_resume_log("already with newline\n")
        body = (writer.run_dir / "resume.log").read_text(encoding="utf-8")
        assert body.count("\n") == 1

    def test_write_node_input_and_output(self, writer: EvidenceWriter):
        writer.write_node_input("node-A", {"args": 1})
        writer.write_node_output("node-A", {"result": 2})
        assert json.loads(
            (writer.run_dir / "nodes" / "node-A" / "input.json").read_text(encoding="utf-8")
        )["args"] == 1
        assert json.loads(
            (writer.run_dir / "nodes" / "node-A" / "output.json").read_text(encoding="utf-8")
        )["result"] == 2

    def test_write_node_log_appends_text_and_jsonl(self, writer: EvidenceWriter):
        writer.write_node_log("node-B", "log line 1")
        writer.write_node_log("node-B", "log line 2\n")  # already newline-terminated
        txt = (writer.run_dir / "nodes" / "node-B" / "logs.txt").read_text(encoding="utf-8")
        assert "log line 1" in txt
        assert "log line 2" in txt
        jsonl_lines = (
            (writer.run_dir / "nodes" / "node-B" / "events.v1.jsonl")
            .read_text(encoding="utf-8").strip().splitlines()
        )
        assert len(jsonl_lines) == 2
        events = [json.loads(line) for line in jsonl_lines]
        assert all(event["event_type"] == "NODE_LOG" for event in events)

    def test_write_provenance_without_git(self, writer: EvidenceWriter, tmp_path: Path):
        writer.write_provenance(
            workspace=tmp_path,
            summary={
                "workflow_fingerprint": "fp-1",
                "provider_used": "openai",
                "model_used": "gpt-4",
                "execution_target": {"provider": "openai", "model": "gpt-4"},
            },
        )
        data = json.loads((writer.run_dir / "provenance.v1.json").read_text(encoding="utf-8"))
        assert data["git"]["commit"] == "unknown"
        assert data["provider"]["provider_used"] == "openai"
        assert data["execution_target"] == {"provider": "openai", "model": "gpt-4"}
        assert "policies_hash" in data["fingerprints"]

    def test_write_provenance_handles_missing_fields(self, writer: EvidenceWriter, tmp_path: Path):
        writer.write_provenance(workspace=tmp_path, summary={})
        data = json.loads((writer.run_dir / "provenance.v1.json").read_text(encoding="utf-8"))
        assert data["provider"]["provider_used"] == "unknown"
        assert data["provider"]["model_used"] is None
        assert data["fingerprints"]["workflow_fingerprint"] is None
        assert "execution_target" not in data

    def test_write_integrity_manifest_lists_all_files(self, writer: EvidenceWriter):
        writer.write_request({"a": 1})
        writer.write_summary({"b": 2})
        writer.write_node_input("node-x", {"c": 3})
        writer.write_integrity_manifest()
        manifest_path = writer.run_dir / "integrity.manifest.v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        names = {f["path"] for f in manifest["files"]}
        assert "request.json" in names
        assert "summary.json" in names
        assert "nodes/node-x/input.json" in names
        assert "integrity.manifest.v1.json" not in names  # self-excluded
        # Every file has a 64-char sha256
        assert all(len(f["sha256"]) == 64 for f in manifest["files"])

    def test_write_integrity_manifest_with_empty_run_dir(self, writer: EvidenceWriter):
        writer.write_integrity_manifest()
        manifest = json.loads(
            (writer.run_dir / "integrity.manifest.v1.json").read_text(encoding="utf-8")
        )
        assert manifest["files"] == []
