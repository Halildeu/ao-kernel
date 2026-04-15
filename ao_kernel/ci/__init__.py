"""Public facade for ``ao_kernel.ci`` — governed CI gate runner.

PR-A4a primitives: ``run_pytest`` and ``run_ruff`` invoke CI tools via
``python3 -m <tool>`` so only the interpreter needs to pass policy
command resolution (basename + realpath + prefix). ``run_all``
orchestrates a sequence with optional ``fail_fast``.

``CIResult.status`` ∈ ``{"pass", "fail", "timeout"}`` — all outcomes
returned. Exceptions are reserved for preflight failures
(``CIRunnerNotFoundError``) and explicit opt-in (``CITimeoutError``
when ``raise_on_timeout=True``). Flaky tolerance is zero.
"""

from __future__ import annotations

from ao_kernel.ci.errors import CIError, CIRunnerNotFoundError, CITimeoutError
from ao_kernel.ci.runners import CIResult, run_all, run_pytest, run_ruff

__all__ = [
    # Results / DTOs
    "CIResult",
    # Primitives
    "run_all",
    "run_pytest",
    "run_ruff",
    # Errors
    "CIError",
    "CIRunnerNotFoundError",
    "CITimeoutError",
]
