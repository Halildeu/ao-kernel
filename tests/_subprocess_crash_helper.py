"""Subprocess crash-kill test harness (v3.4.0 #7).

Shared helper for tests that need to prove a given I/O sequence is
crash-safe: spawn a fresh Python subprocess that runs the target
function up to a chosen checkpoint, then calls ``os._exit`` so the
interpreter halts without running finalizers. The caller then
inspects the surviving on-disk state and verifies a recovery call in
the parent process reconstructs the intended outcome.

Why this matters: mock-based "exception after line N" tests exercise
the exception-handling branches but cannot catch problems that only
surface when the OS really terminates mid-write (unflushed buffers,
fsync gaps, open-file leaks). Subprocess + ``os._exit`` gives a
realistic crash signal without destabilizing the test host.

Design:

- Caller supplies a string snippet of Python to execute inside the
  subprocess. The snippet closes over ``workspace_root`` (passed via
  CLI arg) and performs whatever setup + partial work it wants,
  ending with ``os._exit(77)`` (or any non-zero code).
- Harness runs the subprocess, asserts it exited with the expected
  code, and returns the workspace so the parent process can perform
  its recovery + verification.
- No dependency on test frameworks other than stdlib subprocess +
  pytest's tmp_path (injected by the caller).

Intentionally minimal scope: one helper, not a full orchestration
library. v3.4.0 #7 ships the harness + a single reconciler crash
test that proves the end-to-end "ledger survived, marker did not,
reconciler recovers" invariant under a real OS-level crash.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


_DEFAULT_CRASH_EXIT_CODE = 77


def run_crash_scenario(
    *,
    script: str,
    workspace_root: Path,
    expected_exit_code: int = _DEFAULT_CRASH_EXIT_CODE,
    timeout_seconds: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run ``script`` in a fresh subprocess and assert it exits with
    ``expected_exit_code``.

    The subprocess receives ``str(workspace_root)`` as ``sys.argv[1]``
    so the script can reuse that path. The script should end with
    ``os._exit(<exit_code>)`` to simulate the crash — a clean
    ``sys.exit`` would run finalizers and defeat the point of the
    harness.

    Returns the :class:`CompletedProcess` so the caller can inspect
    stdout/stderr for diagnostic logging when a scenario regresses.

    Raises ``AssertionError`` if the subprocess exits with any other
    code (including 0) — a successful exit indicates the crash was
    not injected, and the recovery assertion would be invalid.
    """
    wrapper = textwrap.dedent(f"""
        import os, sys
        workspace_root = sys.argv[1]
        {textwrap.indent(textwrap.dedent(script), "        ").lstrip()}
    """)
    result = subprocess.run(
        [sys.executable, "-c", wrapper, str(workspace_root)],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    assert result.returncode == expected_exit_code, (
        f"crash harness expected exit {expected_exit_code}, got "
        f"{result.returncode}. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    return result


__all__ = ["run_crash_scenario"]
