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

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


@dataclass
class ToolSpec:
    """Specification for a registered tool.

    v3.9 B2: `is_mutating` additive opt-in flag. Tools that mutate
    workspace/state should declare it explicitly; default False keeps
    pre-B2 behavior. Enforcement: `default_permission="read_only"` +
    `mutating_requires_confirmation=True` + `is_mutating=True` → DENY.
    """

    name: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    description: str = ""
    allowed: bool = True
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    is_mutating: bool = False  # v3.9 B2


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
    """Result of a tool dispatch.

    v3.9 B2: `reason_code` is machine-readable denial key; `reason` is
    the free-form human-readable message. MCP envelope uses
    `reason_code` for reliable policy branching.
    """

    status: str  # OK | DENIED | ERROR
    tool_name: str
    output: dict[str, Any] | None = None
    reason: str = ""
    reason_code: str = ""  # v3.9 B2 — machine-readable denial key
    round_number: int = 0


# v3.9 B2 — machine-readable denial reason codes.
# Pre-B2 (legacy) codes kept verbatim for backward compatibility with
# callers that already match on them.
REASON_POLICY_DISABLED = "POLICY_DISABLED"
REASON_TOOL_NOT_REGISTERED = "TOOL_NOT_REGISTERED"
REASON_TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
REASON_MAX_ROUNDS_EXCEEDED = "MAX_ROUNDS_EXCEEDED"
# v3.9 B2 new codes:
REASON_BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
REASON_NOT_IN_ALLOWLIST = "NOT_IN_ALLOWLIST"
REASON_MAX_CALLS_PER_REQUEST = "MAX_CALLS_PER_REQUEST_EXCEEDED"
REASON_CYCLE_DETECTED = "CYCLE_DETECTED"
REASON_MUTATING_REQUIRES_CONFIRMATION = "MUTATING_REQUIRES_CONFIRMATION"


def _fingerprint_params(params: dict[str, Any]) -> str:
    """Hashable fingerprint for cycle detection. JSON-native with repr fallback.

    Custom tool inputs may contain non-JSON-native values (e.g. dataclass
    instances, datetime). `default=repr` guarantees a stable string without
    raising. Sort keys so dict-order is irrelevant.
    """
    try:
        return json.dumps(params, sort_keys=True, default=repr)
    except Exception:
        # Last-resort: repr of the sorted items. Should never trigger
        # given `default=repr`, but keeps this helper fail-closed-safe.
        return repr(sorted(params.items(), key=lambda kv: kv[0]))


