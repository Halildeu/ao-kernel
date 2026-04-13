"""Tests for _internal rate limiter — token bucket acquire/timeout."""

from __future__ import annotations

from ao_kernel._internal.prj_kernel_api.rate_limiter import (
    TokenBucketRateLimiter,
    get_rate_limiter,
    reset_all,
)


class TestTokenBucket:
    def test_first_acquire_succeeds(self):
        rl = TokenBucketRateLimiter(rps=10.0)
        assert rl.acquire(timeout_s=0.1) is True

    def test_try_acquire_succeeds_once(self):
        rl = TokenBucketRateLimiter(rps=10.0)
        assert rl.try_acquire() is True

    def test_try_acquire_fails_when_empty(self):
        rl = TokenBucketRateLimiter(rps=0.01)  # very slow refill
        rl.try_acquire()  # drain token
        assert rl.try_acquire() is False

    def test_acquire_timeout_returns_false(self):
        rl = TokenBucketRateLimiter(rps=0.01)
        rl.try_acquire()  # drain
        assert rl.acquire(timeout_s=0.05) is False

    def test_rps_clamped_to_minimum(self):
        rl = TokenBucketRateLimiter(rps=0.001)
        # Should be clamped to 0.01
        assert rl._rps == 0.01

    def test_refill_restores_tokens(self):
        rl = TokenBucketRateLimiter(rps=100.0)  # fast refill
        rl.try_acquire()  # drain
        import time
        time.sleep(0.02)  # wait for refill
        assert rl.try_acquire() is True

    def test_max_tokens_bounded(self):
        rl = TokenBucketRateLimiter(rps=5.0)
        assert rl._max_tokens == 5.0


class TestRegistry:
    def setup_method(self):
        reset_all()

    def test_get_rate_limiter_singleton(self):
        rl1 = get_rate_limiter("openai", rps=1.0)
        rl2 = get_rate_limiter("openai", rps=1.0)
        assert rl1 is rl2

    def test_different_providers_different_limiters(self):
        rl1 = get_rate_limiter("openai")
        rl2 = get_rate_limiter("claude")
        assert rl1 is not rl2

    def test_reset_all_clears(self):
        get_rate_limiter("openai")
        reset_all()
        rl = get_rate_limiter("openai")
        assert rl.try_acquire() is True  # fresh limiter
