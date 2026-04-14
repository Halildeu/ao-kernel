"""Explicit, code-owned activation dispatch for extension entrypoints.

Per CNS-20260414-008 consensus (Codex option b): manifest discovery stays
declarative, but activation is an explicit handler registration — NO
``importlib`` magic, NO ``setuptools`` entry_points, NO manifest-driven
module imports. D7 is preserved.

First activated surface: ``kernel_api_actions`` — the same identifiers
that already live in ``policy_kernel_api_guardrails.v1.json`` (allowlist)
and ``kernel-api-request.schema.v1.json`` (enum). ``ops`` and other
surfaces can be added later without changing the dispatch model.

Contract:
    - Handler callables accept a single ``params`` dict and return a dict.
    - Registration records the owning ``extension_id`` so conflicts and
      activation blockers can be surfaced to operators.
    - ``resolve(action)`` returns ``None`` for unknown actions — callers
      treat that as "handler not activated" (fail-open) or raise (fail-
      closed) based on their own policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

ActionHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class RegisteredAction:
    """One (action, extension_id, handler) binding."""

    action: str
    extension_id: str
    handler: ActionHandler


class ActionRegistry:
    """Explicit registry of ``kernel_api_action -> handler`` bindings.

    Client-scoped. Multiple registrations of the same action are rejected
    unless ``replace=True`` is passed — avoids accidental shadowing when
    several extensions claim overlapping entrypoints.
    """

    def __init__(self) -> None:
        self._actions: dict[str, RegisteredAction] = {}

    def register(
        self,
        action: str,
        handler: ActionHandler,
        *,
        extension_id: str,
        replace: bool = False,
    ) -> None:
        existing = self._actions.get(action)
        if existing is not None and not replace:
            raise ValueError(
                f"action {action!r} already registered by "
                f"{existing.extension_id!r}; pass replace=True to override"
            )
        self._actions[action] = RegisteredAction(
            action=action,
            extension_id=extension_id,
            handler=handler,
        )

    def resolve(self, action: str) -> RegisteredAction | None:
        return self._actions.get(action)

    def list_actions(self) -> list[RegisteredAction]:
        return sorted(self._actions.values(), key=lambda a: a.action)

    def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Resolve + call the handler. Raises LookupError for unknown actions.

        Callers that prefer fail-open behavior should use ``resolve()`` and
        branch on ``None`` instead.
        """
        record = self._actions.get(action)
        if record is None:
            raise LookupError(f"no handler registered for action {action!r}")
        return record.handler(params)


__all__ = ["ActionHandler", "RegisteredAction", "ActionRegistry"]
