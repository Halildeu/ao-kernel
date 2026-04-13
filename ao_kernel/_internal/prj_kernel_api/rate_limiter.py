"""Token bucket rate limiter — per-provider request throttling.

Enforces providers_registry.policy.rate_limit_rps. Thread-safe.
"""

from __future__ import annotations

import threading
import time
from typing import Dict

from ao_kernel._internal.shared.logger import get_logger

log = get_logger(__name__)


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rps: float) -> None:
        self._rps = max(0.01, rps)
        self._lock = threading.Lock()
        self._tokens = 1.0
        self._max_tokens = max(1.0, rps)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rps)
        self._last_refill = now

    def acquire(self, timeout_s: float = 5.0) -> bool:
        """Acquire a token. Blocks up to timeout_s if no tokens available.

        Returns True if acquired, False if timeout.
        """
        deadline = time.monotonic() + timeout_s
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.05, 1.0 / self._rps))

    def try_acquire(self) -> bool:
        """Non-blocking acquire. Returns True if token available."""
        with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
        return False


# --- Module-level registry ---

_registry_lock = threading.Lock()
_registry: Dict[str, TokenBucketRateLimiter] = {}


def get_rate_limiter(provider_id: str, rps: float = 1.0) -> TokenBucketRateLimiter:
    """Get or create rate limiter for a provider."""
    with _registry_lock:
        if provider_id not in _registry:
            _registry[provider_id] = TokenBucketRateLimiter(rps)
        return _registry[provider_id]


def reset_all() -> None:
    """Reset all rate limiters (for testing)."""
    with _registry_lock:
        _registry.clear()
