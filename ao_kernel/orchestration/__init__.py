"""AO-MA-3 — Local orchestrator package.

This package implements the read-only local orchestrator from the AO-MA
multi-agent execution model (`AO-MA-1` §8 slice AO-MA-3). It reads SSOT
(`AGENTS.md`, `gpp_status.v1.json`) and a user goal, builds a task graph,
assigns disjoint write scopes to bounded agent slots, and emits no-secret
artifacts (`task_graph.v1`, `agent_assignment.v1`, `manifest.v1`).

This package deliberately does NOT:

- spawn any agent (LLM call, subprocess, worker)
- mutate git state, branch protection, or the GPP `support_widening` /
  `production_platform_claim` / `live_adapter_execution` guard flags
- post to GitHub (no Checks API write, no PR review submission)
- read or transmit any secret material

Worker spawning is the next slice (AO-MA-4). Reviewer loop is AO-MA-6.
Verifier is AO-MA-7.

Public API:

- :class:`Orchestrator` — high-level entrypoint
- :func:`build_task_graph` — task graph builder
- :class:`RiskClassifier` — path → risk class heuristic
- :class:`ArtifactWriter` — JSON write + SHA256 manifest
- :class:`OrchestrationError` — explicit fail-closed surface
"""

from __future__ import annotations

from ao_kernel.orchestration.artifact_writer import ArtifactWriter
from ao_kernel.orchestration.orchestrator import (
    Orchestrator,
    OrchestrationError,
    SSOTPaths,
)
from ao_kernel.orchestration.risk_classifier import RiskClassifier
from ao_kernel.orchestration.task_graph_builder import build_task_graph

__all__ = [
    "ArtifactWriter",
    "OrchestrationError",
    "Orchestrator",
    "RiskClassifier",
    "SSOTPaths",
    "build_task_graph",
]
