#!/usr/bin/env python3
"""Build-and-install smoke for the packaged Public Beta surface.

The smoke is intentionally wheel-first:

1. Build sdist + wheel from the checkout.
2. Create a fresh virtualenv.
3. Install the built wheel only.
4. Run all supported CLI entry points.
5. Run ``examples/demo_review.py --cleanup`` from a temp cwd outside
   the repository.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"

    shutil.rmtree(dist_dir, ignore_errors=True)
    shutil.rmtree(build_dir, ignore_errors=True)

    with tempfile.TemporaryDirectory(
        prefix="ao-kernel-packaging-smoke-"
    ) as tmp_dir:
        temp_root = Path(tmp_dir)
        venv_dir = temp_root / "venv"
        smoke_cwd = temp_root / "cwd"
        smoke_cwd.mkdir()

        _run([sys.executable, "-m", "build"], cwd=repo_root)
        _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=repo_root)

        venv_bin = _venv_bin_dir(venv_dir)
        venv_python = venv_bin / ("python.exe" if os.name == "nt" else "python")
        venv_pip = venv_bin / ("pip.exe" if os.name == "nt" else "pip")
        console_script = venv_bin / ("ao-kernel.exe" if os.name == "nt" else "ao-kernel")

        wheel_path = _single_wheel(dist_dir)
        _run([str(venv_pip), "install", str(wheel_path)], cwd=smoke_cwd)

        _run([str(console_script), "version"], cwd=smoke_cwd)
        _run([str(venv_python), "-m", "ao_kernel", "version"], cwd=smoke_cwd)
        _run([str(venv_python), "-m", "ao_kernel.cli", "version"], cwd=smoke_cwd)
        _run(
            [
                str(venv_python),
                str(repo_root / "examples" / "demo_review.py"),
                "--cleanup",
            ],
            cwd=smoke_cwd,
        )

    return 0


def _single_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("ao_kernel-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"expected exactly one ao-kernel wheel in {dist_dir}, found {len(wheels)}"
        )
    return wheels[0]


def _venv_bin_dir(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts"
    return venv_dir / "bin"


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"+ {shlex.join(command)}")
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode == 0:
        return
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    if proc.stdout.strip():
        print(proc.stdout.strip(), file=sys.stderr)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
