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
from typing import Any, Callable, Literal


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
    """Policy controlling tool dispatch behavior.

    v3.9 B1: contract absorb for dormant fields in
    `policy_tool_calling.v1.json`. Parser-only change — runtime
    enforcement for the absorbed fields lands in B2 (ToolGateway.dispatch).

    Mutable by design: call sites (e.g. `create_tool_gateway()` in
    `mcp_server.py`) mutate `enabled` after parse. A frozen dataclass
    would break that contract; see CNS v3.9-B1 iter-1 BLOCKER.
    """

    enabled: bool = True
    max_rounds: int = 10
    allow_unknown: bool = False  # fail-closed: unknown tools rejected
    # --- v3.9 B1 absorbed fields (parser-only; enforcement in B2) ---
    max_calls_per_request: int = 5
    allowed_tools: tuple[str, ...] = ()
    blocked_tools: tuple[str, ...] = ()
    default_permission: Literal["read_only", "mutating"] = "read_only"
    mutating_requires_confirmation: bool = True
    cycle_detection_enabled: bool = True
    cycle_max_identical_calls: int = 2

    @classmethod
    def from_dict(cls, policy: dict[str, Any]) -> ToolCallPolicy:
        """Parse policy dict into ToolCallPolicy. Raises ValueError on invalid input.

        Absorbs v3.9 B1 dormant fields from `policy_tool_calling.v1.json`.
        Normalization is intentionally minimal: list→tuple only, no dedupe,
        no sort, no case-folding. Semantic interpretation (precedence,
        empty-allowlist meaning, etc.) is B2's responsibility.
        """
        # Existing fields (unchanged behavior)
        enabled = policy.get("enabled", True)
        max_rounds = int(policy.get("max_tool_rounds", 10))
        allow_unknown = policy.get("allow_unknown", False)

        # max_calls_per_request: positive int
        raw_max_calls = policy.get("max_tool_calls_per_request", 5)
        if not isinstance(raw_max_calls, int) or isinstance(raw_max_calls, bool):
            raise ValueError(f"max_tool_calls_per_request must be int, got {type(raw_max_calls).__name__}")
        if raw_max_calls < 1:
            raise ValueError(f"max_tool_calls_per_request must be >= 1, got {raw_max_calls}")

        # allowed_tools / blocked_tools: list[str] → tuple[str, ...]
        allowed_tools_raw = policy.get("allowed_tools", [])
        if not isinstance(allowed_tools_raw, (list, tuple)):
            raise ValueError(f"allowed_tools must be list, got {type(allowed_tools_raw).__name__}")
        for item in allowed_tools_raw:
            if not isinstance(item, str):
                raise ValueError(f"allowed_tools entries must be str, got {type(item).__name__}")
        allowed_tools = tuple(allowed_tools_raw)

        blocked_tools_raw = policy.get("blocked_tools", [])
        if not isinstance(blocked_tools_raw, (list, tuple)):
            raise ValueError(f"blocked_tools must be list, got {type(blocked_tools_raw).__name__}")
        for item in blocked_tools_raw:
            if not isinstance(item, str):
                raise ValueError(f"blocked_tools entries must be str, got {type(item).__name__}")
        blocked_tools = tuple(blocked_tools_raw)

        # tool_permissions nested object
        perms = policy.get("tool_permissions", {})
        if not isinstance(perms, dict):
            raise ValueError(f"tool_permissions must be object, got {type(perms).__name__}")
        default_permission = perms.get("default", "read_only")
        if default_permission not in ("read_only", "mutating"):
            raise ValueError(f"tool_permissions.default must be 'read_only' or 'mutating', got {default_permission!r}")
        # Strict bool — no silent coercion of "false", 0, [], etc.
        raw_mutating_req = perms.get("mutating_requires_confirmation", True)
        if not isinstance(raw_mutating_req, bool):
            raise ValueError(
                f"tool_permissions.mutating_requires_confirmation must be bool, got {type(raw_mutating_req).__name__}"
            )
        mutating_requires_confirmation = raw_mutating_req

        # cycle_detection nested object
        cycle = policy.get("cycle_detection", {})
        if not isinstance(cycle, dict):
            raise ValueError(f"cycle_detection must be object, got {type(cycle).__name__}")
        # Strict bool — no silent coercion.
        raw_cycle_enabled = cycle.get("enabled", True)
        if not isinstance(raw_cycle_enabled, bool):
            raise ValueError(f"cycle_detection.enabled must be bool, got {type(raw_cycle_enabled).__name__}")
        cycle_detection_enabled = raw_cycle_enabled
        raw_cycle_max = cycle.get("max_identical_calls", 2)
        if not isinstance(raw_cycle_max, int) or isinstance(raw_cycle_max, bool):
            raise ValueError(f"cycle_detection.max_identical_calls must be int, got {type(raw_cycle_max).__name__}")
        if raw_cycle_max < 1:
            raise ValueError(f"cycle_detection.max_identical_calls must be >= 1, got {raw_cycle_max}")

        return cls(
            enabled=enabled,
            max_rounds=max_rounds,
            allow_unknown=allow_unknown,
            max_calls_per_request=raw_max_calls,
            allowed_tools=allowed_tools,
            blocked_tools=blocked_tools,
            default_permission=default_permission,
            mutating_requires_confirmation=mutating_requires_confirmation,
            cycle_detection_enabled=cycle_detection_enabled,
            cycle_max_identical_calls=raw_cycle_max,
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
        self.register(
            ToolSpec(
                name=name,
                handler=handler,
                description=description,
                allowed=allowed,
                input_schema=input_schema or {},
            )
        )

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
