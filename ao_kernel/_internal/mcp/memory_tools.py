"""MCP memory tool helpers (ao_memory_read + ao_memory_write).

Private sub-module of :mod:`ao_kernel.mcp_server`. Not part of the
public API.

This module hosts the param-aware workspace resolver, rate-limit
registry, validated policy loader, and handler bodies for the
memory MCP tools. Placing them here keeps ``mcp_server.py`` under
the 800-LOC budget documented in CLAUDE.md §12 while isolating the
strict resolver scope recommended by CNS-20260414-011 iter-3 W1 —
the strict param-aware resolver must NOT be applied to the existing
governance tools, only to memory read/write and their evidence /
implicit-promotion hooks.

Exposed symbols (imported by :mod:`ao_kernel.mcp_server`)::

    _resolve_workspace_for_call   param-aware workspace resolver
    _IMPLICIT_PROMOTE_SKIP        implicit-promotion denylist
    _memory_rate_limiter_for      per-(workspace, op) token bucket
    _memory_rate_limit_reset      test-only registry reset
    _load_memory_policy_validated schema-validated policy loader
    handle_memory_read            ao_memory_read tool handler
"""

from __future__ import annotations

import fnmatch as _fn
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ao_kernel._internal.prj_kernel_api.rate_limiter import TokenBucketRateLimiter


# ── Module-level state ──────────────────────────────────────────────

# Tools whose MCP envelopes must NOT be fed into the implicit
# canonical-promotion path run by ``mcp_server.call_tool``. A
# read-only tool that promotes its own envelope metadata would
# generate self-referential noise in the canonical store
# (CNS-20260414-011 iter-1 B2).
_IMPLICIT_PROMOTE_SKIP: set[str] = {"ao_memory_read"}

_memory_rate_limiters: dict[tuple[str, str], TokenBucketRateLimiter] = {}
_memory_rl_lock = threading.Lock()


# ── Param-aware workspace resolver ──────────────────────────────────

def _resolve_workspace_for_call(
    params: dict[str, Any] | None,
    *,
    fallback: Callable[[], Path | None] | None = None,
) -> Path | None:
    """Resolve the workspace for an MCP memory tool call.

    Fallback policy (CNS-20260414-011 iter-2 B1 / iter-3 accepted):
    the ``fallback`` callable is consulted **only** when the
    ``workspace_root`` key is absent from ``params``. If the key is
    present but the value is malformed (wrong type, empty, not a
    directory, or missing ``.ao/``) we return ``None`` so the
    handler can emit a deny envelope — falling back to CWD in that
    case would silently redirect evidence and promotions to the
    wrong workspace.

    Scope (iter-3 W1): only memory tool paths and their evidence /
    implicit-promotion hooks. Do **not** apply this resolver
    uniformly to the existing governance tools.
    """
    if not isinstance(params, dict):
        return fallback() if fallback else None
    if "workspace_root" not in params:
        return fallback() if fallback else None
    raw = params["workspace_root"]
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        candidate = Path(raw).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if candidate.name == ".ao":
        candidate = candidate.parent
    if not candidate.is_dir() or not (candidate / ".ao").is_dir():
        return None
    return candidate


# ── Rate limit helpers ──────────────────────────────────────────────

def _memory_rate_limiter_for(
    ws: Path,
    op: str,
    *,
    rpm: int,
) -> TokenBucketRateLimiter:
    """Return the token bucket for ``(workspace, operation)``.

    A per-workspace bucket prevents cross-workspace contamination
    (CNS-20260414-011 iter-1 W1). We reuse the provider-grade
    :class:`TokenBucketRateLimiter` implementation but keep a
    separate registry so that :func:`reset_all` from the provider
    module cannot affect memory state.
    """
    key = (str(ws), op)
    with _memory_rl_lock:
        limiter = _memory_rate_limiters.get(key)
        if limiter is None:
            limiter = TokenBucketRateLimiter(rps=rpm / 60.0)
            _memory_rate_limiters[key] = limiter
        return limiter


def _memory_rate_limit_reset() -> None:
    """Clear the memory rate-limiter registry. Test-only helper."""
    with _memory_rl_lock:
        _memory_rate_limiters.clear()


# ── Validated policy loader ─────────────────────────────────────────

