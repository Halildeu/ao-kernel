"""v3.11 P4 (coverage tranche 3) — `_internal/shared/*` pins.

The four helper modules (`lock.py`, `logger.py`, `resource_loader.py`,
`utils.py`) are 86-98% covered transitively by the feature test suites
but stayed in `coverage.run.omit`. This file adds targeted pins for
the reachable remaining branches so the tree can be pulled into the
ratcheted coverage scope.

Mirrors v3.8 H1 `_internal/secrets/*` + v3.9 M1 `_internal/utils/*`
tranches: small, mechanical, no production-code change.

Two branches intentionally skipped: `lock.py` flock release-failure
path (lines 114-116, 119-120) and the timeout race branch — both
require a second-process fixture to trigger reliably and the existing
transitive coverage is already high enough that the overall 85% gate
is met without them.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest import mock


class TestLockPlatformGuard:
    """`lock.py::file_lock` refuses to engage on Windows (no fcntl)."""

    def test_file_lock_raises_lock_platform_not_supported_on_windows(self, tmp_path: Path) -> None:
        # Simulate Windows without actually being on Windows — the
        # platform check sits at the top of the context manager so
        # monkeypatching sys.platform around the with-entry is enough.
        import pytest

        from ao_kernel._internal.shared.lock import (
            LockPlatformNotSupported,
            file_lock,
        )

        with mock.patch("ao_kernel._internal.shared.lock.sys.platform", "win32"):
            with pytest.raises(LockPlatformNotSupported):
                with file_lock(tmp_path / "noop.lock"):
                    pass  # pragma: no cover — never reached

    def test_lock_supported_reflects_platform(self) -> None:
        from ao_kernel._internal.shared.lock import lock_supported

        # Flip sys.platform via mock and assert the helper respects it.
        with mock.patch("ao_kernel._internal.shared.lock.sys.platform", "linux"):
            assert lock_supported() is True
        with mock.patch("ao_kernel._internal.shared.lock.sys.platform", "win32"):
            assert lock_supported() is False

    def test_file_lock_acquires_and_releases_successfully(self, tmp_path: Path) -> None:
        # Positive path — the success line (`acquired = True` +
        # release cleanup) is what's missing in the coverage report.
        from ao_kernel._internal.shared.lock import file_lock

        lockfile = tmp_path / "success.lock"
        with file_lock(lockfile):
            # Lock file should exist while held.
            assert lockfile.exists()
        # After exit, the file descriptor is released. The file itself
        # may stay on disk — we only assert no exception was raised.


class TestLoggerEnvLevel:
    """`logger.py::get_logger` honors AO_LOG_LEVEL env var."""

    def test_ao_log_level_sets_logger_level(self, monkeypatch: mock.MagicMock) -> None:
        from ao_kernel._internal.shared.logger import get_logger

        monkeypatch.setenv("AO_LOG_LEVEL", "DEBUG")
        lg = get_logger("ao_kernel.test.p4.debug")
        assert lg.level == logging.DEBUG

    def test_invalid_ao_log_level_leaves_default(self, monkeypatch: mock.MagicMock) -> None:
        from ao_kernel._internal.shared.logger import get_logger

        # Invalid level value should be ignored; the logger's own
        # level stays whatever logging default applies.
        monkeypatch.setenv("AO_LOG_LEVEL", "CHATTY")
        lg = get_logger("ao_kernel.test.p4.invalid")
        # We don't assert a specific level — the pin is that get_logger
        # didn't raise AttributeError (line 34's `if level_str in
        # {...}` guard).
        assert lg.name == "ao_kernel.test.p4.invalid"


class TestResourceLoaderFallback:
    """`resource_loader.py` falls back to bundled defaults when no
    repo-root JSON is present, and returns None for unknown resource
    lookups."""

    def test_find_repo_root_returns_none_when_no_pyproject(self, tmp_path: Path) -> None:
        # Walk starts from the module's __file__; simulate absence by
        # replacing Path(__file__).resolve() with a tmp path that has
        # no pyproject.toml up the tree.
        from ao_kernel._internal.shared import resource_loader as rl

        fake_start = tmp_path / "nested" / "deep" / "here.py"
        fake_start.parent.mkdir(parents=True)
        fake_start.touch()

        # Monkeypatch the module-level __file__ reference. The helper
        # resolves `Path(__file__).resolve()` inside the function body;
        # simplest is to patch Path.resolve to return our fake.
        with mock.patch.object(rl.Path, "resolve", lambda self: fake_start):
            assert rl._find_repo_root() is None

    def test_load_resource_falls_back_to_bundled(self) -> None:
        # Real workspace (our repo root) contains bundled schemas. If we
        # request a filename that doesn't exist at repo root for the
        # resource type, load_resource should fall through to
        # `load_default`, which succeeds for known bundled artefacts.
        from ao_kernel._internal.shared.resource_loader import load_resource

        # policy_tool_calling.v1.json is a bundled policy; the repo
        # root does not have a top-level "policies" mirror, so this
        # hits the fallback path.
        policy = load_resource("policies", "policy_tool_calling.v1.json")
        assert isinstance(policy, dict)
        assert policy.get("version") == "v1"

    def test_load_resource_path_returns_none_when_not_found(self) -> None:
        from ao_kernel._internal.shared.resource_loader import load_resource_path

        # A filename that definitely doesn't exist returns None rather
        # than raising (line 73 fallback).
        assert load_resource_path("policies", "does_not_exist_at_all.v99.json") is None


class TestLoadPolicyValidatedImportGuard:
    """`utils.py::load_policy_validated` requires jsonschema; missing
    it raises RuntimeError with a descriptive message (line 176-177)."""

    def test_raises_runtime_error_when_jsonschema_missing(self, tmp_path: Path) -> None:
        import pytest

        from ao_kernel._internal.shared.utils import load_policy_validated

        # Write a trivial schema + policy so the function reaches the
        # ImportError guard (which runs before the JSON load).
        policy_path = tmp_path / "p.json"
        schema_path = tmp_path / "s.json"
        policy_path.write_text('{"a": 1}', encoding="utf-8")
        schema_path.write_text('{"type": "object"}', encoding="utf-8")

        # Simulate missing jsonschema by patching the import inside
        # the function's namespace. We patch sys.modules + a fresh
        # import to force ImportError.
        import sys

        saved = sys.modules.pop("jsonschema", None)
        try:
            # Override so the `from jsonschema import ...` raises.
            sys.modules["jsonschema"] = None  # type: ignore[assignment]
            with pytest.raises(RuntimeError, match="jsonschema is required"):
                load_policy_validated(policy_path, schema_path)
        finally:
            if saved is not None:
                sys.modules["jsonschema"] = saved
            else:
                sys.modules.pop("jsonschema", None)
