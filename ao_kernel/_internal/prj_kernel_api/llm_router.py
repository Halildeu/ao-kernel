"""Deterministic LLM router: intent→class→provider→model (verified-only, TTL-gated)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_json(path: Path) -> Dict[str, Any]:
    loaded: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


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


def _load_operations_json(filename: str, repo_root: Path) -> Dict[str, Any]:
    """Load operations JSON — tries repo-root first, falls back to bundled defaults."""
    from ao_kernel._internal.shared.resource_loader import load_resource
    payload: Dict[str, Any] = load_resource("operations", filename)
    return payload


_RESOLVER_RULES_SCHEMA_VALIDATED = False


def _validate_resolver_rules_once(rules_dict: Dict[str, Any]) -> None:
    """Schema-validate the loaded resolver rules on first use.

    PR-C4.1: guards malformed ``soft_degrade.rules[]`` entries (e.g.
    negative ``budget_remaining_threshold_usd``) before the runtime
    evaluates them. Cached via module-level flag — validation runs
    once per interpreter process, zero overhead on subsequent calls.
    Malformed rules → ``jsonschema.ValidationError`` fail-closed.
    """
    global _RESOLVER_RULES_SCHEMA_VALIDATED
    if _RESOLVER_RULES_SCHEMA_VALIDATED:
        return
    from jsonschema import Draft7Validator
    from ao_kernel._internal.shared.resource_loader import load_resource
    schema = load_resource("schemas", "schema_llm_resolver_rules.v1.json")
    Draft7Validator(schema).validate(rules_dict)
    _RESOLVER_RULES_SCHEMA_VALIDATED = True


def _reset_resolver_rules_cache() -> None:
    """Test-only hook: reset the schema-validation cache.

    Invoked by the test suite between fixtures that swap the bundled
    resolver rules; production code does not call this.
    """
    global _RESOLVER_RULES_SCHEMA_VALIDATED
    _RESOLVER_RULES_SCHEMA_VALIDATED = False


def _policy_paths(repo_root: Path, workspace_root: str | Path | None = None) -> Tuple[Path | None, Path | None, Path | None, Path]:
    """Return probe_state path only. Operations loaded via _load_operations_json()."""
    ws_root = _resolve_workspace_root(repo_root, workspace_root)
    probe_state = ws_root / ".cache" / "state" / "llm_probe_state.v1.json"
    # class_registry, resolver_rules, provider_map loaded directly via _load_operations_json
    return None, None, None, probe_state


def _merge_state(provider_map: Dict[str, Any], probe_state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge runtime probe state into provider_map (without mutating input)."""
    merged: Dict[str, Any] = json.loads(json.dumps(provider_map))
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

    # PR-C4.1 ACTIVE: budget-aware cross-class soft-degrade.
    # Defaults carried through every return path below; populated
    # in the gating block further down when the caller opts in via
    # cross_class_downgrade=True + budget_remaining snapshot.
    _c4_meta: Dict[str, Any] = {
        "downgrade_applied": False,
        "original_class": None,
        "downgraded_class": None,
        "matched_rule_index": None,
        "threshold_usd": None,
        "budget_remaining_usd": None,
    }

    if "model" in request:
        return {
            "status": "FAIL",
            "reason": "MODEL_OVERRIDE_NOT_ALLOWED",
            **_c4_meta,
        }
    if "params_override" in request:
        return {
            "status": "FAIL",
            "reason": "PROFILE_PARAM_OVERRIDE_NOT_ALLOWED",
            **_c4_meta,
        }

    intent = request.get("intent")
    perspective = request.get("perspective")
    provider_priority: List[str] = request.get("provider_priority") or []

    _, _, _, probe_state_path = _policy_paths(repo_root, workspace_root=workspace_root)

    # Load operations via resource_loader (bundled defaults fallback)
    _load_operations_json("llm_class_registry.v1.json", repo_root)  # validate
    resolver_rules = _load_operations_json("llm_resolver_rules.v1.json", repo_root)
    _validate_resolver_rules_once(resolver_rules)
    provider_map = _load_operations_json("llm_provider_map.v1.json", repo_root)
    probe_state = _load_json(probe_state_path) if probe_state_path.exists() else {"classes": {}}

    merged_map = _merge_state(provider_map, probe_state)
    intent_map = resolver_rules["intent_to_class"]
    if intent not in intent_map:
        return {
            "status": "FAIL",
            "reason": "UNKNOWN_INTENT",
            **_c4_meta,
        }
    requested_class = intent_map[intent]

    # PR-C4.1 gating: budget-aware soft-degrade.
    # Preconditions stack (all must hold for a downgrade to apply):
    #   1. Caller opted in via cross_class_downgrade=True
    #   2. Caller supplied budget_remaining snapshot (Budget object)
    #   3. Requested class allows degrade (strictness.degrade_allowed
    #      defaults True; REASONING_TEXT / CODE_AGENTIC /
    #      GOVERNANCE_ASSURANCE are absolute-deny)
    #   4. Budget snapshot has a cost_usd axis configured
    #   5. soft_degrade.rules[] contains a threshold-bearing rule that
    #      matches (from_class, intent) AND remaining < threshold_usd
    #      (STRICT less-than; equal → no downgrade)
    # Threshold-less rules (the bundled DISCOVERY/BASELINE ones) are
    # inert in C4.1 — behavior preserved, no unintended activation.
    budget_snap = request.get("budget_remaining")
    want_downgrade = bool(request.get("cross_class_downgrade", False))
    strictness = resolver_rules.get("strictness", {})
    soft_degrade = resolver_rules.get("soft_degrade", {})
    soft_degrade_rules = (
        soft_degrade.get("rules", []) if soft_degrade.get("enabled", False) else []
    )

    target_class = requested_class

    if (
        want_downgrade
        and budget_snap is not None
        and soft_degrade_rules
    ):
        strict_cfg = strictness.get(requested_class, {})
        if strict_cfg.get("degrade_allowed", True):
            # budget_snap expected to be a Budget (workflow.budget)
            # with .cost_usd field (BudgetAxis | None).
            cost_axis = getattr(budget_snap, "cost_usd", None)
            if cost_axis is not None:
                remaining_val = getattr(cost_axis, "remaining", None)
                if remaining_val is not None:
                    remaining_usd = float(remaining_val)
                    _c4_meta["budget_remaining_usd"] = remaining_usd
                    for idx, rule in enumerate(soft_degrade_rules):
                        if not isinstance(rule, dict):
                            continue
                        threshold = rule.get("budget_remaining_threshold_usd")
                        if threshold is None:
                            continue  # inert in C4.1
                        if rule.get("from_class") != requested_class:
                            continue
                        intents_list = rule.get("intents", []) or []
                        if intent not in intents_list:
                            continue
                        if remaining_usd < float(threshold):
                            target_class = rule["to_class"]
                            _c4_meta["downgrade_applied"] = True
                            _c4_meta["original_class"] = requested_class
                            _c4_meta["downgraded_class"] = target_class
                            _c4_meta["matched_rule_index"] = idx
                            _c4_meta["threshold_usd"] = float(threshold)
                            break

    ttl_default = resolver_rules.get("ttl_hours_default", 72)
    ttl_by_class = resolver_rules.get("ttl_hours_by_class", {})
    ttl_hours = ttl_by_class.get(target_class, ttl_default)

    fallback_default = resolver_rules["fallback_order_by_class"].get(target_class, [])
    order = provider_priority or fallback_default

    attempts = []
    selected = None
    cls_entry = merged_map.get("classes", {}).get(target_class, {})
    providers = cls_entry.get("providers", {}) if isinstance(cls_entry, dict) else {}

    # PR-B3 cost-aware routing injection (plan v5 §2.4).
    # Loader fail-closes on malformed override (cost/policy.py:142-143);
    # missing workspace override returns bundled dormant policy (no raise).
    # Router does NOT swallow loader exceptions — malformed cost policy
    # propagates naturally to the caller (fail-closed per llm.py:32-33).
    explicit_provider_priority = bool(request.get("provider_priority"))
    ws_root_for_cost = _resolve_workspace_root(repo_root, workspace_root)

    from ao_kernel.cost.policy import load_cost_policy
    cost_policy = load_cost_policy(ws_root_for_cost)

    cost_route_active = (
        cost_policy.enabled
        and cost_policy.routing_by_cost.enabled
        and cost_policy.routing_by_cost.priority == "lowest_cost"
    )

    if cost_route_active and not explicit_provider_priority:
        try:
            from ao_kernel.cost.catalog import load_price_catalog
            catalog = load_price_catalog(ws_root_for_cost, policy=cost_policy)
        except Exception as exc:
            if cost_policy.routing_by_cost.fail_closed_on_catalog_missing:
                from ao_kernel.cost.errors import RoutingCatalogMissingError
                raise RoutingCatalogMissingError(
                    provider_order=list(order),
                    target_class=target_class,
                    workspace_root=str(ws_root_for_cost),
                ) from exc
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "cost-aware routing: price catalog load failed; "
                "fail_closed_on_catalog_missing=false — falling back to "
                "provider_priority (class=%s, error=%r)",
                target_class,
                exc,
            )
        else:
            from ao_kernel.cost.routing import sort_providers_by_cost
            known_cost_sorted, _unknown = sort_providers_by_cost(
                provider_order=order,
                providers_map=providers,
                catalog=catalog,
            )
            if known_cost_sorted:
                order = known_cost_sorted

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
            **_c4_meta,
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
        **_c4_meta,
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
