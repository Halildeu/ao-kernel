"""Tests for ao_kernel.project_sync.slice_adder.

The slice adder is the only place all three GitHub APIs cross. The stubs
mimic their public surface so we can verify atomic-call sequencing +
rollback without touching the network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ao_kernel.project_sync import (
    AddSliceRequest,
    AddSliceResult,
    IssueRecord,
    ProjectField,
    ProjectFieldId,
    ProjectItemId,
    ProjectOptionId,
    ProjectSyncError,
    ProjectV2APIError,
    ProjectionManifest,
    SliceAdder,
)


def _manifest(tmp_path: Path) -> ProjectionManifest:
    payload: dict[str, Any] = {
        "schema_version": "v5-issue-projection.v1",
        "runtime_created_state": {
            "project_board": {
                "number": 3,
                "node_id": "PVT_kwHOCx7tY84BZW65",
                "title": "Roadmap v5.0.0",
            },
            "milestone": {"title": "v5.0.0 — Full Production Promotion"},
            "issues_created": {},
        },
    }
    return ProjectionManifest(path=tmp_path / "m.json", payload=payload)


def _fields_map() -> dict[str, ProjectField]:
    return {
        "Epic": ProjectField(
            field_id=ProjectFieldId("epic_id"),
            name="Epic",
            data_type="SINGLE_SELECT",
            options={
                "1": ProjectOptionId("opt_epic_1"),
                "2": ProjectOptionId("opt_epic_2"),
                "P0": ProjectOptionId("opt_epic_p0"),
            },
        ),
        "Risk": ProjectField(
            field_id=ProjectFieldId("risk_id"),
            name="Risk",
            data_type="SINGLE_SELECT",
            options={
                "low": ProjectOptionId("opt_risk_low"),
                "normal": ProjectOptionId("opt_risk_normal"),
                "high": ProjectOptionId("opt_risk_high"),
                "critical": ProjectOptionId("opt_risk_critical"),
            },
        ),
        "Guard": ProjectField(
            field_id=ProjectFieldId("guard_id"),
            name="Guard",
            data_type="SINGLE_SELECT",
            options={
                "none": ProjectOptionId("opt_guard_none"),
                "live_adapter": ProjectOptionId("opt_guard_live"),
                "support_widening": ProjectOptionId("opt_guard_sw"),
                "production_platform_claim": ProjectOptionId("opt_guard_ppc"),
            },
        ),
        "Estimate": ProjectField(
            field_id=ProjectFieldId("est_id"),
            name="Estimate",
            data_type="NUMBER",
            options={},
        ),
        "Consensus": ProjectField(
            field_id=ProjectFieldId("cons_id"),
            name="Consensus",
            data_type="SINGLE_SELECT",
            options={
                "2-way": ProjectOptionId("opt_cons_2"),
                "3-way": ProjectOptionId("opt_cons_3"),
                "AGREE-merged": ProjectOptionId("opt_cons_agree"),
                "pending": ProjectOptionId("opt_cons_pending"),
            },
        ),
        "Evidence": ProjectField(
            field_id=ProjectFieldId("ev_id"),
            name="Evidence",
            data_type="TEXT",
            options={},
        ),
        "Mirror digest": ProjectField(
            field_id=ProjectFieldId("dig_id"),
            name="Mirror digest",
            data_type="TEXT",
            options={},
        ),
        "Release impact": ProjectField(
            field_id=ProjectFieldId("rel_id"),
            name="Release impact",
            data_type="SINGLE_SELECT",
            options={
                "patch": ProjectOptionId("opt_rel_patch"),
                "minor": ProjectOptionId("opt_rel_minor"),
                "major": ProjectOptionId("opt_rel_major"),
            },
        ),
    }


class StubProjectV2Client:
    def __init__(self, *, fail_on_set: bool = False) -> None:
        self.fields_calls: list[str] = []
        self.add_calls: list[tuple[str, str]] = []
        self.set_calls: list[tuple[str, str, str, Any]] = []
        self.delete_calls: list[tuple[str, str]] = []
        self.fail_on_set = fail_on_set
        self._next_item = 1
        self._fields_map = _fields_map()

    def fetch_fields(self, project_node_id: str) -> dict[str, ProjectField]:
        self.fields_calls.append(project_node_id)
        return self._fields_map

    def find_item_for_issue(self, project_node_id: str, issue_node_id: str) -> ProjectItemId | None:
        return None

    def add_issue_to_project(self, project_node_id: str, issue_node_id: str) -> ProjectItemId:
        self.add_calls.append((project_node_id, issue_node_id))
        item = ProjectItemId(f"item_{self._next_item}")
        self._next_item += 1
        return item

    def set_field_value(
        self,
        *,
        project_node_id: str,
        item_id: ProjectItemId,
        field: ProjectField,
        value: Any,
    ) -> None:
        if self.fail_on_set and field.name == "Estimate":
            raise ProjectV2APIError("simulated set failure")
        self.set_calls.append((project_node_id, item_id, field.name, value))

    def delete_item(self, project_node_id: str, item_id: ProjectItemId) -> None:
        self.delete_calls.append((project_node_id, item_id))


class StubIssueClient:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.run_calls: list[list[str]] = []
        self._next_number = 1000

    def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: list[str],
        milestone: str | None = None,
    ) -> IssueRecord:
        number = self._next_number
        self._next_number += 1
        record = IssueRecord(
            number=number,
            node_id=f"I_kw_{number}",
            title=title,
            body=body,
            labels=labels,
        )
        self.created.append({"title": title, "labels": labels, "milestone": milestone})
        return record

    def _run(self, args: list[str]) -> str:
        self.run_calls.append(args)
        return ""


def _request() -> AddSliceRequest:
    return AddSliceRequest(
        epic="1",
        slice_id="E-1-3",
        title="[Epic 1 | E-1-3] CI changelog enforcement",
        risk="normal",
        plan_ref=".claude/plans/E-1-3.md",
        consensus="2-way",
    )


def test_add_slice_atomic_happy_path(tmp_path: Path) -> None:
    """All three API calls succeed in order; result contains issue + fields."""
    issues_client = StubIssueClient()
    project_client = StubProjectV2Client()
    adder = SliceAdder(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    result = adder.add(_request())
    assert isinstance(result, AddSliceResult)
    assert len(issues_client.created) == 1
    assert len(project_client.add_calls) == 1
    assert "Epic" in result.fields_set
    assert "Risk" in result.fields_set
    assert "Estimate" in result.fields_set


def test_add_slice_dry_run_does_not_call_clients(tmp_path: Path) -> None:
    """Dry-run path stops before any mutation."""
    issues_client = StubIssueClient()
    project_client = StubProjectV2Client()
    adder = SliceAdder(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    result = adder.add(_request(), dry_run=True)
    assert issues_client.created == []
    assert project_client.add_calls == []
    assert project_client.set_calls == []
    assert "Epic" in result.fields_set


def test_add_slice_rollback_closes_issue_on_set_failure(tmp_path: Path) -> None:
    """If a field set call fails, the freshly created issue is closed."""
    issues_client = StubIssueClient()
    project_client = StubProjectV2Client(fail_on_set=True)
    adder = SliceAdder(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    with pytest.raises(ProjectV2APIError):
        adder.add(_request())
    # Rollback ran a `gh issue close ...` command via _run.
    assert any(args[:2] == ["issue", "close"] for args in issues_client.run_calls)


def test_add_slice_rollback_deletes_board_item_on_set_failure(tmp_path: Path) -> None:
    """Rollback also removes the partially-set board item (no lingering half-state)."""
    issues_client = StubIssueClient()
    project_client = StubProjectV2Client(fail_on_set=True)
    adder = SliceAdder(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    with pytest.raises(ProjectV2APIError):
        adder.add(_request())
    assert len(project_client.delete_calls) == 1
    project_id, item_id = project_client.delete_calls[0]
    assert project_id == "PVT_kwHOCx7tY84BZW65"
    assert item_id.startswith("item_")


def test_add_slice_refuses_when_manifest_lacks_project(tmp_path: Path) -> None:
    """No project_board node_id -> immediate ProjectSyncError."""
    manifest = ProjectionManifest(path=tmp_path / "m.json", payload={})
    adder = SliceAdder(
        issue_client=StubIssueClient(),
        project_client=StubProjectV2Client(),
        manifest=manifest,
    )
    with pytest.raises(ProjectSyncError) as exc_info:
        adder.add(_request())
    assert "project_board" in str(exc_info.value)


def test_add_slice_uses_estimate_override(tmp_path: Path) -> None:
    """estimate_days override beats the risk default mapping."""
    issues_client = StubIssueClient()
    project_client = StubProjectV2Client()
    adder = SliceAdder(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    request = AddSliceRequest(
        epic="1",
        slice_id="E-1-3",
        title="t",
        risk="low",
        plan_ref="x",
        consensus="2-way",
        estimate_days=7.5,
    )
    adder.add(request)
    estimate_calls = [v for *_, name, v in project_client.set_calls if name == "Estimate"]
    assert estimate_calls == [7.5]


def test_add_slice_body_depends_round_trips_through_deriver(tmp_path: Path) -> None:
    """Body emitted by AddSliceRequest.to_body() parses back into the deriver.

    The earlier regex assumed plain ``Depends on #N`` and missed the
    markdown bold + comma-list format the body actually emits. This test
    pins the round-trip so a future format tweak cannot silently break
    dependency derivation.
    """
    from ao_kernel.project_sync import FieldDeriver

    request = AddSliceRequest(
        epic="1",
        slice_id="E-1-3",
        title="t",
        risk="normal",
        plan_ref="x",
        consensus="2-way",
        depends_on=[774, 775],
    )
    body = request.to_body()
    deriver = FieldDeriver()
    assert deriver.derive_dependency(body) == "#774,#775"
