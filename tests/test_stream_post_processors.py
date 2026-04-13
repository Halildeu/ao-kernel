"""Tests for streaming post-processor evidence writing."""

from __future__ import annotations

import json
from pathlib import Path


from src.prj_kernel_api.llm_stream_transport import StreamResult


class TestStreamPostProcessors:
    def test_process_stream_response_writes_summary(self, tmp_path: Path):
        from src.prj_kernel_api.llm_post_processors import process_stream_response

        ws = tmp_path / ".cache" / "ws"
        ws.mkdir(parents=True)

        result = StreamResult(
            status="OK", complete=True, text="Hello world",
            finish_reason="stop", elapsed_ms=150, first_token_ms=30,
            chunk_count=5, usage={"input_tokens": 10, "output_tokens": 5},
        )

        summary = process_stream_response(
            stream_result=result,
            provider_id="openai",
            model="gpt-4",
            workspace_root=str(ws),
            request_id="req-001",
        )

        assert summary["status"] == "OK"
        assert summary["complete"] is True
        assert summary["text_length"] == 11

        # Verify summary file written
        summary_path = ws / ".cache" / "reports" / "llm_live_outputs" / "req-001.stream.summary.v1.json"
        assert summary_path.exists()
        saved = json.loads(summary_path.read_text())
        assert saved["chunk_count"] == 5

    def test_process_stream_response_writes_text(self, tmp_path: Path):
        from src.prj_kernel_api.llm_post_processors import process_stream_response

        ws = tmp_path / ".cache" / "ws"
        ws.mkdir(parents=True)

        result = StreamResult(
            status="OK", complete=True, text="Full output text",
            finish_reason="stop", elapsed_ms=100, chunk_count=3,
        )

        process_stream_response(
            stream_result=result,
            provider_id="claude",
            model="claude-3",
            workspace_root=str(ws),
            request_id="req-002",
        )

        text_path = ws / ".cache" / "reports" / "llm_live_outputs" / "req-002_claude.txt"
        assert text_path.exists()
        assert text_path.read_text() == "Full output text"

    def test_process_stream_response_writes_events(self, tmp_path: Path):
        from src.prj_kernel_api.llm_post_processors import process_stream_response

        ws = tmp_path / ".cache" / "ws"
        ws.mkdir(parents=True)

        result = StreamResult(
            status="OK", complete=True, text="test",
            finish_reason="stop", elapsed_ms=50, chunk_count=2,
            events=[
                {"choices": [{"delta": {"content": "te"}}]},
                {"choices": [{"delta": {"content": "st"}}]},
            ],
        )

        process_stream_response(
            stream_result=result,
            provider_id="openai",
            model="gpt-4",
            workspace_root=str(ws),
            request_id="req-003",
        )

        events_path = ws / ".cache" / "reports" / "llm_live_outputs" / "req-003.stream.events.v1.jsonl"
        assert events_path.exists()
        lines = events_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_partial_result_evidence(self, tmp_path: Path):
        from src.prj_kernel_api.llm_post_processors import process_stream_response

        ws = tmp_path / ".cache" / "ws"
        ws.mkdir(parents=True)

        result = StreamResult(
            status="PARTIAL", complete=False, text="partial output",
            finish_reason="timeout", elapsed_ms=5000, chunk_count=10,
            error_code="STREAM_IDLE_TIMEOUT",
        )

        summary = process_stream_response(
            stream_result=result,
            provider_id="openai",
            model="gpt-4",
            workspace_root=str(ws),
            request_id="req-004",
        )

        assert summary["status"] == "PARTIAL"
        assert summary["error_code"] == "STREAM_IDLE_TIMEOUT"
        assert summary["complete"] is False
