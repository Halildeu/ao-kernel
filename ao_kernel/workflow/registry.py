"""Workflow definition registry.

Loads bundled (``ao_kernel.defaults.workflows``) and workspace
(``<workspace_root>/.ao/workflows``) workflow definition JSON files,
validates each against ``workflow-definition.schema.v1.json`` at load
boundary, and exposes lookup by ``(workflow_id, workflow_version)``.

Workspace > Bundled precedence applies ONLY for identical keys (same
workflow_id + workflow_version): workspace wins, bundled record is
skipped with ``reason="workspace_overrides_bundled"`` for audit.
Different versions from different sources both load; ``get(id,
version=None)`` returns the highest SemVer across sources (so bundled
1.0.0 beats workspace 0.9.0 by SemVer — explicit pin via ``version="0.9.0"``
is the documented way to choose a specific version).

SemVer comparison uses a local comparator (no new runtime dependency;
core dep remains ``jsonschema>=4.23.0``).

Cross-reference validation with the adapter manifest registry is
opt-in via ``validate_cross_refs``; returns a structured
``list[CrossRefIssue]`` so callers can choose between per-issue
logging, aggregate exception raise, or custom reporting.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal, Mapping

from jsonschema.validators import Draft202012Validator

from ao_kernel.workflow.errors import WorkflowDefinitionNotFoundError

# Forward reference — the adapters package defines AdapterRegistry; we
# avoid a hard import to keep the workflow package self-contained and
# allow independent testing. The type alias documents the expected
# shape without forcing an import cycle.
AdapterRegistryLike = Any


_SCHEMA_PACKAGE = "ao_kernel.defaults.schemas"
_SCHEMA_FILENAME = "workflow-definition.schema.v1.json"
_BUNDLED_WORKFLOWS_PACKAGE = "ao_kernel.defaults.workflows"


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepDefinition:
    """One step in a workflow definition. Immutable."""

    step_name: str
    actor: Literal["adapter", "ao-kernel", "human", "system"]
    adapter_id: str | None
    required_capabilities: tuple[str, ...]
    policy_refs: tuple[str, ...]
    on_failure: Literal[
        "transition_to_failed",
        "retry_once",
        "escalate_to_human",
    ]
    timeout_seconds: int | None
    human_interrupt_allowed: bool
    gate: str | None


@dataclass(frozen=True)
class WorkflowDefinition:
    """Parsed workflow definition. Immutable."""

    workflow_id: str
    workflow_version: str
    display_name: str
    description: str
    steps: tuple[StepDefinition, ...]
    expected_adapter_refs: tuple[str, ...]
    default_policy_refs: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    tags: tuple[str, ...]
    source: Literal["bundled", "workspace"]
    source_path: Path


@dataclass(frozen=True)
class CrossRefIssue:
    """Structured cross-reference violation between a workflow definition
    and an adapter manifest registry.

    ``kind`` distinguishes missing-adapter issues from capability-gap
    issues so callers can triage differently.
    """

    kind: Literal["missing_adapter", "capability_gap"]
    workflow_id: str
    step_name: str | None
    adapter_id: str
    missing_capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SkippedDefinition:
    """One workflow definition file that failed to load cleanly."""

    source_path: Path
    reason: Literal[
        "schema_invalid",
        "json_decode",
        "duplicate_workflow_key",
        "workspace_overrides_bundled",
        "read_error",
    ]
    details: str


@dataclass(frozen=True)
class LoadReport:
    """Outcome of a load pass: successful loads + skipped entries."""

    loaded: tuple[WorkflowDefinition, ...]
    skipped: tuple[SkippedDefinition, ...]


# ---------------------------------------------------------------------------
# Schema + validator caches
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _load_schema() -> Mapping[str, Any]:
    text = (
        resources.files(_SCHEMA_PACKAGE)
        .joinpath(_SCHEMA_FILENAME)
        .read_text(encoding="utf-8")
    )
    schema: Mapping[str, Any] = json.loads(text)
    return schema


@functools.lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema())


# ---------------------------------------------------------------------------
# SemVer comparator (local; no external dep)
# ---------------------------------------------------------------------------


def _parse_semver(ver: str) -> tuple[tuple[int, int, int], tuple[Any, ...]]:
    """Parse ``MAJOR.MINOR.PATCH[-pre][+build]`` into a sort key.

    Returns a tuple of ``((major, minor, patch), pre_release_key)`` where
    ``pre_release_key`` is ``(1,)`` for release versions (so they sort
    AFTER any pre-release with the same MAJOR.MINOR.PATCH) and a tuple
    of parsed pre-release segments otherwise.
    """
    core, _, build = ver.partition("+")
    core, _, pre = core.partition("-")
    major_s, minor_s, patch_s = core.split(".")
    base = (int(major_s), int(minor_s), int(patch_s))
    if pre == "":
        # Release versions sort above any pre-release at the same base.
        return base, (1,)
    # Each pre-release segment is compared numerically when numeric,
    # lexically otherwise; numeric beats alphanumeric at the same
    # position per SemVer 2.0.
    segments: list[tuple[int, Any]] = []
    for seg in pre.split("."):
        if seg.isdigit():
            segments.append((0, int(seg)))
        else:
            segments.append((1, seg))
    return base, (0,) + tuple(segments)


def _semver_sort_key(ver: str) -> tuple[Any, ...]:
    base, pre_key = _parse_semver(ver)
    return base + pre_key


# ---------------------------------------------------------------------------
# WorkflowRegistry
# ---------------------------------------------------------------------------


class WorkflowRegistry:
    """Index of workflow definitions keyed by ``(workflow_id, workflow_version)``."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], WorkflowDefinition] = {}

    # -- loading ------------------------------------------------------------

    def load_bundled(self) -> LoadReport:
        """Load every ``*.v1.json`` under ``ao_kernel/defaults/workflows/``."""
        loaded: list[WorkflowDefinition] = []
        skipped: list[SkippedDefinition] = []
        try:
            package_root = resources.files(_BUNDLED_WORKFLOWS_PACKAGE)
        except ModuleNotFoundError:
            return LoadReport(loaded=(), skipped=())
        for entry in sorted(package_root.iterdir(), key=lambda p: p.name):
            if not entry.name.endswith(".v1.json"):
                continue
            if not entry.is_file():
                continue
            source_path = Path(str(entry))
            self._ingest(
                source_path=source_path,
                source="bundled",
                loaded=loaded,
                skipped=skipped,
            )
        return LoadReport(loaded=tuple(loaded), skipped=tuple(skipped))

    def load_workspace(self, workspace_root: Path) -> LoadReport:
        """Load every ``*.v1.json`` under ``<workspace_root>/.ao/workflows/``."""
        loaded: list[WorkflowDefinition] = []
        skipped: list[SkippedDefinition] = []
        dir_path = workspace_root / ".ao" / "workflows"
        if not dir_path.is_dir():
            return LoadReport(loaded=(), skipped=())
        for source_path in sorted(dir_path.glob("*.v1.json")):
            self._ingest(
                source_path=source_path,
                source="workspace",
                loaded=loaded,
                skipped=skipped,
            )
        return LoadReport(loaded=tuple(loaded), skipped=tuple(skipped))

    def _ingest(
        self,
        *,
        source_path: Path,
        source: Literal["bundled", "workspace"],
        loaded: list[WorkflowDefinition],
        skipped: list[SkippedDefinition],
    ) -> None:
        try:
            text = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append(SkippedDefinition(
                source_path=source_path,
                reason="read_error",
                details=str(exc),
            ))
            return
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            skipped.append(SkippedDefinition(
                source_path=source_path,
                reason="json_decode",
                details=str(exc),
            ))
            return
        if not isinstance(raw, dict):
            skipped.append(SkippedDefinition(
                source_path=source_path,
                reason="schema_invalid",
                details="top-level value is not an object",
            ))
            return
        errors = list(_validator().iter_errors(raw))
        if errors:
            summary = "; ".join(
                f"{e.json_path}: {e.message}" for e in errors[:3]
            )
            if len(errors) > 3:
                summary += f" (+{len(errors) - 3} more)"
            skipped.append(SkippedDefinition(
                source_path=source_path,
                reason="schema_invalid",
                details=summary,
            ))
            return

        definition = _parse_definition(raw, source=source, source_path=source_path)
        key = (definition.workflow_id, definition.workflow_version)

        existing = self._by_key.get(key)
        if existing is not None:
            if existing.source == "bundled" and source == "workspace":
                # Workspace wins; drop the previously loaded bundled.
                self._by_key[key] = definition
                loaded.append(definition)
                # Record the demotion of the bundled record.
                skipped.append(SkippedDefinition(
                    source_path=existing.source_path,
                    reason="workspace_overrides_bundled",
                    details=(
                        f"workspace definition at {source_path} "
                        f"overrides bundled"
                    ),
                ))
                return
            if existing.source == "workspace" and source == "bundled":
                # Workspace already loaded wins; new bundled arrival
                # is skipped for audit.
                skipped.append(SkippedDefinition(
                    source_path=source_path,
                    reason="workspace_overrides_bundled",
                    details=(
                        f"bundled definition superseded by workspace at "
                        f"{existing.source_path}"
                    ),
                ))
                return
            # Same source + same key → genuine duplicate; reject the
            # second arrival so loads are deterministic.
            skipped.append(SkippedDefinition(
                source_path=source_path,
                reason="duplicate_workflow_key",
                details=(
                    f"duplicate (workflow_id={definition.workflow_id!r}, "
                    f"workflow_version={definition.workflow_version!r}) in "
                    f"{source}"
                ),
            ))
            return

        self._by_key[key] = definition
        loaded.append(definition)

    # -- lookup -------------------------------------------------------------

    def list_workflows(self) -> list[WorkflowDefinition]:
        return sorted(
            self._by_key.values(),
            key=lambda d: (d.workflow_id, _semver_sort_key(d.workflow_version)),
        )

    def get(
        self,
        workflow_id: str,
        *,
        version: str | None = None,
    ) -> WorkflowDefinition:
        """Return the workflow definition for ``workflow_id``.

        ``version=None`` → highest SemVer across bundled + workspace
        entries; source precedence applies ONLY when keys are
        identical. Explicit ``version`` returns that exact pin.
        """
        if version is not None:
            key = (workflow_id, version)
            definition = self._by_key.get(key)
            if definition is None:
                raise WorkflowDefinitionNotFoundError(
                    workflow_id=workflow_id, version=version,
                )
            return definition
        candidates = [
            defn for (wid, _), defn in self._by_key.items()
            if wid == workflow_id
        ]
        if not candidates:
            raise WorkflowDefinitionNotFoundError(
                workflow_id=workflow_id, version=None,
            )
        candidates.sort(key=lambda d: _semver_sort_key(d.workflow_version))
        return candidates[-1]

    # -- cross-reference validation ----------------------------------------

    def validate_cross_refs(
        self,
        definition: WorkflowDefinition,
        adapter_registry: AdapterRegistryLike,
    ) -> list[CrossRefIssue]:
        """Check every expected adapter + step binding resolves in the
        adapter registry. Returns an empty list when all references
        resolve and capabilities align; non-empty list otherwise.

        The adapter_registry argument must expose ``get(adapter_id)``
        returning an object with a ``capabilities`` frozenset (or
        raising ``AdapterManifestNotFoundError``) and
        ``missing_capabilities(adapter_id, required)`` returning a
        ``frozenset[str]`` gap set.
        """
        issues: list[CrossRefIssue] = []

        # Top-level expected adapter refs must all resolve.
        for expected_adapter_id in definition.expected_adapter_refs:
            try:
                adapter_registry.get(expected_adapter_id)
            except Exception:  # noqa: BLE001 - registry raises its own type
                issues.append(CrossRefIssue(
                    kind="missing_adapter",
                    workflow_id=definition.workflow_id,
                    step_name=None,
                    adapter_id=expected_adapter_id,
                ))

        # Per-step checks: adapter_id must resolve AND capabilities align.
        for step in definition.steps:
            if step.actor != "adapter":
                continue
            adapter_id = step.adapter_id
            if adapter_id is None:
                continue
            try:
                adapter_registry.get(adapter_id)
            except Exception:  # noqa: BLE001
                issues.append(CrossRefIssue(
                    kind="missing_adapter",
                    workflow_id=definition.workflow_id,
                    step_name=step.step_name,
                    adapter_id=adapter_id,
                ))
                continue
            if step.required_capabilities:
                gap = adapter_registry.missing_capabilities(
                    adapter_id, step.required_capabilities,
                )
                if gap:
                    issues.append(CrossRefIssue(
                        kind="capability_gap",
                        workflow_id=definition.workflow_id,
                        step_name=step.step_name,
                        adapter_id=adapter_id,
                        missing_capabilities=frozenset(gap),
                    ))
        return issues


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_definition(
    raw: Mapping[str, Any],
    *,
    source: Literal["bundled", "workspace"],
    source_path: Path,
) -> WorkflowDefinition:
    steps = tuple(_parse_step(s) for s in raw["steps"])
    return WorkflowDefinition(
        workflow_id=raw["workflow_id"],
        workflow_version=raw["workflow_version"],
        display_name=raw["display_name"],
        description=raw["description"],
        steps=steps,
        expected_adapter_refs=tuple(raw.get("expected_adapter_refs", ())),
        default_policy_refs=tuple(raw.get("default_policy_refs", ())),
        required_capabilities=tuple(raw.get("required_capabilities", ())),
        tags=tuple(raw.get("tags", ())),
        source=source,
        source_path=source_path,
    )


def _parse_step(raw: Mapping[str, Any]) -> StepDefinition:
    return StepDefinition(
        step_name=raw["step_name"],
        actor=raw["actor"],
        adapter_id=raw.get("adapter_id"),
        required_capabilities=tuple(raw.get("required_capabilities", ())),
        policy_refs=tuple(raw.get("policy_refs", ())),
        on_failure=raw["on_failure"],
        timeout_seconds=raw.get("timeout_seconds"),
        human_interrupt_allowed=bool(raw.get("human_interrupt_allowed", False)),
        gate=raw.get("gate"),
    )


__all__ = [
    "WorkflowDefinition",
    "StepDefinition",
    "CrossRefIssue",
    "SkippedDefinition",
    "LoadReport",
    "WorkflowRegistry",
]
