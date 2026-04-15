"""CI-gate subprocess runners.

Public primitives: ``run_pytest``, ``run_ruff``, ``run_all``. Each
invokes its tool via ``python3 -m <tool>`` (CNS-023 iter-1 B8 absorb)
inside a hermetic environment supplied by the caller (typically
``SandboxedEnvironment.env_vars`` built by
``policy_enforcer.build_sandbox``).

Flaky tolerance is zero (Plan v2 invariant #12): any non-zero exit →
``CIResult(status='fail')``. Timeouts return ``CIResult(status=
'timeout')`` unless ``raise_on_timeout=True`` is passed. Only preflight
failures (command realpath outside policy prefixes) raise exceptions.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

from ao_kernel.ci.errors import CIRunnerNotFoundError, CITimeoutError
from ao_kernel.executor.policy_enforcer import (
    SandboxedEnvironment,
    validate_command,
)


_CheckName = Literal["pytest", "ruff", "mypy"]


@dataclass(frozen=True)
class CIResult:
    """Outcome of one CI subprocess invocation. Frozen."""

    check_name: str
    command: tuple[str, ...]
    status: Literal["pass", "fail", "timeout"]
    exit_code: int
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str


def run_pytest(
    worktree_root: Path,
    sandbox: SandboxedEnvironment,
    *,
    extra_args: tuple[str, ...] = (),
    timeout: float = 300.0,
    raise_on_timeout: bool = False,
) -> CIResult:
    """Invoke ``python3 -m pytest`` inside the hermetic sandbox.

    Command resolution goes through PR-A3 ``validate_command`` preflight
    (B1 absorb) before any subprocess is spawned.
    """
    cmd = ("python3", "-m", "pytest", *extra_args)
    return _run_check(
        check_name="pytest",
        command=cmd,
        worktree_root=worktree_root,
        sandbox=sandbox,
        timeout=timeout,
        raise_on_timeout=raise_on_timeout,
    )


def run_ruff(
    worktree_root: Path,
    sandbox: SandboxedEnvironment,
    *,
    extra_args: tuple[str, ...] = (),
    timeout: float = 60.0,
    raise_on_timeout: bool = False,
) -> CIResult:
    """Invoke ``python3 -m ruff check`` inside the hermetic sandbox.

    Command resolution goes through PR-A3 ``validate_command`` preflight
    (B1 absorb) before any subprocess is spawned.
    """
    args = extra_args or (".",)
    cmd = ("python3", "-m", "ruff", "check", *args)
    return _run_check(
        check_name="ruff",
        command=cmd,
        worktree_root=worktree_root,
        sandbox=sandbox,
        timeout=timeout,
        raise_on_timeout=raise_on_timeout,
    )


def run_all(
    worktree_root: Path,
    sandbox: SandboxedEnvironment,
    checks: Sequence[_CheckName],
    *,
    fail_fast: bool = False,
    timeouts: Mapping[str, float] | None = None,
    raise_on_timeout: bool = False,
) -> list[CIResult]:
    """Run a sequence of checks; collect results.

    With ``fail_fast=True``, stops at the first non-pass result. Each
    entry in ``timeouts`` overrides the default timeout for that check.
    """
    results: list[CIResult] = []
    timeouts = timeouts or {}
    for name in checks:
        if name == "pytest":
            r = run_pytest(
                worktree_root,
                sandbox,
                timeout=timeouts.get("pytest", 300.0),
                raise_on_timeout=raise_on_timeout,
            )
        elif name == "ruff":
            r = run_ruff(
                worktree_root,
                sandbox,
                timeout=timeouts.get("ruff", 60.0),
                raise_on_timeout=raise_on_timeout,
            )
        else:
            # mypy or other extension: caller should add a runner.
            continue
        results.append(r)
        if fail_fast and r.status != "pass":
            break
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_check(
    *,
    check_name: str,
    command: tuple[str, ...],
    worktree_root: Path,
    sandbox: SandboxedEnvironment,
    timeout: float,
    raise_on_timeout: bool,
) -> CIResult:
    # Preflight policy check — raises CIRunnerNotFoundError if the
    # resolved command realpath is outside policy prefixes (B1 absorb).
    violations = validate_command(
        command[0], tuple(command[1:]), sandbox, secret_values={},
    )
    if violations:
        attempted = " ".join(command)
        realpath = ""
        for v in violations:
            if v.kind == "command_path_outside_policy":
                realpath = v.detail
                break
        raise CIRunnerNotFoundError(
            check_name=check_name,
            attempted_command=attempted,
            realpath=realpath,
        )

    start = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 - preflighted + hermetic env
            list(command),
            cwd=worktree_root,
            capture_output=True,
            timeout=timeout,
            env=dict(sandbox.env_vars),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        stdout_tail = _tail(_decode(exc.stdout), 100)
        stderr_tail = _tail(_decode(exc.stderr), 100)
        if raise_on_timeout:
            raise CITimeoutError(
                check_name=check_name,
                timeout_seconds=timeout,
                stdout_tail=stdout_tail,
                stderr_tail=stderr_tail,
            ) from exc
        return CIResult(
            check_name=check_name,
            command=command,
            status="timeout",
            exit_code=-1,
            duration_seconds=duration,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        duration = time.monotonic() - start
        return CIResult(
            check_name=check_name,
            command=command,
            status="fail",
            exit_code=-1,
            duration_seconds=duration,
            stdout_tail="",
            stderr_tail=str(exc),
        )

    duration = time.monotonic() - start
    status: Literal["pass", "fail"] = "pass" if proc.returncode == 0 else "fail"
    return CIResult(
        check_name=check_name,
        command=command,
        status=status,
        exit_code=proc.returncode,
        duration_seconds=duration,
        stdout_tail=_tail(_decode(proc.stdout), 100),
        stderr_tail=_tail(_decode(proc.stderr), 100),
    )


def _decode(b: bytes | None) -> str:
    if not b:
        return ""
    return b.decode("utf-8", errors="replace")


def _tail(text: str, max_lines: int, max_bytes: int = 10_000) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    chunk = "\n".join(lines[-max_lines:])
    if len(chunk.encode("utf-8")) > max_bytes:
        chunk = chunk.encode("utf-8")[-max_bytes:].decode("utf-8", errors="replace")
    return chunk


__all__ = ["CIResult", "run_pytest", "run_ruff", "run_all"]
