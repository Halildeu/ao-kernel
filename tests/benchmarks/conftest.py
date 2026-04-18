"""Shared fixtures for PR-B7 benchmarks.

`--benchmark-mode` flag intentionally NOT exposed — fast mode is
the only mode B7 ships (full real-adapter mode deferred to B7.1
per plan v5 §7).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


_BUNDLED_ROOT = Path(__file__).resolve().parents[2] / "ao_kernel" / "defaults"


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Materialise a tmp workspace with `.ao/` skeleton + bundled
    policies + bundled workflows copied in so the driver /
    governance path has a real filesystem to read from."""
    ws = tmp_path / "ws"
    (ws / ".ao" / "policies").mkdir(parents=True, exist_ok=True)
    (ws / ".ao" / "workflows").mkdir(parents=True, exist_ok=True)
    (ws / ".ao" / "adapters").mkdir(parents=True, exist_ok=True)
    (ws / ".ao" / "evidence" / "workflows").mkdir(parents=True, exist_ok=True)

    # Copy bundled policies so `governance.check_policy` resolves
    # via workspace override (the loader falls back to bundled
    # anyway, but some scenarios parametrise a local copy).
    for policy in (_BUNDLED_ROOT / "policies").glob("policy_*.v1.json"):
        shutil.copy2(policy, ws / ".ao" / "policies" / policy.name)
    for workflow in (_BUNDLED_ROOT / "workflows").glob("*.v1.json"):
        shutil.copy2(workflow, ws / ".ao" / "workflows" / workflow.name)
    for adapter in (_BUNDLED_ROOT / "adapters").glob("*.manifest.v1.json"):
        shutil.copy2(adapter, ws / ".ao" / "adapters" / adapter.name)
    return ws


@pytest.fixture
def seeded_budget() -> dict[str, dict[str, float]]:
    """Canonical budget axes the benchmark runs assume.

    Returned as a plain dict so callers pass it through to
    `run_store.create_run(..., budget=...)` exactly as received.
    """
    return {
        "cost_usd": {"limit": 10.0, "consumed": 0.0, "remaining": 10.0},
        "tokens": {"limit": 50_000.0, "consumed": 0.0, "remaining": 50_000.0},
        "time_seconds": {
            "limit": 600.0,
            "consumed": 0.0,
            "remaining": 600.0,
        },
    }


@pytest.fixture
def bundled_adapter_registry(workspace_root: Path):
    """Adapter registry populated with bundled + workspace manifests.

    Taken BEFORE any purity context would apply (simulator-style
    guard not active in benchmarks) — but the resulting snapshot
    is the same shape policy_sim uses: `{adapter_id: manifest}`.
    """
    from ao_kernel.adapters import AdapterRegistry

    reg = AdapterRegistry()
    reg.load_bundled()
    try:
        reg.load_workspace(workspace_root)
    except Exception:
        # Workspace adapters optional; the bundled set covers
        # `codex-stub` + `gh-cli-pr` used by both scenarios.
        pass
    return reg


@pytest.fixture
def write_adapter_override(workspace_root: Path):
    """Factory fixture — writes an override manifest JSON into
    `<ws>/.ao/adapters/`. Useful when a scenario needs a relaxed
    or altered adapter contract without editing bundled defaults."""

    def _writer(filename: str, manifest: dict) -> Path:
        path = workspace_root / ".ao" / "adapters" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    return _writer
