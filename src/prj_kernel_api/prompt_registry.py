"""Prompt registry + experiment governance — version lineage + A/B/canary/shadow lanes.

Tracks prompt×model×experiment combinations. Records lineage for every LLM call.
Enables experiment governance: control/treatment/canary/shadow lanes with rollout%.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src.shared.logger import get_logger
from src.shared.utils import load_json, now_iso8601, write_json_atomic

log = get_logger(__name__)

# Experiment lanes
LANE_CONTROL = "control"
LANE_TREATMENT = "treatment"
LANE_CANARY = "canary"
LANE_SHADOW = "shadow"
VALID_LANES = frozenset({LANE_CONTROL, LANE_TREATMENT, LANE_CANARY, LANE_SHADOW})

# Experiment statuses
STATUS_ACTIVE = "active"
STATUS_PROMOTED = "promoted"
STATUS_ARCHIVED = "archived"
VALID_STATUSES = frozenset({STATUS_ACTIVE, STATUS_PROMOTED, STATUS_ARCHIVED})


@dataclass(frozen=True)
class PromptEntry:
    """A registered prompt with version and experiment metadata."""
    prompt_id: str
    version: str
    prompt_hash: str
    template: str
    model_compatibility: list[str]
    tool_schema_version: str | None
    guardrail_version: str
    input_schema: dict | None
    output_schema: dict | None
    eval_score: float | None
    last_tested_at: str | None
    experiment_id: str | None
    lane: str  # control | treatment | canary | shadow
    rollout_pct: int  # 0-100
    owner: str | None
    status: str  # active | promoted | archived


def _compute_prompt_hash(template: str) -> str:
    """Deterministic hash of prompt template for change detection."""
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:16]


def load_prompt_registry(workspace_root: str | Path) -> Dict[str, PromptEntry]:
    """Load prompt registry. Returns dict keyed by prompt_id.

    Searches workspace then repo root.
    """
    candidates = [
        Path(workspace_root) / "policies" / "prompt_registry.v1.json",
        Path("policies") / "prompt_registry.v1.json",
    ]
    for path in candidates:
        if path.exists():
            data = load_json(path)
            break
    else:
        return {}

    if not isinstance(data, dict):
        return {}

    prompts = data.get("prompts", [])
    registry: dict[str, PromptEntry] = {}
    for p in prompts:
        if not isinstance(p, dict) or "prompt_id" not in p:
            continue
        exp = p.get("experiment", {}) if isinstance(p.get("experiment"), dict) else {}
        entry = PromptEntry(
            prompt_id=p["prompt_id"],
            version=p.get("version", "0.0.0"),
            prompt_hash=p.get("prompt_hash", _compute_prompt_hash(p.get("template", ""))),
            template=p.get("template", ""),
            model_compatibility=p.get("model_compatibility", []),
            tool_schema_version=p.get("tool_schema_version"),
            guardrail_version=p.get("guardrail_version", "v1"),
            input_schema=p.get("input_schema"),
            output_schema=p.get("output_schema"),
            eval_score=p.get("eval_score"),
            last_tested_at=p.get("last_tested_at"),
            experiment_id=exp.get("experiment_id"),
            lane=exp.get("lane", LANE_CONTROL),
            rollout_pct=int(exp.get("rollout_pct", 100)),
            owner=exp.get("owner"),
            status=exp.get("status", STATUS_ACTIVE),
        )
        registry[entry.prompt_id] = entry
    return registry


def resolve_prompt(
    prompt_id: str,
    *,
    provider_id: str,
    model: str,
    registry: Dict[str, PromptEntry],
) -> PromptEntry | None:
    """Resolve a prompt by ID, checking model compatibility.

    Returns None if prompt not found or model not compatible.
    """
    entry = registry.get(prompt_id)
    if entry is None:
        return None

    # Check status
    if entry.status == STATUS_ARCHIVED:
        return None

    # Check model compatibility (wildcard pattern matching)
    if entry.model_compatibility:
        compatible = False
        for pattern in entry.model_compatibility:
            if pattern == "*":
                compatible = True
                break
            if pattern.endswith("*") and model.startswith(pattern[:-1]):
                compatible = True
                break
            if model == pattern:
                compatible = True
                break
        if not compatible:
            return None

    return entry


def select_experiment_lane(
    prompts: List[PromptEntry],
) -> PromptEntry | None:
    """Select which prompt variant to use based on experiment lanes and rollout%.

    Control lane always available. Treatment/canary/shadow selected by rollout%.
    """
    if not prompts:
        return None

    # Filter active prompts
    active = [p for p in prompts if p.status == STATUS_ACTIVE]
    if not active:
        return None

    # Find control (always the fallback)
    control = next((p for p in active if p.lane == LANE_CONTROL), None)

    # Find treatment/canary/shadow candidates
    experiments = [p for p in active if p.lane != LANE_CONTROL and p.rollout_pct > 0]

    if not experiments:
        return control

    # Roll dice for experiment selection
    roll = random.randint(1, 100)
    cumulative = 0
    for exp in sorted(experiments, key=lambda e: e.lane):
        cumulative += exp.rollout_pct
        if roll <= cumulative:
            return exp

    return control


def record_prompt_lineage(
    *,
    workspace_root: str | Path,
    prompt_id: str,
    prompt_version: str,
    prompt_hash: str,
    model: str,
    provider_id: str,
    experiment_id: str | None = None,
    lane: str = LANE_CONTROL,
    eval_score: float | None = None,
    run_id: str = "",
) -> None:
    """Append prompt lineage record to JSONL evidence file."""
    ws = Path(workspace_root).resolve()
    lineage_dir = ws / ".cache" / "index"
    lineage_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = lineage_dir / "prompt_lineage.v1.jsonl"

    entry = {
        "timestamp": now_iso8601(),
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash,
        "model": model,
        "provider_id": provider_id,
        "experiment_id": experiment_id,
        "lane": lane,
        "eval_score": eval_score,
        "run_id": run_id,
    }

    try:
        with open(lineage_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.warning("Failed to write prompt lineage: %s", exc)