class ToolGateway:
    """Policy-gated tool dispatch gateway.

    Fail-closed design:
        - Tool not registered → DENIED
        - Tool not allowed → DENIED
        - Policy disabled → DENIED
        - Max rounds exceeded → DENIED
        - Max calls per request exceeded → DENIED (v3.9 B2)
        - Tool not in non-empty allowlist → DENIED (v3.9 B2)
        - Tool in blocklist → DENIED (v3.9 B2; overrides allowlist)
        - Cycle detected (same call repeated) → DENIED (v3.9 B2)
        - Mutating tool requires confirmation → DENIED (v3.9 B2)
        - Handler raises → ERROR (not silent allow)

    Allowlist semantic (v3.9 B2):
        - `allowed_tools=()` (empty) → allowlist disabled; all registered
          tools permitted modulo blocklist. Preserves pre-B2 behavior
          and matches `create_tool_gateway()` bundled-default reality.
        - `allowed_tools=("a","b")` (non-empty) → strict fail-closed;
          only listed tools are allowed.
        - `blocked_tools` always overrides `allowed_tools`.
    """

    def __init__(
        self,
        *,
        policy: ToolCallPolicy | None = None,
    ) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._policy = policy or ToolCallPolicy()
        self._call_count = 0
        # v3.9 B2 stateful counters/history
        self._request_call_count: int = 0
        # Bounded cycle history: only need a suffix of `cycle_max_identical_calls`
        # entries since cycle check is "last N are all the current key".
        self._recent_calls: deque[str] = deque(maxlen=max(self._policy.cycle_max_identical_calls, 1))

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
        is_mutating: bool = False,  # v3.9 B2 additive
    ) -> None:
        """Convenience method to register a tool handler."""
        self.register(
            ToolSpec(
                name=name,
                handler=handler,
                description=description,
                allowed=allowed,
                input_schema=input_schema or {},
                is_mutating=is_mutating,
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
                "is_mutating": spec.is_mutating,  # v3.9 B2
            }
            for spec in self._tools.values()
        ]

    def authorize(self, tool_name: str) -> tuple[bool, str]:
        """Static policy check — NO stateful/input-dependent branches.

        v3.9 B2 split: `authorize()` handles policy-static checks that only
        depend on tool identity + policy config:

            disabled, unregistered, spec.allowed, blocklist, allowlist,
            max_rounds, mutating-confirmation

        Stateful/input-dependent checks (`max_calls_per_request`,
        cycle detection) live in `dispatch()` because they require a
        live tool_input or mutate per-call counters.

        The second element of the returned tuple is the machine-readable
        `reason_code`. Kept as a string (not enum) for BC with existing
        callers that match on string literals.
        """
        if not self._policy.enabled:
            return False, REASON_POLICY_DISABLED

        if tool_name not in self._tools:
            if not self._policy.allow_unknown:
                return False, REASON_TOOL_NOT_REGISTERED

        spec = self._tools.get(tool_name)
        if spec and not spec.allowed:
            return False, REASON_TOOL_NOT_ALLOWED

        # Blocklist overrides allowlist (v3.9 B2).
        if tool_name in self._policy.blocked_tools:
            return False, REASON_BLOCKED_BY_POLICY

        # Allowlist: empty = permissive (matches create_tool_gateway()
        # bundled-default reality + governance._check_tool_calling).
        # Non-empty = strict fail-closed.
        if self._policy.allowed_tools and tool_name not in self._policy.allowed_tools:
            return False, REASON_NOT_IN_ALLOWLIST

        # Mutating-confirmation gate (v3.9 B2): a mutating tool under a
        # read_only default + confirmation-required policy cannot run in
        # this fire-and-forget gateway (no confirmation flow here).
        if (
            spec is not None
            and spec.is_mutating
            and self._policy.default_permission == "read_only"
            and self._policy.mutating_requires_confirmation
        ):
            return False, REASON_MUTATING_REQUIRES_CONFIRMATION

        if self._call_count >= self._policy.max_rounds:
            return False, REASON_MAX_ROUNDS_EXCEEDED

        return True, "AUTHORIZED"

    def dispatch(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> ToolCallResult:
        """Dispatch a tool call through the policy gate.

        Fail-closed: unauthorized or erroring tools return DENIED/ERROR.
        Runs `authorize()` first for static checks, then enforces
        stateful/input-dependent checks (v3.9 B2):
            - `max_calls_per_request` — per-request call cap
            - `cycle_detection` — suffix-based repeat-call detection

        Denied attempts are NOT recorded in cycle history (prevents a
        deny from feeding itself on repeated attempts).
        """
        # Static authorization check first.
        allowed, reason_code = self.authorize(tool_name)
        if not allowed:
            return ToolCallResult(
                status="DENIED",
                tool_name=tool_name,
                reason=reason_code,
                reason_code=reason_code,
            )

        spec = self._tools.get(tool_name)
        if spec is None:
            return ToolCallResult(
                status="DENIED",
                tool_name=tool_name,
                reason=REASON_TOOL_NOT_REGISTERED,
                reason_code=REASON_TOOL_NOT_REGISTERED,
            )

        # v3.9 B2: per-request call cap (stateful).
        if self._request_call_count >= self._policy.max_calls_per_request:
            return ToolCallResult(
                status="DENIED",
                tool_name=tool_name,
                reason=REASON_MAX_CALLS_PER_REQUEST,
                reason_code=REASON_MAX_CALLS_PER_REQUEST,
            )

        # v3.9 B2: cycle detection (stateful + input-dependent).
        # Suffix semantics: DENY iff the last N recent calls are ALL
        # identical to the current (tool_name, params) key, where
        # N = cycle_max_identical_calls. Deque is maxlen=N, so this is
        # just "deque is full AND every entry equals current key".
        fingerprint = f"{tool_name}|{_fingerprint_params(tool_input)}"
        if (
            self._policy.cycle_detection_enabled
            and self._policy.cycle_max_identical_calls >= 1
            and len(self._recent_calls) == self._policy.cycle_max_identical_calls
            and all(k == fingerprint for k in self._recent_calls)
        ):
            # Do NOT append — a denied attempt must not extend the cycle.
            return ToolCallResult(
                status="DENIED",
                tool_name=tool_name,
                reason=REASON_CYCLE_DETECTED,
                reason_code=REASON_CYCLE_DETECTED,
            )

        # Dispatch.
        self._call_count += 1
        self._request_call_count += 1
        self._recent_calls.append(fingerprint)
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
        """Reset all transient per-request gateway state.

        v3.9 B2: in addition to `_call_count`, clears
        `_request_call_count` and `_recent_calls` so the next request
        starts with a clean slate. Call this at the start of every new
        LLM request from a persistent gateway instance (e.g.
        `AoKernelClient`). MCP path creates a fresh gateway per
        `call_tool()` so this is implicit there.
        """
        self._call_count = 0
        self._request_call_count = 0
        self._recent_calls.clear()


__all__ = [
    "ToolGateway",
    "ToolSpec",
    "ToolCallPolicy",
    "ToolCallResult",
]
