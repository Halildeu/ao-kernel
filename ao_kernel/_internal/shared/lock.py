"""Platform-neutral filesystem lock — POSIX-only, Windows fail-closed.

Per CNS-20260414-010 consensus:
    - Core dependency line is preserved (only jsonschema is required).
    - Platform-neutral claim is deliberately NOT over-promised: Windows
      raises :class:`NotImplementedError` explicitly rather than failing
      open with a no-op "lock." Windows support is tracked for Tranche D.
    - POSIX path uses ``fcntl.flock(fd, LOCK_EX)`` on a sidecar lockfile
      so the primary data file never holds an OS advisory lock tied to a
      file descriptor we also use for reads.

Public API is the :func:`file_lock` context manager:

    from ao_kernel._internal.shared.lock import file_lock

    with file_lock(workspace_root / ".ao" / "canonical_decisions.v1.lock"):
        # Mutate canonical store — exclusive access guaranteed.
        ...

Callers that want to know whether locking is supported on this platform
(e.g. to emit a clear error at startup instead of at write time) can call
:func:`lock_supported`.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


class LockTimeoutError(TimeoutError):
    """Raised when :func:`file_lock` cannot acquire within its deadline."""


class LockPlatformNotSupported(NotImplementedError):
    """Raised when the host OS does not expose the lock primitives we use."""


def lock_supported() -> bool:
    """Return True on platforms where :func:`file_lock` is implemented.

    Currently POSIX-only. Windows support is deferred to Tranche D
    (v3.1.0); see :class:`LockPlatformNotSupported` for the error path
    callers see if they try to use the lock on an unsupported platform.
    """
    return sys.platform != "win32"


@contextlib.contextmanager
def file_lock(
    lockfile: Path,
    *,
    timeout: float = 5.0,
    poll_interval: float = 0.05,
) -> Iterator[None]:
    """Acquire an exclusive advisory lock on *lockfile*.

    The lockfile is created on demand (``O_CREAT``); it is a sidecar path
    — typically ``<target>.lock`` — not the file you are mutating. Keeping
    the lock separate means readers of the data file never need to open
    the lockfile, and fs-scoped tools (grep, rsync) see a clean data file.

    Args:
        lockfile: Path to the advisory lock file. Created if missing.
        timeout: Maximum seconds to wait for the lock before raising.
        poll_interval: Sleep between acquisition attempts. Kept small
            enough that typical short-held locks return promptly.

    Raises:
        LockPlatformNotSupported: When the host OS is not POSIX.
        LockTimeoutError: When *timeout* elapses before the lock can be
            acquired. Callers handle this as fail-closed — the underlying
            mutation must not proceed.
    """
    if sys.platform == "win32":
        raise LockPlatformNotSupported(
            "Filesystem lock requires POSIX fcntl; Windows support is "
            "planned for v3.1.0 (Tranche D)."
        )

    # Deferred import keeps the module importable on Windows for the
    # lock_supported() / exception path above.
    import fcntl

    lockfile.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockfile), os.O_CREAT | os.O_RDWR, 0o600)

    deadline = time.monotonic() + max(0.0, timeout)
    acquired = False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(
                        f"Could not acquire lock on {lockfile} within {timeout}s"
                    )
                time.sleep(poll_interval)
        yield
    finally:
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError as exc:
                # Lock release failure cannot block the caller's exit path.
                logger.warning("lock release failed for %s: %s", lockfile, exc)
        try:
            os.close(fd)
        except OSError:
            pass


__all__ = [
    "file_lock",
    "lock_supported",
    "LockTimeoutError",
    "LockPlatformNotSupported",
]
