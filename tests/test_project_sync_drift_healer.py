"""Tests for ao_kernel.project_sync.drift_healer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ao_kernel.project_sync import (
    DriftHealer,
    DriftReport,
    IssueRecord,
    ManifestDriftError,
    ProjectField,
    ProjectFieldId,
    ProjectItemId,
    ProjectOptionId,
    ProjectionManifest,
)


def _manifest(tmp_path: Path) -> ProjectionManifest:
    return ProjectionManifest(
        path=tmp_path / "m.json",
        payload={
            "runtime_created_state": {
                "project_board": {
                    "number": 3,
                    "node_id": "PVT_X",
                }
            }
        },
    )


def _fields() -> dict[str, ProjectField]:
    return {
        "Epic": ProjectField(
            field_id=ProjectFieldId("ep"),
            name="Epic",
            data_type="SINGLE_SELECT",
            options={"1": ProjectOptionId("o1"), "2": ProjectOptionId("o2")},
        ),
        "Risk": ProjectField(
            field_id=ProjectFieldId("rk"),
            name="Risk",
            data_type="SINGLE_SELECT",
            options={
                "high": ProjectOptionId("rh"),
                "normal": ProjectOptionId("rn"),
            },
        ),
        "Guard": ProjectField(
            field_id=ProjectFieldId("gr"),
            name="Guard",
            data_type="SINGLE_SELECT",
            options={
                "none": ProjectOptionId("gn"),
                "live_adapter": ProjectOptionId("gl"),
            },
        ),
    }


class StubProjectClient:
    def __init__(self, *, item_id: ProjectItemId | None, actual: dict[str, str]) -> None:
        self._item_id = item_id
        self._actual = actual
        self.set_calls: list[tuple[str, Any]] = []

    def fetch_fields(self, project_node_id: str) -> dict[str, ProjectField]:
        return _fields()

    def find_item_for_issue(self, project_node_id: str, issue_node_id: str) -> ProjectItemId | None:
        return self._item_id

    def add_issue_to_project(self, project_node_id: str, issue_node_id: str) -> ProjectItemId:
        new_id = ProjectItemId("new_item")
        self._item_id = new_id
        return new_id

    def fetch_field_values(self, project_node_id: str, item_id: ProjectItemId) -> dict[str, str]:
        return dict(self._actual)

    def set_field_value(self, *, project_node_id: str, item_id: ProjectItemId, field: ProjectField, value: Any) -> None:
        self.set_calls.append((field.name, value))
        self._actual[field.name] = str(value)


class StubIssueClient:
    pass


def _issues() -> list[IssueRecord]:
    return [
        IssueRecord(
            number=1,
            node_id="I_1",
            title="t1",
            body="",
            labels=["epic-1", "risk:high", "guard-flip:live_adapter"],
        )
    ]


def test_drift_check_no_drift_when_actual_matches_expected(tmp_path: Path) -> None:
    """Matching state -> empty findings."""
    client = StubProjectClient(
        item_id=ProjectItemId("item_1"),
        actual={"Epic": "1", "Risk": "high", "Guard": "live_adapter"},
    )
    healer = DriftHealer(
        issue_client=StubIssueClient(),
        project_client=client,
        manifest=_manifest(tmp_path),
    )
    report = healer.check(_issues())
    assert isinstance(report, DriftReport)
    assert report.findings == []


def test_drift_check_detects_field_mismatch(tmp_path: Path) -> None:
    """Different value -> mismatch finding."""
    client = StubProjectClient(
        item_id=ProjectItemId("item_1"),
        actual={"Epic": "2", "Risk": "high", "Guard": "live_adapter"},
    )
    healer = DriftHealer(
        issue_client=StubIssueClient(),
        project_client=client,
        manifest=_manifest(tmp_path),
    )
    report = healer.check(_issues())
    mismatch = [f for f in report.findings if f.field_name == "Epic"]
    assert len(mismatch) == 1
    assert mismatch[0].expected == "1"
    assert mismatch[0].actual == "2"
    assert mismatch[0].kind == "mismatch"


def test_drift_check_detects_missing_item(tmp_path: Path) -> None:
    """Issue not on board -> every expected field surfaces as missing."""
    client = StubProjectClient(item_id=None, actual={})
    healer = DriftHealer(
        issue_client=StubIssueClient(),
        project_client=client,
        manifest=_manifest(tmp_path),
    )
    report = healer.check(_issues())
    kinds = {f.kind for f in report.findings}
    assert kinds == {"missing"}
    assert len(report.findings) >= 3  # Epic + Risk + Guard


def test_drift_check_strict_raises_after_full_scan(tmp_path: Path) -> None:
    """strict=True raises ManifestDriftError after collecting findings."""
    client = StubProjectClient(item_id=None, actual={})
    healer = DriftHealer(
        issue_client=StubIssueClient(),
        project_client=client,
        manifest=_manifest(tmp_path),
    )
    with pytest.raises(ManifestDriftError) as exc_info:
        healer.check(_issues(), strict=True)
    assert "drift finding" in str(exc_info.value)


def test_drift_heal_brings_state_into_line_idempotently(tmp_path: Path) -> None:
    """heal() fixes drift; a second call sees no remaining findings."""
    client = StubProjectClient(
        item_id=ProjectItemId("item_1"),
        actual={"Epic": "2", "Risk": "normal", "Guard": "none"},
    )
    healer = DriftHealer(
        issue_client=StubIssueClient(),
        project_client=client,
        manifest=_manifest(tmp_path),
    )
    first = healer.heal(_issues())
    assert len(first.healed) >= 3
    second = healer.check(_issues())
    assert second.findings == []


def test_drift_values_match_does_not_numeric_coerce_text_fields() -> None:
    """Type-aware: 'high' vs '1' on a SINGLE_SELECT must stay mismatch.

    Earlier _values_match coerced via float() unconditionally, so two
    string values that happened to parse as numbers would be treated as
    equal even on a SINGLE_SELECT or TEXT field. The fix only coerces
    when the field is NUMBER.
    """
    assert DriftHealer._values_match("high", "1", data_type="SINGLE_SELECT") is False
    assert DriftHealer._values_match("1", "1.0", data_type="NUMBER") is True
    assert DriftHealer._values_match("1.5", "2", data_type="NUMBER") is False
    assert DriftHealer._values_match("alpha", "alpha", data_type="TEXT") is True
