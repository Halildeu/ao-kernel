"""Minimum runtime-backed handlers for PRJ-KERNEL-API.

This module intentionally promotes only the bounded, read-only tranche:
``system_status`` and ``doc_nav_check``. Wider project/roadmap actions stay
deferred until their workspace and write-side contracts are explicit.
"""

from __future__ import annotations

from typing import Any

import ao_kernel

from ao_kernel.extensions.loader import ExtensionRegistry

EXTENSION_ID = "PRJ-KERNEL-API"
SUPPORTED_ACTIONS = ("system_status", "doc_nav_check")
DEFERRED_ACTIONS = ("project_status", "roadmap_follow", "roadmap_finish")


def _truth_payload() -> dict[str, Any]:
    registry = ExtensionRegistry()
    registry.load_from_defaults()
    summary = registry.truth_summary()
    return {
        "total_extensions": summary.total_extensions,
        "runtime_backed": summary.runtime_backed,
        "contract_only": summary.contract_only,
        "quarantined": summary.quarantined,
        "remap_candidate_refs": summary.remap_candidate_refs,
        "missing_runtime_refs": summary.missing_runtime_refs,
        "runtime_backed_ids": list(summary.runtime_backed_ids),
        "quarantined_ids": list(summary.quarantined_ids),
    }


def _extension_payload() -> dict[str, Any]:
    registry = ExtensionRegistry()
    registry.load_from_defaults()
    manifest = registry.get(EXTENSION_ID)
    if manifest is None:
        return {
            "extension_id": EXTENSION_ID,
            "present": False,
            "truth_tier": "missing",
            "runtime_handler_registered": False,
            "missing_runtime_refs": [],
            "remap_candidate_refs": [],
            "kernel_api_actions": [],
        }
    return {
        "extension_id": manifest.extension_id,
        "present": True,
        "truth_tier": manifest.truth_tier,
        "runtime_handler_registered": manifest.runtime_handler_registered,
        "missing_runtime_refs": list(manifest.missing_runtime_refs),
        "remap_candidate_refs": list(manifest.remap_candidate_refs),
        "kernel_api_actions": list(manifest.entrypoints.get("kernel_api_actions", [])),
    }


def _envelope(action: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "action": action,
        "extension_id": EXTENSION_ID,
        "result": result,
    }


def system_status(params: dict[str, Any]) -> dict[str, Any]:
    """Return a read-only runtime truth snapshot for the installed package."""
    return _envelope(
        "system_status",
        {
            "version": ao_kernel.__version__,
            "supported_actions": list(SUPPORTED_ACTIONS),
            "deferred_actions": list(DEFERRED_ACTIONS),
            "extension_truth": _truth_payload(),
            "params_echo": {
                key: params[key]
                for key in sorted(params)
                if key in {"detail", "request_id"}
            },
        },
    )


def doc_nav_check(params: dict[str, Any]) -> dict[str, Any]:
    """Return the package-local manifest/ref truth used by doctor audit."""
    return _envelope(
        "doc_nav_check",
        {
            "extension": _extension_payload(),
            "supported_actions": list(SUPPORTED_ACTIONS),
            "deferred_actions": list(DEFERRED_ACTIONS),
            "network_required": False,
            "workspace_write": False,
            "params_echo": {
                key: params[key]
                for key in sorted(params)
                if key in {"detail", "request_id"}
            },
        },
    )


def register(registry: Any) -> None:
    """Register the bounded PRJ-KERNEL-API action tranche."""
    registry.register("system_status", system_status, extension_id=EXTENSION_ID)
    registry.register("doc_nav_check", doc_nav_check, extension_id=EXTENSION_ID)
