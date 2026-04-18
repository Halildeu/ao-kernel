"""No-side-effects guard for the policy simulation harness (PR-B4).

The simulator evaluates scenarios against proposed policy changes
without touching the workspace, spawning subprocesses, hitting
the network, or writing any files. ``pure_execution_context``
monkey-patches a fixed set of sentinel APIs so that any
accidental side effect — from the simulator itself or from
re-used code paths in ``executor`` / ``governance`` — fail-closes
rather than silently mutating state.

Sentinel coverage (plan v3 §2.1):

- 4 evidence-emit entry points (3 pre-imported aliases + public
  facade re-export).
- ``worktree_builder.create_worktree``.
- 4 ``subprocess`` entry points.
- 4 ``pathlib.Path`` write methods.
- 4 ``os`` mutation entry points.
- 4 ``tempfile`` allocators.
- 2 ``socket`` operations (connect + bind).
- ``importlib.resources.as_file`` (temp extraction).

Total: 23 sentinels + re-entrancy guard.

The context manager is **not** re-entrant: a nested entry raises
``PolicySimReentrantError`` rather than partially restoring
state on exit. Tests must always use a fresh context per
invocation.
"""

from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from importlib import resources as _importlib_resources
from typing import Any, Callable, Iterator

from ao_kernel.policy_sim.errors import (
    PolicySimReentrantError,
    PolicySimSideEffectError,
)


# Sentinel name → (owning module object, attribute name).
# Order matters for deterministic save/restore bookkeeping.
_SENTINELS: tuple[tuple[str, Any, str], ...] = (
    # Evidence emit — patch all four import paths so pre-imported
    # aliases in executor.py / multi_step_driver.py and the
    # public facade re-export all fail-close together.
    (
        "ao_kernel.executor.evidence_emitter.emit_event",
        None,
        "emit_event",
    ),
    (
        "ao_kernel.executor.executor.emit_event",
        None,
        "emit_event",
    ),
    (
        "ao_kernel.executor.multi_step_driver.emit_event",
        None,
        "emit_event",
    ),
    (
        "ao_kernel.executor.emit_event",
        None,
        "emit_event",
    ),
    # Worktree creation.
    (
        "ao_kernel.executor.worktree_builder.create_worktree",
        None,
        "create_worktree",
    ),
    # Subprocess (re-entrant safe — we patch __init__ not Popen
    # itself so the class identity is preserved for isinstance
    # checks downstream).
    ("subprocess.Popen.__init__", subprocess.Popen, "__init__"),
    ("subprocess.run", subprocess, "run"),
    ("subprocess.call", subprocess, "call"),
    ("subprocess.check_output", subprocess, "check_output"),
    # Filesystem writes (pathlib).
    ("pathlib.Path.write_text", pathlib.Path, "write_text"),
    ("pathlib.Path.write_bytes", pathlib.Path, "write_bytes"),
    ("pathlib.Path.mkdir", pathlib.Path, "mkdir"),
    ("pathlib.Path.touch", pathlib.Path, "touch"),
    # Filesystem mutations (os).
    ("os.replace", os, "replace"),
    ("os.rename", os, "rename"),
    ("os.remove", os, "remove"),
    ("os.unlink", os, "unlink"),
    # Tempfile allocators (importlib.resources.as_file uses
    # mkstemp internally for extractable resources; patching
    # tempfile.mkstemp + as_file covers both the low-level call
    # and the common high-level helper).
    ("tempfile.NamedTemporaryFile", tempfile, "NamedTemporaryFile"),
    ("tempfile.mkstemp", tempfile, "mkstemp"),
    ("tempfile.TemporaryFile", tempfile, "TemporaryFile"),
    ("tempfile.mkdtemp", tempfile, "mkdtemp"),
    # Network.
    ("socket.socket.connect", socket.socket, "connect"),
    ("socket.socket.bind", socket.socket, "bind"),
    # Importlib resource extraction.
    (
        "importlib.resources.as_file",
        _importlib_resources,
        "as_file",
    ),
)


PATCHED_SENTINEL_NAMES: frozenset[str] = frozenset(
    entry[0] for entry in _SENTINELS
)
"""Public read-only view of the sentinel names for test assertions."""


def _resolve_target(path: str, owner: Any, attr: str) -> tuple[Any, str]:
    """Resolve ``path`` to ``(module_or_class, attribute_name)``.

    Owners for the emit_event / worktree_builder sentinels are
    supplied as ``None`` because the ao_kernel submodules are not
    necessarily imported at module load time (purity guard must
    stay importable in minimal environments). Lazily resolve the
    module via ``__import__`` on first sentinel setup.
    """
    if owner is not None:
        return owner, attr

    module_path, _, attr_name = path.rpartition(".")
    module = __import__(module_path, fromlist=[attr_name])
    return module, attr_name


def _make_raiser(sentinel_name: str) -> Callable[..., None]:
    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise PolicySimSideEffectError(sentinel_name)

    _raise.__name__ = f"_policy_sim_guard_{sentinel_name.replace('.', '_')}"
    _raise.__qualname__ = _raise.__name__
    return _raise


_ACTIVE: dict[str, bool] = {"in_context": False}


@contextmanager
def pure_execution_context() -> Iterator[None]:
    """Monkeypatch the sentinel surface so any forbidden side
    effect raises :class:`PolicySimSideEffectError`.

    The context manager is strictly not re-entrant: a nested
    entry raises :class:`PolicySimReentrantError` before any
    patching occurs so the outer state remains intact. On exit,
    originals are always restored via ``finally`` — even if an
    exception propagates — so pytest parametrisation and failure
    paths do not leak guards.
    """
    if _ACTIVE["in_context"]:
        raise PolicySimReentrantError()

    originals: list[tuple[Any, str, Any]] = []
    try:
        for path, owner_hint, attr in _SENTINELS:
            owner, attr_name = _resolve_target(path, owner_hint, attr)
            original = getattr(owner, attr_name)
            originals.append((owner, attr_name, original))
            setattr(owner, attr_name, _make_raiser(path))
        _ACTIVE["in_context"] = True
        yield
    finally:
        # Restore in reverse patch order so multi-target attrs
        # (e.g. subprocess.Popen.__init__ after subprocess.run
        # patched) roll back cleanly.
        for owner, attr_name, original in reversed(originals):
            setattr(owner, attr_name, original)
        _ACTIVE["in_context"] = False


__all__ = [
    "PATCHED_SENTINEL_NAMES",
    "pure_execution_context",
]
