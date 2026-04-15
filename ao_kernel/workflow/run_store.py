"""CAS-backed workflow run store.

Mirrors the ``canonical_store.py`` pattern: every public write routes
through the module-private ``_mutate_with_cas`` helper so the canonical
write path stays single-source (CNS-20260414-010 invariant).

Residual plan v2 fixes applied here:

- ``_run_path`` validates ``run_id`` as UUIDv4 before joining to any
  filesystem path (B3 fix + CNS-020 iter-2 residual #3: explicit
  ``parsed.version == 4`` check beyond generic UUID parse).
- ``_lock_path`` uses ``with_name`` to produce ``state.v1.json.lock``
  rather than ``with_suffix`` which would double-append (CNS-020 iter-2
  residual #1).
- ``validate_workflow_run`` is called once per write, AFTER the revision
  is stamped, because the schema lists ``revision`` as required (CNS-020
  iter-2 residual #2).
- Canonicalization uses ``json.dumps(sort_keys=True, ensure_ascii=False)``
  matching ``canonical_store.store_revision``; no byte-level equality
  claim (CNS-020 iter-2 residual #4).

Revision self-reference is avoided by computing the hash over a
projection of the record with the ``revision`` field removed (plan v2
B1 fix).

Lock semantic: ``file_lock`` from ``ao_kernel._internal.shared.lock``
handles POSIX-only + fail-closed for Windows. Acquired for the whole
load-mutate-write cycle (plan v2 W4 rationale).

Atomic write: ``write_text_atomic`` from
``ao_kernel._internal.shared.utils`` — tempfile + fsync + ``os.replace``.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ao_kernel._internal.shared.lock import file_lock
from ao_kernel._internal.shared.utils import write_text_atomic
from ao_kernel.workflow.errors import (
    WorkflowCASConflictError,
    WorkflowRunCorruptedError,
    WorkflowRunIdInvalidError,
    WorkflowRunNotFoundError,
    WorkflowSchemaValidationError,
)
from ao_kernel.workflow.schema_validator import validate_workflow_run


def _run_path(workspace_root: Path, run_id: str) -> Path:
    """Return the canonical state-file path for ``run_id``.

    Validates ``run_id`` as UUIDv4 before any path join. Rejects
    ``run_id`` values that cannot be parsed as UUID or whose version is
    not 4; raising ``WorkflowRunIdInvalidError`` prevents path-traversal
    (``../etc/passwd``-style) attacks from reaching the filesystem.
    """
    try:
        parsed = uuid.UUID(run_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise WorkflowRunIdInvalidError(run_id=run_id) from exc
    if parsed.version != 4:
        raise WorkflowRunIdInvalidError(run_id=run_id)
    return workspace_root / ".ao" / "runs" / run_id / "state.v1.json"


def _lock_path(workspace_root: Path, run_id: str) -> Path:
    """Sidecar lock path next to the state file.

    Uses ``with_name`` (not ``with_suffix``) so the result is
    ``state.v1.json.lock`` rather than
    ``state.v1.v1.json.lock`` — residual plan-fix #1.
    """
    return _run_path(workspace_root, run_id).with_name("state.v1.json.lock")


def run_revision(record: Mapping[str, Any]) -> str:
    """Return the 64-character SHA-256 hex digest for ``record``.

    The hash is computed over a projection of the record with the
    ``revision`` field REMOVED, which eliminates the self-reference
    that would otherwise make the token unstable (plan v2 B1 fix).

    Canonicalization is ``json.dumps(sort_keys=True, ensure_ascii=False)``
    — the repo convention shared with ``canonical_store.store_revision``
    and ``agent_coordination.get_revision``. Byte-level equality with
    those artefacts is not claimed; each store is content-addressed
    within its own type.
    """
    projection = {k: v for k, v in record.items() if k != "revision"}
    payload = json.dumps(projection, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_run(
    workspace_root: Path,
    run_id: str,
) -> tuple[dict[str, Any], str]:
    """Load the canonical run record and its revision.

    Validates the record against the schema before returning.
    Raises:
    - ``WorkflowRunIdInvalidError`` for non-UUIDv4 ``run_id``.
    - ``WorkflowRunNotFoundError`` when the state file is absent.
    - ``WorkflowRunCorruptedError`` on JSON decode failure or schema
      validation failure.
    """
    data_path = _run_path(workspace_root, run_id)
    if not data_path.exists():
        raise WorkflowRunNotFoundError(
            run_id=run_id,
            store_path=str(data_path),
        )
    record = _load_record_from_disk(data_path, run_id)
    revision = record.get("revision", "")
    return record, revision


def create_run(
    workspace_root: Path,
    *,
    run_id: str,
    workflow_id: str,
    workflow_version: str,
    intent: Mapping[str, Any],
    budget: Mapping[str, Any],
    policy_refs: Sequence[str],
    evidence_refs: Sequence[str],
    adapter_refs: Sequence[str] = (),
) -> tuple[dict[str, Any], str]:
    """Atomically create a new workflow run record.

    Raises ``FileExistsError`` if ``run_id`` already has a record on
    disk. Raises ``WorkflowSchemaValidationError`` if the assembled
    record does not match ``workflow-run.schema.v1.json``.

    ``adapter_refs`` defaults to an empty tuple (plan v2 B7); the
    workflow registry (PR-A2) will populate it when a workflow
    definition specifies adapters at run start.
    """
    created_at = _now_iso()

    def _creator(_empty: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "state": "created",
            "created_at": created_at,
            "intent": dict(intent),
            "steps": [],
            "policy_refs": list(policy_refs),
            "adapter_refs": list(adapter_refs),
            "evidence_refs": list(evidence_refs),
            "budget": dict(budget),
        }

    return _mutate_with_cas(
        workspace_root,
        run_id,
        mutator=_creator,
    )


def save_run_cas(
    workspace_root: Path,
    run_id: str,
    *,
    record: Mapping[str, Any],
    expected_revision: str,
) -> tuple[dict[str, Any], str]:
    """CAS-guarded atomic replacement of an existing run record.

    The caller-supplied ``record`` replaces the current on-disk state,
    provided the current revision matches ``expected_revision``. The
    revision is re-stamped post-replacement.

    Raises:
    - ``WorkflowRunNotFoundError`` if the record does not exist.
    - ``WorkflowCASConflictError`` on revision mismatch.
    - ``WorkflowSchemaValidationError`` if ``record`` violates the
      schema.
    """

    def _replacer(_current: dict[str, Any]) -> dict[str, Any]:
        return dict(record)

    return _mutate_with_cas(
        workspace_root,
        run_id,
        mutator=_replacer,
        expected_revision=expected_revision,
    )


def update_run(
    workspace_root: Path,
    run_id: str,
    *,
    mutator: Callable[[dict[str, Any]], dict[str, Any]],
    max_retries: int = 1,
) -> tuple[dict[str, Any], str]:
    """Load + mutate + save atomically under CAS.

    ``max_retries=1`` by default (plan v2 W4 fix); ``file_lock`` is the
    primary wait primitive, so CAS conflicts under a held lock are rare
    and a single retry suffices. Callers who know their workload has
    hot writes can raise ``max_retries``; the helper does no backoff.

    Raises:
    - ``WorkflowRunNotFoundError`` when the record does not exist at
      the first load attempt.
    - ``WorkflowCASConflictError`` after ``max_retries`` exhausted.
    - Anything the ``mutator`` raises propagates (e.g.
      ``WorkflowTransitionError``, ``WorkflowBudgetExhaustedError``).
    """
    attempts = 0
    last_err: WorkflowCASConflictError | None = None
    while attempts <= max_retries:
        _, revision = load_run(workspace_root, run_id)
        try:
            return _mutate_with_cas(
                workspace_root,
                run_id,
                mutator=mutator,
                expected_revision=revision,
            )
        except WorkflowCASConflictError as exc:
            last_err = exc
            attempts += 1
    assert last_err is not None  # loop structure guarantees this
    raise last_err


def _mutate_with_cas(
    workspace_root: Path,
    run_id: str,
    *,
    mutator: Callable[[dict[str, Any]], dict[str, Any]],
    expected_revision: str | None = None,
    allow_overwrite: bool = False,
) -> tuple[dict[str, Any], str]:
    """Single canonical write path for run records (CNS-010 invariant).

    Semantics:

    - ``allow_overwrite=False`` + ``expected_revision is None``: CREATE
      mode. Record must NOT already exist; otherwise raises
      ``FileExistsError``.
    - ``allow_overwrite=False`` + ``expected_revision`` set: UPDATE
      mode. Record must exist, and its current revision must match
      ``expected_revision``; otherwise raises
      ``WorkflowRunNotFoundError`` or ``WorkflowCASConflictError``.
    - ``allow_overwrite=True``: UNSAFE REPLACE. Absent record is
      treated as empty initial; existing record is replaced without a
      revision check. Reserved for admin flows; not used by the public
      API at this point.

    Lock is held for the entire load-mutate-write cycle. On lock
    timeout or Windows host, the underlying ``file_lock`` raises
    (``LockTimeoutError`` or ``LockPlatformNotSupported``); both
    propagate.
    """
    data_path = _run_path(workspace_root, run_id)
    lockfile = _lock_path(workspace_root, run_id)

    with file_lock(lockfile):
        existing = data_path.exists()

        if not allow_overwrite:
            if expected_revision is None:
                # CREATE
                if existing:
                    raise FileExistsError(
                        f"Run {run_id!r} already exists at {data_path}"
                    )
                current: dict[str, Any] = {}
            else:
                # UPDATE
                if not existing:
                    raise WorkflowRunNotFoundError(
                        run_id=run_id,
                        store_path=str(data_path),
                    )
                current = _load_record_from_disk(data_path, run_id)
                actual = current.get("revision", "")
                if actual != expected_revision:
                    raise WorkflowCASConflictError(
                        run_id=run_id,
                        expected_revision=expected_revision,
                        actual_revision=actual if actual else "<none>",
                    )
        else:
            # UNSAFE REPLACE
            if existing:
                current = _load_record_from_disk(data_path, run_id)
            else:
                current = {}

        new_record = mutator(dict(current))
        new_record["updated_at"] = _now_iso()

        # Re-stamp revision AFTER mutation. run_revision projects out
        # the existing 'revision' field so the hash is content-stable.
        new_revision = run_revision(new_record)
        new_record["revision"] = new_revision

        # Schema validation AFTER stamp — the schema lists 'revision'
        # as required, so pre-stamp validation would always fail for
        # mutators that don't themselves stamp (most mutators don't).
        validate_workflow_run(new_record, run_id=run_id)

        # Atomic write; tempfile + fsync + os.replace on POSIX.
        payload = json.dumps(
            new_record,
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        write_text_atomic(data_path, payload)

        return new_record, new_revision


def _load_record_from_disk(
    data_path: Path,
    run_id: str,
) -> dict[str, Any]:
    """Decode JSON + run schema validation at the load boundary.

    Wraps both failure modes in ``WorkflowRunCorruptedError`` with a
    ``reason`` distinguishing ``json_decode`` from ``schema_invalid``.
    """
    try:
        text = data_path.read_text(encoding="utf-8")
        record: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkflowRunCorruptedError(
            run_id=run_id,
            reason="json_decode",
            details=str(exc),
        ) from exc
    try:
        validate_workflow_run(record, run_id=run_id)
    except WorkflowSchemaValidationError as exc:
        raise WorkflowRunCorruptedError(
            run_id=run_id,
            reason="schema_invalid",
            details=str(exc),
        ) from exc
    return record


def _now_iso() -> str:
    """Return current UTC time as an ISO-8601 string.

    Matches ``ao_kernel._internal.shared.utils.now_iso8601`` formatting
    (``...+00:00`` form; schema ``format: date-time`` accepts both
    ``Z`` and explicit offset).
    """
    return datetime.now(timezone.utc).isoformat()
