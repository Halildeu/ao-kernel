"""Tests for _internal circuit breaker — CLOSED→OPEN→HALF_OPEN state transitions."""

from __future__ import annotations

import time

from ao_kernel._internal.prj_kernel_api.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitState,
    ProviderCircuitBreaker,
    get_circuit_breaker,
    reset_all,
)


class TestCircuitStates:
    def test_initial_state_closed(self):
        cb = ProviderCircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_allow_request_when_closed(self):
        cb = ProviderCircuitBreaker("test")
        allowed, reason = cb.allow_request()
        assert allowed is True
        assert reason == "circuit_closed"

    def test_failures_open_circuit(self):
        cb = ProviderCircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_requests(self):
        cb = ProviderCircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure()
        cb.record_failure()
        allowed, reason = cb.allow_request()
        assert allowed is False
        assert reason == "circuit_open"

    def test_below_threshold_stays_closed(self):
        cb = ProviderCircuitBreaker("test", CircuitBreakerConfig(failure_threshold=5))
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_open_transitions_to_half_open(self):
        cb = ProviderCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.01),
        )
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = ProviderCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.01),
        )
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = ProviderCircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.01),
        )
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_max_calls_limit(self):
        cb = ProviderCircuitBreaker(
            "test",
            CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout_seconds=0.01,
                half_open_max_calls=1,
            ),
        )
        cb.record_failure()
        time.sleep(0.02)
        ok1, _ = cb.allow_request()
        ok2, reason2 = cb.allow_request()
        assert ok1 is True
        assert ok2 is False
        assert reason2 == "circuit_half_open_limit"


class TestStatusAndReset:
    def test_status_dict_shape(self):
        cb = ProviderCircuitBreaker("openai")
        status = cb.status_dict()
        assert status["provider_id"] == "openai"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert "failure_threshold" in status

    def test_reset_clears_state(self):
        cb = ProviderCircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestRegistry:
    def setup_method(self):
        reset_all()

    def test_get_circuit_breaker_singleton(self):
        cb1 = get_circuit_breaker("openai")
        cb2 = get_circuit_breaker("openai")
        assert cb1 is cb2

    def test_different_providers_different_breakers(self):
        cb1 = get_circuit_breaker("openai")
        cb2 = get_circuit_breaker("claude")
        assert cb1 is not cb2

    def test_reset_all_clears_registry(self):
        get_circuit_breaker("openai")
        reset_all()
        # New call creates fresh instance
        cb = get_circuit_breaker("openai")
        assert cb.state == CircuitState.CLOSED
