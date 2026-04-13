"""Memory tier enforcement — hot/warm/cold classification and budget limits.

Tiers (from policy_context_memory_tiers.v1.json):
    HOT:  always_load, max 30 rules — most recent, highest confidence
    WARM: load_on_match, max 50 rules — relevant to current task
    COLD: load_on_demand, archive after 30 sessions — historical

Enforcement: context compiler respects tier budgets.
Classification: based on recency + frequency + confidence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# Default tier configuration (from bundled policy)
DEFAULT_TIERS = {
    "hot": {"max_rules": 30, "min_confidence": 0.7},
    "warm": {"max_rules": 50, "min_confidence": 0.4},
    "cold": {"max_rules": 100, "min_confidence": 0.0},
}


def classify_tier(
    decision: dict[str, Any],
    *,
    now: str | None = None,
) -> str:
    """Classify a decision into hot/warm/cold tier.

    Classification rules:
    - HOT: confidence >= 0.7 AND age < 7 days
    - WARM: confidence >= 0.4 OR age < 30 days
    - COLD: everything else
    """
    confidence = decision.get("confidence", 0.5)
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            confidence = 0.5

    age_days = _age_days(decision.get("created_at", decision.get("promoted_at", "")), now)

    if confidence >= 0.7 and age_days < 7:
        return "hot"
    if confidence >= 0.4 or age_days < 30:
        return "warm"
    return "cold"


def enforce_tier_budgets(
    decisions: list[dict[str, Any]],
    *,
    tier_config: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Classify decisions into tiers and enforce max budget per tier.

    Returns {hot: [...], warm: [...], cold: [...]} with each tier
    capped at max_rules. Excess decisions are demoted to next tier.
    """
    config = tier_config or DEFAULT_TIERS
    tiers: dict[str, list[dict[str, Any]]] = {"hot": [], "warm": [], "cold": []}

    for d in decisions:
        tier = classify_tier(d)
        tiers[tier].append(d)

    # Enforce budgets — overflow demotes to next tier
    hot_max = config.get("hot", {}).get("max_rules", 30)
    warm_max = config.get("warm", {}).get("max_rules", 50)

    if len(tiers["hot"]) > hot_max:
        # Sort by confidence desc, demote lowest
        tiers["hot"].sort(key=lambda d: d.get("confidence", 0), reverse=True)
        overflow = tiers["hot"][hot_max:]
        tiers["hot"] = tiers["hot"][:hot_max]
        tiers["warm"].extend(overflow)

    if len(tiers["warm"]) > warm_max:
        tiers["warm"].sort(key=lambda d: d.get("confidence", 0), reverse=True)
        overflow = tiers["warm"][warm_max:]
        tiers["warm"] = tiers["warm"][:warm_max]
        tiers["cold"].extend(overflow)

    return tiers


def load_tier_policy() -> dict[str, Any]:
    """Load tier policy from bundled defaults."""
    try:
        from ao_kernel.config import load_default
        return load_default("policies", "policy_context_memory_tiers.v1.json")
    except Exception:
        return {"tiers": DEFAULT_TIERS}


def _age_days(timestamp: str, now: str | None = None) -> float:
    """Calculate age in days from ISO timestamp."""
    if not timestamp:
        return 999.0
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        return (now_dt - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        return 999.0


__all__ = [
    "classify_tier",
    "enforce_tier_budgets",
    "load_tier_policy",
    "DEFAULT_TIERS",
]
