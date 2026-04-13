"""Tests for checkpoint/resume — durable session state."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.context.checkpoint import (
    CheckpointError,
    list_checkpoints,
    resume_checkpoint,
    save_checkpoint,
)


class TestSaveCheckpoint:
    def test_save_creates_file(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="cp-save-001", workspace_root=tmp_path)
        path = save_checkpoint(ctx, workspace_root=tmp_path)
        assert Path(path).exists()

    def test_save_with_decisions(self, tmp_path: Path):
        from ao_kernel.session import new_context
        from ao_kernel.context.memory_pipeline import process_turn

        ctx = new_context(session_id="cp-save-002", workspace_root=tmp_path)
        ctx = process_turn(
            json.dumps({"status": "approved"}),
            ctx, request_id="req-1", workspace_root=tmp_path,
        )
        path = save_checkpoint(ctx, workspace_root=tmp_path)
        assert Path(path).exists()

        # Verify content
        saved = json.loads(Path(path).read_text())
        assert len(saved.get("ephemeral_decisions", [])) >= 1


class TestResumeCheckpoint:
    def test_resume_valid_checkpoint(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="cp-resume-001", workspace_root=tmp_path)
        save_checkpoint(ctx, workspace_root=tmp_path)

        loaded = resume_checkpoint(workspace_root=tmp_path, session_id="cp-resume-001")
        assert loaded["session_id"] == "cp-resume-001"
        assert "session_context_sha256" in loaded.get("hashes", {})

    def test_resume_not_found_raises(self, tmp_path: Path):
        with pytest.raises(CheckpointError):
            resume_checkpoint(workspace_root=tmp_path, session_id="nonexistent")

    def test_resume_corrupted_raises(self, tmp_path: Path):
        session_dir = tmp_path / ".cache" / "sessions" / "corrupt"
        session_dir.mkdir(parents=True)
        (session_dir / "session_context.v1.json").write_text("BROKEN!")

        with pytest.raises(CheckpointError):
            resume_checkpoint(workspace_root=tmp_path, session_id="corrupt")

    def test_resume_preserves_decisions(self, tmp_path: Path):
        from ao_kernel.session import new_context
        from ao_kernel.context.memory_pipeline import process_turn

        ctx = new_context(session_id="cp-resume-002", workspace_root=tmp_path)
        ctx = process_turn(
            json.dumps({"framework": "ao-kernel", "version": "0.3.0"}),
            ctx, request_id="req-1", workspace_root=tmp_path,
        )
        save_checkpoint(ctx, workspace_root=tmp_path)

        loaded = resume_checkpoint(workspace_root=tmp_path, session_id="cp-resume-002")
        decisions = loaded.get("ephemeral_decisions", [])
        keys = [d["key"] for d in decisions]
        assert any("framework" in k for k in keys)

    def test_resume_after_process_turn_continues(self, tmp_path: Path):
        """Full cycle: save → resume → continue processing."""
        from ao_kernel.session import new_context
        from ao_kernel.context.memory_pipeline import process_turn

        # Turn 1-2
        ctx = new_context(session_id="cp-cycle", workspace_root=tmp_path)
        ctx = process_turn(json.dumps({"lang": "python"}), ctx, workspace_root=tmp_path)
        save_checkpoint(ctx, workspace_root=tmp_path)

        # "Restart" — resume
        ctx = resume_checkpoint(workspace_root=tmp_path, session_id="cp-cycle")

        # Turn 3 — continue
        ctx = process_turn(json.dumps({"version": "3.11"}), ctx, workspace_root=tmp_path)
        save_checkpoint(ctx, workspace_root=tmp_path)

        final = resume_checkpoint(workspace_root=tmp_path, session_id="cp-cycle")
        decisions = final.get("ephemeral_decisions", [])
        keys = [d["key"] for d in decisions]
        assert any("lang" in k for k in keys)
        assert any("version" in k for k in keys)


class TestListCheckpoints:
    def test_list_empty(self, tmp_path: Path):
        assert list_checkpoints(tmp_path) == []

    def test_list_multiple(self, tmp_path: Path):
        from ao_kernel.session import new_context
        for sid in ["cp-list-1", "cp-list-2", "cp-list-3"]:
            ctx = new_context(session_id=sid, workspace_root=tmp_path)
            save_checkpoint(ctx, workspace_root=tmp_path)

        cps = list_checkpoints(tmp_path)
        assert len(cps) == 3
        ids = {cp["session_id"] for cp in cps}
        assert "cp-list-1" in ids
        assert "cp-list-2" in ids

    def test_list_includes_metadata(self, tmp_path: Path):
        from ao_kernel.session import new_context
        ctx = new_context(session_id="cp-meta", workspace_root=tmp_path)
        save_checkpoint(ctx, workspace_root=tmp_path)

        cps = list_checkpoints(tmp_path)
        assert len(cps) == 1
        cp = cps[0]
        assert "session_id" in cp
        assert "created_at" in cp
        assert "expires_at" in cp
        assert "decision_count" in cp
        assert "path" in cp
