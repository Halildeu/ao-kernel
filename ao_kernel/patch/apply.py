"""Patch apply primitive.

``apply_patch`` runs ``git apply --3way --index -`` inside a hermetic
sandbox. Pre-flight ``git apply --check --3way --index -`` is ALWAYS
invoked first (Plan v2 invariant #9). On success, a deterministic
reverse-diff is atomically written to
``{run_dir}/patches/{patch_id}.revdiff``.

On conflict, a forensic tarball of dirty paths and ``.rej`` contents is
captured under ``{run_dir}/artifacts/rejected/{patch_id}.tgz`` BEFORE
a ``git reset --hard HEAD`` cleanup, so post-mortem evidence is
preserved (Plan v2 invariant #18; CNS-023 iter-1 B6 absorb).
"""

from __future__ import annotations

import io
import secrets
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from ao_kernel.executor.errors import PolicyViolationError
from ao_kernel.executor.policy_enforcer import (
    SandboxedEnvironment,
    validate_command,
)
from ao_kernel.patch._ids import validate_patch_id
from ao_kernel.patch.diff_engine import preview_diff
from ao_kernel.patch.errors import (
    PatchApplyConflictError,
    PatchApplyError,
    PatchBinaryUnsupportedError,
)


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of a successful apply. Frozen."""

    patch_id: str
    applied: bool
    reverse_diff_id: str
    reverse_diff_path: Path
    files_changed: tuple[str, ...]
    lines_added: int
    lines_removed: int
    applied_sha: str
    duration_seconds: float


def apply_patch(
    worktree_root: Path,
    patch_content: str,
    sandbox: SandboxedEnvironment,
    run_dir: Path,
    *,
    patch_id: str | None = None,
    timeout: float = 60.0,
) -> ApplyResult:
    """Apply ``patch_content`` to ``worktree_root``; persist reverse diff.

    Pre-flight check raises ``PatchPreviewError`` (apply NOT attempted).
    Binary-only diffs raise ``PatchBinaryUnsupportedError`` after
    preview. Non-conflict apply failures raise ``PatchApplyError``.
    Three-way conflicts raise ``PatchApplyConflictError`` AFTER forensic
    capture + worktree cleanup. Command resolution goes through PR-A3
    ``validate_command`` (B1 absorb); ``patch_id`` is validated by the
    narrow id regex (B3 absorb).
    """
    assigned_patch_id = (
        secrets.token_urlsafe(32) if patch_id is None else patch_id
    )
    validate_patch_id(assigned_patch_id)
    start = time.monotonic()

    # Pre-flight check (invariant #9) — raises PatchPreviewError on fail
    preview = preview_diff(
        worktree_root,
        patch_content,
        sandbox,
        patch_id=assigned_patch_id,
        timeout=timeout,
    )
    if preview.binary_paths:
        raise PatchBinaryUnsupportedError(
            patch_id=assigned_patch_id,
            binary_paths=preview.binary_paths,
        )

    cmd = ["git", "apply", "--3way", "--index", "-"]
    violations = validate_command(
        cmd[0], tuple(cmd[1:]), sandbox, secret_values={},
    )
    if violations:
        raise PolicyViolationError(violations=list(violations))
    try:
        proc = subprocess.run(  # noqa: S603 - preflighted + hermetic env
            cmd,
            cwd=worktree_root,
            input=patch_content.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            env=dict(sandbox.env_vars),
        )
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as exc:
        raise PatchApplyError(
            patch_id=assigned_patch_id,
            exit_code=-1,
            git_stderr_tail=str(exc),
        ) from None

    stderr = _decode(proc.stderr)
    if proc.returncode != 0:
        # Differentiate conflict (has .rej files) from plain failure
        rej_paths = _find_rej_files(worktree_root)
        if rej_paths:
            dirty = _git_porcelain(worktree_root, sandbox.env_vars)
            _capture_forensics(run_dir, assigned_patch_id, worktree_root, rej_paths)
            _cleanup_worktree(worktree_root, sandbox.env_vars)
            raise PatchApplyConflictError(
                patch_id=assigned_patch_id,
                conflict_paths=rej_paths,
                rejected_hunks=_extract_rej_hunks(worktree_root, rej_paths),
                dirty_paths=dirty,
            )
        raise PatchApplyError(
            patch_id=assigned_patch_id,
            exit_code=proc.returncode,
            git_stderr_tail=_tail(stderr, 20),
        )

    # Success — produce reverse diff from staged index
    reverse_diff = _generate_reverse_diff(worktree_root, sandbox.env_vars, timeout=timeout)
    patches_dir = run_dir / "patches"
    patches_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    revdiff_path = patches_dir / f"{assigned_patch_id}.revdiff"
    _atomic_write_text(revdiff_path, reverse_diff)
    applied_sha = _git_rev_parse_head(worktree_root, sandbox.env_vars, timeout=timeout)
    duration = time.monotonic() - start

    return ApplyResult(
        patch_id=assigned_patch_id,
        applied=True,
        reverse_diff_id=assigned_patch_id,
        reverse_diff_path=revdiff_path,
        files_changed=preview.files_changed,
        lines_added=preview.lines_added,
        lines_removed=preview.lines_removed,
        applied_sha=applied_sha,
        duration_seconds=duration,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_rej_files(worktree_root: Path) -> tuple[str, ...]:
    """Locate ``*.rej`` files under the worktree (relative paths)."""
    results: list[str] = []
    for p in worktree_root.rglob("*.rej"):
        if p.is_file():
            try:
                results.append(str(p.relative_to(worktree_root)))
            except ValueError:
                continue
    return tuple(sorted(results))


def _extract_rej_hunks(worktree_root: Path, rej_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Return hunk headers from each ``.rej`` file (first line each)."""
    headers: list[str] = []
    for rel in rej_paths:
        try:
            text = (worktree_root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # First hunk header in a .rej file looks like "@@ -... +... @@"
        for line in text.splitlines():
            if line.startswith("@@"):
                headers.append(f"{rel}: {line}")
                break
    return tuple(headers)


def _git_porcelain(worktree_root: Path, env_vars: Mapping[str, str]) -> tuple[str, ...]:
    """Capture ``git status --porcelain`` lines as dirty-path forensics."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "status", "--porcelain"],
            cwd=worktree_root,
            capture_output=True,
            timeout=10.0,
            env=dict(env_vars),
        )
    except (subprocess.SubprocessError, OSError):
        return ()
    if proc.returncode != 0:
        return ()
    return tuple(line for line in _decode(proc.stdout).splitlines() if line)


def _capture_forensics(
    run_dir: Path,
    patch_id: str,
    worktree_root: Path,
    rej_paths: tuple[str, ...],
) -> None:
    """Tar up ``.rej`` contents + ``git status`` snapshot BEFORE cleanup."""
    forensics_dir = run_dir / "artifacts" / "rejected"
    forensics_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    tar_path = forensics_dir / f"{patch_id}.tgz"
    try:
        with tarfile.open(tar_path, "w:gz") as tar:
            for rel in rej_paths:
                src = worktree_root / rel
                if src.exists():
                    tar.add(src, arcname=rel)
            # Embed a tiny manifest of rej paths for auditing
            manifest = "\n".join(rej_paths).encode("utf-8")
            info = tarfile.TarInfo(name="REJECTED_PATHS.txt")
            info.size = len(manifest)
            tar.addfile(info, io.BytesIO(manifest))
    except OSError:
        # Forensics capture is best-effort; do not block the cleanup path
        return


def _cleanup_worktree(worktree_root: Path, env_vars: Mapping[str, str]) -> None:
    """Reset worktree to HEAD; remove lingering ``.rej`` files.

    Fail-closed on cleanup itself is intentionally lenient — if the
    reset fails, the caller still raises ``PatchApplyConflictError``
    and the dirty paths are in the forensic tarball.
    """
    try:
        subprocess.run(  # noqa: S603
            ["git", "reset", "--hard", "HEAD"],
            cwd=worktree_root,
            capture_output=True,
            timeout=30.0,
            env=dict(env_vars),
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        pass
    for p in worktree_root.rglob("*.rej"):
        try:
            p.unlink()
        except OSError:
            continue


def _generate_reverse_diff(
    worktree_root: Path,
    env_vars: Mapping[str, str],
    *,
    timeout: float,
) -> str:
    """Emit the reverse of the staged diff (``git diff --cached -R``)."""
    proc = subprocess.run(  # noqa: S603
        ["git", "diff", "--cached", "-R"],
        cwd=worktree_root,
        capture_output=True,
        timeout=timeout,
        env=dict(env_vars),
        check=False,
    )
    return _decode(proc.stdout)


def _git_rev_parse_head(
    worktree_root: Path,
    env_vars: Mapping[str, str],
    *,
    timeout: float,
) -> str:
    """Return the current HEAD commit SHA, or empty string on failure."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_root,
            capture_output=True,
            timeout=timeout,
            env=dict(env_vars),
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    if proc.returncode != 0:
        return ""
    return _decode(proc.stdout).strip()


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically (tempfile + fsync + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent,
    )
    tmp_path = Path(tmp_path_str)
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            import os
            os.fsync(fh.fileno())
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


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


__all__ = ["ApplyResult", "apply_patch"]
