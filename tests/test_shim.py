"""Behavioral tests for ao_kernel._internal — real function calls, real output validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


class TestInternalNamespace:
    def test_internal_importable(self):
        """v2.0.0: src.* removed, ao_kernel._internal is internal."""
        import ao_kernel._internal
        assert ao_kernel._internal is not None


class TestSharedUtils:
    def test_load_json_parses_file(self, tmp_path: Path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value", "num": 42}')
        from ao_kernel._internal.shared.utils import load_json
        data = load_json(f)
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_load_json_raises_on_missing(self, tmp_path: Path):
        from ao_kernel._internal.shared.utils import load_json
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "nonexistent.json")

    def test_load_json_raises_on_invalid(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        from ao_kernel._internal.shared.utils import load_json
        with pytest.raises(json.JSONDecodeError):
            load_json(f)

    def test_write_json_atomic_creates_file(self, tmp_path: Path):
        from ao_kernel._internal.shared.utils import write_json_atomic
        f = tmp_path / "output.json"
        write_json_atomic(f, {"written": True, "count": 7})
        content = json.loads(f.read_text())
        assert content["written"] is True
        assert content["count"] == 7

    def test_write_json_atomic_creates_parent_dirs(self, tmp_path: Path):
        from ao_kernel._internal.shared.utils import write_json_atomic
        f = tmp_path / "deep" / "nested" / "output.json"
        write_json_atomic(f, {"nested": True})
        assert f.exists()
        assert json.loads(f.read_text())["nested"] is True

    def test_now_iso8601_format(self):
        from ao_kernel._internal.shared.utils import now_iso8601
        ts = now_iso8601()
        # Format: 2026-04-12T23:32:43Z or 2026-04-12T23:32:43.123456Z
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$", ts)

    def test_sha256_text_deterministic(self):
        from ao_kernel._internal.shared.utils import sha256_text
        h1 = sha256_text("hello")
        h2 = sha256_text("hello")
        h3 = sha256_text("world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA-256 hex = 64 chars


class TestSharedLogger:
    def test_get_logger_returns_logger(self):
        from ao_kernel._internal.shared.logger import get_logger
        logger = get_logger("test_module")
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert logger.name == "test_module"


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        from ao_kernel._internal.prj_kernel_api.circuit_breaker import ProviderCircuitBreaker
        cb = ProviderCircuitBreaker(provider_id="test_cb")
        allowed, reason = cb.allow_request()
        assert allowed is True

    def test_failures_open_circuit(self):
        from ao_kernel._internal.prj_kernel_api.circuit_breaker import ProviderCircuitBreaker, CircuitBreakerConfig
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout_seconds=60.0)
        cb = ProviderCircuitBreaker(provider_id="test_open", config=config)
        cb.record_failure(Exception("err1"))
        cb.record_failure(Exception("err2"))
        allowed, reason = cb.allow_request()
        assert allowed is False

    def test_success_resets_failures(self):
        from ao_kernel._internal.prj_kernel_api.circuit_breaker import ProviderCircuitBreaker, CircuitBreakerConfig
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = ProviderCircuitBreaker(provider_id="test_reset", config=config)
        cb.record_failure(Exception("err"))
        cb.record_success()
        allowed, _ = cb.allow_request()
        assert allowed is True


class TestRateLimiter:
    def test_acquire_succeeds_initially(self):
        from ao_kernel._internal.prj_kernel_api.rate_limiter import TokenBucketRateLimiter
        rl = TokenBucketRateLimiter(rps=10.0)
        acquired = rl.acquire()
        assert acquired is True

    def test_limiter_has_acquire_method(self):
        from ao_kernel._internal.prj_kernel_api.rate_limiter import TokenBucketRateLimiter
        rl = TokenBucketRateLimiter(rps=1.0)
        assert hasattr(rl, "acquire")
        result = rl.acquire()
        assert isinstance(result, bool)


class TestRequestBuilder:
    def test_build_openai_request_structure(self):
        from ao_kernel._internal.prj_kernel_api.llm_request_builder import build_live_request
        req = build_live_request(
            provider_id="openai", model="gpt-4",
            messages=[{"role": "user", "content": "hello"}],
            base_url="https://api.openai.com/v1/chat/completions",
            api_key="sk-test",
        )
        assert req["url"] == "https://api.openai.com/v1/chat/completions"
        body = req["body_json"]
        assert body["model"] == "gpt-4"
        assert body["messages"][0]["content"] == "hello"
        assert "Authorization" in req["headers"]

    def test_build_anthropic_request_structure(self):
        from ao_kernel._internal.prj_kernel_api.llm_request_builder import build_live_request
        req = build_live_request(
            provider_id="claude", model="claude-3-opus",
            messages=[{"role": "user", "content": "hi"}],
            base_url="https://api.anthropic.com/v1/messages",
            api_key="sk-ant-test",
        )
        assert "x-api-key" in req["headers"]
        assert req["body_json"]["model"] == "claude-3-opus"


class TestResponseNormalizer:
    def test_normalize_openai_response(self):
        from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import normalize_response
        resp = json.dumps({
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }).encode()
        result = normalize_response(resp, provider_id="openai")
        assert result["text"] == "Hello world"
        assert result["usage"]["input_tokens"] == 5
        assert result["usage"]["output_tokens"] == 2
        assert result["provider_id"] == "openai"

    def test_normalize_anthropic_response(self):
        from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import normalize_response
        resp = json.dumps({
            "content": [{"type": "text", "text": "Merhaba dunya"}],
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }).encode()
        result = normalize_response(resp, provider_id="claude")
        assert result["text"] == "Merhaba dunya"
        assert result["usage"]["input_tokens"] == 10


class TestResourceLoader:
    def test_load_policy_returns_valid_json(self):
        from ao_kernel._internal.shared.resource_loader import load_resource
        data = load_resource("policies", "policy_autonomy.v1.json")
        assert isinstance(data, dict)
        assert "version" in data or "enabled" in data or len(data) > 0

    def test_load_schema_returns_valid_json(self):
        from ao_kernel._internal.shared.resource_loader import load_resource
        data = load_resource("schemas", "active-context-profile.schema.v1.json")
        assert isinstance(data, dict)
        assert "$schema" in data or "type" in data or "properties" in data

    def test_load_operations_returns_valid_json(self):
        from ao_kernel._internal.shared.resource_loader import load_resource
        data = load_resource("operations", "llm_class_registry.v1.json")
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_load_resource_path_returns_existing_file(self):
        from ao_kernel._internal.shared.resource_loader import load_resource_path
        path = load_resource_path("policies", "policy_autonomy.v1.json")
        if path is not None:
            assert path.is_file()
            content = json.loads(path.read_text())
            assert isinstance(content, dict)
