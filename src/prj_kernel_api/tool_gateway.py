"""DEPRECATED: Legacy tool gateway — use ao_kernel.tool_gateway instead.

This file uses subprocess dispatch via src.ops.manage (not available in ao-kernel).
The new ao_kernel/tool_gateway.py uses callable handlers with policy-gated dispatch.
Will be removed in v2.0.0.
"""
# ruff: noqa

from __future__ import annotations

import warnings
warnings.warn(
    "src.prj_kernel_api.tool_gateway is deprecated. Use ao_kernel.tool_gateway instead.",
    DeprecationWarning,
    stacklevel=2,
)

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src.shared.logger import get_logger
from src.shared.utils import load_json

log = get_logger(__name__)


@dataclass(frozen=True)
class ToolPermission:
    """A registered tool with its permission level and dispatch target."""
    tool_name: str
    permission: str  # "read_only" | "mutating"
    ops_command: str
    input_schema: dict = field(default_factory=dict)
    description: str = ""


class ToolCallPolicy:
    """Enforces tool calling policy — max calls, allowed/blocked, cycles."""

    def __init__(self, policy: Dict[str, Any]) -> None:
        self._enabled = bool(policy.get("enabled", False))
        self._max_calls = int(policy.get("max_tool_calls_per_request", 5))
        self._max_rounds = int(policy.get("max_tool_rounds", 3))
        self._allowed = set(policy.get("allowed_tools", []))
        self._blocked = set(policy.get("blocked_tools", []))
        perms = policy.get("tool_permissions", {}) if isinstance(policy.get("tool_permissions"), dict) else {}
        self._default_permission = perms.get("default", "read_only")
        self._mutating_requires_confirmation = bool(perms.get("mutating_requires_confirmation", True))
        cycle = policy.get("cycle_detection", {}) if isinstance(policy.get("cycle_detection"), dict) else {}
        self._cycle_enabled = bool(cycle.get("enabled", True))
        self._max_identical = int(cycle.get("max_identical_calls", 2))
        self._fail_action = policy.get("fail_action", "block")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def max_rounds(self) -> int:
        return self._max_rounds

    def authorize_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        call_history: List[Dict[str, Any]],
    ) -> tuple[bool, str]:
        """Check if a tool call is authorized.

        Returns (allowed, reason).
        """
        if not self._enabled:
            return False, "tool_calling_disabled"

        # Blocked tools always rejected
        if tool_name in self._blocked:
            return False, f"tool_blocked:{tool_name}"

        # Allowed tools check (empty = none allowed, fail-closed)
        if self._allowed and tool_name not in self._allowed:
            return False, f"tool_not_allowed:{tool_name}"
        if not self._allowed:
            return False, "no_tools_allowed"

        # Max calls check
        call_count = sum(1 for c in call_history if c.get("name") == tool_name)
        if call_count >= self._max_calls:
            return False, f"max_calls_exceeded:{tool_name}:{call_count}/{self._max_calls}"

        # Cycle detection
        if self._cycle_enabled:
            input_key = json.dumps(tool_input, sort_keys=True, ensure_ascii=True)
            identical = sum(
                1 for c in call_history
                if c.get("name") == tool_name
                and json.dumps(c.get("input", {}), sort_keys=True, ensure_ascii=True) == input_key
            )
            if identical >= self._max_identical:
                return False, f"cycle_detected:{tool_name}:{identical}/{self._max_identical}"

        return True, "authorized"


