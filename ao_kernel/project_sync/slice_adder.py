"""Atomic add-slice flow: create issue + add to board + set fields.

Slice addition is the only mutation path that crosses three GitHub APIs
(issues, project items, item field values). This module sequences the
calls and rolls back the partially-applied state on failure so manifests
never see an item with half-set fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ao_kernel.project_sync.derivers import (
    DerivedFields,
    FieldDeriver,
    derive_all_fields,
)
from ao_kernel.project_sync.errors import ProjectSyncError, ProjectV2APIError
from ao_kernel.project_sync.issues import IssueClient, IssueRecord
from ao_kernel.project_sync.manifest import ProjectionManifest
from ao_kernel.project_sync.project_v2 import (
    ProjectField,
    ProjectItemId,
    ProjectV2Client,
)

_GUARD_FLAGS = ("live_adapter", "support_widening", "production_platform_claim")


@dataclass(frozen=True)
class AddSliceRequest:
    """Caller-supplied input for ``SliceAdder.add``.

    ``consensus`` is exposed as a string so the CLI surface keeps the
    operator's exact wording (``2-way`` / ``3-way`` / ``AGREE-merged``).
    """

    epic: str
    slice_id: str
    title: str
    risk: str
    plan_ref: str
    consensus: str
    guard: str = "none"
    depends_on: list[int] = field(default_factory=list)
    estimate_days: float | None = None
    body_extra: str = ""

    def to_labels(self) -> list[str]:
        labels = [
            f"epic-{self.epic.lower()}" if self.epic.lower() != "p0" else "epic-p0",
            f"risk:{self.risk.lower()}",
            "status:planned",
            "mirror:authority",
        ]
        if self.guard != "none":
            labels.append(f"guard-flip:{self.guard}")
        return labels

    def to_body(self) -> str:
        depends_clause = ""
        if self.depends_on:
            joined = ", ".join(f"#{n}" for n in self.depends_on)
            depends_clause = f"\n\n**Depends on** {joined}\n"
        guard_pinning = "\n".join(f"- {flag} (const false until operator flip)" for flag in _GUARD_FLAGS)
        return (
            f"<!-- AO-MA-SPM mirror; manifest-bound slice {self.slice_id} -->\n"
            f"## Slice {self.slice_id}\n\n"
            f"**Epic:** {self.epic}\n"
            f"**Risk:** {self.risk}\n"
            f"**Consensus:** {self.consensus}\n"
            f"**Authority artifact:** `{self.plan_ref}`\n"
            f"\n### Guard flag invariants\n{guard_pinning}\n"
            f"{depends_clause}"
            f"{self.body_extra}".rstrip()
            + "\n"
        )


@dataclass(frozen=True)
class AddSliceResult:
    """Outcome of a successful add-slice call.

    Drift checkers persist this back to the manifest so subsequent runs
    treat the slice as already-bound.
    """

    issue: IssueRecord
    item_id: ProjectItemId
    derived: DerivedFields
    fields_set: list[str]
    manifest_digest: str


class SliceAdder:
    """Atomic slice creation with rollback.

    The clients are injected so tests can hand stubs in. The public
    surface is intentionally narrow: callers call :py:meth:`add` once and
    receive either a fully-bound :class:`AddSliceResult` or an exception
    (with side-effects rolled back as far as the GitHub API allows).
    """

    def __init__(
        self,
        *,
        issue_client: IssueClient,
        project_client: ProjectV2Client,
        manifest: ProjectionManifest,
    ) -> None:
        self._issues = issue_client
        self._project = project_client
        self._manifest = manifest

    def add(self, request: AddSliceRequest, *, dry_run: bool = False) -> AddSliceResult:
        project_node_id = self._manifest.project_node_id()
        if project_node_id is None:
            raise ProjectSyncError("manifest has no runtime project_board.node_id; run mirror creation first")
        fields_map = self._project.fetch_fields(project_node_id)
        if dry_run:
            stub_issue = IssueRecord(
                number=0,
                node_id="dry-run",
                title=request.title,
                body=request.to_body(),
                labels=request.to_labels(),
            )
            derived = derive_all_fields(stub_issue, deriver=FieldDeriver())
            return AddSliceResult(
                issue=stub_issue,
                item_id=ProjectItemId("dry-run"),
                derived=derived,
                fields_set=sorted(self._planned_fields(fields_map, derived, request)),
                manifest_digest=self._manifest.digest(),
            )
        issue = self._issues.create_issue(
            title=request.title,
            body=request.to_body(),
            labels=request.to_labels(),
            milestone=self._milestone_title(),
        )
        derived = derive_all_fields(issue, deriver=FieldDeriver())
        item_id: ProjectItemId | None = None
        try:
            item_id = self._project.add_issue_to_project(project_node_id, issue.node_id)
            fields_set = self._apply_fields(
                project_node_id=project_node_id,
                item_id=item_id,
                fields_map=fields_map,
                derived=derived,
                request=request,
            )
        except (ProjectV2APIError, ProjectSyncError) as exc:
            self._rollback(
                issue,
                project_node_id=project_node_id,
                item_id=item_id,
                reason=str(exc),
            )
            raise
        return AddSliceResult(
            issue=issue,
            item_id=item_id,
            derived=derived,
            fields_set=fields_set,
            manifest_digest=self._manifest.digest(),
        )

    def _planned_fields(
        self,
        fields_map: dict[str, ProjectField],
        derived: DerivedFields,
        request: AddSliceRequest,
    ) -> list[str]:
        planned: list[str] = []
        plan = self._planned_field_values(fields_map, derived, request)
        planned.extend(name for name, _ in plan)
        return planned

    def _planned_field_values(
        self,
        fields_map: dict[str, ProjectField],
        derived: DerivedFields,
        request: AddSliceRequest,
    ) -> list[tuple[str, Any]]:
        """Compose (field_name, value) pairs to apply.

        Centralised so dry-run and real apply paths cannot drift.
        """
        plan: list[tuple[str, Any]] = []
        if "Epic" in fields_map and derived.epic is not None:
            plan.append(("Epic", derived.epic))
        if "Risk" in fields_map and derived.risk is not None:
            plan.append(("Risk", derived.risk))
        if "Guard" in fields_map:
            plan.append(("Guard", derived.guard))
        if "Dependency" in fields_map and derived.dependency:
            plan.append(("Dependency", derived.dependency))
        if "Estimate" in fields_map:
            estimate = request.estimate_days if request.estimate_days is not None else derived.estimate
            if estimate is not None:
                plan.append(("Estimate", estimate))
        if "Consensus" in fields_map:
            plan.append(("Consensus", request.consensus))
        if "Evidence" in fields_map:
            plan.append(("Evidence", request.plan_ref))
        if "Mirror digest" in fields_map:
            plan.append(("Mirror digest", self._manifest.digest()))
        if "Release impact" in fields_map and derived.release_impact is not None:
            plan.append(("Release impact", derived.release_impact))
        return plan

    def _apply_fields(
        self,
        *,
        project_node_id: str,
        item_id: ProjectItemId,
        fields_map: dict[str, ProjectField],
        derived: DerivedFields,
        request: AddSliceRequest,
    ) -> list[str]:
        applied: list[str] = []
        for name, value in self._planned_field_values(fields_map, derived, request):
            field_obj = fields_map[name]
            self._project.set_field_value(
                project_node_id=project_node_id,
                item_id=item_id,
                field=field_obj,
                value=value,
            )
            applied.append(name)
        return applied

    def _rollback(
        self,
        issue: IssueRecord,
        *,
        project_node_id: str,
        item_id: ProjectItemId | None,
        reason: str,
    ) -> None:
        """Best-effort rollback after a partial failure.

        Two ordered steps so the board never lingers in a half-set state:

        1. If the board item was created before the failure, delete it
           via ``deleteProjectV2Item`` so partially-applied field values
           do not linger on the project.
        2. Close the freshly created issue with a comment pointing at the
           failure reason. Leaving the issue open would make follow-up
           runs attempt to re-create it; closing keeps the audit trail
           intact.

        Each step is wrapped in its own try/except — a failure in step 1
        must not prevent step 2 from running, and any rollback exception
        is swallowed so the caller still surfaces the original error.
        """
        if item_id is not None:
            try:
                self._project.delete_item(project_node_id, item_id)
            except (ProjectV2APIError, Exception):  # noqa: BLE001 - rollback is best-effort
                # Item deletion failure surfaces only as audit noise; the
                # original add-slice error is still propagated by the
                # caller.
                pass
        try:
            self._issues._run(
                [
                    "issue",
                    "close",
                    str(issue.number),
                    "--comment",
                    f"Auto-closed by ao-kernel project add-slice rollback: {reason}",
                ]
            )
        except ProjectV2APIError:
            # rollback is best-effort; surface the original error instead.
            return

    def _milestone_title(self) -> str | None:
        runtime = self._manifest.payload.get("runtime_created_state")
        if not isinstance(runtime, dict):
            return None
        milestone = runtime.get("milestone")
        if not isinstance(milestone, dict):
            return None
        title = milestone.get("title")
        return title if isinstance(title, str) else None
