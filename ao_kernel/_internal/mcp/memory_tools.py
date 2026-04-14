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
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ao_kernel._internal.prj_kernel_api.rate_limiter import TokenBucketRateLimiter


# ── Module-level state ──────────────────────────────────────────────

# Tools whose MCP envelopes must NOT be fed into the implicit
# canonical-promotion path run by ``mcp_server.call_tool``. Both
# memory tools return envelopes whose top-level scalar fields
# (api_version, tool, allowed, decision) would otherwise be
# extracted by ``decision_extractor.extract_from_tool_result`` and
# promoted as ``tool.ao_memory_*.{api_version,tool,allowed,decision}``
# — self-referential noise. ``ao_memory_write`` also promotes
# explicitly via ``promote_decision``, so implicit promotion would
# double-write. Both tools must therefore be denylisted
# (CNS-20260414-011 iter-1 B2 + CNS-20260414-012 iter-2 Q1).
_IMPLICIT_PROMOTE_SKIP: set[str] = {"ao_memory_read", "ao_memory_write"}

# Server-side confidence for ``ao_memory_write``. Caller-supplied
# confidence is NOT trusted (CNS-20260414-010 iter-3 Q9). 0.8 aligns
# with the repo defaults for :class:`CanonicalDecision.confidence`
# and :func:`promote_decision` (CNS-20260414-012 iter-1 W2).
_SERVER_SIDE_CONFIDENCE = 0.8

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


def run_implicit_promote(
    tool_name: str,
    result: dict[str, Any],
    ws_root: Path | None,
) -> None:
    """Run the implicit canonical-promotion side-channel for a tool result.

    Encapsulates the logic previously inlined in
    :func:`ao_kernel.mcp_server.call_tool`:

    * Skip when ``ws_root`` is ``None`` (library mode).
    * Skip tools in :data:`_IMPLICIT_PROMOTE_SKIP` (memory read/write).
    * Read threshold + source prefix from
      ``policy_tool_calling.v1.json::implicit_canonical_promote`` via
      :func:`_load_tool_calling_policy_validated` (workspace-aware).
    * Fail-open on policy load/validate errors (side-channel only).
    * Extract decisions via
      :func:`ao_kernel.context.decision_extractor.extract_from_tool_result`
      and promote those whose confidence meets the threshold.

    This helper is best-effort: all failures are swallowed by the caller
    so the MCP response path never blocks on wiring issues.
    """
    if ws_root is None or tool_name in _IMPLICIT_PROMOTE_SKIP:
        return
    from ao_kernel.context.canonical_store import promote_decision
    from ao_kernel.context.decision_extractor import extract_from_tool_result

    try:
        tool_policy = _load_tool_calling_policy_validated(ws_root)
    except Exception:  # noqa: BLE001 — fail-open side-channel
        tool_policy = {}
    implicit_cfg = tool_policy.get("implicit_canonical_promote") or {}
    if not bool(implicit_cfg.get("enabled", True)):
        return
    threshold = float(implicit_cfg.get("threshold", 0.8))
    source_prefix = str(implicit_cfg.get("source_prefix", "mcp:tool_result"))
    decisions = extract_from_tool_result(tool_name, result)
    for d in decisions:
        if d.confidence >= threshold:
            promote_decision(
                ws_root,
                key=d.key,
                value=d.value,
                source=source_prefix,
                confidence=d.confidence,
            )


def _load_tool_calling_policy_validated(ws: Path | None) -> dict[str, Any]:
    """Load ``policy_tool_calling.v1.json`` with workspace override + schema validation.

    Used ONLY by the implicit-promote path in
    :func:`ao_kernel.mcp_server.call_tool`, so workspace overrides can
    tune ``implicit_canonical_promote`` per project. The gateway
    constructor :func:`ao_kernel.mcp_server.create_tool_gateway` still
    uses :func:`load_default` because the gateway-level tool policy is
    a process-wide fallback, not a per-workspace override
    (CNS-20260414-012 iter-2 W2).
    """
    import jsonschema

    from ao_kernel.config import load_default, load_with_override

    policy_workspace = ws / ".ao" if (ws is not None and (ws / ".ao").is_dir()) else ws
    policy = load_with_override(
        "policies",
        "policy_tool_calling.v1.json",
        workspace=policy_workspace,
    )
    schema = load_default("schemas", "policy-tool-calling.schema.v1.json")
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


