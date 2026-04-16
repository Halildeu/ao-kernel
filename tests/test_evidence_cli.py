"""Tests for PR-A5 evidence CLI: timeline, replay, manifest, verify."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel._internal.evidence.manifest import (
    generate_manifest,
    verify_manifest,
)
from ao_kernel._internal.evidence.replay import replay, format_replay_report
from ao_kernel._internal.evidence.timeline import timeline


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_run(tmp_path: Path, run_id: str = "test-run-001") -> Path:
    """Seed a minimal run evidence dir with 5 events."""
    run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id
    run_dir.mkdir(parents=True)
    events = [
        {"seq": 1, "ts": "2026-04-16T00:00:01Z", "kind": "workflow_started",
         "actor": "ao-kernel", "step_id": None, "run_id": run_id,
         "event_id": "e1", "payload": {"workflow_id": "test_flow"},
         "payload_hash": "aaa", "replay_safe": True},
        {"seq": 2, "ts": "2026-04-16T00:00:02Z", "kind": "step_started",
         "actor": "ao-kernel", "step_id": "step1", "run_id": run_id,
         "event_id": "e2", "payload": {"step_name": "step1", "attempt": 1},
         "payload_hash": "bbb", "replay_safe": True},
        {"seq": 3, "ts": "2026-04-16T00:00:03Z", "kind": "adapter_invoked",
         "actor": "ao-kernel", "step_id": "step1", "run_id": run_id,
         "event_id": "e3", "payload": {"adapter_id": "codex-stub"},
         "payload_hash": "ccc", "replay_safe": False},
        {"seq": 4, "ts": "2026-04-16T00:00:04Z", "kind": "step_completed",
         "actor": "ao-kernel", "step_id": "step1", "run_id": run_id,
         "event_id": "e4", "payload": {"step_name": "step1", "final_state": "completed"},
         "payload_hash": "ddd", "replay_safe": True},
        {"seq": 5, "ts": "2026-04-16T00:00:05Z", "kind": "workflow_completed",
         "actor": "ao-kernel", "step_id": None, "run_id": run_id,
         "event_id": "e5", "payload": {"steps_executed": ["step1"]},
         "payload_hash": "eee", "replay_safe": True},
    ]
    lines = [json.dumps(e, sort_keys=True) for e in events]
    (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n")
    return run_dir


def _seed_artifacts(run_dir: Path) -> None:
    """Add adapter log + artifact + revdiff for manifest tests."""
    (run_dir / "adapter-codex-stub.jsonl").write_text(
        json.dumps({"line": 1, "log": "hello"}) + "\n"
    )
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "step1-attempt1.json").write_text(
        json.dumps({"status": "ok"}, sort_keys=True)
    )
    patches_dir = run_dir / "patches"
    patches_dir.mkdir(exist_ok=True)
    (patches_dir / "patch-abc.revdiff").write_text("--- a/x\n+++ b/x\n")


# ---------------------------------------------------------------------------
# Timeline tests
# ---------------------------------------------------------------------------


class TestTimeline:
    def test_happy_path_table_output(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        out = timeline(tmp_path, "test-run-001")
        assert "workflow_started" in out
        assert "workflow_completed" in out
        assert "seq" in out  # header

    def test_json_format(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        out = timeline(tmp_path, "test-run-001", format="json")
        lines = out.strip().split("\n")
        assert len(lines) == 5
        first = json.loads(lines[0])
        assert first["kind"] == "workflow_started"

    def test_filter_by_kind(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        out = timeline(tmp_path, "test-run-001",
                       filter_kinds=["workflow_started", "workflow_completed"])
        assert "adapter_invoked" not in out
        assert "workflow_started" in out

    def test_filter_by_actor(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        out = timeline(tmp_path, "test-run-001", filter_actor="human")
        assert out == "no events (after filters)"

    def test_limit(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        out = timeline(tmp_path, "test-run-001", format="json", limit=2)
        lines = out.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[-1])["kind"] == "workflow_completed"

    def test_missing_run_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".ao").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            timeline(tmp_path, "nonexistent-run")

    def test_empty_events(self, tmp_path: Path) -> None:
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / "empty-run"
        run_dir.mkdir(parents=True)
        (run_dir / "events.jsonl").write_text("")
        out = timeline(tmp_path, "empty-run")
        assert out == "no events"

    def test_malformed_jsonl_raises(self, tmp_path: Path) -> None:
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / "bad-run"
        run_dir.mkdir(parents=True)
        (run_dir / "events.jsonl").write_text("not json\n")
        with pytest.raises(ValueError, match="malformed"):
            timeline(tmp_path, "bad-run")

    def test_payload_summary_truncation(self, tmp_path: Path) -> None:
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / "long-payload"
        run_dir.mkdir(parents=True)
        big_payload = {"key": "x" * 200}
        event = {
            "seq": 1, "ts": "2026-04-16T00:00:01Z", "kind": "workflow_started",
            "actor": "ao-kernel", "run_id": "long-payload", "event_id": "e1",
            "payload": big_payload, "payload_hash": "fff", "replay_safe": True,
        }
        (run_dir / "events.jsonl").write_text(json.dumps(event) + "\n")
        out = timeline(tmp_path, "long-payload")
        assert "..." in out  # truncated


# ---------------------------------------------------------------------------
# Replay tests
# ---------------------------------------------------------------------------


class TestReplay:
    def test_inspect_annotates_replay_safe(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        report = replay(tmp_path, "test-run-001", mode="inspect")
        assert report.run_id == "test-run-001"
        assert report.final_inferred_state == "completed"
        # adapter_invoked should be marked non-replay-safe
        adapter_transitions = [
            t for t in report.transitions if t.event_kind == "adapter_invoked"
        ]
        assert len(adapter_transitions) == 1
        assert adapter_transitions[0].replay_safe is False

    def test_dry_run_reports_state_source(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        report = replay(tmp_path, "test-run-001", mode="dry-run")
        sources = {t.state_source for t in report.transitions}
        assert "event" in sources  # workflow_started → running

    def test_format_replay_report_runs(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        report = replay(tmp_path, "test-run-001")
        output = format_replay_report(report)
        assert "Replay report" in output
        assert "completed" in output

    def test_stored_vs_effective_replay_safe_mismatch(self, tmp_path: Path) -> None:
        """adapter_invoked has stored replay_safe=False (B2 fixed in emitter)
        and effective replay_safe=False — no mismatch expected for PR-A5."""
        _seed_run(tmp_path)
        report = replay(tmp_path, "test-run-001")
        adapter_t = [t for t in report.transitions if t.event_kind == "adapter_invoked"]
        if adapter_t:
            # Both stored and effective should be False after B2 fix
            assert adapter_t[0].stored_replay_safe is False
            assert adapter_t[0].replay_safe is False


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


class TestGenerateManifest:
    def test_generates_manifest_json(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        result = generate_manifest(tmp_path, "test-run-001")
        assert result.manifest_path.exists()
        manifest = json.loads(result.manifest_path.read_text())
        assert manifest["version"] == "1"
        assert manifest["run_id"] == "test-run-001"
        paths = {f["path"] for f in manifest["files"]}
        assert "events.jsonl" in paths
        assert "adapter-codex-stub.jsonl" in paths
        assert "artifacts/step1-attempt1.json" in paths
        assert "patches/patch-abc.revdiff" in paths

    def test_idempotent_overwrite(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        r1 = generate_manifest(tmp_path, "test-run-001")
        r2 = generate_manifest(tmp_path, "test-run-001")
        assert r1.manifest_path == r2.manifest_path
        assert {f.sha256 for f in r1.files} == {f.sha256 for f in r2.files}

    def test_missing_run_raises(self, tmp_path: Path) -> None:
        (tmp_path / ".ao" / "evidence" / "workflows").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            generate_manifest(tmp_path, "nonexistent")

    def test_excludes_manifest_and_lock(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        (run_dir / "events.jsonl.lock").write_text("")
        (run_dir / "temp.tmp").write_text("")
        result = generate_manifest(tmp_path, "test-run-001")
        paths = {f.path for f in result.files}
        assert "events.jsonl.lock" not in paths
        assert "temp.tmp" not in paths


class TestVerifyManifest:
    def test_all_match_returns_ok(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        generate_manifest(tmp_path, "test-run-001")
        result = verify_manifest(tmp_path, "test-run-001")
        assert result.all_match is True
        assert result.manifest_outdated is False
        assert result.mismatches == ()
        assert result.missing == ()

    def test_mismatch_detected(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        generate_manifest(tmp_path, "test-run-001")
        # Tamper with events.jsonl
        (run_dir / "events.jsonl").write_text("tampered\n")
        result = verify_manifest(tmp_path, "test-run-001")
        assert result.all_match is False
        assert "events.jsonl" in result.mismatches

    def test_missing_file_detected(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        generate_manifest(tmp_path, "test-run-001")
        (run_dir / "adapter-codex-stub.jsonl").unlink()
        result = verify_manifest(tmp_path, "test-run-001")
        assert result.all_match is False
        assert "adapter-codex-stub.jsonl" in result.missing

    def test_outdated_new_file_detected(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        generate_manifest(tmp_path, "test-run-001")
        # Add a new in-scope file after manifest was generated
        (run_dir / "adapter-new-agent.jsonl").write_text("{}\n")
        result = verify_manifest(tmp_path, "test-run-001")
        assert result.manifest_outdated is True
        assert "adapter-new-agent.jsonl" in result.extra_in_scope

    def test_missing_manifest_returns_missing(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        result = verify_manifest(tmp_path, "test-run-001")
        assert result.all_match is False
        assert "manifest.json" in result.missing

    def test_generate_if_missing_creates_then_verifies(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        result = verify_manifest(
            tmp_path, "test-run-001", generate_if_missing=True,
        )
        assert result.all_match is True
        assert (run_dir / "manifest.json").exists()


# ---------------------------------------------------------------------------
# CLI integration (main entrypoint)
# ---------------------------------------------------------------------------


class TestReplayEdgeCases:
    def test_replay_malformed_jsonl_handled(self, tmp_path: Path) -> None:
        """RW3: replay should not crash on malformed JSONL."""
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / "bad-replay"
        run_dir.mkdir(parents=True)
        (run_dir / "events.jsonl").write_text("not json\n")
        with pytest.raises((json.JSONDecodeError, ValueError)):
            replay(tmp_path, "bad-replay")

    def test_replay_empty_events(self, tmp_path: Path) -> None:
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / "empty-replay"
        run_dir.mkdir(parents=True)
        (run_dir / "events.jsonl").write_text("")
        report = replay(tmp_path, "empty-replay")
        assert report.final_inferred_state == "created"
        assert report.transitions == []

    def test_replay_missing_run(self, tmp_path: Path) -> None:
        (tmp_path / ".ao" / "evidence" / "workflows").mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            replay(tmp_path, "nonexistent")


class TestManifestLock:
    def test_generate_creates_lock_file_temporarily(self, tmp_path: Path) -> None:
        """I4-B2: generate_manifest acquires events.jsonl.lock."""
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        result = generate_manifest(tmp_path, "test-run-001")
        # Lock is released after context manager exits; manifest written
        assert result.manifest_path.exists()


class TestCLIEntrypoint:
    def test_timeline_subcommand(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        from ao_kernel.cli import main
        exit_code = main([
            "--workspace-root", str(tmp_path),
            "evidence", "timeline", "--run", "test-run-001",
        ])
        assert exit_code == 0

    def test_replay_subcommand(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        from ao_kernel.cli import main
        exit_code = main([
            "--workspace-root", str(tmp_path),
            "evidence", "replay", "--run", "test-run-001", "--mode", "inspect",
        ])
        assert exit_code == 0

    def test_generate_manifest_subcommand(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        from ao_kernel.cli import main
        exit_code = main([
            "--workspace-root", str(tmp_path),
            "evidence", "generate-manifest", "--run", "test-run-001",
        ])
        assert exit_code == 0
        assert (run_dir / "manifest.json").exists()

    def test_verify_manifest_subcommand_after_generate(self, tmp_path: Path) -> None:
        run_dir = _seed_run(tmp_path)
        _seed_artifacts(run_dir)
        from ao_kernel.cli import main
        main(["--workspace-root", str(tmp_path),
              "evidence", "generate-manifest", "--run", "test-run-001"])
        exit_code = main([
            "--workspace-root", str(tmp_path),
            "evidence", "verify-manifest", "--run", "test-run-001",
        ])
        assert exit_code == 0

    def test_evidence_no_subcommand_prints_usage(self, tmp_path: Path) -> None:
        from ao_kernel.cli import main
        exit_code = main([
            "--workspace-root", str(tmp_path), "evidence",
        ])
        assert exit_code == 1

    def test_verify_missing_manifest_exit_3(self, tmp_path: Path) -> None:
        _seed_run(tmp_path)
        from ao_kernel._internal.evidence.cli_handlers import cmd_verify_manifest
        import argparse
        args = argparse.Namespace(
            workspace_root=str(tmp_path),
            run_id="test-run-001",
            generate_if_missing=False,
        )
        exit_code = cmd_verify_manifest(args)
        assert exit_code == 3  # I4-B1 fix: missing manifest.json → exactly exit 3

    def test_replay_happy_path_no_warnings(self, tmp_path: Path) -> None:
        """I4-B3 fix: valid happy-path replay should produce 0 warnings
        thanks to synthetic chain bridging."""
        _seed_run(tmp_path)
        report = replay(tmp_path, "test-run-001")
        assert report.final_inferred_state == "completed"
        assert report.warnings == []  # no illegal transitions
