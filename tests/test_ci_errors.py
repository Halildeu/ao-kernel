"""Contract tests for ``ao_kernel.ci.errors`` raise/catch surfaces."""

from __future__ import annotations

import pytest

from ao_kernel.ci.errors import CIRunnerNotFoundError, CITimeoutError


class TestCIRunnerNotFoundError:
    def test_roundtrip_carries_all_fields(self) -> None:
        """Driver catches CIRunnerNotFoundError from a preflight-gated
        call and needs every diagnostic field intact for evidence /
        policy_denied event payload construction."""
        with pytest.raises(CIRunnerNotFoundError) as excinfo:
            raise CIRunnerNotFoundError(
                check_name="pytest",
                attempted_command="python3 -m pytest",
                realpath="/usr/bin/python3",
            )
        assert excinfo.value.check_name == "pytest"
        assert excinfo.value.attempted_command == "python3 -m pytest"
        assert excinfo.value.realpath == "/usr/bin/python3"
        assert "pytest" in str(excinfo.value)


class TestCITimeoutError:
    def test_roundtrip_carries_tails_for_evidence(self) -> None:
        """When ``raise_on_timeout=True`` opt-in fires, the driver must
        be able to persist stdout/stderr tails for post-mortem without
        the runner itself serialising the event."""
        with pytest.raises(CITimeoutError) as excinfo:
            raise CITimeoutError(
                check_name="pytest",
                timeout_seconds=300.0,
                stdout_tail="collected 10 items\n",
                stderr_tail="warning: ...\n",
            )
        assert excinfo.value.check_name == "pytest"
        assert excinfo.value.timeout_seconds == 300.0
        assert excinfo.value.stdout_tail == "collected 10 items\n"
        assert excinfo.value.stderr_tail == "warning: ...\n"
        assert "300" in str(excinfo.value)
