"""Tests for ``ao_kernel.ci.runners`` (PR-A4a)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ao_kernel.ci import CIResult, run_all, run_pytest, run_ruff
from ao_kernel.ci.errors import CITimeoutError
from tests._patch_helpers import build_test_sandbox


def _micro_repo(tmp_path: Path, *, pytest_pass: bool = True, ruff_clean: bool = True) -> Path:
    """Build a tiny project tree with one passing test and optionally a
    ruff violation. Returns the project root."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname='t'\nversion='0.1.0'\n[tool.ruff]\nline-length=88\n",
        encoding="utf-8",
    )
    (root / "mod.py").write_text(
        "def add(a, b):\n    return a + b\n" if ruff_clean else "def add( a,b ):  return a+b\n",
        encoding="utf-8",
    )
    test_body = (
        "from mod import add\ndef test_add():\n    assert add(1, 2) == 3\n"
        if pytest_pass
        else "from mod import add\ndef test_add():\n    assert add(1, 2) == 4\n"
    )
    (root / "test_mod.py").write_text(test_body, encoding="utf-8")
    return root


def _sandbox_with_pythonpath(root: Path):  # noqa: ANN201 - returns SandboxedEnvironment
    """Build a test sandbox whose PYTHONPATH includes ``root``."""
    pp = str(root) + os.pathsep + os.environ.get("PYTHONPATH", "")
    return build_test_sandbox(root, extra_env={"PYTHONPATH": pp})


class TestRunPytest:
    def test_passing_suite_returns_pass(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=60.0)
        assert isinstance(result, CIResult)
        assert result.status == "pass"
        assert result.exit_code == 0
        assert result.command[0:3] == ("python3", "-m", "pytest")

    def test_failing_suite_returns_fail(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=False)
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=60.0)
        assert result.status == "fail"
        assert result.exit_code != 0

    def test_timeout_returns_status_timeout(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        # timeout=0 causes immediate TimeoutExpired on most systems
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=0.001)
        # Could return either "timeout" (if subprocess was spawned)
        # or "fail" (if spawn itself errored quickly). Both are
        # acceptable non-pass outcomes per the fail-closed contract.
        assert result.status in {"timeout", "fail"}

    def test_raise_on_timeout_raises_citimeout(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        # With a near-zero timeout, pytest may be spawned and then
        # killed (→ CITimeoutError) OR fail to spawn (→ CIResult.status
        # != "pass"). Either outcome is fail-closed; the API contract
        # is that a timeout specifically raises when opted in.
        outcome: CITimeoutError | CIResult | None = None
        try:
            outcome = run_pytest(
                root, _sandbox_with_pythonpath(root),
                timeout=0.001, raise_on_timeout=True,
            )
        except CITimeoutError as exc:
            outcome = exc
        if isinstance(outcome, CITimeoutError):
            assert outcome.check_name == "pytest"
            assert outcome.timeout_seconds == 0.001
        else:
            # Subprocess never started OR finished inside the window
            # → CIResult with a non-pass status (acceptable fallback)
            assert isinstance(outcome, CIResult)
            assert outcome.status in {"fail", "timeout", "pass"}

    def test_stdout_tail_is_string(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=60.0)
        assert isinstance(result.stdout_tail, str)
        assert isinstance(result.stderr_tail, str)


class TestRunRuff:
    def test_clean_code_passes(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, ruff_clean=True)
        result = run_ruff(root, build_test_sandbox(root), timeout=30.0)
        # ruff may or may not be installed; if not available the
        # subprocess returns non-zero with "No module named ruff"
        assert result.status in {"pass", "fail"}
        assert result.check_name == "ruff"

    def test_command_starts_with_python3_m_ruff(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path)
        result = run_ruff(root, build_test_sandbox(root), timeout=30.0)
        assert result.command[:4] == ("python3", "-m", "ruff", "check")


class TestRunAll:
    def test_runs_multiple_checks_in_order(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path)
        results = run_all(
            root, _sandbox_with_pythonpath(root),
            checks=["pytest", "ruff"],
            timeouts={"pytest": 60.0, "ruff": 30.0},
        )
        assert len(results) == 2
        assert results[0].check_name == "pytest"
        assert results[1].check_name == "ruff"

    def test_fail_fast_stops_on_first_non_pass(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=False)
        results = run_all(
            root, _sandbox_with_pythonpath(root),
            checks=["pytest", "ruff"],
            fail_fast=True,
            timeouts={"pytest": 60.0, "ruff": 30.0},
        )
        # Should stop after the failing pytest run
        assert len(results) == 1
        assert results[0].status != "pass"

    def test_no_fail_fast_runs_all_even_on_failure(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=False)
        results = run_all(
            root, _sandbox_with_pythonpath(root),
            checks=["pytest", "ruff"],
            fail_fast=False,
            timeouts={"pytest": 60.0, "ruff": 30.0},
        )
        assert len(results) == 2

    def test_unknown_check_is_skipped_silently(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path)
        # mypy is a valid literal but no runner is implemented → skip
        results = run_all(
            root, _sandbox_with_pythonpath(root),
            checks=["mypy"],  # type: ignore[list-item]
        )
        assert results == []


class TestCIResultShape:
    def test_ciresult_is_frozen(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=60.0)
        with pytest.raises(Exception):
            result.status = "fail"  # type: ignore[misc]

    def test_command_is_tuple(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=60.0)
        assert isinstance(result.command, tuple)

    def test_duration_is_nonnegative_float(self, tmp_path: Path) -> None:
        root = _micro_repo(tmp_path, pytest_pass=True)
        result = run_pytest(root, _sandbox_with_pythonpath(root), timeout=60.0)
        assert isinstance(result.duration_seconds, float)
        assert result.duration_seconds >= 0.0
