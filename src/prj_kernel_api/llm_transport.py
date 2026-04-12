"""LLM HTTP transport — urlopen execution, TLS, timeout, error classification.

Extracted from adapter_llm_actions_runtime.py (PR0 seam extraction).
Single responsibility: execute HTTP request, return status + bytes + timing.
"""

from __future__ import annotations

import hashlib
import os
import re
import ssl
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict
from urllib import error as url_error
from urllib import request as url_request


def _resolve_tls_cafile() -> str | None:
    """Find the best CA bundle path from env or system."""
    env_candidates = [
        os.environ.get("SSL_CERT_FILE"),
        os.environ.get("REQUESTS_CA_BUNDLE"),
        os.environ.get("CURL_CA_BUNDLE"),
    ]
    for cand in env_candidates:
        if isinstance(cand, str) and cand.strip():
            try:
                if Path(cand).exists():
                    return cand
            except Exception:
                continue
    system_candidates = ["/etc/ssl/cert.pem"]
    for cand in system_candidates:
        try:
            if Path(cand).exists():
                return cand
        except Exception:
            continue
    return None


@lru_cache(maxsize=2)
def resolve_tls_context() -> tuple[ssl.SSLContext | None, str | None]:
    """Return (ssl_context, cafile_path). Cached."""
    cafile = _resolve_tls_cafile()
    if not cafile:
        return None, None
    try:
        return ssl.create_default_context(cafile=cafile), cafile
    except Exception:
        return None, cafile


def bucket_elapsed_ms(elapsed_ms: float) -> int:
    """Round elapsed time to nearest 10ms bucket."""
    return int(round(elapsed_ms / 10.0) * 10)


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def redact_secrets(text: str) -> str:
    """Replace known API key env values in text with ***REDACTED***."""
    redacted = text
    for key in (
        "KERNEL_API_TOKEN",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "CLAUDE_API_KEY",
        "ANTHROPIC_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
        "XAI_API_KEY",
        "GITHUB_TOKEN",
        "SUPPLY_CHAIN_SIGNING_KEY",
    ):
        val = os.environ.get(key)
        if val:
            redacted = redacted.replace(val, "***REDACTED***")
    return redacted


def execute_http_request(
    *,
    url: str,
    headers: Dict[str, str],
    body_bytes: bytes,
    timeout_seconds: float,
    max_response_bytes: int,
) -> Dict[str, Any]:
    """Execute a live HTTP POST request via urllib.

    Returns dict with keys:
        status: "OK" or "FAIL"
        http_status: int or None
        resp_bytes: bytes
        elapsed_ms: int
        error_code: str or None
        error_type: str or None
        error_detail: str or None
        tls_cafile: str or None
    """
    tls_context, tls_cafile = resolve_tls_context()
    req = url_request.Request(url, data=body_bytes, headers=headers, method="POST")

    start = time.monotonic()
    http_status = None
    resp_bytes = b""
    error_code = None
    error_type: str | None = None
    error_detail: str | None = None
    status = "OK"

    try:
        with url_request.urlopen(req, timeout=timeout_seconds, context=tls_context) as resp:
            http_status = int(getattr(resp, "status", 0) or 0)
            resp_bytes = resp.read(max_response_bytes)
    except url_error.HTTPError as exc:
        http_status = int(getattr(exc, "code", 0) or 0)
        try:
            resp_bytes = exc.read(max_response_bytes)
        except Exception:
            resp_bytes = b""
        status = "FAIL"
        error_code = "PROVIDER_HTTP_ERROR"
    except Exception as exc:
        status = "FAIL"
        error_code = "PROVIDER_REQUEST_FAILED"
        error_type = type(exc).__name__
        error_detail = redact_secrets(str(exc))[:400] if str(exc) else None
    finally:
        elapsed_ms = bucket_elapsed_ms((time.monotonic() - start) * 1000.0)

    return {
        "status": status,
        "http_status": http_status,
        "resp_bytes": resp_bytes,
        "elapsed_ms": elapsed_ms,
        "error_code": error_code,
        "error_type": error_type,
        "error_detail": error_detail,
        "tls_cafile": tls_cafile,
    }


def execute_http_request_with_resilience(
    *,
    url: str,
    headers: Dict[str, str],
    body_bytes: bytes,
    timeout_seconds: float,
    max_response_bytes: int,
    provider_id: str,
    request_id: str,
    max_retries: int = 0,
) -> Dict[str, Any]:
    """Execute HTTP request with retry + circuit breaker.

    Wraps execute_http_request with:
    1. Circuit breaker check (fail-fast if circuit open)
    2. Retry with exponential backoff (tenacity)
    3. Circuit breaker state update (success/failure)

    Args:
        max_retries: From providers_registry policy (canonical SSOT). 0 = no retry.
    """
    from src.prj_kernel_api.circuit_breaker import get_circuit_breaker
    from src.prj_kernel_api.llm_retry import execute_with_retry

    cb = get_circuit_breaker(provider_id)
    allowed, reason = cb.allow_request()
    if not allowed:
        return {
            "status": "FAIL",
            "http_status": None,
            "resp_bytes": b"",
            "elapsed_ms": 0,
            "error_code": "CIRCUIT_OPEN",
            "error_type": None,
            "error_detail": f"Circuit breaker {reason} for {provider_id}",
            "tls_cafile": None,
        }

    retry_evidence: list[dict] = []

    def _on_retry(attempt: int, wait: float, exc: Exception) -> None:
        retry_evidence.append({
            "attempt": attempt,
            "wait_seconds": round(wait, 2),
            "error": str(exc)[:100],
        })

    def _do_request() -> Dict[str, Any]:
        return execute_http_request(
            url=url,
            headers=headers,
            body_bytes=body_bytes,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )

    result = execute_with_retry(
        _do_request,
        max_retries=max_retries,
        provider_id=provider_id,
        request_id=request_id,
        on_retry=_on_retry,
    )

    # Update circuit breaker state
    if result.get("status") == "OK":
        cb.record_success()
    else:
        cb.record_failure(
            Exception(f"HTTP {result.get('http_status')} {result.get('error_code')}")
        )

    # Attach retry evidence
    if retry_evidence:
        result["retry_evidence"] = retry_evidence
    result["retry_attempts"] = result.get("retry_attempts", len(retry_evidence))
    result["circuit_state"] = cb.status_dict()

    return result
