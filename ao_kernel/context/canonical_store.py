"""Canonical decision store — promoted, permanent decisions with temporal lifecycle.

Separates facts from decisions:
    - Decision: actionable choice (e.g., "use Python 3.11", "deploy to staging")
    - Fact: observed state (e.g., "repo has 300 files", "CI is green")

Temporal lifecycle:
    - fresh_until: decision is considered current until this timestamp
    - review_after: decision should be reconsidered after this timestamp
    - expires_at: decision auto-expires (hard deadline)
    - supersedes: previous decision key this one replaces

Promotion: ephemeral → canonical (auto or approved)
Storage: .ao/canonical_decisions.v1.json (workspace-scoped, atomic writes)

Note on naming: This module's "decisions" dict refers to promoted, permanent
decisions stored in .ao/canonical_decisions.v1.json. This is different from
session context's "ephemeral_decisions" field which holds session-scoped,
temporary decisions. The promotion flow is:
    session ephemeral_decisions[] → canonical_store["decisions"]
"""

from __future__ import annotations

import hashlib
import json
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable

from ao_kernel._internal.shared.lock import file_lock, lock_supported
from ao_kernel._internal.shared.utils import write_json_atomic
from ao_kernel.errors import (
    CanonicalRevisionConflict,
    CanonicalStoreCorruptedError,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _future_iso(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CanonicalDecision:
    """A promoted, permanent decision with full lifecycle metadata."""

    key: str
    value: Any
    category: str = "general"  # architecture | runtime | user_pref | approved_plan | fact
    source: str = "agent"
    confidence: float = 0.8
    promoted_from: str = ""    # session_id where decision originated
    promoted_at: str = ""
    fresh_until: str = ""      # considered current until
    review_after: str = ""     # should be reconsidered
    expires_at: str = ""       # hard expiration
    supersedes: str | None = None  # previous decision key
    provenance: dict[str, Any] = field(default_factory=dict)  # evidence linkage
    schema_version: str = "v1"


def _store_path(workspace_root: Path) -> Path:
    """Store canonical decisions in .ao/ directory if available."""
    ao_dir = workspace_root / ".ao"
    if ao_dir.is_dir():
        return ao_dir / "canonical_decisions.v1.json"
    return workspace_root / "canonical_decisions.v1.json"


def _lock_path(workspace_root: Path) -> Path:
    """Sidecar lockfile path for CAS writes."""
    return _store_path(workspace_root).with_suffix(".v1.json.lock")


def _empty_store() -> dict[str, Any]:
    return {"version": "v1", "decisions": {}, "facts": {}, "updated_at": _now_iso()}


def store_revision(store: dict[str, Any]) -> str:
    """Return the canonical revision token for a store snapshot.

    Full SHA-256 hex digest of the sort-key JSON serialization. Callers
    treat the value as opaque. Same contract as
    :func:`ao_kernel.context.agent_coordination.get_revision`.
    """
    payload = json.dumps(store, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_store(workspace_root: Path) -> dict[str, Any]:
    """Load canonical decision store.

    Empty-store semantics:
        - File absent -> return a fresh empty store (normal first-write path).
        - File present but unreadable / unparseable / wrong shape -> raise
          :class:`CanonicalStoreCorruptedError`.

    CNS-20260414-010 iter-2 blocking: the previous silent-empty fallback
    masked data loss. Callers that truly want empty-on-corruption must
    catch the exception explicitly and decide whether to repair, archive,
    or reset.
    """
    path = _store_path(workspace_root)
    if not path.exists():
        return _empty_store()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CanonicalStoreCorruptedError(
            f"Cannot read canonical store at {path}: {exc}"
        ) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CanonicalStoreCorruptedError(
            f"Canonical store JSON at {path} is invalid: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise CanonicalStoreCorruptedError(
            f"Canonical store at {path} must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def save_store(workspace_root: Path, store: dict[str, Any]) -> None:
    """Legacy save — unconditional overwrite, no CAS, no lock.

    Deprecated since v3.0.0. New code should use :func:`save_store_cas`
    or rely on the mutator helpers (``promote_decision``, ``forget``, ...)
    which route through the locked + CAS-aware path. Scheduled for
    removal in v4.0.0.
    """
    warnings.warn(
        "save_store() is deprecated since v3.0.0; use save_store_cas() "
        "or the canonical_store mutator helpers instead. Scheduled for "
        "removal in v4.0.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    store["updated_at"] = _now_iso()
    write_json_atomic(_store_path(workspace_root), store)


def save_store_cas(
    workspace_root: Path,
    store: dict[str, Any],
    *,
    expected_revision: str | None,
    allow_overwrite: bool = False,
) -> str:
    """Atomically save the store under an exclusive lock with CAS check.

    The write pipeline is:
        1. Acquire the sidecar filesystem lock (:mod:`lock`).
        2. Re-read the on-disk store INSIDE the lock.
        3. If ``expected_revision`` is not None, compare against the freshly
           loaded revision. Mismatch raises :class:`CanonicalRevisionConflict`
           unless ``allow_overwrite=True``.
        4. Stamp ``updated_at`` and write atomically via ``write_json_atomic``.
        5. Return the post-write revision token.

    Args:
        workspace_root: Project root containing ``.ao/``.
        store: The full store dict to persist.
        expected_revision: Revision the caller believes the store is at.
            ``None`` skips the CAS check; the caller must still pass
            ``allow_overwrite=True`` for a no-expectation write.
        allow_overwrite: Bypass both the CAS and the None-revision check.
            Used by the deprecated ``save_store`` shim and internal
            bootstrap paths only.

    Returns:
        The SHA-256 revision token of the newly written store.

    Raises:
        CanonicalRevisionConflict: Fresh revision differs from
            ``expected_revision`` and ``allow_overwrite`` is False.
        LockPlatformNotSupported: On Windows (until Tranche D).
        LockTimeoutError: Lock acquisition timed out.
    """
    path = _store_path(workspace_root)
    lockfile = _lock_path(workspace_root)

    # Windows still lands on the existing (non-locked) path until Tranche D;
    # raising here instead of falling back avoids a silent downgrade.
    if not lock_supported():
        from ao_kernel._internal.shared.lock import LockPlatformNotSupported
        raise LockPlatformNotSupported(
            "save_store_cas requires POSIX fcntl locking; Windows support "
            "is tracked in Tranche D (v3.1.0)."
        )

    with file_lock(lockfile):
        current = _load_store_locked(workspace_root)
        current_rev = store_revision(current)
        if not allow_overwrite and expected_revision is not None:
            if current_rev != expected_revision:
                raise CanonicalRevisionConflict(
                    f"Revision mismatch: expected {expected_revision}, "
                    f"store is at {current_rev}"
                )
        store["updated_at"] = _now_iso()
        write_json_atomic(path, store)
        return store_revision(store)


def _load_store_locked(workspace_root: Path) -> dict[str, Any]:
    """Load the store while the caller already holds the lock.

    Missing file -> empty store (first write), corruption propagates.
    Split from ``load_store`` so the public helper does not re-enter the
    lock on every read.
    """
    path = _store_path(workspace_root)
    if not path.exists():
        return _empty_store()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CanonicalStoreCorruptedError(
            f"Canonical store JSON at {path} is invalid: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise CanonicalStoreCorruptedError(
            f"Canonical store at {path} must be a JSON object"
        )
    return parsed


def _mutate_with_cas(
    workspace_root: Path,
    mutator: Callable[[dict[str, Any]], None],
    *,
    expected_revision: str | None,
    allow_overwrite: bool,
) -> str:
    """Lock + read-modify-write helper used by every canonical mutator.

    ``mutator`` receives the current store and mutates it in place. The
    helper handles revision comparison, stamping, atomic write, and
    returning the new revision.
    """
    lockfile = _lock_path(workspace_root)

    if not lock_supported():
        from ao_kernel._internal.shared.lock import LockPlatformNotSupported
        raise LockPlatformNotSupported(
            "canonical mutators require POSIX fcntl locking; "
            "Windows support is tracked in Tranche D (v3.1.0)."
        )

    with file_lock(lockfile):
        current = _load_store_locked(workspace_root)
        current_rev = store_revision(current)
        if not allow_overwrite and expected_revision is not None:
            if current_rev != expected_revision:
                raise CanonicalRevisionConflict(
                    f"Revision mismatch: expected {expected_revision}, "
                    f"store is at {current_rev}"
                )
        mutator(current)
        current["updated_at"] = _now_iso()
        write_json_atomic(_store_path(workspace_root), current)
        return store_revision(current)


def promote_decision(
    workspace_root: Path,
    *,
    key: str,
    value: Any,
    category: str = "general",
    source: str = "agent",
    confidence: float = 0.8,
    session_id: str = "",
    fresh_days: int = 30,
    review_days: int = 90,
    expire_days: int = 365,
    supersedes: str | None = None,
    provenance: dict[str, Any] | None = None,
    vector_store: Any | None = None,
    embedding_config: Any | None = None,
    expected_revision: str | None = None,
    allow_overwrite: bool = True,
) -> CanonicalDecision:
    """Promote an ephemeral decision to canonical store.

    If key already exists, it's updated (latest wins).

    When ``vector_store`` is provided, the promoted decision is also
    embedded and indexed for semantic retrieval. Write-path failures
    are silently logged (never block promotion).

    CAS parameters (CNS-20260414-010 iter-3 migration stage A):
        expected_revision: Opt-in revision guard. When supplied together
            with ``allow_overwrite=False``, a concurrent writer that
            moved the store past this revision will cause the call to
            raise :class:`CanonicalRevisionConflict`. ``None`` + the
            default ``allow_overwrite=True`` preserves the v2.x behavior.
        allow_overwrite: Default ``True`` for backward compatibility.
            v4.0.0 will flip this to ``False`` and require callers to
            opt in to overwriting stale revisions.
    """
    now = _now_iso()
    decision = CanonicalDecision(
        key=key,
        value=value,
        category=category,
        source=source,
        confidence=confidence,
        promoted_from=session_id,
        promoted_at=now,
        fresh_until=_future_iso(fresh_days),
        review_after=_future_iso(review_days),
        expires_at=_future_iso(expire_days),
        supersedes=supersedes,
        provenance=provenance or {},
    )
    target = "facts" if category == "fact" else "decisions"

    def _apply(store: dict[str, Any]) -> None:
        store.setdefault(target, {})[key] = asdict(decision)

    _mutate_with_cas(
        workspace_root,
        _apply,
        expected_revision=expected_revision,
        allow_overwrite=allow_overwrite,
    )

    try:
        from ao_kernel.telemetry import record_canonical_promote
        record_canonical_promote(category=category)
    except Exception:
        pass

    if vector_store is not None:
        try:
            from ao_kernel.context.semantic_indexer import index_decision
            index_decision(
                key=key,
                value=value,
                source=f"canonical:{category}",
                namespace=str(workspace_root),
                vector_store=vector_store,
                embedding_config=embedding_config,
                extra_metadata={"confidence": confidence, "session_id": session_id},
            )
        except Exception:  # noqa: BLE001 — write-path best-effort
            pass

    return decision


def query(
    workspace_root: Path,
    *,
    key_pattern: str = "*",
    category: str | None = None,
    include_expired: bool = False,
) -> list[dict[str, Any]]:
    """Query canonical decisions and/or facts.

    Args:
        key_pattern: glob pattern (e.g., "runtime.*", "architecture.*")
        category: filter by category (None = all)
        include_expired: include expired decisions

    Returns list of matching decisions/facts as dicts.
    """
    store = load_store(workspace_root)
    now = _now_iso()
    results: list[dict[str, Any]] = []

    for section in ("decisions", "facts"):
        items = store.get(section, {})
        for key, item in items.items():
            if not isinstance(item, dict):
                continue
            if not fnmatch(key, key_pattern):
                continue
            if category and item.get("category") != category:
                continue
            if not include_expired and item.get("expires_at", "") and item["expires_at"] < now:
                continue

            # Temporal lifecycle metadata
            item_copy = dict(item)
            fresh_until = item_copy.get("fresh_until", "")
            review_after = item_copy.get("review_after", "")
            item_copy["_is_fresh"] = not fresh_until or fresh_until >= now
            item_copy["_needs_review"] = bool(review_after and review_after < now)

            results.append(item_copy)

    # Sort by promoted_at descending (newest first)
    results.sort(key=lambda x: x.get("promoted_at", ""), reverse=True)
    return results


def promote_from_ephemeral(
    workspace_root: Path,
    ephemeral_decisions: list[dict[str, Any]],
    *,
    min_confidence: float = 0.7,
    session_id: str = "",
    auto_category: str = "general",
) -> list[CanonicalDecision]:
    """Batch promote ephemeral decisions above confidence threshold.

    Returns list of promoted CanonicalDecisions.
    """
    promoted: list[CanonicalDecision] = []
    for d in ephemeral_decisions:
        confidence = d.get("confidence", 0.5)
        if isinstance(confidence, (int, float)) and confidence >= min_confidence:
            cd = promote_decision(
                workspace_root,
                key=d.get("key", ""),
                value=d.get("value"),
                category=auto_category,
                source=d.get("source", "agent"),
                confidence=confidence,
                session_id=session_id,
                provenance={"evidence_id": d.get("evidence_id", "")},
            )
            promoted.append(cd)
    return promoted


__all__ = [
    "CanonicalDecision",
    "load_store",
    "save_store",
    "save_store_cas",
    "store_revision",
    "promote_decision",
    "promote_from_ephemeral",
    "query",
]
