"""v3.13.2 F5 — CLI entry-point contract pins.

Pinleri 3 yol için:

- ``python -m ao_kernel version`` (new module entrypoint via
  ``ao_kernel/__main__.py``)
- ``python -m ao_kernel.cli version`` (direct module invocation via
  ``if __name__ == "__main__"`` guard in ``cli.py``)
- ``ao-kernel version`` (console script installed via
  ``pyproject.toml::project.scripts``) — shells out to ``ao-kernel`` on
  ``$PATH``; skipped when the console script isn't installed in the
  test interpreter's environment (e.g. running from source without
  ``pip install -e .``).

All three must echo ``ao-kernel <version>``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

import ao_kernel


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def _run_console(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ao-kernel", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def test_python_m_ao_kernel_version() -> None:
    proc = _run_module("-m", "ao_kernel", "version")
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"ao-kernel {ao_kernel.__version__}"


def test_python_m_ao_kernel_cli_version() -> None:
    proc = _run_module("-m", "ao_kernel.cli", "version")
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"ao-kernel {ao_kernel.__version__}"


@pytest.mark.skipif(
    shutil.which("ao-kernel") is None,
    reason="ao-kernel console script not on PATH (run `pip install -e .` or install wheel)",
)
def test_ao_kernel_console_version() -> None:
    """Codex iter-1 M2 absorb: console script was claimed in CHANGELOG
    but not pinned. Contract is ``ao-kernel version`` (subcommand, NOT
    ``--version`` flag — cli.py parser only accepts the subcommand)."""
    proc = _run_console("version")
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"ao-kernel {ao_kernel.__version__}"
