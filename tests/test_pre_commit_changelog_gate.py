"""V5 Epic 1 E-1-4 invariants: pre-commit changelog gate hook.

Shell hook (local-only, opt-in install per CLAUDE.md §17 pattern).
Tests verify the hook's structural correctness + decision contract
WITHOUT actually invoking the hook against git (would require a
sandboxed git repo). Hook semantics are exercised via direct subprocess
calls against a temp directory.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".claude" / "scripts" / "pre-commit-changelog-gate.sh"
VERSION_HOOK_PATH = REPO_ROOT / ".claude" / "scripts" / "pre-commit-version-gate.sh"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"


# ---- 1. Presence + structure (6) ----------------------------------------


def test_hook_file_exists() -> None:
    assert HOOK_PATH.exists(), f"changelog hook missing at {HOOK_PATH}"


def test_hook_is_executable() -> None:
    mode = HOOK_PATH.stat().st_mode
    assert mode & 0o111, f"changelog hook is not executable (mode={oct(mode)})"


def test_hook_uses_bash_shebang() -> None:
    first_line = HOOK_PATH.read_text().splitlines()[0]
    assert first_line.startswith("#!"), "hook must start with shebang"
    assert "bash" in first_line, f"hook must use bash; got: {first_line!r}"


def test_hook_set_e_strict_mode() -> None:
    text = HOOK_PATH.read_text()
    assert "set -e" in text, "hook must use 'set -e' for fail-closed exit semantics"


def test_hook_references_changelog_md() -> None:
    text = HOOK_PATH.read_text()
    assert "CHANGELOG.md" in text


def test_hook_references_keep_a_changelog_discipline() -> None:
    text = HOOK_PATH.read_text()
    # Either the discipline name OR the ADR id must be cited
    assert "Keep-a-Changelog" in text or "ADR-0005" in text


# ---- 2. Allowed-prefix contract (4) -------------------------------------


def test_hook_lists_chore_docs_test_ci_style_prefixes() -> None:
    text = HOOK_PATH.read_text()
    for prefix in ("chore", "docs", "test", "ci", "style"):
        assert prefix in text, f"hook must allow {prefix}: prefix"


def test_hook_blocks_feat_without_changelog() -> None:
    """Run the hook in a temp git repo: staged code change with feat: prefix
    and no CHANGELOG -> exit 1."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        subprocess.run(["git", "init", "--quiet"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
        # Set up the ao_kernel structure with a tracked initial commit
        ao_dir = tmp / "ao_kernel"
        ao_dir.mkdir()
        (ao_dir / "__init__.py").write_text("__version__ = '0.0.0'\n")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        # Stage a code change (not test, not pyproject) with no CHANGELOG
        new_file = ao_dir / "feature.py"
        new_file.write_text("def hello(): return 1\n")
        subprocess.run(["git", "add", str(new_file)], cwd=tmp, check=True)
        # Write commit message with feat: prefix
        msg = tmp / ".git" / "COMMIT_EDITMSG"
        msg.write_text("feat(ao): add hello function\n")
        # Copy hook locally and invoke
        local_hook = tmp / "hook.sh"
        shutil.copy(HOOK_PATH, local_hook)
        os.chmod(local_hook, 0o755)
        result = subprocess.run(
            [str(local_hook)],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1, (
            f"hook must block feat: without CHANGELOG; got returncode={result.returncode}, stderr={result.stderr!r}"
        )
        assert "CHANGELOG" in result.stderr


def test_hook_allows_chore_without_changelog() -> None:
    """chore: prefix bypasses CHANGELOG requirement."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        subprocess.run(["git", "init", "--quiet"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
        ao_dir = tmp / "ao_kernel"
        ao_dir.mkdir()
        (ao_dir / "__init__.py").write_text("__version__ = '0.0.0'\n")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp, check=True, capture_output=True)
        new_file = ao_dir / "internal.py"
        new_file.write_text("CONST = 1\n")
        subprocess.run(["git", "add", str(new_file)], cwd=tmp, check=True)
        msg = tmp / ".git" / "COMMIT_EDITMSG"
        msg.write_text("chore: internal cleanup\n")
        local_hook = tmp / "hook.sh"
        shutil.copy(HOOK_PATH, local_hook)
        os.chmod(local_hook, 0o755)
        result = subprocess.run([str(local_hook)], cwd=tmp, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"hook must allow chore:; got {result.returncode}, stderr={result.stderr!r}"


def test_hook_allows_when_changelog_staged() -> None:
    """feat: with CHANGELOG.md staged is allowed."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        subprocess.run(["git", "init", "--quiet"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=tmp, check=True)
        ao_dir = tmp / "ao_kernel"
        ao_dir.mkdir()
        (ao_dir / "__init__.py").write_text("__version__ = '0.0.0'\n")
        cl = tmp / "CHANGELOG.md"
        cl.write_text("# Changelog\n\n## [Unreleased]\n")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp, check=True, capture_output=True)
        new_file = ao_dir / "feature.py"
        new_file.write_text("def hi(): pass\n")
        cl.write_text("# Changelog\n\n## [Unreleased]\n- Added hi()\n")
        subprocess.run(["git", "add", str(new_file), str(cl)], cwd=tmp, check=True)
        msg = tmp / ".git" / "COMMIT_EDITMSG"
        msg.write_text("feat: add hi()\n")
        local_hook = tmp / "hook.sh"
        shutil.copy(HOOK_PATH, local_hook)
        os.chmod(local_hook, 0o755)
        result = subprocess.run([str(local_hook)], cwd=tmp, capture_output=True, text=True, check=False)
        assert result.returncode == 0, (
            f"hook must allow feat: with CHANGELOG; got {result.returncode}, stderr={result.stderr!r}"
        )


# ---- 3. Coexistence with version-gate hook (2) --------------------------


def test_version_gate_hook_still_present() -> None:
    """E-1-4 must not delete the pre-existing pre-commit-version-gate.sh."""
    assert VERSION_HOOK_PATH.exists()


def test_hook_documents_install_path_alongside_version_gate() -> None:
    """Install instruction must compose the changelog hook with the
    version-gate hook so both fire on every commit."""
    text = HOOK_PATH.read_text()
    assert "pre-commit-version-gate.sh" in text


# ---- 4. ADR-0005 + governance (3) ---------------------------------------


def test_adr_0005_keep_a_changelog_present() -> None:
    """ADR-0005 establishes the Keep-a-Changelog discipline."""
    adr_path = REPO_ROOT / ".claude" / "plans" / "adr" / "ADR-0005-keep-a-changelog-per-pr-discipline.md"
    assert adr_path.exists()


def test_changelog_md_exists_in_repo() -> None:
    assert CHANGELOG_PATH.exists()
    text = CHANGELOG_PATH.read_text()
    assert "## [Unreleased]" in text
    assert "Keep a Changelog" in text


def test_no_workflow_mutation() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = proc.stdout.split()
    for path in changed:
        assert not path.startswith(".github/workflows/"), f"E-1-4 must not touch workflows (E-1-3 covers CI): {path}"