class ToolGateway:
    """Typed allowlist dispatch gateway for tool calls."""

    def __init__(
        self,
        registry: List[ToolPermission],
        policy: ToolCallPolicy,
    ) -> None:
        self._registry = {t.tool_name: t for t in registry}
        self._policy = policy

    @property
    def policy(self) -> ToolCallPolicy:
        return self._policy

    def dispatch(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        *,
        workspace_root: str,
        request_id: str,
        call_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Authorize and dispatch a tool call.

        Returns: {status, tool_name, output, elapsed_ms, authorization, error}
        """
        import time

        # Authorization check
        allowed, reason = self._policy.authorize_call(tool_name, tool_input, call_history)
        if not allowed:
            log.warning("Tool call blocked: %s reason=%s request=%s", tool_name, reason, request_id)
            return {
                "status": "BLOCKED",
                "tool_name": tool_name,
                "output": None,
                "elapsed_ms": 0,
                "authorization": reason,
                "error": f"Tool call not authorized: {reason}",
            }

        # Registry lookup
        tool_def = self._registry.get(tool_name)
        if not tool_def:
            return {
                "status": "FAIL",
                "tool_name": tool_name,
                "output": None,
                "elapsed_ms": 0,
                "authorization": "authorized",
                "error": f"Tool not found in registry: {tool_name}",
            }

        # Mutating permission check
        if tool_def.permission == "mutating" and self._policy._mutating_requires_confirmation:
            return {
                "status": "CONFIRMATION_REQUIRED",
                "tool_name": tool_name,
                "output": None,
                "elapsed_ms": 0,
                "authorization": "mutating_requires_confirmation",
                "error": None,
            }

        # Dispatch to ops command
        start = time.monotonic()
        try:
            cmd = [
                sys.executable, "-m", "src.ops.manage",
                tool_def.ops_command,
                "--workspace-root", workspace_root,
            ]
            # Add tool input as JSON via stdin or args
            for key, value in tool_input.items():
                if key != "workspace_root":
                    cmd.extend([f"--{key}", str(value)])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(workspace_root).parent) if Path(workspace_root).parent.exists() else None,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            output_text = result.stdout.strip()
            try:
                output = json.loads(output_text) if output_text else {"raw": output_text}
            except json.JSONDecodeError:
                output = {"raw": output_text}

            if result.returncode != 0:
                return {
                    "status": "FAIL",
                    "tool_name": tool_name,
                    "output": output,
                    "elapsed_ms": elapsed_ms,
                    "authorization": "authorized",
                    "error": f"Command exited with code {result.returncode}: {result.stderr[:200]}",
                }

            return {
                "status": "OK",
                "tool_name": tool_name,
                "output": output,
                "elapsed_ms": elapsed_ms,
                "authorization": "authorized",
                "error": None,
            }
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "FAIL",
                "tool_name": tool_name,
                "output": None,
                "elapsed_ms": elapsed_ms,
                "authorization": "authorized",
                "error": "Tool dispatch timeout (30s)",
            }
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "status": "FAIL",
                "tool_name": tool_name,
                "output": None,
                "elapsed_ms": elapsed_ms,
                "authorization": "authorized",
                "error": str(exc)[:200],
            }


def load_tool_registry(workspace_root: str) -> List[ToolPermission]:
    """Load tool registry from policies/tool_registry.v1.json."""
    path = Path(workspace_root) / "policies" / "tool_registry.v1.json"
    if not path.exists():
        # Fallback to repo root
        path = Path("policies") / "tool_registry.v1.json"
    if not path.exists():
        return []
    data = load_json(path)
    tools = data.get("tools", []) if isinstance(data, dict) else []
    return [
        ToolPermission(
            tool_name=t["name"],
            permission=t.get("permission", "read_only"),
            ops_command=t["ops_command"],
            input_schema=t.get("parameters", {}),
            description=t.get("description", ""),
        )
        for t in tools
        if isinstance(t, dict) and "name" in t and "ops_command" in t
    ]


def load_tool_policy(workspace_root: str) -> ToolCallPolicy:
    """Load tool calling policy from policies/policy_tool_calling.v1.json."""
    path = Path(workspace_root) / "policies" / "policy_tool_calling.v1.json"
    if not path.exists():
        path = Path("policies") / "policy_tool_calling.v1.json"
    if not path.exists():
        return ToolCallPolicy({"enabled": False, "fail_action": "block"})
    data = load_json(path)
    return ToolCallPolicy(data if isinstance(data, dict) else {"enabled": False})
