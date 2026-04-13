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
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from ao_kernel._internal.shared.utils import write_json_atomic


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


def load_store(workspace_root: Path) -> dict[str, Any]:
    """Load canonical decision store. Returns empty store if not found."""
    path = _store_path(workspace_root)
    if not path.exists():
        return {"version": "v1", "decisions": {}, "facts": {}, "updated_at": _now_iso()}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": "v1", "decisions": {}, "facts": {}, "updated_at": _now_iso()}


def save_store(workspace_root: Path, store: dict[str, Any]) -> None:
    """Save canonical decision store atomically."""
    store["updated_at"] = _now_iso()
    write_json_atomic(_store_path(workspace_root), store)


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
) -> CanonicalDecision:
    """Promote an ephemeral decision to canonical store.

    If key already exists, it's updated (latest wins).
    """
    store = load_store(workspace_root)
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

    # Separate decisions from facts
    target = "facts" if category == "fact" else "decisions"
    store.setdefault(target, {})[key] = asdict(decision)

    save_store(workspace_root, store)
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
    "promote_decision",
    "promote_from_ephemeral",
    "query",
]
