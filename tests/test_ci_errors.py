"""Coverage for ``ao_kernel.ci.errors``."""

from __future__ import annotations

from ao_kernel.ci.errors import CIError, CIRunnerNotFoundError, CITimeoutError


class TestCIRunnerNotFoundError:
    def test_carries_attempted_command(self) -> None:
        err = CIRunnerNotFoundError(
            check_name="pytest",
            attempted_command="python3 -m pytest",
            realpath="/usr/bin/python3",
        )
        assert err.check_name == "pytest"
        assert err.attempted_command == "python3 -m pytest"
        assert err.realpath == "/usr/bin/python3"
        assert "pytest" in str(err)

    def test_realpath_defaults_empty(self) -> None:
        err = CIRunnerNotFoundError(
            check_name="ruff",
            attempted_command="ruff check",
        )
        assert err.realpath == ""


class TestCITimeoutError:
    def test_carries_tails(self) -> None:
        err = CITimeoutError(
            check_name="pytest",
            timeout_seconds=300.0,
            stdout_tail="collected 10 items\n",
            stderr_tail="warning: ...\n",
        )
        assert err.check_name == "pytest"
        assert err.timeout_seconds == 300.0
        assert err.stdout_tail == "collected 10 items\n"
        assert err.stderr_tail == "warning: ...\n"
        assert "300" in str(err)

    def test_tails_default_to_empty(self) -> None:
        err = CITimeoutError(check_name="ruff", timeout_seconds=60.0)
        assert err.stdout_tail == ""
        assert err.stderr_tail == ""


class TestCIErrorHierarchy:
    def test_subclass_cierror(self) -> None:
        assert issubclass(CIRunnerNotFoundError, CIError)
        assert issubclass(CITimeoutError, CIError)
