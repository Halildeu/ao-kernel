"""V5 Epic 7 E-7-4 invariants: provider rate limit production tuning (per-tenant).

A tuning runbook over the existing public get_rate_limiter surface. The
per-tenant pattern (namespaced "<tenant>:<provider>" registry key) is verified
to actually isolate buckets — so the doc's claim is machine-backed, not
aspirational (HARD RULE No Fake Work).

Machine-enforced invariants:
  - docs/RATE-LIMIT-TUNING.md present + covers per-tenant key, rps sizing,
    retry/circuit-breaker interaction, measurement
  - the documented per-tenant key pattern genuinely isolates buckets
  - doc affirms guard flags untouched (request shaping != live-call auth)
  - no .github/workflows/ mutation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC = _REPO_ROOT / "docs" / "RATE-LIMIT-TUNING.md"


# ---- 1. doc present + coverage (4) --------------------------------------


def test_doc_present() -> None:
    assert _DOC.is_file(), "docs/RATE-LIMIT-TUNING.md missing (E-7-4)"


def test_doc_covers_per_tenant_key_pattern() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert "get_rate_limiter" in text
    assert '"<tenant>:<provider>"' in text or "{tenant_id}:{provider_id}" in text


def test_doc_covers_rps_sizing_and_headroom() -> None:
    text = _DOC.read_text(encoding="utf-8").lower()
    assert "rps" in text
    assert "headroom" in text
    assert "divide by" in text, "doc must explain dividing quota by pod count"


def test_doc_covers_retry_and_circuit_breaker_interaction() -> None:
    text = _DOC.read_text(encoding="utf-8").lower()
    assert "circuit breaker" in text
    assert "429" in text


# ---- 2. per-tenant key genuinely isolates (2) ---------------------------


def test_per_tenant_key_isolates_buckets() -> None:
    """The documented '<tenant>:<provider>' pattern must yield independent
    buckets — draining tenant A must not affect tenant B."""
    from ao_kernel.llm import get_rate_limiter
    from ao_kernel._internal.prj_kernel_api.rate_limiter import reset_all

    reset_all()
    try:
        a = get_rate_limiter("acme:openai", rps=1.0)
        b = get_rate_limiter("globex:openai", rps=1.0)
        assert a is not b, "per-tenant keys must produce distinct limiter instances"
        # Drain tenant A's single starting token.
        assert a.try_acquire() is True
        assert a.try_acquire() is False  # A exhausted
        # Tenant B is unaffected (isolation).
        assert b.try_acquire() is True, "draining tenant A must not starve tenant B"
    finally:
        reset_all()


def test_same_key_returns_same_bucket() -> None:
    from ao_kernel.llm import get_rate_limiter
    from ao_kernel._internal.prj_kernel_api.rate_limiter import reset_all

    reset_all()
    try:
        first = get_rate_limiter("acme:openai", rps=2.0)
        second = get_rate_limiter("acme:openai", rps=2.0)
        assert first is second, "same registry key must return the same bucket"
    finally:
        reset_all()


# ---- 3. governance (2) --------------------------------------------------


def test_doc_affirms_guard_flags_untouched() -> None:
    text = _DOC.read_text(encoding="utf-8").lower()
    assert "live adapter execution" in text and "const false" in text
    assert "request shaping" in text, "doc must distinguish shaping from live-call auth"


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_7_4_rate_limit_tuning.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-7-4 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-7-4 must not touch .github/workflows/. Touched: {touched}"
