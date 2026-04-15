"""Typed errors for ``ao_kernel.ci`` runners.

Per CNS-023 iter-2 W7 absorb, fail/timeout are NORMAL CI outcomes and
returned as ``CIResult(status='fail'|'timeout')``. Exceptions here are
reserved for situations where the subprocess cannot start in the first
place (policy / preflight failures), or when a caller explicitly
opts into ``raise_on_timeout=True``.
"""

from __future__ import annotations


class CIError(Exception):
    """Base class for CI-runner errors."""


class CIRunnerNotFoundError(CIError):
    """The resolved command realpath is not under a policy prefix.

    This is a preflight failure: ``policy_enforcer.validate_command``
    rejected the command before any subprocess was spawned. The caller
    MUST handle this at the driver layer (workflow step fails closed
    with ``policy_denied`` evidence kind).
    """

    def __init__(
        self,
        *,
        check_name: str,
        attempted_command: str,
        realpath: str = "",
    ) -> None:
        super().__init__(
            f"CI runner not allowed: {check_name} via {attempted_command!r}"
        )
        self.check_name = check_name
        self.attempted_command = attempted_command
        self.realpath = realpath


class CITimeoutError(CIError):
    """Raised only when ``raise_on_timeout=True`` is passed.

    Default API returns ``CIResult(status='timeout')`` instead; this
    class exists for callers that prefer exception-driven control flow.
    """

    def __init__(
        self,
        *,
        check_name: str,
        timeout_seconds: float,
        stdout_tail: str = "",
        stderr_tail: str = "",
    ) -> None:
        super().__init__(
            f"CI runner {check_name!r} timed out after {timeout_seconds}s"
        )
        self.check_name = check_name
        self.timeout_seconds = timeout_seconds
        self.stdout_tail = stdout_tail
        self.stderr_tail = stderr_tail


__all__ = ["CIError", "CIRunnerNotFoundError", "CITimeoutError"]
