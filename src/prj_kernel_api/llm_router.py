"""Deterministic LLM router: intent→class→provider→model (verified-only, TTL-gated)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_stale(ts: Optional[str], ttl_hours: int, now: datetime) -> bool:
    dt = _parse_ts(ts)
    if dt is None:
        return True
    return now - dt > timedelta(hours=ttl_hours)


def _resolve_workspace_root(repo_root: Path, workspace_root: str | Path | None) -> Path:
    if isinstance(workspace_root, Path):
        ws_root = workspace_root
    elif isinstance(workspace_root, str) and workspace_root.strip():
        ws_root = Path(workspace_root)
    else:
        ws_root = repo_root / ".cache" / "ws_customer_default"
    if not ws_root.is_absolute():
        ws_root = (repo_root / ws_root).resolve()
    return ws_root


def _policy_paths(repo_root: Path, workspace_root: str | Path | None = None) -> Tuple[Path, Path, Path, Path]:
    from src.shared.resource_loader import load_resource_path

    class_registry = load_resource_path("operations", "llm_class_registry.v1.json")
    resolver_rules = load_resource_path("operations", "llm_resolver_rules.v1.json")
    provider_map = load_resource_path("operations", "llm_provider_map.v1.json")

    # Fallback to repo-root if resource_loader returns paths
    if class_registry is None:
        class_registry = repo_root / "docs" / "OPERATIONS" / "llm_class_registry.v1.json"
    if resolver_rules is None:
        resolver_rules = repo_root / "docs" / "OPERATIONS" / "llm_resolver_rules.v1.json"
    if provider_map is None:
        provider_map = repo_root / "docs" / "OPERATIONS" / "llm_provider_map.v1.json"

    ws_root = _resolve_workspace_root(repo_root, workspace_root)
    probe_state = ws_root / ".cache" / "state" / "llm_probe_state.v1.json"
    return class_registry, resolver_rules, provider_map, probe_state


def _merge_state(provider_map: Dict[str, Any], probe_state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge runtime probe state into provider_map (without mutating input)."""
    merged = json.loads(json.dumps(provider_map))
    state_classes = probe_state.get("classes", {})
    for cls, cls_data in state_classes.items():
        mp_cls = merged.get("classes", {}).get(cls)
        if not isinstance(mp_cls, dict):
            continue
        state_providers = cls_data.get("providers", {})
        for prov, prov_data in state_providers.items():
            mp_prov = mp_cls.get("providers", {}).get(prov)
            if not isinstance(mp_prov, dict):
                continue
            models_state = prov_data.get("models", {})
            models_mp = {m.get("model_id"): m for m in mp_prov.get("models", []) if isinstance(m, dict)}
            for model_id, st in models_state.items():
                mp_entry = models_mp.get(model_id)
                if not isinstance(mp_entry, dict):
                    continue
                # Overlay probe fields
                for key in (
                    "probe_status",
                    "probe_last_at",
                    "probe_latency_ms_p95",
                    "probe_error_code",
                    "verified_at",
                    "probe_kind",
                ):
                    if key in st:
                        mp_entry[key] = st[key]
    return merged


def _eligible(model: Dict[str, Any], ttl_hours: int, now: datetime) -> bool:
    if not isinstance(model, dict):
        return False
    if model.get("stage") != "verified":
        return False
    if model.get("probe_status") != "ok":
        return False
    if _is_stale(model.get("probe_last_at"), ttl_hours, now):
        return False
    return True


