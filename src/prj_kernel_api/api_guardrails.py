"""Program-led API guardrails for PRJ-KERNEL-API (stdlib-only, deterministic)."""

from __future__ import annotations

import fnmatch
import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from jsonschema import Draft202012Validator

from src.prj_kernel_api.dotenv_loader import resolve_env_value

POLICY_PATH = "policies/policy_kernel_api_guardrails.v1.json"
SCHEMA_PATH = "schemas/policy-kernel-api-guardrails.schema.json"

_rate_lock = threading.Lock()
_rate_state: dict[str, Any] = {"minute": None, "count": 0, "limit": None}

_concurrency_lock = threading.Lock()
_concurrency_state: dict[str, Any] = {"limit": None, "semaphore": None}

_audit_lock = threading.Lock()


class GuardrailsError(ValueError):
    pass


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_env_mode(env_mode: str | None) -> str:
    return "process" if env_mode == "process" else "dotenv"


def _resolve_auth_mode(policy: Dict[str, Any], workspace_root: str, env_mode: str) -> str:
    mode = "bearer"
    auth = policy.get("auth") if isinstance(policy.get("auth"), dict) else {}
    if isinstance(auth.get("mode"), str):
        mode = auth.get("mode")
    present, override = resolve_env_value("KERNEL_API_AUTH_MODE", workspace_root, env_mode=env_mode)
    if present and override in {"bearer", "hmac"}:
        mode = override
    return mode


def _resolve_auth_key(policy: Dict[str, Any], mode: str) -> str:
    auth = policy.get("auth") if isinstance(policy.get("auth"), dict) else {}
    env_key = auth.get("env_key") if isinstance(auth.get("env_key"), str) else "KERNEL_API_TOKEN"
    if mode == "hmac" and env_key == "KERNEL_API_TOKEN":
        env_key = "KERNEL_API_HMAC_SECRET"
    return env_key


def _resolve_int_override(key: str, workspace_root: str, env_mode: str) -> int | None:
    present, value = resolve_env_value(key, workspace_root, env_mode=env_mode)
    if not present or value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def load_guardrails_policy(workspace_root: str) -> Dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    ws_policy = Path(workspace_root) / "policies" / "policy_kernel_api_guardrails.v1.json"
    policy_path = ws_policy if ws_policy.exists() else repo_root / POLICY_PATH
    if not policy_path.exists():
        raise GuardrailsError("KERNEL_API_POLICY_MISSING")

    policy = _load_json(policy_path)
    schema_path = repo_root / SCHEMA_PATH
    if not schema_path.exists():
        raise GuardrailsError("KERNEL_API_POLICY_SCHEMA_MISSING")
    schema = _load_json(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda e: e.json_path)
    if errors:
        raise GuardrailsError("KERNEL_API_POLICY_INVALID")
    return policy


def effective_limits(policy: Dict[str, Any], workspace_root: str, *, env_mode: str) -> Dict[str, int]:
    limits = policy.get("limits") if isinstance(policy.get("limits"), dict) else {}
    max_body_bytes = int(limits.get("max_body_bytes", 65536))
    max_json_depth = int(limits.get("max_json_depth", 40))
    rate_limit_per_minute = int(limits.get("rate_limit_per_minute", 60))
    max_concurrent = int(limits.get("max_concurrent", 4))

    override_rate = _resolve_int_override("KERNEL_API_RATE_LIMIT_PER_MINUTE", workspace_root, env_mode)
    if override_rate is not None and override_rate >= 0:
        rate_limit_per_minute = override_rate

    override_concurrent = _resolve_int_override("KERNEL_API_MAX_CONCURRENT", workspace_root, env_mode)
    if override_concurrent is not None and override_concurrent > 0:
        max_concurrent = override_concurrent

    return {
        "max_body_bytes": max_body_bytes,
        "max_json_depth": max_json_depth,
        "rate_limit_per_minute": rate_limit_per_minute,
        "max_concurrent": max_concurrent,
    }


