"""Tests for ao_kernel.project_sync.label_migrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ao_kernel.project_sync import (
    IssueRecord,
    LabelMigrator,
    MigrationReport,
    ProjectField,
    ProjectFieldId,
    ProjectItemId,
    ProjectOptionId,
    ProjectionManifest,
)


def _manifest(tmp_path: Path) -> ProjectionManifest:
    return ProjectionManifest(
        path=tmp_path / "m.json",
        payload={"runtime_created_state": {"project_board": {"node_id": "PVT_X", "number": 3}}},
    )


def _fields() -> dict[str, ProjectField]:
    return {
        "Epic": ProjectField(
            field_id=ProjectFieldId("ep"),
            name="Epic",
            data_type="SINGLE_SELECT",
            options={"1": ProjectOptionId("o1")},
        ),
        "Risk": ProjectField(
            field_id=ProjectFieldId("rk"),
            name="Risk",
            data_type="SINGLE_SELECT",
            options={"high": ProjectOptionId("rh")},
        ),
        "Guard": ProjectField(
            field_id=ProjectFieldId("gr"),
            name="Guard",
            data_type="SINGLE_SELECT",
            options={"none": ProjectOptionId("gn"), "live_adapter": ProjectOptionId("gl")},
        ),
        "Status": ProjectField(
            field_id=ProjectFieldId("st"),
            name="Status",
            data_type="SINGLE_SELECT",
            options={"in_progress": ProjectOptionId("si")},
        ),
    }


class StubProjectClient:
    def __init__(
        self,
        *,
        actual: dict[str, str],
        on_fetch_clear: set[str] | None = None,
    ) -> None:
        self._actual = dict(actual)
        self._on_fetch_clear = on_fetch_clear or set()
        self._fetch_calls = 0

    def fetch_fields(self, project_node_id: str) -> dict[str, ProjectField]:
        return _fields()

    def find_item_for_issue(self, project_node_id: str, issue_node_id: str) -> ProjectItemId | None:
        return ProjectItemId("item_1")

    def fetch_field_values(self, project_node_id: str, item_id: ProjectItemId) -> dict[str, str]:
        self._fetch_calls += 1
        snapshot = dict(self._actual)
        # Simulate concurrent mutation between the first fetch (used for
        # planning) and the second fetch (TOCTOU re-verify): on call N>=2
        # the named fields disappear from the actual state.
        if self._fetch_calls >= 2:
            for name in self._on_fetch_clear:
                self._actual.pop(name, None)
        return snapshot if self._fetch_calls == 1 else dict(self._actual)

    def set_field_value(self, *, project_node_id: str, item_id: ProjectItemId, field: ProjectField, value: Any) -> None:
        # Migrator should not invoke this — fields are already verified set.
        raise AssertionError("LabelMigrator must not mutate project fields")


class StubIssueClient:
    def __init__(self) -> None:
        self.removed: list[tuple[int, str]] = []

    def remove_label(self, number: int, label: str) -> None:
        self.removed.append((number, label))


def _issue() -> IssueRecord:
    return IssueRecord(
        number=42,
        node_id="I_42",
        title="t",
        body="",
        labels=[
            "epic-1",
            "risk:high",
            "guard-flip:live_adapter",
            "status:in_progress",
            "mirror:authority",
            "area:gitops",
        ],
    )


def test_label_cleanup_dry_run_reports_but_does_not_drop(tmp_path: Path) -> None:
    """Dry-run path records entries but issues no remove_label calls."""
    project_client = StubProjectClient(
        actual={
            "Epic": "1",
            "Risk": "high",
            "Guard": "live_adapter",
            "Status": "in_progress",
        }
    )
    issues_client = StubIssueClient()
    migrator = LabelMigrator(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    report = migrator.migrate([_issue()], dry_run=True)
    assert isinstance(report, MigrationReport)
    assert len(report.entries) == 4
    assert report.dropped_count == 0
    assert issues_client.removed == []


def test_label_cleanup_drops_labels_when_field_already_set(tmp_path: Path) -> None:
    """Apply mode removes each migratable label after verifying the field."""
    project_client = StubProjectClient(
        actual={
            "Epic": "1",
            "Risk": "high",
            "Guard": "live_adapter",
            "Status": "in_progress",
        }
    )
    issues_client = StubIssueClient()
    migrator = LabelMigrator(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    report = migrator.migrate([_issue()], dry_run=False)
    assert report.dropped_count == 4
    dropped_labels = {label for _, label in issues_client.removed}
    assert "epic-1" in dropped_labels
    assert "risk:high" in dropped_labels
    assert "guard-flip:live_adapter" in dropped_labels
    assert "status:in_progress" in dropped_labels
    # Cross-cutting labels are preserved.
    assert ("mirror:authority" not in dropped_labels) is True
    assert ("area:gitops" not in dropped_labels) is True


def test_label_cleanup_refuses_to_drop_when_field_unset(tmp_path: Path) -> None:
    """If a field isn't set yet, the label is kept and skipped is logged."""
    project_client = StubProjectClient(actual={})  # no fields set on board
    issues_client = StubIssueClient()
    migrator = LabelMigrator(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    report = migrator.migrate([_issue()], dry_run=False)
    assert issues_client.removed == []
    assert report.dropped_count == 0
    assert any("field_not_set" in entry for entry in report.skipped)


def test_label_cleanup_no_migratable_labels_returns_empty_report(tmp_path: Path) -> None:
    """Issues with only cross-cutting labels produce no entries."""
    issue = IssueRecord(number=1, node_id="I_1", title="t", body="", labels=["mirror:authority"])
    project_client = StubProjectClient(actual={})
    issues_client = StubIssueClient()
    migrator = LabelMigrator(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    report = migrator.migrate([issue], dry_run=False)
    assert report.entries == []
    assert report.skipped == []


def test_label_cleanup_refuses_drop_when_field_cleared_at_toctou(tmp_path: Path) -> None:
    """If the field disappears between planning and drop, skip the label.

    The migrator's TOCTOU re-verify must catch the case where another
    agent unsets the field between the first fetch (planning) and the
    second fetch (right before remove_label). Without that re-verify,
    the label would be dropped while the field is gone — silent data
    loss.
    """
    project_client = StubProjectClient(
        actual={
            "Epic": "1",
            "Risk": "high",
            "Guard": "live_adapter",
            "Status": "in_progress",
        },
        on_fetch_clear={"Risk"},  # Risk vanishes on the second fetch.
    )
    issues_client = StubIssueClient()
    migrator = LabelMigrator(
        issue_client=issues_client,
        project_client=project_client,
        manifest=_manifest(tmp_path),
    )
    report = migrator.migrate([_issue()], dry_run=False)
    removed_labels = {label for _, label in issues_client.removed}
    assert "risk:high" not in removed_labels
    assert any("field_unset_at_drop_time" in entry for entry in report.skipped)
