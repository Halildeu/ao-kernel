"""LLM retry logic — exponential backoff for transient HTTP errors.

Uses tenacity for retry orchestration. Retryable status codes: 429, 500-504.
Non-retryable: 400, 401, 403, 404. Provider registry max_retries is canonical SSOT.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, TypeVar

from src.shared.logger import get_logger

log = get_logger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
NON_RETRYABLE_STATUS_CODES = frozenset({400, 401, 403, 404})


class LLMHTTPError(Exception):
    """HTTP error from an LLM provider with retryability classification."""

    def __init__(self, status_code: int, body: bytes, provider_id: str) -> None:
        self.status_code = status_code
        self.body = body
        self.provider_id = provider_id
        super().__init__(f"HTTP {status_code} from {provider_id}")

    @property
    def is_retryable(self) -> bool:
        return self.status_code in RETRYABLE_STATUS_CODES


def _is_retryable_exception(exc: BaseException) -> bool:
    """Check if an exception should trigger a retry."""
    if isinstance(exc, LLMHTTPError):
        return exc.is_retryable
    if isinstance(exc, (TimeoutError, OSError, ConnectionError)):
        return True
    return False


def execute_with_retry(
    fn: Callable[[], Dict[str, Any]],
    *,
    max_retries: int,
    provider_id: str,
    request_id: str,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> Dict[str, Any]:
    """Execute fn with retry logic.

    Args:
        fn: Callable that returns transport result dict.
        max_retries: Max retry attempts (0 = no retry). Canonical source: providers_registry.
        provider_id: For logging.
        request_id: For logging.
        on_retry: Optional callback(attempt_number, wait_seconds, exception) for evidence.

    Returns:
        Transport result dict from fn.

    Raises:
        LLMHTTPError: On non-retryable HTTP error.
        Exception: On exhausted retries.
    """
    if max_retries <= 0:
        return fn()

    try:
        from tenacity import (
            RetryError,
            retry,
            retry_if_exception,
            stop_after_attempt,
            wait_exponential,
        )
    except ImportError:
        log.warning("tenacity not installed, executing without retry")
        return fn()

    attempt_count = 0

    def _before_retry(retry_state: Any) -> None:
        nonlocal attempt_count
        attempt_count += 1
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        wait = retry_state.next_action.sleep if hasattr(retry_state, "next_action") and retry_state.next_action else 0
        log.info(
            "LLM retry attempt=%d provider=%s request=%s wait=%.1fs error=%s",
            attempt_count,
            provider_id,
            request_id,
            wait,
            str(exc)[:100] if exc else "unknown",
        )
        if on_retry and exc:
            on_retry(attempt_count, float(wait), exc)

    @retry(
        retry=retry_if_exception(_is_retryable_exception),
        stop=stop_after_attempt(max_retries + 1),  # +1 because first attempt isn't a retry
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=_before_retry,
        reraise=False,
    )
    def _call_with_retry() -> Dict[str, Any]:
        result = fn()
        # If transport returned FAIL with retryable status, raise to trigger retry
        if result.get("status") == "FAIL":
            http_status = result.get("http_status")
            if isinstance(http_status, int) and http_status in RETRYABLE_STATUS_CODES:
                raise LLMHTTPError(
                    status_code=http_status,
                    body=result.get("resp_bytes", b""),
                    provider_id=provider_id,
                )
        return result

    try:
        return _call_with_retry()
    except RetryError as exc:
        log.warning(
            "LLM retries exhausted provider=%s request=%s attempts=%d",
            provider_id,
            request_id,
            attempt_count + 1,
        )
        last = exc.last_attempt
        if last and last.exception():
            inner = last.exception()
            if isinstance(inner, LLMHTTPError):
                # Return the failed transport result instead of raising
                return {
                    "status": "FAIL",
                    "http_status": inner.status_code,
                    "resp_bytes": inner.body,
                    "elapsed_ms": 0,
                    "error_code": "PROVIDER_HTTP_ERROR",
                    "error_type": "LLMHTTPError",
                    "error_detail": f"Retries exhausted after {attempt_count + 1} attempts",
                    "tls_cafile": None,
                    "retry_attempts": attempt_count + 1,
                }
        return {
            "status": "FAIL",
            "http_status": None,
            "resp_bytes": b"",
            "elapsed_ms": 0,
            "error_code": "RETRY_EXHAUSTED",
            "error_type": "RetryError",
            "error_detail": f"All {max_retries} retries exhausted for {provider_id}",
            "tls_cafile": None,
            "retry_attempts": attempt_count + 1,
        }
