"""Per-surface smoke harness runner (V5 Epic 3 E-3-2).

`run_surface_smoke(surface_class, ...)` runs a library-mode, stub-adapter-only
smoke for one surface class under the dominant runtime kill-switch
(`killswitch.live_call_killswitch`) and emits a `support_widening_evidence.v1`
artifact (via the E-3-1 module) with `support_widening: false` in every emit path.

Stub adapters per surface are declared in `_SURFACE_STUBS`; each carries
`live_capability=False` (re-asserted at runtime, layer 3). The per-surface
evidence shape mirrors the E-3-1 `$defs` exactly so `recompute_v1` (which checks
`evidence_dimensions == recompute_inputs.raw_dimensions`) passes.

A registry + parametrized tests replace the plan's "one module + one test file
per surface class" literal: the five surfaces are near-identical stub shells, so a
registry is the DRY/maintainable form (CLAUDE.md long-term-durable-solution rule).
The per-surface behaviour is still fully covered — one parametrized test case per
surface class.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

__all__ = ["SURFACE_CLASSES", "run_surface_smoke"]

from ao_kernel._internal.support_widening.evidence import parse_v1
from ao_kernel.config import load_default

from .killswitch import SupportWideningError, assert_no_live_capability, live_call_killswitch


class _StubAdapter:
    """A surface stub that conforms to an adapter shape but makes no live call."""

    live_capability = False

    def __init__(self, surface_class: str, dimensions: dict[str, Any]) -> None:
        self.surface_class = surface_class
        self._dimensions = dimensions

    def evidence_dimensions(self) -> dict[str, Any]:
        return deepcopy(self._dimensions)


# Per-surface stub dimension builders (shapes mirror the E-3-1 $defs exactly).
_SURFACE_STUBS: dict[str, Callable[[], dict[str, Any]]] = {
    "provider": lambda: {
        "integration_tests": {"count": 0},
        "stub_adapter_ids": ["stub:provider"],
        "note": "library-mode stub smoke; no live integration tests (v2 requires >=3)",
    },
    "python_version": lambda: {"matrix": ["3.11", "3.12", "3.13"], "pytest_passed": True},
    "os_platform": lambda: {"platform": "linux-x86_64", "smoke_passed": True},
    "db_backend": lambda: {"backend": "sqlite_in_memory", "round_trip_passed": True},
    "deployment_topology": lambda: {"topology": "library", "isolation_passed": True},
}

SURFACE_CLASSES = tuple(_SURFACE_STUBS)


def run_surface_smoke(
    surface_class: str,
    *,
    repo: str = "Halildeu/ao-kernel",
    generated_at: str,
    evidence_out: Path | None = None,
) -> dict[str, Any]:
    """Run the stub smoke for one surface class and return a validated
    `support_widening_evidence.v1` payload (also written to `evidence_out` if given).

    Raises ``SupportWideningError`` for an unknown surface class or if the stub
    declares live capability; raises ``SupportWideningEvidenceError`` (from the
    E-3-1 module) if the emitted artifact is not schema-valid.
    """
    if surface_class not in _SURFACE_STUBS:
        raise SupportWideningError(f"unknown surface_class {surface_class!r}; expected one of {sorted(_SURFACE_STUBS)}")

    # Build the stub + run its dimension extraction under the kill-switch so any
    # accidental network/subprocess/secret-env access fails closed.
    with live_call_killswitch():
        stub = _StubAdapter(surface_class, _SURFACE_STUBS[surface_class]())
        assert_no_live_capability(stub)  # layer 3
        dimensions = stub.evidence_dimensions()

    payload: dict[str, Any] = {
        "schema_version": "support_widening_evidence.v1",
        "artifact_kind": "support_widening_evidence",
        "generated_at": generated_at,
        "repo": repo,
        "surface_class": surface_class,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
        "simulated_only": True,
        "live_call_made": False,
        "evidence_dimensions": dimensions,
        "reviewer_providers": [],
        "recompute_inputs": {"raw_dimensions": deepcopy(dimensions)},
    }

    # Fail closed if the artifact is not schema-valid (recompute-not-trust corollary).
    parse_v1(payload, schema=load_default("schemas", "support-widening-evidence.schema.v1.json"))

    if evidence_out is not None:
        # "No .ao/ mutation" contract: refuse to write the artifact into a workspace
        # `.ao/` directory (the harness is read-only w.r.t. the workspace).
        if any(part == ".ao" for part in evidence_out.parts):
            raise SupportWideningError(
                f"evidence_out must not be under a workspace .ao/ directory (read-only contract): {evidence_out}"
            )
        evidence_out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        # 0o600 owner-only (CodeQL py/overly-permissive-file). fchmod after open so
        # an overwrite of a pre-existing wider-mode file is also tightened (O_TRUNC
        # alone keeps the old mode).
        fd = os.open(evidence_out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, text.encode("utf-8"))
        finally:
            os.close(fd)

    return payload
