"""Per-provider circuit breaker — prevents cascading failures.

States: CLOSED (normal) → OPEN (reject) → HALF_OPEN (test) → CLOSED.
Thread-safe with per-provider isolation.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from src.shared.logger import get_logger

log = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_max_calls: int = 1


class ProviderCircuitBreaker:
    """Thread-safe circuit breaker for a single provider."""

    def __init__(self, provider_id: str, config: CircuitBreakerConfig | None = None) -> None:
        self.provider_id = provider_id
        self._config = config or CircuitBreakerConfig()
        self._lock = threading.Lock()
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._get_state_locked()

    def _get_state_locked(self) -> CircuitState:
        """Compute current state (must hold lock)."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._config.recovery_timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                log.info("Circuit HALF_OPEN for provider=%s after %.1fs", self.provider_id, elapsed)
        return self._state

    def allow_request(self) -> tuple[bool, str]:
        """Check if a request is allowed through the circuit.

        Returns (allowed, reason).
        """
        with self._lock:
            state = self._get_state_locked()
            if state == CircuitState.CLOSED:
                return True, "circuit_closed"
            if state == CircuitState.OPEN:
                return False, "circuit_open"
            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self._config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True, "circuit_half_open_test"
                return False, "circuit_half_open_limit"
            return True, "unknown"

    def record_success(self) -> None:
        """Record a successful call — resets failure count, closes circuit."""
        with self._lock:
            state = self._get_state_locked()
            if state == CircuitState.HALF_OPEN:
                log.info("Circuit CLOSED for provider=%s (half_open success)", self.provider_id)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count += 1
            self._half_open_calls = 0

    def record_failure(self, error: Exception | None = None) -> None:
        """Record a failed call — may open the circuit."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            state = self._get_state_locked()
            if state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                log.warning(
                    "Circuit OPEN for provider=%s (half_open failure, error=%s)",
                    self.provider_id,
                    type(error).__name__ if error else "unknown",
                )
            elif self._failure_count >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                log.warning(
                    "Circuit OPEN for provider=%s (failures=%d >= threshold=%d)",
                    self.provider_id,
                    self._failure_count,
                    self._config.failure_threshold,
                )

    def status_dict(self) -> Dict[str, Any]:
        """Return current circuit status for evidence/monitoring."""
        with self._lock:
            state = self._get_state_locked()
            return {
                "provider_id": self.provider_id,
                "state": state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "failure_threshold": self._config.failure_threshold,
                "recovery_timeout_seconds": self._config.recovery_timeout_seconds,
            }

    def reset(self) -> None:
        """Reset circuit to initial state (for testing)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._opened_at = 0.0


# --- Module-level registry (thread-safe singleton) ---

_registry_lock = threading.Lock()
_registry: Dict[str, ProviderCircuitBreaker] = {}


def get_circuit_breaker(
    provider_id: str,
    config: CircuitBreakerConfig | None = None,
) -> ProviderCircuitBreaker:
    """Get or create circuit breaker for a provider."""
    with _registry_lock:
        if provider_id not in _registry:
            _registry[provider_id] = ProviderCircuitBreaker(provider_id, config)
        return _registry[provider_id]


def get_all_circuit_status() -> Dict[str, Dict[str, Any]]:
    """Return status of all circuit breakers for monitoring."""
    with _registry_lock:
        return {pid: cb.status_dict() for pid, cb in _registry.items()}


def reset_all() -> None:
    """Reset all circuit breakers (for testing)."""
    with _registry_lock:
        _registry.clear()
