"""Package-private artifact writer for PR-A4b.

``_write_artifact`` canonically serialises an invocation / CI / patch
result to ``{run_dir}/artifacts/{step_id}-attempt{n}.json`` via an
atomic write (tempfile + fsync + rename) and returns the run-relative
``output_ref`` plus the SHA-256 hex of the canonical JSON bytes.

**Canonical JSON format (deterministic for replay):**
- ``sort_keys=True``
- ``ensure_ascii=False``
- ``separators=(",", ":")``

**Crash-safety:** the temp file lives in the same directory as the
target so ``os.replace`` is atomic on POSIX. The containing directory
is fsync'd after rename so the durable entry does not depend on
background writeback. A second write for the same ``(step_id, attempt)``
with identical content is idempotent (same target replaced atomically);
different content REPLACES the prior artifact — callers that need a
change-detection hook should inspect the returned ``output_sha256``.

**Ownership note (CNS-024 iter-1 W2 absorb):** this helper is
package-private (leading underscore) but lives in a dedicated module so
both ``Executor.run_step`` and ``MultiStepDriver`` can import it
without a private cross-module path. Do not re-export from
``ao_kernel.executor.__init__``; callers import from
``ao_kernel.executor.artifacts`` directly.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


__all__ = ["write_artifact"]


def write_artifact(
    run_dir: Path,
    step_id: str,
    attempt: int,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    """Serialise + write + fsync ``payload`` for a given step attempt.

    Returns ``(output_ref, output_sha256)`` where:
    - ``output_ref`` — run-relative path ``"artifacts/{step_id}-attempt{attempt}.json"``
    - ``output_sha256`` — hex digest of the canonical JSON bytes

    Raises ``OSError`` if the directory cannot be created or the rename
    fails. ``ValueError`` if ``attempt < 1``.
    """
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    filename = f"{step_id}-attempt{attempt}.json"
    target = artifacts_dir / filename

    # Canonical JSON — deterministic for replay / idempotency
    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    body = serialized.encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()

    # Atomic write: tempfile in same directory → fsync → rename → fsync dir
    fd, tmp_name = tempfile.mkstemp(
        prefix=filename + ".",
        suffix=".tmp",
        dir=artifacts_dir,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)
    except Exception:
        # Best-effort cleanup of stranded tempfile on any error path.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise

    # Fsync the directory so the rename is durable across a crash.
    try:
        dir_fd = os.open(str(artifacts_dir), os.O_RDONLY)
    except OSError:
        dir_fd = None
    if dir_fd is not None:
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    output_ref = f"artifacts/{filename}"
    return output_ref, digest
