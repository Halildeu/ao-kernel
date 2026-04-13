"""ao_kernel.policy — Public policy management facade.

Clean import path for policy operations.

Usage:
    from ao_kernel.policy import check, load, list_policies
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def check(
    policy_name: str,
    action: dict[str, Any],
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Check an action against a policy. Fail-closed.

    Supports: autonomy, tool_calling, provider guardrails, generic rules.
    Returns {allowed, decision, reason_codes, policy_ref, data}.
    """
    from ao_kernel.governance import check_policy
    return check_policy(policy_name, action, workspace=workspace)


def load(policy_name: str, *, workspace: Path | None = None) -> dict[str, Any]:
    """Load a policy by name. Workspace override > bundled default."""
    from ao_kernel.config import load_with_override
    return load_with_override("policies", policy_name, workspace=workspace)


def list_policies() -> list[str]:
    """List all bundled policy filenames."""
    from importlib.resources import files
    policies_pkg = files("ao_kernel.defaults.policies")
    return sorted(
        item.name for item in policies_pkg.iterdir()
        if item.name.endswith(".json") and not item.name.startswith("_")
    )


__all__ = ["check", "load", "list_policies"]
