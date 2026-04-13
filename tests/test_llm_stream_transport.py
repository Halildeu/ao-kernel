"""Tests for streaming HTTP transport — mock SSE server, guardrails, circuit breaker."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ao_kernel._internal.prj_kernel_api.llm_stream_transport import StreamResult, execute_stream_request


class SSEHandler(BaseHTTPRequestHandler):
    """Mock SSE server handler."""

    response_lines: list[str] = []
    status_code: int = 200
    content_type: str = "text/event-stream"

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_len)

        self.send_response(self.status_code)
        self.send_header("Content-Type", self.content_type)
        self.end_headers()

        for line in self.__class__.response_lines:
            self.wfile.write((line + "\n").encode("utf-8"))
            self.wfile.flush()

    def log_message(self, format, *args):
        pass  # Suppress log output


@pytest.fixture()
def sse_server():
    """Start a mock SSE server on a random port."""
    server = HTTPServer(("127.0.0.1", 0), SSEHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, f"http://127.0.0.1:{port}"
    server.shutdown()


class TestStreamTransport:
    def test_successful_stream(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = [
            'data: {"choices":[{"index":0,"delta":{"content":"Hello"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{"content":" world"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            "",
            "data: [DONE]",
            "",
        ]
        SSEHandler.status_code = 200
        SSEHandler.content_type = "text/event-stream"

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-001",
        )

        assert result.status == "OK"
        assert result.complete is True
        assert result.text == "Hello world"
        assert result.finish_reason == "stop"
        assert result.chunk_count > 0
        assert result.elapsed_ms >= 0

    def test_invalid_content_type(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = ['{"error": "not streaming"}']
        SSEHandler.status_code = 200
        SSEHandler.content_type = "application/json"

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-002",
        )

        assert result.status == "FAIL"
        assert result.error_code == "STREAM_INVALID_CONTENT_TYPE"

    def test_callback_cancel(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = [
            'data: {"choices":[{"index":0,"delta":{"content":"chunk1"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{"content":"chunk2"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{"content":"chunk3"}}]}',
            "",
            "data: [DONE]",
            "",
        ]
        SSEHandler.status_code = 200
        SSEHandler.content_type = "text/event-stream"

        chunks_received = []

        def on_chunk(event):
            chunks_received.append(event.text)
            if len(chunks_received) >= 2:
                return False  # Cancel after 2 text chunks

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-003",
            on_chunk=on_chunk,
        )

        assert result.finish_reason == "cancelled"
        assert len(result.text) > 0

    def test_capture_events(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = [
            'data: {"choices":[{"index":0,"delta":{"content":"hi"}}]}',
            "",
            "data: [DONE]",
            "",
        ]
        SSEHandler.status_code = 200
        SSEHandler.content_type = "text/event-stream"

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-004",
            capture_events=True,
        )

        assert result.events is not None
        assert len(result.events) >= 1

    def test_max_output_chars_guardrail(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = [
            'data: {"choices":[{"index":0,"delta":{"content":"' + "x" * 100 + '"}}]}',
            "",
            'data: {"choices":[{"index":0,"delta":{"content":"' + "y" * 100 + '"}}]}',
            "",
            "data: [DONE]",
            "",
        ]
        SSEHandler.status_code = 200
        SSEHandler.content_type = "text/event-stream"

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-005",
            max_output_chars=50,
        )

        assert result.error_code == "STREAM_MAX_OUTPUT_CHARS"

    def test_http_error(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = []
        SSEHandler.status_code = 429
        SSEHandler.content_type = "text/event-stream"

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-006",
        )

        assert result.status == "FAIL"
        assert "429" in (result.error_code or "")

    def test_first_token_ms_timing(self, sse_server):
        server, url = sse_server
        SSEHandler.response_lines = [
            'data: {"choices":[{"index":0,"delta":{"content":"fast"}}]}',
            "",
            "data: [DONE]",
            "",
        ]
        SSEHandler.status_code = 200
        SSEHandler.content_type = "text/event-stream"

        result = execute_stream_request(
            url=url,
            headers={"Content-Type": "application/json"},
            body_bytes=b'{"stream":true}',
            timeout_seconds=10.0,
            provider_id="openai",
            request_id="test-007",
        )

        assert result.first_token_ms is not None
        assert result.first_token_ms >= 0


class TestStreamNormalizer:
    def test_normalize_ok_result(self):
        from ao_kernel._internal.prj_kernel_api.llm_stream_normalizer import normalize_stream_result

        result = StreamResult(
            status="OK", complete=True, text="Hello", finish_reason="stop",
            elapsed_ms=100, chunk_count=2,
        )
        normalized = normalize_stream_result(result, "openai")
        assert normalized["text"] == "Hello"
        assert normalized["stream_metadata"]["complete"] is True
        assert normalized["tool_calls"] == []

    def test_partial_result_detection(self):
        from ao_kernel._internal.prj_kernel_api.llm_stream_normalizer import is_stream_complete, normalize_stream_result

        result = StreamResult(
            status="PARTIAL", complete=False, text="partial",
            finish_reason="timeout", elapsed_ms=5000, chunk_count=10,
        )
        normalized = normalize_stream_result(result, "openai")
        assert not is_stream_complete(normalized)
