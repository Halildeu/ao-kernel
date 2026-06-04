"""Value-based secret taint tracking for V5 Epic 2 E-2-5.

The primary invariant is simple: once a secret value is resolved, that exact
value must not appear in any serialized payload. Regex redaction is retained as
defense-in-depth for secret-shaped values that were not resolved through this
module.
"""

from __future__ import annotations

import copy
import hashlib
import re
import threading
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

Jsonish = dict[str, Any] | list[Any] | tuple[Any, ...] | str | int | float | Decimal | bool | None

_PROVIDER_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class SecretPattern:
    """A named defense-in-depth redaction pattern."""

    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SecretTaint:
    """One resolved in-memory secret value."""

    provider_id: str
    value: str


DEFAULT_SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    SecretPattern("openai_project_key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
    SecretPattern("generic_sk_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    SecretPattern("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    SecretPattern("slack_bot_token", re.compile(r"xoxb-[A-Za-z0-9-]{10,}")),
    SecretPattern("gitlab_pat", re.compile(r"glpat-[A-Za-z0-9_-]{20}")),
    SecretPattern("github_oauth", re.compile(r"gho_[A-Za-z0-9]{36}")),
    SecretPattern("github_pat_classic", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    SecretPattern("github_fine_grained_pat", re.compile(r"github_pat_[A-Za-z0-9_]{82}")),
    SecretPattern("github_server_token", re.compile(r"ghs_[A-Za-z0-9]{36}")),
    SecretPattern("github_user_token", re.compile(r"ghu_[A-Za-z0-9]{36}")),
    SecretPattern("jwt_prefix", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.")),
    SecretPattern(
        "teams_webhook_url",
        re.compile(r"https://[a-z0-9.-]+\.webhook\.office\.com/webhookb2/[A-Za-z0-9@/\-]+"),
    ),
)


def _provider_placeholder(provider_id: str) -> str:
    safe = _PROVIDER_SAFE.sub("_", provider_id).strip("._-")[:64] or "unknown"
    return f"[REDACTED:provider={safe}]"


def _pattern_placeholder(pattern: SecretPattern) -> str:
    return f"[REDACTED:pattern={pattern.name}]"


class SecretTaintSet:
    """In-memory set of resolved secret values.

    Instances are intentionally process-local. The class stores raw secret
    values so it can redact by value; callers must not serialize the instance.
    """

    def __init__(self, *, patterns: tuple[SecretPattern, ...] = DEFAULT_SECRET_PATTERNS) -> None:
        self._patterns = patterns
        self._taints: dict[tuple[str, str], SecretTaint] = {}
        self._lock = threading.RLock()

    def add(self, provider_id: str, value: str) -> None:
        """Register a resolved secret value.

        Empty or whitespace-only values are ignored: callers should raise their
        own resolution error for required missing secrets.
        """

        if not isinstance(value, str):
            raise TypeError("secret value must be a string")
        stripped = value.strip()
        if not stripped:
            return
        provider = str(provider_id).strip() or "unknown"
        with self._lock:
            self._taints[(provider, stripped)] = SecretTaint(provider, stripped)

    def remove_provider(self, provider_id: str) -> None:
        """Remove all taints for one provider after rotation/invalidation."""

        provider = str(provider_id).strip() or "unknown"
        with self._lock:
            for key in [key for key in self._taints if key[0] == provider]:
                del self._taints[key]

    def clear(self) -> None:
        """Remove every tracked value."""

        with self._lock:
            self._taints.clear()

    def contains(self, value: str) -> bool:
        """Return true iff any tracked secret appears in ``value``."""

        if not isinstance(value, str):
            return False
        with self._lock:
            return any(taint.value in value for taint in self._taints.values())

    def scan_and_redact(self, payload: Jsonish) -> Jsonish:
        """Return a deep-redacted copy of ``payload``.

        String values are redacted by resolved taint first, then by regex
        defense-in-depth. Numeric, boolean, and null values are returned
        unchanged so cost and counter fields cannot be accidentally rewritten.
        """

        return self._scan(copy.deepcopy(payload))

    def redact_text(self, text: str) -> str:
        """Redact one string using value-based taint plus regex fallback."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")
        redacted = text
        with self._lock:
            taints = sorted(self._taints.values(), key=lambda taint: len(taint.value), reverse=True)
        for taint in taints:
            redacted = redacted.replace(taint.value, _provider_placeholder(taint.provider_id))
        for pattern in self._patterns:
            redacted = pattern.pattern.sub(_pattern_placeholder(pattern), redacted)
        return redacted

    def _scan(self, payload: Jsonish) -> Jsonish:
        if isinstance(payload, str):
            return self.redact_text(payload)
        if isinstance(payload, dict):
            return {str(key): self._scan(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self._scan(value) for value in payload]
        if isinstance(payload, tuple):
            return tuple(self._scan(value) for value in payload)
        return payload

    def snapshot_metadata(self) -> tuple[Mapping[str, str], ...]:
        """Return non-secret metadata about tracked values for tests/audits."""

        with self._lock:
            return tuple(
                {
                    "provider_id": taint.provider_id,
                    "value_sha256": "sha256:" + hashlib.sha256(taint.value.encode()).hexdigest(),
                }
                for taint in self._taints.values()
            )


__all__ = [
    "DEFAULT_SECRET_PATTERNS",
    "Jsonish",
    "SecretPattern",
    "SecretTaint",
    "SecretTaintSet",
]
