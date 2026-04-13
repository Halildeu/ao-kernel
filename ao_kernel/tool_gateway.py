"""ao_kernel.tool_gateway — Policy-gated tool dispatch for governed runtime.

Rewritten from src/prj_kernel_api/tool_gateway.py. Removes subprocess/ops.manage
dependency. Uses callable handlers instead.

MCP integration: call_tool → ToolGateway.authorize → handler → envelope → telemetry

Design:
    - Fail-closed: unknown tool → REJECT, unauthorized tool → REJECT
    - Allowlist-based: only registered tools can be dispatched
    - Round-limited: prevents infinite tool call loops
    - Evidence: every dispatch decision is recorded
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    """Specification for a registered tool."""

    name: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    description: str = ""
    allowed: bool = True
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallPolicy:
    """Policy controlling tool dispatch behavior."""

    enabled: bool = True
    max_rounds: int = 10
    allow_unknown: bool = False  # fail-closed: unknown tools rejected

    @classmethod
    def from_dict(cls, policy: dict[str, Any]) -> ToolCallPolicy:
        return cls(
            enabled=policy.get("enabled", True),
            max_rounds=int(policy.get("max_tool_rounds", 10)),
            allow_unknown=policy.get("allow_unknown", False),
        )


@dataclass
class ToolCallResult:
    """Result of a tool dispatch."""

    status: str  # OK | DENIED | ERROR
    tool_name: str
    output: dict[str, Any] | None = None
    reason: str = ""
    round_number: int = 0


class ToolGateway:
    """Policy-gated tool dispatch gateway.

    Fail-closed design:
        - Tool not registered → DENIED
        - Tool not allowed → DENIED
        - Policy disabled → DENIED
        - Max rounds exceeded → DENIED
        - Handler raises → ERROR (not silent allow)
    """

    def __init__(
        self,
        *,
        policy: ToolCallPolicy | None = None,
    ) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._policy = policy or ToolCallPolicy()
        self._call_count = 0

    @property
    def policy(self) -> ToolCallPolicy:
        return self._policy

    def register(self, spec: ToolSpec) -> None:
        """Register a tool. Overwrites if name exists."""
        self._tools[spec.name] = spec

    def register_handler(
        self,
        name: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        description: str = "",
        allowed: bool = True,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        """Convenience method to register a tool handler."""
        self.register(ToolSpec(
            name=name,
            handler=handler,
            description=description,
            allowed=allowed,
            input_schema=input_schema or {},
        ))

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "allowed": spec.allowed,
                "input_schema": spec.input_schema,
            }
            for spec in self._tools.values()
        ]

    def authorize(self, tool_name: str) -> tuple[bool, str]:
        """Check if a tool call is authorized. Returns (allowed, reason)."""
        if not self._policy.enabled:
            return False, "POLICY_DISABLED"

        if tool_name not in self._tools:
            if not self._policy.allow_unknown:
                return False, "TOOL_NOT_REGISTERED"

        spec = self._tools.get(tool_name)
        if spec and not spec.allowed:
            return False, "TOOL_NOT_ALLOWED"

        if self._call_count >= self._policy.max_rounds:
            return False, "MAX_ROUNDS_EXCEEDED"

        return True, "AUTHORIZED"

    def dispatch(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> ToolCallResult:
        """Dispatch a tool call through the policy gate.

        Fail-closed: unauthorized or erroring tools return DENIED/ERROR.
        """
        # Authorization check
        allowed, reason = self.authorize(tool_name)
        if not allowed:
            return ToolCallResult(
                status="DENIED",
                tool_name=tool_name,
                reason=reason,
            )

        spec = self._tools.get(tool_name)
        if spec is None:
            return ToolCallResult(
                status="DENIED",
                tool_name=tool_name,
                reason="TOOL_NOT_REGISTERED",
            )

        # Dispatch
        self._call_count += 1
        try:
            output = spec.handler(tool_input)
            return ToolCallResult(
                status="OK",
                tool_name=tool_name,
                output=output,
                round_number=self._call_count,
            )
        except Exception as exc:
            return ToolCallResult(
                status="ERROR",
                tool_name=tool_name,
                reason=f"Handler error: {str(exc)[:200]}",
                round_number=self._call_count,
            )

    def reset_rounds(self) -> None:
        """Reset round counter (e.g., between requests)."""
        self._call_count = 0


__all__ = [
    "ToolGateway",
    "ToolSpec",
    "ToolCallPolicy",
    "ToolCallResult",
]
