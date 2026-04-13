"""Decision Extractor — extract structured decisions from LLM responses.

Strategies (in priority order):
1. JSON response: extract key-value pairs directly
2. Structured output: extract from known field patterns
3. Heuristic: detect "X is Y" and "decided to Z" patterns

Each extracted decision links back to its evidence (request_id).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Decision:
    """A structured decision extracted from LLM output."""

    key: str
    value: Any
    source: str = "agent"  # agent | user_chat
    confidence: float = 0.5
    evidence_id: str = ""
    extracted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "evidence_id": self.evidence_id,
            "extracted_at": self.extracted_at or _now_iso(),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_decisions(
    output_text: str,
    *,
    provider_id: str = "",
    request_id: str = "",
) -> list[Decision]:
    """Extract decisions from LLM output text.

    Tries JSON extraction first (highest confidence), then heuristic patterns.
    Returns empty list if no decisions found — never fails.
    """
    if not output_text or not output_text.strip():
        return []

    decisions: list[Decision] = []
    ts = _now_iso()

    # Strategy 1: JSON extraction (highest confidence)
    json_decisions = _extract_from_json(output_text, request_id=request_id, timestamp=ts)
    if json_decisions:
        decisions.extend(json_decisions)

    # Strategy 2: Heuristic patterns (lower confidence)
    if not decisions:
        heuristic_decisions = _extract_heuristic(output_text, request_id=request_id, timestamp=ts)
        decisions.extend(heuristic_decisions)

    return decisions


def _extract_from_json(text: str, *, request_id: str, timestamp: str) -> list[Decision]:
    """Extract decisions from JSON content in the output."""
    decisions = []
    stripped = text.strip()

    # Try parsing entire output as JSON
    obj = None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        # Try to find JSON block within text
        match = re.search(r"\{[^{}]*\}", stripped, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if not isinstance(obj, dict):
        return []

    # Extract flat key-value pairs as decisions
    for key, value in obj.items():
        if key.startswith("_") or key in ("type", "id", "timestamp"):
            continue
        if isinstance(value, (str, int, float, bool)):
            decisions.append(Decision(
                key=f"llm.{key}",
                value=value,
                source="agent",
                confidence=0.9,
                evidence_id=request_id,
                extracted_at=timestamp,
            ))
        elif isinstance(value, dict) and len(value) <= 5:
            # Nested dict with few keys — extract each
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, (str, int, float, bool)):
                    decisions.append(Decision(
                        key=f"llm.{key}.{sub_key}",
                        value=sub_val,
                        source="agent",
                        confidence=0.8,
                        evidence_id=request_id,
                        extracted_at=timestamp,
                    ))

    return decisions[:20]  # Cap at 20 decisions per response


def _extract_heuristic(text: str, *, request_id: str, timestamp: str) -> list[Decision]:
    """Extract decisions using text pattern matching.

    Patterns:
    - "X is Y" (assertion)
    - "decided to X" (action decision)
    - "recommendation: X" (recommendation)
    - "status: X" (status report)
    """
    decisions = []

    # Pattern: "key: value" or "key = value" lines
    kv_pattern = re.compile(
        r"^[\s\-\*]*(\w[\w\s]{2,30}):\s+(.{3,100})$",
        re.MULTILINE,
    )
    for match in kv_pattern.finditer(text):
        key = match.group(1).strip().lower().replace(" ", "_")
        value = match.group(2).strip().rstrip(".,;")
        if len(key) >= 3 and len(value) >= 3:
            decisions.append(Decision(
                key=f"llm.heuristic.{key}",
                value=value,
                source="agent",
                confidence=0.4,
                evidence_id=request_id,
                extracted_at=timestamp,
            ))

    # Pattern: "decided to X" or "decision: X"
    decision_pattern = re.compile(
        r"(?:decided?\s+to|decision:\s*)(.{5,100}?)(?:\.|$)",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in decision_pattern.finditer(text):
        value = match.group(1).strip()
        decisions.append(Decision(
            key="llm.decision",
            value=value,
            source="agent",
            confidence=0.5,
            evidence_id=request_id,
            extracted_at=timestamp,
        ))

    return decisions[:10]  # Cap heuristic extractions
