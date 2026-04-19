"""Profile router — detect task type and configure context loading strategy.

3 profiles for v0.2.0:
    STARTUP: First session, workspace discovery — minimal context
    TASK_EXECUTION: Active development — full decisions + facts
    REVIEW: Code/plan review — standards + quality focus

Detection: keyword matching on first user message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProfileConfig:
    """Configuration for a context loading profile.

    v3.6 E2 adds ``max_consultations`` — per-profile cap on promoted
    consultations rendered in the ``## Consultations`` section
    (plan §3.E2 + Codex iter-1 revision #6 — SSOT on the profile,
    not hardcoded in the compiler).
    """

    profile_id: str
    description: str
    priority_prefixes: tuple[str, ...]  # key prefixes to prioritize
    max_decisions: int  # max decisions to inject
    max_tokens: int  # token budget for context preamble
    enable_semantic_search: bool = False  # opt-in semantic reranking (default OFF)
    max_consultations: int = 3  # v3.6 E2 — see per-profile overrides below


PROFILES: dict[str, ProfileConfig] = {
    "STARTUP": ProfileConfig(
        profile_id="STARTUP",
        description="First session, workspace discovery",
        priority_prefixes=("workspace.", "config.", "setup."),
        max_decisions=10,
        max_tokens=1000,
        max_consultations=3,
    ),
    "TASK_EXECUTION": ProfileConfig(
        profile_id="TASK_EXECUTION",
        description="Active development or task work",
        priority_prefixes=("runtime.", "decision.", "approved.", "tool.", "llm."),
        max_decisions=30,
        max_tokens=4000,
        max_consultations=3,
    ),
    "REVIEW": ProfileConfig(
        profile_id="REVIEW",
        description="Code or plan review",
        priority_prefixes=("review.", "standard.", "quality.", "policy.", "architecture."),
        max_decisions=20,
        max_tokens=2000,
        max_consultations=10,
    ),
    "EMERGENCY": ProfileConfig(
        profile_id="EMERGENCY",
        description="Incident response, urgent fix",
        priority_prefixes=("error.", "incident.", "alert.", "hotfix.", "rollback."),
        max_decisions=15,
        max_tokens=2000,
        max_consultations=0,  # lean context — see plan §3.E2 rationale
    ),
    "ASSESSMENT": ProfileConfig(
        profile_id="ASSESSMENT",
        description="System assessment, maturity evaluation",
        priority_prefixes=("assessment.", "maturity.", "metric.", "benchmark.", "score."),
        max_decisions=25,
        max_tokens=3000,
        max_consultations=3,
    ),
    "PLANNING": ProfileConfig(
        profile_id="PLANNING",
        description="Roadmap planning, sprint planning",
        priority_prefixes=("plan.", "roadmap.", "sprint.", "milestone.", "priority."),
        max_decisions=25,
        max_tokens=3000,
        max_consultations=10,
    ),
}

DEFAULT_PROFILE = "TASK_EXECUTION"

# Detection keywords per profile
_DETECTION_KEYWORDS: dict[str, list[str]] = {
    "STARTUP": ["init", "setup", "install", "configure", "bootstrap", "workspace", "getting started"],
    "REVIEW": ["review", "check", "audit", "inspect", "evaluate", "assess", "quality", "standard"],
    "EMERGENCY": ["incident", "emergency", "urgent", "hotfix", "rollback", "outage", "down", "broken", "critical"],
    "ASSESSMENT": ["assessment", "maturity", "benchmark", "evaluate", "score", "measure", "baseline"],
    "PLANNING": ["plan", "roadmap", "sprint", "milestone", "priority", "schedule", "backlog"],
    # TASK_EXECUTION is the default — no specific keywords needed
}


def detect_profile(messages: list[dict[str, Any]]) -> str:
    """Detect the most likely profile from conversation messages.

    Scans the first user message for keywords. Returns profile ID.
    Falls back to TASK_EXECUTION if no match.
    """
    if not messages:
        return DEFAULT_PROFILE

    # Find first user message
    user_text = ""
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_text = content.lower()
                break
            if isinstance(content, list):
                user_text = " ".join(c.get("text", "") for c in content if isinstance(c, dict)).lower()
                break

    if not user_text:
        return DEFAULT_PROFILE

    # Score each profile by keyword matches
    best_profile = DEFAULT_PROFILE
    best_score = 0

    for profile_id, keywords in _DETECTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in user_text)
        if score > best_score:
            best_score = score
            best_profile = profile_id

    return best_profile


def get_profile(profile_id: str | None = None) -> ProfileConfig:
    """Get profile configuration by ID. Falls back to default."""
    if profile_id and profile_id in PROFILES:
        return PROFILES[profile_id]
    return PROFILES[DEFAULT_PROFILE]