def _load_memory_policy_validated(ws: Path | None) -> dict[str, Any]:
    """Load ``policy_mcp_memory.v1.json`` with schema validation.

    Applies the project-root → ``.ao/`` bridge (CNS-20260414-011
    accepted) so that :func:`load_with_override` sees the expected
    override directory layout.

    Raises on missing/corrupt schema or policy to let the handler
    produce a fail-closed deny envelope.
    """
    import jsonschema

    from ao_kernel.config import load_default, load_with_override

    policy_workspace = ws / ".ao" if (ws is not None and (ws / ".ao").is_dir()) else ws
    policy = load_with_override(
        "policies",
        "policy_mcp_memory.v1.json",
        workspace=policy_workspace,
    )
    schema = load_default("schemas", "policy-mcp-memory.schema.v1.json")
    jsonschema.validate(policy, schema)
    return policy


# ── Envelope helpers ────────────────────────────────────────────────

_API_VERSION = "0.1.0"


def _deny(tool: str, reason: str, *, error: str | None = None) -> dict[str, Any]:
    return {
        "api_version": _API_VERSION,
        "tool": tool,
        "allowed": False,
        "decision": "deny",
        "reason_codes": [reason],
        "data": None,
        "error": error,
    }


def _error(tool: str, message: str) -> dict[str, Any]:
    return {
        "api_version": _API_VERSION,
        "tool": tool,
        "allowed": True,
        "decision": "error",
        "reason_codes": ["runtime_failure"],
        "data": None,
        "error": message,
    }


# ── Handler: ao_memory_read ─────────────────────────────────────────

def handle_memory_read(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for the ``ao_memory_read`` MCP tool.

    Policy-gated, param-aware, rate-limited, read-only query over
    canonical decisions and workspace facts.
    """
    # Lazy imports keep the module free of a mcp_server import cycle
    # and avoid paying the canonical-store/agent-coordination cost
    # at import time.
    from ao_kernel.context.agent_coordination import query_memory
    from ao_kernel.mcp_server import _find_workspace_root

    tool = "ao_memory_read"

    ws = _resolve_workspace_for_call(params, fallback=_find_workspace_root)
    if ws is None:
        return _deny(tool, "workspace_not_found")

    try:
        policy = _load_memory_policy_validated(ws)
    except Exception as exc:  # noqa: BLE001 — fail-closed on any load/validate error
        return _deny(tool, "policy_load_error", error=str(exc))

    read_cfg = policy.get("read") if isinstance(policy, dict) else None
    if not isinstance(read_cfg, dict) or not bool(read_cfg.get("enabled", False)):
        return _deny(tool, "read_disabled_by_policy")

    user_pattern = params.get("pattern", "*") if isinstance(params, dict) else "*"
    if not isinstance(user_pattern, str) or not user_pattern.strip():
        return _deny(tool, "invalid_pattern")

    allowed_patterns = read_cfg.get("allowed_patterns", ["*"])
    if not isinstance(allowed_patterns, list) or not allowed_patterns:
        return _deny(tool, "pattern_not_allowed")
    if not any(
        isinstance(p, str) and _fn.fnmatchcase(user_pattern, p)
        for p in allowed_patterns
    ):
        return _deny(tool, "pattern_not_allowed")

    rate_cfg = policy.get("rate_limit", {}) if isinstance(policy, dict) else {}
    rpm = int(rate_cfg.get("reads_per_minute", 60)) if isinstance(rate_cfg, dict) else 60
    if rpm < 1:
        rpm = 1
    limiter = _memory_rate_limiter_for(ws, "read", rpm=rpm)
    if not limiter.try_acquire():
        return _deny(tool, "rate_limit_exceeded")

    category = params.get("category") if isinstance(params, dict) else None
    if category is not None and not isinstance(category, str):
        return _deny(tool, "invalid_category")

    try:
        items = query_memory(
            workspace_root=ws,
            key_pattern=user_pattern,
            category=category,
        )
    except Exception as exc:  # noqa: BLE001 — surface runtime failures as error envelope
        return _error(tool, f"query_failure: {exc}")

    return {
        "api_version": _API_VERSION,
        "tool": tool,
        "allowed": True,
        "decision": "executed",
        "reason_codes": [],
        "data": {"items": items, "count": len(items)},
        "error": None,
    }
