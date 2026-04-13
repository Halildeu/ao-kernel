from __future__ import annotations
from ao_kernel._internal.shared.utils import write_text_atomic

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class SessionContextError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


_VALID_ACTOR_ROLES = {
    "architect",
    "planner",
    "implementer",
    "reviewer",
    "verifier",
    "consultant",
    "assurance_owner",
    "operator",
}


def _repo_root() -> Path:
    # src/session/context_store.py -> session -> src -> repo root
    return Path(__file__).resolve().parents[2]


def _load_schema() -> dict[str, Any]:
    """Load session context schema — tries repo root, falls back to bundled defaults."""
    repo_path = _repo_root() / "schemas" / "session-context.schema.json"
    if repo_path.exists():
        return json.loads(repo_path.read_text(encoding="utf-8"))
    # Fallback: bundled defaults
    try:
        from ao_kernel._internal.shared.resource_loader import load_resource
        return load_resource("schemas", "session-context.schema.json")
    except (ImportError, FileNotFoundError):
        pass
    raise SessionContextError("SCHEMA_NOT_FOUND", "Missing session-context.schema.json")


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso8601(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _remaining_session_ttl_seconds(context: dict[str, Any], now_dt: datetime) -> int:
    exp = _parse_iso8601(str(context.get("expires_at") or ""))
    if exp is None:
        return 604800
    seconds = int((exp - now_dt).total_seconds())
    return max(0, seconds)


def _clamp_ttl(value: int) -> int:
    return max(60, min(604800, int(value)))


def _decision_ttl_seconds(
    *,
    context: dict[str, Any],
    now_dt: datetime,
    requested_ttl_seconds: int | None,
) -> int:
    raw_default = context.get("decision_ttl_seconds_default", 3600)
    try:
        default_ttl = _clamp_ttl(int(raw_default))
    except Exception:
        default_ttl = 3600
    ttl = default_ttl
    if requested_ttl_seconds is not None:
        try:
            ttl = _clamp_ttl(int(requested_ttl_seconds))
        except Exception as e:
            raise SessionContextError("INVALID_ARGS", "decision_ttl_seconds must be int in [60, 604800]") from e

    remaining = _remaining_session_ttl_seconds(context, now_dt)
    if remaining > 0:
        ttl = min(ttl, max(60, remaining))
    return ttl


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _validator() -> Draft202012Validator:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _context_for_hash(ctx: dict[str, Any]) -> dict[str, Any]:
    clone = deepcopy(ctx)
    hashes = clone.get("hashes")
    if not isinstance(hashes, dict):
        hashes = {}
    hashes = dict(hashes)
    hashes["session_context_sha256"] = ""
    clone["hashes"] = hashes
    return clone


def compute_context_sha256(ctx: dict[str, Any]) -> str:
    to_hash = _context_for_hash(ctx)
    return compute_sha256(_canonical_json_bytes(to_hash))


def load_context(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SessionContextError("JSON_INVALID", f"Invalid JSON: {path}") from e
    if not isinstance(obj, dict):
        raise SessionContextError("SCHEMA_INVALID", "Session context must be an object")

    validator = _validator()
    errors = sorted(validator.iter_errors(obj), key=lambda e: e.json_path)
    if errors:
        msg = errors[0].message
        where = errors[0].json_path or "$"
        raise SessionContextError("SCHEMA_INVALID", f"{where}: {msg}")

    hashes = obj.get("hashes")
    sha_in = hashes.get("session_context_sha256") if isinstance(hashes, dict) else None
    if not isinstance(sha_in, str) or len(sha_in) != 64:
        raise SessionContextError("HASH_INVALID", "Missing hashes.session_context_sha256")

    sha_calc = compute_context_sha256(obj)
    if sha_calc != sha_in:
        raise SessionContextError("HASH_MISMATCH", "hashes.session_context_sha256 does not match computed hash")

    return obj


def save_context_atomic(path: Path, obj: dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise SessionContextError("SCHEMA_INVALID", "Session context must be an object")
    if "hashes" not in obj or not isinstance(obj.get("hashes"), dict):
        obj["hashes"] = {}

    sha = compute_context_sha256(obj)
    obj["hashes"]["session_context_sha256"] = sha

    validator = _validator()
    errors = sorted(validator.iter_errors(obj), key=lambda e: e.json_path)
    if errors:
        msg = errors[0].message
        where = errors[0].json_path or "$"
        raise SessionContextError("SCHEMA_INVALID", f"{where}: {msg}")

    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    write_text_atomic(tmp, payload)
    tmp.replace(path)


def new_context(
    session_id: str,
    workspace_root: str,
    ttl_seconds: int,
    *,
    predecessor_session_id: str | None = None,
) -> dict[str, Any]:
    if not session_id or not isinstance(session_id, str):
        raise SessionContextError("INVALID_ARGS", "session_id must be non-empty")
    if not isinstance(ttl_seconds, int) or ttl_seconds < 60 or ttl_seconds > 604800:
        raise SessionContextError("INVALID_ARGS", "ttl_seconds must be in [60, 604800]")

    now = datetime.now(timezone.utc)
    created_at = now.isoformat().replace("+00:00", "Z")
    expires_at = (now + timedelta(seconds=int(ttl_seconds))).isoformat().replace("+00:00", "Z")

    ctx: dict[str, Any] = {
        "version": "v1",
        "session_id": session_id,
        "workspace_root": str(workspace_root),
        "created_at": created_at,
        "updated_at": created_at,
        "ttl_seconds": int(ttl_seconds),
        "decision_ttl_seconds_default": min(3600, int(ttl_seconds)),
        "expires_at": expires_at,
        "paused": False,
        "memory_strategy": "hybrid",
        "compaction": {"status": "idle"},
        "ephemeral_decisions": [],
        "hashes": {"session_context_sha256": ""},
    }
    if predecessor_session_id and isinstance(predecessor_session_id, str) and predecessor_session_id.strip():
        ctx["predecessor_session_id"] = predecessor_session_id.strip()
    ctx["hashes"]["session_context_sha256"] = compute_context_sha256(ctx)
    return ctx


def upsert_decision(
    context: dict[str, Any],
    key: str,
    value: Any,
    source: str,
    *,
    decision_ttl_seconds: int | None = None,
) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")
    if not isinstance(key, str) or not key:
        raise SessionContextError("INVALID_ARGS", "key must be non-empty string")
    if source not in {"user_chat", "agent"}:
        raise SessionContextError("INVALID_ARGS", "source must be user_chat|agent")

    if isinstance(value, list) or value is None:
        raise SessionContextError("INVALID_ARGS", "value_json must be string|number|boolean|object")

    now = _now_iso8601()
    now_dt = _parse_iso8601(now)
    if now_dt is None:
        raise SessionContextError("INVALID_TIME", "failed to resolve current time")

    decisions = context.get("ephemeral_decisions")
    if not isinstance(decisions, list):
        decisions = []
    out: list[dict[str, Any]] = []
    replaced = False
    for d in decisions:
        if not isinstance(d, dict):
            continue
        if d.get("key") == key:
            existing_ttl = d.get("ttl_seconds") if isinstance(d.get("ttl_seconds"), int) else None
            ttl = _decision_ttl_seconds(
                context=context,
                now_dt=now_dt,
                requested_ttl_seconds=decision_ttl_seconds if decision_ttl_seconds is not None else existing_ttl,
            )
            exp = (now_dt + timedelta(seconds=ttl)).isoformat().replace("+00:00", "Z")
            # Track history: append old value if different (max 10, FIFO)
            history = list(d.get("history", []) if isinstance(d.get("history"), list) else [])
            old_val = d.get("value")
            old_val_json = json.dumps(old_val, sort_keys=True, ensure_ascii=True) if old_val is not None else ""
            new_val_json = json.dumps(value, sort_keys=True, ensure_ascii=True)
            if old_val_json and old_val_json != new_val_json:
                history.append({"value": old_val, "changed_at": now, "source": str(d.get("source") or "agent")})
                if len(history) > 10:
                    history = history[-10:]
            new_decision: dict[str, Any] = {
                "key": key,
                "value": value,
                "source": source,
                "created_at": now,
                "ttl_seconds": int(ttl),
                "expires_at": exp,
            }
            if history:
                new_decision["history"] = history
            out.append(new_decision)
            replaced = True
        else:
            out.append(d)
    if not replaced:
        ttl = _decision_ttl_seconds(
            context=context,
            now_dt=now_dt,
            requested_ttl_seconds=decision_ttl_seconds,
        )
        exp = (now_dt + timedelta(seconds=ttl)).isoformat().replace("+00:00", "Z")
        out.append(
            {
                "key": key,
                "value": value,
                "source": source,
                "created_at": now,
                "ttl_seconds": int(ttl),
                "expires_at": exp,
            }
        )

    out.sort(key=lambda x: str(x.get("key") or ""))
    context["ephemeral_decisions"] = out
    context["updated_at"] = now
    return context


def upsert_provider_state(
    context: dict[str, Any],
    *,
    provider: str,
    wire_api: str,
    conversation_id: str = "",
    last_response_id: str = "",
    summary_ref: str = "",
) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")
    provider_norm = str(provider or "").strip()
    wire_api_norm = str(wire_api or "").strip()
    if not provider_norm:
        raise SessionContextError("INVALID_ARGS", "provider must be non-empty")
    if not wire_api_norm:
        raise SessionContextError("INVALID_ARGS", "wire_api must be non-empty")

    now = _now_iso8601()
    state = {
        "provider": provider_norm,
        "wire_api": wire_api_norm,
        "updated_at": now,
    }
    if str(conversation_id or "").strip():
        state["conversation_id"] = str(conversation_id).strip()
    if str(last_response_id or "").strip():
        state["last_response_id"] = str(last_response_id).strip()
    if str(summary_ref or "").strip():
        state["summary_ref"] = str(summary_ref).strip()

    context["provider_state"] = state
    context["memory_strategy"] = str(context.get("memory_strategy") or "hybrid")
    context["updated_at"] = now
    return context


def upsert_actor_state(
    context: dict[str, Any],
    *,
    role: str,
    actor: str,
    provider: str,
    model: str,
    target_id: str = "",
    selection_reason: str = "",
    fallback_used: bool = False,
) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")

    role_norm = str(role or "").strip()
    actor_norm = str(actor or "").strip()
    provider_norm = str(provider or "").strip()
    model_norm = str(model or "").strip()

    if role_norm not in _VALID_ACTOR_ROLES:
        raise SessionContextError("INVALID_ARGS", "role must be a valid actor role")
    if not actor_norm:
        raise SessionContextError("INVALID_ARGS", "actor must be non-empty")
    if not provider_norm:
        raise SessionContextError("INVALID_ARGS", "provider must be non-empty")
    if not model_norm:
        raise SessionContextError("INVALID_ARGS", "model must be non-empty")

    now = _now_iso8601()
    state: dict[str, Any] = {
        "role": role_norm,
        "actor": actor_norm,
        "provider": provider_norm,
        "model": model_norm,
        "updated_at": now,
    }
    if str(target_id or "").strip():
        state["target_id"] = str(target_id).strip()
    if str(selection_reason or "").strip():
        state["selection_reason"] = str(selection_reason).strip()
    if bool(fallback_used):
        state["fallback_used"] = True

    context["actor_state"] = state
    context["updated_at"] = now
    return context


def mark_compaction(
    context: dict[str, Any],
    *,
    summary_ref: str,
    trigger: str,
    source: str,
    approx_input_tokens: int = 0,
) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")
    summary_ref_norm = str(summary_ref or "").strip()
    trigger_norm = str(trigger or "").strip()
    source_norm = str(source or "").strip()
    if not summary_ref_norm:
        raise SessionContextError("INVALID_ARGS", "summary_ref must be non-empty")
    if not trigger_norm:
        raise SessionContextError("INVALID_ARGS", "trigger must be non-empty")
    if not source_norm:
        raise SessionContextError("INVALID_ARGS", "source must be non-empty")
    try:
        approx_tokens = max(0, int(approx_input_tokens))
    except Exception as e:
        raise SessionContextError("INVALID_ARGS", "approx_input_tokens must be integer >= 0") from e

    now = _now_iso8601()
    context["compaction"] = {
        "status": "completed",
        "summary_ref": summary_ref_norm,
        "last_compacted_at": now,
        "trigger": trigger_norm,
        "source": source_norm,
        "approx_input_tokens": approx_tokens,
    }
    context["memory_strategy"] = str(context.get("memory_strategy") or "hybrid")
    context["updated_at"] = now
    return context


def is_expired(context: dict[str, Any], now_iso: str) -> bool:
    if not isinstance(context, dict):
        return True
    exp = context.get("expires_at")
    if not isinstance(exp, str) or not exp:
        return True
    now_dt = _parse_iso8601(str(now_iso) or "")
    exp_dt = _parse_iso8601(exp)
    if now_dt is None or exp_dt is None:
        return True
    return now_dt > exp_dt


def prune_expired_decisions(context: dict[str, Any], now_iso: str) -> dict[str, Any]:
    if not isinstance(context, dict):
        return context
    now_dt = _parse_iso8601(str(now_iso) or "")
    if now_dt is None:
        return context
    decisions = context.get("ephemeral_decisions")
    if not isinstance(decisions, list):
        return context

    out: list[dict[str, Any]] = []
    changed = False
    for decision in decisions:
        if not isinstance(decision, dict):
            changed = True
            continue
        exp = decision.get("expires_at")
        if isinstance(exp, str) and exp:
            exp_dt = _parse_iso8601(exp)
            if exp_dt is not None and now_dt >= exp_dt:
                changed = True
                continue
        out.append(decision)

    if changed:
        out.sort(key=lambda x: str(x.get("key") or ""))
        context["ephemeral_decisions"] = out
        context["updated_at"] = now_iso
    return context


def renew_context(context: dict[str, Any], ttl_seconds: int) -> dict[str, Any]:
    """Extend session expiry without losing valid decisions or provider state."""
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")
    if not isinstance(ttl_seconds, int) or ttl_seconds < 60 or ttl_seconds > 604800:
        raise SessionContextError("INVALID_ARGS", "ttl_seconds must be in [60, 604800]")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")
    expires_at = (now + timedelta(seconds=int(ttl_seconds))).isoformat().replace("+00:00", "Z")

    context = prune_expired_decisions(context, now_iso)
    context["updated_at"] = now_iso
    context["ttl_seconds"] = int(ttl_seconds)
    context["decision_ttl_seconds_default"] = min(3600, int(ttl_seconds))
    context["expires_at"] = expires_at
    if "hashes" not in context or not isinstance(context.get("hashes"), dict):
        context["hashes"] = {}
    context["hashes"]["session_context_sha256"] = compute_context_sha256(context)
    return context


def link_to_parent(
    context: dict[str, Any],
    *,
    parent_workspace_root: str,
    parent_session_id: str = "default",
) -> dict[str, Any]:
    """Link session to a parent session (orchestrator → managed repo)."""
    if not isinstance(context, dict):
        raise SessionContextError("SCHEMA_INVALID", "context must be a dict")
    if not parent_workspace_root:
        raise SessionContextError("INVALID_ARGS", "parent_workspace_root must be non-empty")

    context["parent_session_ref"] = {
        "workspace_root": str(parent_workspace_root),
        "session_id": str(parent_session_id or "default"),
        "relationship": "parent",
    }
    context["updated_at"] = _now_iso8601()
    if "hashes" not in context or not isinstance(context.get("hashes"), dict):
        context["hashes"] = {}
    context["hashes"]["session_context_sha256"] = compute_context_sha256(context)
    return context


def inherit_parent_decisions(
    child_context: dict[str, Any],
    *,
    parent_context: dict[str, Any],
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    """Inherit non-expired decisions from parent into child.

    Parent decisions are copied with source='agent'. Child's own decisions
    are preserved unless overwrite_existing=True.
    """
    if not isinstance(child_context, dict) or not isinstance(parent_context, dict):
        raise SessionContextError("SCHEMA_INVALID", "contexts must be dicts")

    now = _now_iso8601()
    now_dt = _parse_iso8601(now)
    if now_dt is None:
        raise SessionContextError("INVALID_TIME", "failed to resolve current time")

    parent_decisions = parent_context.get("ephemeral_decisions")
    if not isinstance(parent_decisions, list) or not parent_decisions:
        return child_context

    child_decisions = child_context.get("ephemeral_decisions")
    if not isinstance(child_decisions, list):
        child_decisions = []

    child_keys: set[str] = {str(d.get("key") or "") for d in child_decisions if isinstance(d, dict)}

    child_remaining_ttl = _remaining_session_ttl_seconds(child_context, now_dt)

    inherited = 0
    for pd in parent_decisions:
        if not isinstance(pd, dict):
            continue
        key = str(pd.get("key") or "").strip()
        if not key:
            continue

        # Skip expired parent decisions
        exp = pd.get("expires_at")
        if isinstance(exp, str) and exp:
            exp_dt = _parse_iso8601(exp)
            if exp_dt is not None and now_dt >= exp_dt:
                continue

        if key in child_keys and not overwrite_existing:
            continue

        # Clamp TTL to child's remaining session TTL
        parent_ttl = pd.get("ttl_seconds", 3600)
        if not isinstance(parent_ttl, int):
            parent_ttl = 3600
        clamped_ttl = min(parent_ttl, max(60, child_remaining_ttl))
        child_exp = (now_dt + timedelta(seconds=clamped_ttl)).isoformat().replace("+00:00", "Z")

        new_decision = {
            "key": key,
            "value": pd.get("value"),
            "source": "agent",
            "created_at": now,
            "ttl_seconds": clamped_ttl,
            "expires_at": child_exp,
        }

        if key in child_keys:
            child_decisions = [d for d in child_decisions if not (isinstance(d, dict) and d.get("key") == key)]
        child_decisions.append(new_decision)
        child_keys.add(key)
        inherited += 1

    if inherited > 0:
        child_decisions.sort(key=lambda x: str(x.get("key") or ""))
        child_context["ephemeral_decisions"] = child_decisions
        child_context["updated_at"] = now
        if "hashes" not in child_context or not isinstance(child_context.get("hashes"), dict):
            child_context["hashes"] = {}
        child_context["hashes"]["session_context_sha256"] = compute_context_sha256(child_context)

    return child_context


@dataclass(frozen=True)
class SessionPaths:
    workspace_root: Path
    session_id: str

    @property
    def context_path(self) -> Path:
        return (self.workspace_root / ".cache" / "sessions" / self.session_id / "session_context.v1.json").resolve()