# ── Handler: ao_memory_write ────────────────────────────────────────

def handle_memory_write(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for the ``ao_memory_write`` MCP tool.

    Policy-gated, rate-limited write-through to the canonical store.
    Caller-supplied ``confidence`` is IGNORED (CNS-20260414-010 iter-3
    Q9); the server always promotes at ``_SERVER_SIDE_CONFIDENCE``
    (0.8, aligned with :func:`promote_decision` default). Explicit
    promotion is paired with ``ao_memory_write``'s membership in
    :data:`_IMPLICIT_PROMOTE_SKIP` so the implicit-promotion path in
    ``mcp_server.call_tool`` does not double-write the envelope.
    """
    from ao_kernel.context.canonical_store import promote_decision
    from ao_kernel.mcp_server import _find_workspace_root

    tool = "ao_memory_write"

    ws = _resolve_workspace_for_call(params, fallback=_find_workspace_root)
    if ws is None:
        return _deny(tool, "workspace_not_found")

    try:
        policy = _load_memory_policy_validated(ws)
    except Exception as exc:  # noqa: BLE001 — fail-closed on any load/validate error
        return _deny(tool, "policy_load_error", error=str(exc))

    write_cfg = policy.get("write") if isinstance(policy, dict) else None
    if not isinstance(write_cfg, dict) or not bool(write_cfg.get("enabled", False)):
        return _deny(tool, "write_disabled_by_policy")

    if not isinstance(params, dict):
        return _deny(tool, "invalid_params")
    key = params.get("key")
    value = params.get("value", None)
    source = params.get("source", "mcp:tool_write")
    if not isinstance(key, str) or not key.strip():
        return _deny(tool, "invalid_key")
    if value is None:
        return _deny(tool, "invalid_value")
    if not isinstance(source, str) or not source.strip():
        return _deny(tool, "invalid_source")

    key_prefixes = write_cfg.get("allowed_key_prefixes", [])
    if not isinstance(key_prefixes, list) or not key_prefixes:
        return _deny(tool, "key_prefix_not_allowed")
    if not any(isinstance(p, str) and key.startswith(p) for p in key_prefixes):
        return _deny(tool, "key_prefix_not_allowed")

    source_prefixes = write_cfg.get("allowed_source_prefixes", ["mcp:"])
    if not isinstance(source_prefixes, list) or not source_prefixes:
        return _deny(tool, "source_prefix_not_allowed")
    if not any(isinstance(p, str) and source.startswith(p) for p in source_prefixes):
        return _deny(tool, "source_prefix_not_allowed")

    max_bytes = int(write_cfg.get("max_value_bytes", 4096))
    try:
        encoded = json.dumps(value).encode("utf-8")
    except (TypeError, ValueError) as exc:
        return _deny(tool, "value_not_serializable", error=str(exc))
    if len(encoded) > max_bytes:
        return _deny(tool, "oversize")

    rate_cfg = policy.get("rate_limit", {}) if isinstance(policy, dict) else {}
    rpm = int(rate_cfg.get("writes_per_minute", 10)) if isinstance(rate_cfg, dict) else 10
    if rpm < 1:
        rpm = 1
    limiter = _memory_rate_limiter_for(ws, "write", rpm=rpm)
    if not limiter.try_acquire():
        return _deny(tool, "rate_limit_exceeded")

    try:
        decision = promote_decision(
            ws,
            key=key,
            value=value,
            source=source,
            confidence=_SERVER_SIDE_CONFIDENCE,
        )
    except Exception as exc:  # noqa: BLE001 — surface runtime failures as error envelope
        return _error(tool, f"promote_failure: {exc}")

    return {
        "api_version": _API_VERSION,
        "tool": tool,
        "allowed": True,
        "decision": "executed",
        "reason_codes": [],
        "data": {
            "key": decision.key,
            "confidence": decision.confidence,
            "promoted_at": decision.promoted_at,
        },
        "error": None,
    }
