"""v3.8 H2: concurrent writer regression pin for ``emit_adapter_log``.

The adapter log append is now serialised by a sibling ``.lock``
sidecar. Prior to v3.8 the append was comment-only "single-writer";
multiple concurrent step attempts (or a future DAG-parallel driver)
could interleave bytes within the same ``adapter-<id>.jsonl``.

Pattern mirrors ``tests/test_cost_ledger_concurrent.py`` — thread-based
contention + line-count + JSONL parse invariant.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from ao_kernel.executor.evidence_emitter import (
    RedactionConfig,
    emit_adapter_log,
)


def _default_redaction() -> RedactionConfig:
    """Empty RedactionConfig — tests don't exercise redaction path."""
    return RedactionConfig(
        env_keys_matching=(),
        stdout_patterns=(),
        file_content_patterns=(),
    )


class TestEmitAdapterLogConcurrent:
    def test_parallel_writers_produce_no_interleave(
        self,
        tmp_path: Path,
    ) -> None:
        """N threads all append to the same adapter log. With the
        v3.8 H2 file lock the resulting JSONL must:
        1. Contain exactly N lines (one per append call)
        2. Parse every line as valid JSON
        3. Preserve every writer's payload (no byte interleave)
        """
        workspace_root = tmp_path
        run_id = "11111111-2222-3333-4444-555555555555"
        adapter_id = "test-adapter"
        evidence_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        redaction = _default_redaction()

        # 8 threads × 4 appends each → 32 total appends.
        threads_count = 8
        appends_per_thread = 4
        barrier = threading.Barrier(threads_count)
        errors: list[Exception] = []
        errors_lock = threading.Lock()

        def worker(worker_idx: int) -> None:
            barrier.wait()  # all threads start simultaneously
            for call_idx in range(appends_per_thread):
                try:
                    emit_adapter_log(
                        workspace_root,
                        run_id=run_id,
                        adapter_id=adapter_id,
                        captured_stdout=(f"worker={worker_idx} call={call_idx} stdout"),
                        captured_stderr=(f"worker={worker_idx} call={call_idx} stderr"),
                        redaction=redaction,
                    )
                except Exception as exc:  # noqa: BLE001 — test harness
                    with errors_lock:
                        errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)

        assert not errors, f"worker errors: {errors}"
        log_path = evidence_dir / f"adapter-{adapter_id}.jsonl"
        assert log_path.is_file()

        lines = log_path.read_text(encoding="utf-8").splitlines()
        expected_total = threads_count * appends_per_thread
        assert len(lines) == expected_total, (
            f"expected {expected_total} JSONL lines, got {len(lines)} — lock may have failed"
        )
        # Every line is valid JSON and carries the expected shape.
        parsed = []
        for line in lines:
            try:
                parsed.append(json.loads(line))
            except json.JSONDecodeError as exc:
                pytest.fail(f"interleaved write produced invalid JSON line: {line!r} (error: {exc})")
        # Every line has stdout + stderr that parses as a worker/call
        # tag (i.e. no byte-level interleave stripped a field).
        for entry in parsed:
            assert "stdout" in entry and "stderr" in entry
            assert entry["adapter_id"] == adapter_id

    def test_lock_sidecar_created_alongside_log(self, tmp_path: Path) -> None:
        """The lock sidecar file (``.jsonl.lock``) is created as a
        distinct artefact so the same fd isn't held by both the
        readers and the lock holder (CNS-20260414-010 pattern)."""
        workspace_root = tmp_path
        run_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        adapter_id = "solo-adapter"
        evidence_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        redaction = _default_redaction()

        emit_adapter_log(
            workspace_root,
            run_id=run_id,
            adapter_id=adapter_id,
            captured_stdout="hello",
            captured_stderr="",
            redaction=redaction,
        )
        log_path = evidence_dir / f"adapter-{adapter_id}.jsonl"
        lock_path = log_path.with_suffix(log_path.suffix + ".lock")
        assert log_path.is_file()
        assert lock_path.is_file()
