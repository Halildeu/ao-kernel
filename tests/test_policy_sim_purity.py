"""Tests for ``ao_kernel.policy_sim._purity`` — the 23-sentinel
no-side-effects guard (PR-B4 plan v3 §2.1)."""

from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import tempfile
from importlib import resources as _importlib_resources

import pytest

from ao_kernel.policy_sim._purity import (
    PATCHED_SENTINEL_NAMES,
    pure_execution_context,
)
from ao_kernel.policy_sim.errors import (
    PolicySimReentrantError,
    PolicySimSideEffectError,
)


class TestSentinelCoverage:
    def test_at_least_22_sentinels(self) -> None:
        """Plan v3 invariant: 22+ sentinel surface.

        Actual count is 23 (4 emit_event paths + 1 worktree + 4
        subprocess + 4 pathlib + 4 os + 4 tempfile + 2 socket +
        1 importlib)."""
        assert len(PATCHED_SENTINEL_NAMES) >= 22

    def test_emit_event_all_four_paths_covered(self) -> None:
        """Pre-imported aliases + public facade re-export all
        covered (plan v3 iter-2 warning 3 absorb)."""
        expected = {
            "ao_kernel.executor.evidence_emitter.emit_event",
            "ao_kernel.executor.executor.emit_event",
            "ao_kernel.executor.multi_step_driver.emit_event",
            "ao_kernel.executor.emit_event",
        }
        assert expected.issubset(PATCHED_SENTINEL_NAMES)

    def test_subprocess_family_covered(self) -> None:
        expected = {
            "subprocess.Popen.__init__",
            "subprocess.run",
            "subprocess.call",
            "subprocess.check_output",
        }
        assert expected.issubset(PATCHED_SENTINEL_NAMES)

    def test_filesystem_writes_covered(self) -> None:
        expected = {
            "pathlib.Path.write_text",
            "pathlib.Path.write_bytes",
            "pathlib.Path.mkdir",
            "pathlib.Path.touch",
            "os.replace",
            "os.rename",
            "os.remove",
            "os.unlink",
        }
        assert expected.issubset(PATCHED_SENTINEL_NAMES)

    def test_tempfile_family_covered(self) -> None:
        expected = {
            "tempfile.NamedTemporaryFile",
            "tempfile.mkstemp",
            "tempfile.TemporaryFile",
            "tempfile.mkdtemp",
        }
        assert expected.issubset(PATCHED_SENTINEL_NAMES)

    def test_socket_network_covered(self) -> None:
        assert {"socket.socket.connect", "socket.socket.bind"}.issubset(
            PATCHED_SENTINEL_NAMES
        )

    def test_importlib_resource_extraction_covered(self) -> None:
        assert "importlib.resources.as_file" in PATCHED_SENTINEL_NAMES


class TestSubprocessGuarded:
    def test_run_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError) as exc_info:
                subprocess.run(["true"])
        assert exc_info.value.sentinel_name == "subprocess.run"

    def test_call_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                subprocess.call(["true"])

    def test_check_output_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                subprocess.check_output(["true"])

    def test_popen_init_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                subprocess.Popen(["true"])


class TestFilesystemGuarded:
    def test_write_text_raises(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "forbidden.txt"
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError) as exc_info:
                target.write_text("nope")
        assert exc_info.value.sentinel_name == "pathlib.Path.write_text"

    def test_write_bytes_raises(self, tmp_path: pathlib.Path) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                (tmp_path / "x").write_bytes(b"nope")

    def test_mkdir_raises(self, tmp_path: pathlib.Path) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                (tmp_path / "subdir").mkdir()

    def test_touch_raises(self, tmp_path: pathlib.Path) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                (tmp_path / "x").touch()

    def test_os_replace_raises(self, tmp_path: pathlib.Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_text("hi")  # Setup OUTSIDE context.
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                os.replace(str(a), str(b))

    def test_os_rename_raises(self, tmp_path: pathlib.Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.write_text("hi")
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                os.rename(str(a), str(b))

    def test_os_remove_raises(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "x"
        target.write_text("x")
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                os.remove(str(target))

    def test_os_unlink_raises(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "x"
        target.write_text("x")
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                os.unlink(str(target))


class TestTempfileGuarded:
    def test_named_temporary_file_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                tempfile.NamedTemporaryFile()

    def test_mkstemp_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                tempfile.mkstemp()

    def test_temporary_file_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                tempfile.TemporaryFile()

    def test_mkdtemp_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                tempfile.mkdtemp()


class TestNetworkGuarded:
    def test_socket_connect_raises(self) -> None:
        sock = socket.socket()
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                sock.connect(("127.0.0.1", 1))
        sock.close()

    def test_socket_bind_raises(self) -> None:
        sock = socket.socket()
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                sock.bind(("127.0.0.1", 0))
        sock.close()


class TestImportlibResourceGuarded:
    def test_as_file_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                ctx = _importlib_resources.as_file(
                    _importlib_resources.files("ao_kernel")
                )
                ctx.__enter__()


class TestEmitEventGuarded:
    def test_evidence_emitter_path_raises(self) -> None:
        import ao_kernel.executor.evidence_emitter as em

        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError) as exc_info:
                em.emit_event("any_kind", {"foo": "bar"})
        assert (
            exc_info.value.sentinel_name
            == "ao_kernel.executor.evidence_emitter.emit_event"
        )

    def test_multi_step_driver_alias_raises(self) -> None:
        """Pre-imported alias must be patched too (plan v3 warning 3)."""
        import ao_kernel.executor.multi_step_driver as driver_mod

        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError) as exc_info:
                driver_mod.emit_event("any_kind", {"foo": "bar"})
        assert (
            exc_info.value.sentinel_name
            == "ao_kernel.executor.multi_step_driver.emit_event"
        )

    def test_public_facade_alias_raises(self) -> None:
        """Public re-export must be patched too (plan v3 iter-2 warning 3)."""
        import ao_kernel.executor as facade

        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError) as exc_info:
                facade.emit_event("any_kind", {"foo": "bar"})
        assert (
            exc_info.value.sentinel_name
            == "ao_kernel.executor.emit_event"
        )


class TestReentrancy:
    def test_nested_entry_raises(self) -> None:
        with pure_execution_context():
            with pytest.raises(PolicySimReentrantError):
                with pure_execution_context():
                    pass  # pragma: no cover

    def test_can_re_enter_after_exit(self) -> None:
        """Sequential entries are OK; only nested entries fail."""
        with pure_execution_context():
            pass
        with pure_execution_context():
            with pytest.raises(PolicySimSideEffectError):
                subprocess.run(["true"])


class TestRestoreOnExit:
    def test_originals_restored_on_normal_exit(self) -> None:
        original_run = subprocess.run
        with pure_execution_context():
            assert subprocess.run is not original_run
        assert subprocess.run is original_run

    def test_originals_restored_on_exception_propagation(self) -> None:
        original_run = subprocess.run
        with pytest.raises(RuntimeError):
            with pure_execution_context():
                assert subprocess.run is not original_run
                raise RuntimeError("scenario failure")
        assert subprocess.run is original_run

    def test_write_text_restored(self, tmp_path: pathlib.Path) -> None:
        """Post-exit filesystem writes must work normally."""
        with pure_execution_context():
            pass
        (tmp_path / "sanity.txt").write_text("OK")
        assert (tmp_path / "sanity.txt").read_text() == "OK"