def compute_request_id(action: str, payload: Dict[str, Any]) -> str:
    stable = json.dumps({"action": action, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return "req_" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:12]


def _json_depth(obj: Any, depth: int = 1) -> int:
    if isinstance(obj, dict):
        if not obj:
            return depth
        return max(_json_depth(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return depth
        return max(_json_depth(v, depth + 1) for v in obj)
    return depth


def enforce_limits(
    *,
    policy: Dict[str, Any],
    workspace_root: str,
    env_mode: str,
    body_bytes: bytes,
    json_obj: Dict[str, Any],
) -> Tuple[bool, str | None, bool]:
    limits = effective_limits(policy, workspace_root, env_mode=env_mode)
    if len(body_bytes) > limits["max_body_bytes"]:
        return False, "KERNEL_API_BODY_TOO_LARGE", False

    depth = _json_depth(json_obj, 1)
    if depth > limits["max_json_depth"]:
        return False, "KERNEL_API_JSON_TOO_DEEP", False

    limit_per_minute = limits["rate_limit_per_minute"]
    if limit_per_minute < 0:
        return False, "KERNEL_API_RATE_LIMIT_INVALID", False

    rate_limited = False
    if limit_per_minute > 0:
        bucket = int(time.time() // 60)
        with _rate_lock:
            if _rate_state.get("limit") != limit_per_minute:
                _rate_state["limit"] = limit_per_minute
                _rate_state["minute"] = bucket
                _rate_state["count"] = 0
            if _rate_state.get("minute") != bucket:
                _rate_state["minute"] = bucket
                _rate_state["count"] = 0
            if _rate_state.get("count", 0) >= limit_per_minute:
                rate_limited = True
            else:
                _rate_state["count"] = int(_rate_state.get("count", 0)) + 1

    if rate_limited:
        return False, "KERNEL_API_RATE_LIMITED", True

    return True, None, False


def acquire_concurrency(policy: Dict[str, Any], workspace_root: str, *, env_mode: str) -> Tuple[bool, str | None, threading.Semaphore | None]:
    limits = effective_limits(policy, workspace_root, env_mode=env_mode)
    limit = limits["max_concurrent"]
    if limit <= 0:
        return False, "KERNEL_API_CONCURRENCY_INVALID", None

    with _concurrency_lock:
        if _concurrency_state.get("limit") != limit or _concurrency_state.get("semaphore") is None:
            _concurrency_state["limit"] = limit
            _concurrency_state["semaphore"] = threading.BoundedSemaphore(limit)
        sem = _concurrency_state.get("semaphore")

    if sem is None:
        return False, "KERNEL_API_CONCURRENCY_INVALID", None

    if not sem.acquire(blocking=False):
        return False, "KERNEL_API_CONCURRENCY_LIMIT", None

    return True, None, sem


def release_concurrency(sem: threading.Semaphore | None) -> None:
    if sem is None:
        return
    try:
        sem.release()
    except Exception:
        return


def _get_header(headers: Dict[str, str], key: str) -> str | None:
    for k, v in headers.items():
        if k.lower() == key.lower():
            return v
    return None


def verify_auth(
    *,
    headers: Dict[str, str],
    body_bytes: bytes,
    policy: Dict[str, Any],
    workspace_root: str,
    env_mode: str,
) -> Tuple[bool, str | None, bool]:
    auth = policy.get("auth") if isinstance(policy.get("auth"), dict) else {}
    required = bool(auth.get("required", True))
    mode = _resolve_auth_mode(policy, workspace_root, env_mode)
    env_key = _resolve_auth_key(policy, mode)

    present, secret = resolve_env_value(env_key, workspace_root, env_mode=env_mode)
    if not present or not secret:
        return (not required), ("KERNEL_API_UNAUTHORIZED" if required else None), False

    if mode == "bearer":
        auth_header = _get_header(headers, "authorization") or ""
        if not auth_header.lower().startswith("bearer "):
            return (not required), ("KERNEL_API_UNAUTHORIZED" if required else None), bool(auth_header)
        token = auth_header.split(" ", 1)[1]
        if not hmac.compare_digest(token, secret):
            return False, "KERNEL_API_UNAUTHORIZED", True
        return True, None, True

    signature = _get_header(headers, "x-signature") or ""
    expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    if not signature:
        return (not required), ("KERNEL_API_UNAUTHORIZED" if required else None), False
    if not hmac.compare_digest(signature, expected):
        return False, "KERNEL_API_UNAUTHORIZED", True
    return True, None, True


def action_allowed(policy: Dict[str, Any], action: str) -> bool:
    actions = policy.get("actions") if isinstance(policy.get("actions"), dict) else {}
    allowlist = actions.get("allowlist") if isinstance(actions.get("allowlist"), list) else []
    return action in allowlist


def llm_live_allowed(policy: Dict[str, Any]) -> bool:
    actions = policy.get("actions") if isinstance(policy.get("actions"), dict) else {}
    return bool(actions.get("llm_call_live_allowed", False))


def _match_patterns(name: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatchcase(name.lower(), pattern.lower()):
            return True
    return False


def redact(obj: Any, patterns: Iterable[str]) -> Any:
    if isinstance(obj, dict):
        redacted: Dict[str, Any] = {}
        for key, value in obj.items():
            if _match_patterns(str(key), patterns):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact(value, patterns)
        return redacted
    if isinstance(obj, list):
        return [redact(v, patterns) for v in obj]
    if isinstance(obj, str) and _match_patterns(obj, patterns):
        return "***REDACTED***"
    return obj


def _resolve_workspace_path(workspace_root: str, relpath: str) -> Path:
    root = Path(workspace_root).resolve()
    target = (root / relpath).resolve()
    if not str(target).startswith(str(root)):
        raise GuardrailsError("KERNEL_API_AUDIT_PATH_INVALID")
    return target


def write_audit_log(
    *,
    workspace_root: str,
    policy: Dict[str, Any],
    record: Dict[str, Any],
) -> None:
    audit = policy.get("audit") if isinstance(policy.get("audit"), dict) else {}
    if not bool(audit.get("enabled", False)):
        return

    relpath = audit.get("path") if isinstance(audit.get("path"), str) else ""
    if not relpath:
        raise GuardrailsError("KERNEL_API_AUDIT_PATH_INVALID")

    redact_keys = audit.get("redact_keys") if isinstance(audit.get("redact_keys"), list) else []
    redacted = redact(record, [str(k) for k in redact_keys])

    path = _resolve_workspace_path(workspace_root, relpath)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(redacted, ensure_ascii=False, sort_keys=True)
    with _audit_lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
