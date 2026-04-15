"""Shared git-repo helpers for patch + CI tests (PR-A4a).

Every helper operates on a fresh ``tmp_path`` that the test provides —
no global state, no ``.git`` leakage across tests. The helpers run
``git`` directly (no subprocess sandboxing); they assume the host has a
modern ``git`` on ``PATH`` (≥ 2.30 for ``--3way``/``--index`` flags).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ao_kernel.executor.policy_enforcer import SandboxedEnvironment


_GIT_CONFIG = [
    "-c", "user.name=ao-kernel-test",
    "-c", "user.email=test@ao-kernel.local",
    "-c", "commit.gpgsign=false",
    "-c", "init.defaultBranch=main",
]


def init_repo(root: Path, *, initial_files: dict[str, str] | None = None) -> Path:
    """Initialise a fresh git repo at ``root`` and commit initial files.

    Default initial tree: single ``a.txt`` with three lines + ``README.md``.
    Returns ``root`` for chaining.
    """
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=main", str(root)],
        check=True,
        capture_output=True,
    )
    files = initial_files if initial_files is not None else {
        "a.txt": "line1\nline2\nline3\n",
        "README.md": "# test repo\n",
    }
    for relpath, content in files.items():
        (root / relpath).parent.mkdir(parents=True, exist_ok=True)
        (root / relpath).write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "commit", "-q", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    return root


def make_patch_from_changes(root: Path, changes: dict[str, str | None]) -> str:
    """Apply temporary changes, capture ``git diff``, and revert.

    ``changes`` maps relative paths to their new content — use ``None``
    to simulate a deletion. The working tree is restored before return
    so the caller can feed the captured patch into ``preview_diff`` /
    ``apply_patch`` against the original HEAD.
    """
    # Apply changes
    for relpath, content in changes.items():
        path = root / relpath
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    # Capture diff (includes additions + modifications + deletions)
    proc = subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "diff", "--no-color"],
        check=True,
        capture_output=True,
        text=True,
    )
    # Untracked additions are not in `git diff`; use a temporary
    # add + diff --cached then reset.
    subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "add", "-N", "."],
        check=True,
        capture_output=True,
    )
    proc_staged = subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "diff", "--no-color"],
        check=True,
        capture_output=True,
        text=True,
    )
    patch = proc_staged.stdout or proc.stdout
    # Restore
    subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "reset", "-q", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "checkout", "-q", "--", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CONFIG, "-C", str(root), "clean", "-qfd"],
        check=True,
        capture_output=True,
    )
    return patch


def host_env_for_git() -> dict[str, str]:
    """Minimal env for helper git + patch-package subprocesses.

    The patch/ci primitives run under a hermetic ``env_vars`` dict in
    production; for tests we still need ``PATH`` so ``git`` resolves,
    and ``HOME`` / ``TMPDIR`` so git can find its config directory.
    """
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
    return {k: os.environ[k] for k in keep if k in os.environ}


def build_test_sandbox(
    worktree_root: Path,
    *,
    extra_env: dict[str, str] | None = None,
    allowed_prefixes: tuple[str, ...] | None = None,
    allowed_commands_exact: frozenset[str] | None = None,
) -> "SandboxedEnvironment":
    """Construct a minimal ``SandboxedEnvironment`` for PR-A4a tests.

    Tests exercise real subprocess invocations of ``git``, ``python3``,
    and sometimes ``pytest`` / ``ruff``; the sandbox must therefore:

    - Inherit the host PATH (plus ``HOME``, ``LANG``, ``TMPDIR``,
      ``PYTHONPATH`` if set) so the commands actually resolve.
    - Advertise common system prefixes in ``allowed_command_prefixes``
      so PR-A3 ``validate_command`` accepts the resolved realpath.
    - Use no redaction (tests don't carry secrets).

    Callers may narrow ``allowed_commands_exact`` / ``allowed_prefixes``
    to exercise negative paths (e.g. PATH-poisoning tests that drop
    ``python3`` from the allowlist).
    """
    from ao_kernel.executor.policy_enforcer import (  # local import to avoid
        RedactionConfig,  # circular concerns at module load time
        SandboxedEnvironment,
    )

    env_vars = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": os.environ.get("LANG", "C"),
    }
    if "TMPDIR" in os.environ:
        env_vars["TMPDIR"] = os.environ["TMPDIR"]
    if "PYTHONPATH" in os.environ:
        env_vars["PYTHONPATH"] = os.environ["PYTHONPATH"]
    if extra_env:
        env_vars.update(extra_env)

    prefixes = allowed_prefixes if allowed_prefixes is not None else (
        "/usr/bin",
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/Library/Frameworks/Python.framework/Versions",
        "/opt/local/bin",
    )
    exact = allowed_commands_exact if allowed_commands_exact is not None else (
        frozenset({"git", "python", "python3", "pytest", "ruff", "mypy"})
    )

    return SandboxedEnvironment(
        env_vars=env_vars,
        cwd=worktree_root,
        allowed_commands_exact=exact,
        allowed_command_prefixes=prefixes,
        policy_derived_path_entries=tuple(Path(p) for p in prefixes),
        exposure_modes=frozenset({"env"}),
        evidence_redaction=RedactionConfig(
            env_keys_matching=(),
            stdout_patterns=(),
            file_content_patterns=(),
        ),
        inherit_from_parent=True,
    )
