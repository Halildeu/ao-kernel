from __future__ import annotations

import subprocess
import sys

import ao_kernel


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
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
