"""AO-MA-3 task graph builder.

Pure-Python deterministic task graph + agent assignment construction.

Codex iter-1 absorb (thread 019e6645):

- Deterministic ``task_graph_id`` (hash-based) so same goal + base_sha +
  declared paths + UTC day → same id
- Conservative default: if no ``declared_paths`` are provided, emit a SINGLE
  task covering "operator-declared scope unknown" — do NOT invent paths or
  slices from free-form goal text
- Overlap fail-closed: two tasks may not share a write path
- ``base_sha`` is a 40-char git SHA; orchestrator caller resolves it
- All artifacts are AO-MA-2 schema valid; guard flags forced to ``false``
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from ao_kernel.orchestration.risk_classifier import RiskClass, RiskClassifier

_TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,80}$")
_BRANCH_PREFIX = "codex/ao-ma"  # AO-MA-2 schema branch pattern: ^(codex|agent)/...
_ALLOWED_ASSIGNMENT_AGENT_KINDS = ("ai", "human")
_AGENT_PROVIDER_DEFAULT = "claude"
_AGENT_PROVIDER_VALID = ("anthropic", "openai", "google", "xai")


class TaskGraphBuilderError(RuntimeError):
    """Raised when the task graph cannot be built fail-closed."""


@dataclass(frozen=True)
class TaskSpec:
    """One bounded slice declaration consumed by the builder."""

    task_id: str
    description: str
    write_paths: list[str]
    depends_on: list[str] = field(default_factory=list)


@dataclass
class BuildResult:
    """Output of :func:`build_task_graph`."""

    task_graph: dict[str, Any]
    assignments: list[dict[str, Any]]


def deterministic_task_graph_id(
    goal: str,
    base_sha: str,
    declared_paths: list[str] | None,
    *,
    utc_now: _dt.datetime | None = None,
) -> str:
    """Return a reproducible ``task_graph_id``.

    Pattern: ``ao-ma-<yyyymmdd>-<sha7>`` where sha7 is the first 7 hex chars
    of ``sha256(goal_normalized + base_sha + sorted_paths)``. Same inputs on
    the same UTC day → same id.
    """

    now = utc_now or _dt.datetime.now(_dt.UTC)
    yyyymmdd = now.strftime("%Y%m%d")
    goal_normalized = " ".join(goal.strip().split())
    sorted_paths = sorted(declared_paths or [])
    payload = "\n".join(
        [
            goal_normalized,
            base_sha,
            *sorted_paths,
        ]
    ).encode("utf-8")
    sha7 = hashlib.sha256(payload).hexdigest()[:7]
    return f"ao-ma-{yyyymmdd}-{sha7}"


def _branch_for(task_graph_id: str, task_id: str) -> str:
    """Build a worker branch name that matches the AO-MA-2 schema pattern."""

    return f"{_BRANCH_PREFIX}-{task_graph_id}/{task_id}"


def _worktree_for(task_graph_id: str, task_id: str) -> str:
    """Default worktree path for a worker. AO-MA-4 may override at runtime."""

    return f".ao/orchestration/{task_graph_id}/workers/{task_id}"


def _guard_flags() -> dict[str, bool]:
    """Return the canonical closed-guard flags AO-MA-3 must always emit."""

    return {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }


def _normalize_paths(paths: list[str]) -> list[str]:
    """Sort + dedupe paths preserving original strings (no path-rewrite)."""

    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return sorted(out)


def _validate_task_ids(specs: list[TaskSpec]) -> None:
    """Ensure task ids match the schema pattern and are unique."""

    seen: set[str] = set()
    for spec in specs:
        if not _TASK_ID_PATTERN.match(spec.task_id):
            raise TaskGraphBuilderError(f"task id {spec.task_id!r} does not match ^[a-z0-9][a-z0-9-]{{2,80}}$")
        if spec.task_id in seen:
            raise TaskGraphBuilderError(f"duplicate task id {spec.task_id!r}")
        seen.add(spec.task_id)


def _check_overlap_fail_closed(specs: list[TaskSpec]) -> None:
    """Reject any two tasks that declare the same write path."""

    seen_path_to_task: dict[str, str] = {}
    for spec in specs:
        for path in spec.write_paths:
            owner = seen_path_to_task.get(path)
            if owner is not None and owner != spec.task_id:
                raise TaskGraphBuilderError(
                    f"ao_ma_3_worker_overlap_detected: path {path!r} claimed by both {owner!r} and {spec.task_id!r}"
                )
            seen_path_to_task[path] = spec.task_id


def _check_dependency_targets(specs: list[TaskSpec]) -> None:
    """Ensure every depends_on entry refers to a declared task id."""

    ids = {spec.task_id for spec in specs}
    for spec in specs:
        for dep in spec.depends_on:
            if dep not in ids:
                raise TaskGraphBuilderError(f"task {spec.task_id!r} depends on unknown task {dep!r}")


def build_task_graph(
    goal: str,
    base_sha: str,
    *,
    repo: str,
    base_ref: str = "refs/heads/main",
    declared_specs: list[TaskSpec] | None = None,
    utc_now: _dt.datetime | None = None,
    agent_label: str = _AGENT_PROVIDER_DEFAULT,
    agent_provider: str = "anthropic",
) -> BuildResult:
    """Build a deterministic task graph + agent assignments.

    Conservative default per Codex iter-1: when ``declared_specs`` is None
    or empty, emit a single low-risk task with no declared write set so the
    orchestrator never invents paths from free-form goal text.
    """

    if not isinstance(goal, str) or not goal.strip():
        raise TaskGraphBuilderError("goal must be a non-empty string")
    if not isinstance(base_sha, str) or len(base_sha) != 40 or not all(c in "0123456789abcdef" for c in base_sha):
        raise TaskGraphBuilderError("base_sha must be a 40-char lowercase hex git SHA")
    if not isinstance(repo, str) or not repo.strip():
        raise TaskGraphBuilderError("repo must be a non-empty string")
    if agent_provider not in _AGENT_PROVIDER_VALID:
        raise TaskGraphBuilderError(f"agent_provider {agent_provider!r} must be one of {_AGENT_PROVIDER_VALID}")

    declared_paths_for_id = [path for spec in (declared_specs or []) for path in spec.write_paths]
    task_graph_id = deterministic_task_graph_id(
        goal,
        base_sha,
        declared_paths_for_id,
        utc_now=utc_now,
    )

    if declared_specs:
        specs = [
            TaskSpec(
                task_id=spec.task_id,
                description=spec.description,
                write_paths=_normalize_paths(spec.write_paths),
                depends_on=list(spec.depends_on),
            )
            for spec in declared_specs
        ]
        _validate_task_ids(specs)
        _check_overlap_fail_closed(specs)
        _check_dependency_targets(specs)
    else:
        # Conservative default: single task, no write set declared.
        specs = [
            TaskSpec(
                task_id="task-001-operator-scope-unknown",
                description=(
                    "Operator did not declare per-slice write scopes. "
                    "Treat the goal as a single conservative task; "
                    "AO-MA-4 must require an explicit write set before "
                    "spawning a worker."
                ),
                write_paths=[],
                depends_on=[],
            )
        ]

    all_paths_for_risk = [path for spec in specs for path in spec.write_paths]
    risk_class: RiskClass = RiskClassifier.classify(all_paths_for_risk)
    max_parallel = min(max(len(specs), 1), 20)

    task_graph = {
        "schema_version": "ao-ma-task-graph.v1",
        "task_graph_id": task_graph_id,
        "repo": repo,
        "goal": goal,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "risk_class": risk_class,
        "max_parallel_workers": max_parallel,
        "tasks": [
            {
                "task_id": spec.task_id,
                "title": spec.description[:120] or f"Slice {spec.task_id}",
                "agent_type": "implementer",
                "declared_write_set": spec.write_paths,
                "dependency_ids": spec.depends_on,
                "acceptance_criteria": [
                    "all_declared_files_modified_or_explicitly_skipped",
                    "tests_pass_locally",
                    "no_secret_material_committed",
                    "guard_flags_remain_closed",
                ],
                "high_risk": RiskClassifier.classify(spec.write_paths) in ("high", "critical"),
            }
            for spec in specs
        ],
        "fan_in_policy": {
            "mode": "all_required",
            "required_task_ids": [spec.task_id for spec in specs],
            "conflict_owner": "integrator",
        },
        "review_policy": {
            "required_reviewers": 2 if risk_class in ("high", "critical") else 1,
            "cross_provider_required": True,
            "consensus_required_for_high_risk": True,
            "max_revise_rounds": 3,
        },
        "guard_flags": _guard_flags(),
    }

    assignments = [
        {
            "schema_version": "ao-ma-agent-assignment.v1",
            "assignment_id": f"{task_graph_id}-{spec.task_id}",
            "task_graph_id": task_graph_id,
            "task_id": spec.task_id,
            "agent": {
                "agent_id": _agent_id_for(agent_label, spec.task_id),
                "agent_type": "implementer",
                "provider": agent_provider,
                "session_id": f"ao-ma-3-orchestrator-{task_graph_id}",
            },
            "base_ref": base_ref,
            "base_sha": base_sha,
            "branch": _branch_for(task_graph_id, spec.task_id),
            "worktree": _worktree_for(task_graph_id, spec.task_id),
            "declared_write_set": spec.write_paths,
            "expected_output_artifact": "worker_result.v1",
            "status": "pending",
            "guard_flags": _guard_flags(),
        }
        for spec in specs
    ]

    return BuildResult(task_graph=task_graph, assignments=assignments)


def _agent_id_for(label: str, task_id: str) -> str:
    """Build a schema-valid agent id (pattern: ^[a-z0-9][a-z0-9._-]{1,80}$)."""

    raw = f"{label}-{task_id}".lower()
    # Replace anything outside [a-z0-9._-] with '-'
    safe = "".join(c if c.isalnum() or c in "._-" else "-" for c in raw)
    return safe[:80]
