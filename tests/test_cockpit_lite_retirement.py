"""Structural invariants enforcing the complete removal of the PRJ-UI-COCKPIT-LITE web UI.

The cockpit-lite extension manifest was retired earlier; this suite locks in the
removal of every remaining declarative cockpit-lite surface (launch profile,
execution app_id, system-status status object, retention globs, ui-snapshot
telemetry props) WITHOUT touching the generic `cockpit_sections` extension
vocabulary or the shared ui-snapshot-bundle schema.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from ao_kernel.extensions.loader import ExtensionRegistry

# Cockpit-lite-specific tokens that must NOT survive anywhere in bundled defaults.
FORBIDDEN_TOKENS = (
    "ao:cockpit-lite",
    "cockpit-serve",
    "cockpit-healthcheck",
    "cockpit_lite",
    "cockpit_decision",
    "last_cockpit_healthcheck_path",
    "cockpit_port",
    "last_cockpit_port",
    "cockpit_notes_count",
)

# ui-snapshot-bundle top-level props that were cockpit-lite snapshot leftovers.
REMOVED_UI_SNAPSHOT_PROPS = (
    "last_cockpit_healthcheck_path",
    "cockpit_port",
    "last_cockpit_port",
    "last_chat_log_path",
    "cockpit_notes_count",
    "last_note_id",
)


def _iter_strings(node: Any):
    """Yield every string scalar (keys and values) in a nested JSON structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _iter_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_strings(item)
    elif isinstance(node, str):
        yield node


def _find_all_keys(node: Any, target: str) -> bool:
    """True if `target` appears as a dict key anywhere in the structure."""
    if isinstance(node, dict):
        if target in node:
            return True
        return any(_find_all_keys(v, target) for v in node.values())
    if isinstance(node, list):
        return any(_find_all_keys(item, target) for item in node)
    return False


# ── REMOVAL invariants ──────────────────────────────────────────────────────


def test_apps_and_launch_registry_has_no_cockpit_lite_profile() -> None:
    registry = load_default("registry", "apps_and_launch_registry.v1.json")
    app_ids = [p.get("app_id") for p in registry.get("profiles", [])]
    assert "ao:cockpit-lite" not in app_ids


def test_active_execution_registry_has_no_cockpit_lite_app_id() -> None:
    registry = load_default("registry", "active_execution_registry.v1.json")
    assert "ao:cockpit-lite" not in list(_iter_strings(registry))


def test_policy_retention_has_no_cockpit_decision_globs() -> None:
    policy = load_default("policies", "policy_retention.v1.json")
    offenders = [s for s in _iter_strings(policy) if "cockpit_decision" in s]
    assert offenders == [], offenders


def test_system_status_schema_drops_cockpit_lite_surface() -> None:
    schema = load_default("schemas", "system-status.schema.json")
    assert not _find_all_keys(schema, "cockpit_lite")
    assert not _find_all_keys(schema, "last_cockpit_healthcheck_path")
    # No cockpit-lite operational token anywhere (keys or values).
    for token in ("cockpit_lite", "cockpit-healthcheck", "cockpit-serve"):
        assert all(token not in s for s in _iter_strings(schema)), token


def test_ui_snapshot_bundle_schema_drops_cockpit_lite_props() -> None:
    schema = load_default("schemas", "ui-snapshot-bundle.schema.v1.json")
    props = schema.get("properties", {})
    for prop in REMOVED_UI_SNAPSHOT_PROPS:
        assert prop not in props, prop


def test_no_cockpit_lite_token_survives_in_any_edited_default() -> None:
    for resource_type, filename in (
        ("registry", "apps_and_launch_registry.v1.json"),
        ("registry", "active_execution_registry.v1.json"),
        ("policies", "policy_retention.v1.json"),
        ("schemas", "system-status.schema.json"),
        ("schemas", "ui-snapshot-bundle.schema.v1.json"),
    ):
        data = load_default(resource_type, filename)
        strings = list(_iter_strings(data))
        for token in FORBIDDEN_TOKENS:
            assert all(token not in s for s in strings), f"{token} survives in {filename}"


# ── PRESERVATION invariants (do not over-remove) ────────────────────────────


def test_ui_snapshot_bundle_schema_is_still_loadable_and_shared() -> None:
    # The shared snapshot schema must survive (PRJ-DEPLOY uses it); only the
    # cockpit-lite props were removed, not the whole schema.
    schema = load_default("schemas", "ui-snapshot-bundle.schema.v1.json")
    assert schema.get("properties"), "ui-snapshot-bundle schema must retain its properties"

    reg = ExtensionRegistry()
    reg.load_from_defaults()
    deploy = reg.get("PRJ-DEPLOY")
    assert deploy is not None
    assert "ui-snapshot-bundle" in deploy.ui_surfaces


def test_generic_cockpit_sections_vocabulary_is_preserved() -> None:
    # The generic `cockpit_sections` entrypoint category is NOT cockpit-lite;
    # it is shared extension vocabulary and must remain.
    schema = load_default("schemas", "extension-manifest.schema.v1.json")
    assert _find_all_keys(schema, "cockpit_sections")


# ── NEGATIVE: old cockpit-lite payloads are rejected ────────────────────────


def test_ui_snapshot_bundle_rejects_removed_cockpit_prop() -> None:
    schema = load_default("schemas", "ui-snapshot-bundle.schema.v1.json")
    assert schema.get("additionalProperties") is False
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors({"last_cockpit_healthcheck_path": "x"}))
    assert errors, "schema must reject a removed cockpit-lite snapshot field"