def resolve(
    request: Dict[str, Any],
    repo_root: Optional[Path] = None,
    now: Optional[datetime] = None,
    workspace_root: str | Path | None = None,
) -> Dict[str, Any]:
    """Resolve provider/model deterministically. Returns manifest-like dict with status."""
    repo_root = repo_root or Path(__file__).resolve().parents[2]
    now = now or datetime.now(timezone.utc)

    if "model" in request:
        return {"status": "FAIL", "reason": "MODEL_OVERRIDE_NOT_ALLOWED"}
    if "params_override" in request:
        return {"status": "FAIL", "reason": "PROFILE_PARAM_OVERRIDE_NOT_ALLOWED"}

    intent = request.get("intent")
    perspective = request.get("perspective")
    provider_priority: List[str] = request.get("provider_priority") or []

    class_registry_path, resolver_rules_path, provider_map_path, probe_state_path = _policy_paths(
        repo_root, workspace_root=workspace_root
    )
    class_registry = _load_json(class_registry_path)
    resolver_rules = _load_json(resolver_rules_path)
    provider_map = _load_json(provider_map_path)
    probe_state = _load_json(probe_state_path) if probe_state_path.exists() else {"classes": {}}

    merged_map = _merge_state(provider_map, probe_state)
    intent_map = resolver_rules["intent_to_class"]
    if intent not in intent_map:
        return {"status": "FAIL", "reason": "UNKNOWN_INTENT"}
    target_class = intent_map[intent]

    ttl_default = resolver_rules.get("ttl_hours_default", 72)
    ttl_by_class = resolver_rules.get("ttl_hours_by_class", {})
    ttl_hours = ttl_by_class.get(target_class, ttl_default)

    fallback_default = resolver_rules["fallback_order_by_class"].get(target_class, [])
    order = provider_priority or fallback_default

    attempts = []
    selected = None
    cls_entry = merged_map.get("classes", {}).get(target_class, {})
    providers = cls_entry.get("providers", {}) if isinstance(cls_entry, dict) else {}

    for prov in order:
        prov_entry = providers.get(prov)
        if not isinstance(prov_entry, dict):
            attempts.append({"provider": prov, "status": "NO_SLOT"})
            continue
        pinned = prov_entry.get("pinned_model_id")
        if not pinned:
            attempts.append({"provider": prov, "status": "NO_PINNED"})
            continue
        model_entry = None
        for m in prov_entry.get("models", []):
            if isinstance(m, dict) and m.get("model_id") == pinned:
                model_entry = m
                break
        if not model_entry:
            attempts.append({"provider": prov, "status": "PINNED_NOT_FOUND"})
            continue
        if intent == "APPLY" and target_class == "CODE_AGENTIC":
            probe_kind = model_entry.get("probe_kind")
            if not isinstance(probe_kind, str) or not probe_kind.strip():
                attempts.append({"provider": prov, "status": "NOT_READY_PROBE_KIND_UNKNOWN"})
                continue
            if probe_kind.startswith("synthetic"):
                attempts.append({"provider": prov, "status": "NOT_READY_SYNTHETIC_PROBE"})
                continue
        if not _eligible(model_entry, ttl_hours, now):
            attempts.append({"provider": prov, "status": "NOT_ELIGIBLE"})
            continue
        selected = (prov, pinned, model_entry)
        attempts.append({"provider": prov, "status": "SELECTED"})
        break

    if not selected:
        # v0.1 hardening: APPLY is strictly gated on verified CODE_AGENTIC.
        # When no eligible model exists, return an explicit reason code so UI/ops can
        # surface "NOT READY" instead of a generic selection failure.
        if intent == "APPLY" and target_class == "CODE_AGENTIC":
            reason = "APPLY_BLOCKED_NO_VERIFIED_CODE_AGENTIC"
        else:
            reason = "NO_VERIFIED_MODEL_FOR_CLASS"
        return {
            "status": "FAIL",
            "reason": reason,
            "selected_class": target_class,
            "provider_attempts": attempts,
        }

    sel_provider, sel_model_id, sel_model = selected
    manifest = {
        "status": "OK",
        "selected_class": target_class,
        "selected_provider": sel_provider,
        "selected_model": sel_model_id,
        "provider_attempts": attempts,
        "probe_status_at_selection": sel_model.get("probe_status"),
        "verified_at": sel_model.get("verified_at"),
        "probe_last_at": sel_model.get("probe_last_at"),
        "ttl_remaining_hours": None,  # compute optionally
        "intent": intent,
        "perspective": perspective,
    }
    return manifest


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="LLM router resolve")
    parser.add_argument("--intent", required=True)
    parser.add_argument("--perspective", default="")
    parser.add_argument("--provider-priority", nargs="*", default=[])
    args = parser.parse_args()
    req = {
        "intent": args.intent,
        "perspective": args.perspective,
        "provider_priority": args.provider_priority,
    }
    result = resolve(req)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
