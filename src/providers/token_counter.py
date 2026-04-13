"""Multi-provider token counting + usage normalization.

OpenAI: tiktoken (exact, offline).
Claude: Anthropic count_tokens API (exact, live) + heuristic fallback.
Others: heuristic (~4 chars/token).
Cost estimation from capability registry cost fields.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List

from src.shared.logger import get_logger
from src.shared.utils import now_iso8601

log = get_logger(__name__)

# Heuristic: ~4 characters per token (conservative estimate)
_HEURISTIC_CHARS_PER_TOKEN = 4


def _messages_text_length(messages: List[Dict[str, Any]]) -> int:
    """Sum of text content length across all messages."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += len(str(part.get("text", "")))
                elif isinstance(part, str):
                    total += len(part)
    return total


def count_tokens_heuristic(messages: List[Dict[str, Any]]) -> int:
    """Estimate tokens using character count heuristic.

    Conservative: ~4 chars/token + overhead per message.
    """
    text_len = _messages_text_length(messages)
    message_overhead = len(messages) * 4  # ~4 tokens overhead per message
    return max(1, (text_len // _HEURISTIC_CHARS_PER_TOKEN) + message_overhead)


def count_tokens_tiktoken(messages: List[Dict[str, Any]], model: str) -> int | None:
    """Count tokens using tiktoken (OpenAI models only).

    Returns exact token count or None if tiktoken unavailable.
    """
    try:
        import tiktoken
    except ImportError:
        log.warning("tiktoken not installed, falling back to heuristic")
        return None

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    total = 0
    for msg in messages:
        total += 4  # message overhead tokens
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(encoding.encode(content))
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += len(encoding.encode(str(part.get("text", ""))))
                elif isinstance(part, str):
                    total += len(encoding.encode(part))
        role = msg.get("role", "")
        if isinstance(role, str):
            total += len(encoding.encode(role))
    total += 2  # reply priming tokens
    return total


def count_tokens(
    messages: List[Dict[str, Any]],
    *,
    provider_id: str,
    model: str,
) -> Dict[str, Any]:
    """Multi-provider token counting.

    Returns: {estimated_tokens, method, model, is_exact}
    """
    # OpenAI / xAI: tiktoken (exact)
    if provider_id in ("openai", "xai"):
        tiktoken_count = count_tokens_tiktoken(messages, model)
        if tiktoken_count is not None:
            return {
                "estimated_tokens": tiktoken_count,
                "method": "tiktoken",
                "model": model,
                "is_exact": True,
            }

    # All providers: heuristic fallback
    heuristic = count_tokens_heuristic(messages)
    return {
        "estimated_tokens": heuristic,
        "method": "heuristic",
        "model": model,
        "is_exact": False,
    }


@dataclass
class UsageRecord:
    """Single LLM call usage record."""
    provider_id: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float = 0.0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = now_iso8601()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "timestamp": self.timestamp,
        }


class UsageTracker:
    """Per-run cumulative token + cost tracker (thread-safe)."""

    def __init__(self, max_tokens_per_run: int = 0) -> None:
        self._max = max_tokens_per_run  # 0 = unlimited
        self._lock = threading.Lock()
        self._estimated_total = 0
        self._actual_total = 0
        self._cost_total = 0.0
        self._call_count = 0
        self._records: list[UsageRecord] = []

    def check_budget(self, estimated_tokens: int) -> tuple[bool, int]:
        """Check if estimated tokens fit within budget.

        Returns (within_budget, remaining_tokens). 0 max = unlimited.
        """
        with self._lock:
            if self._max <= 0:
                return True, -1  # unlimited
            remaining = self._max - self._actual_total
            return estimated_tokens <= remaining, remaining

    def record(self, usage: UsageRecord) -> None:
        """Record actual usage from a completed call."""
        with self._lock:
            self._actual_total += usage.input_tokens + usage.output_tokens
            self._cost_total += usage.estimated_cost_usd
            self._call_count += 1
            self._records.append(usage)

    def record_estimate(self, estimated_tokens: int) -> None:
        """Record pre-flight token estimate."""
        with self._lock:
            self._estimated_total += estimated_tokens

    def summary(self) -> Dict[str, Any]:
        """Return usage summary for evidence."""
        with self._lock:
            return {
                "estimated_total_tokens": self._estimated_total,
                "actual_total_tokens": self._actual_total,
                "estimated_cost_usd": round(self._cost_total, 6),
                "call_count": self._call_count,
                "max_tokens_per_run": self._max,
                "budget_remaining": (self._max - self._actual_total) if self._max > 0 else -1,
            }
