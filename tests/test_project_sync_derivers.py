"""Tests for ao_kernel.project_sync.derivers."""

from __future__ import annotations

import pytest

from ao_kernel.project_sync import (
    DerivedFields,
    FieldDerivationError,
    FieldDeriver,
    IssueRecord,
    derive_all_fields,
)


def _issue(
    *,
    number: int = 42,
    title: str = "[Epic 1 | E-1-3] do the thing",
    body: str = "",
    labels: list[str] | None = None,
) -> IssueRecord:
    return IssueRecord(
        number=number,
        node_id="I_kw",
        title=title,
        body=body,
        labels=labels or [],
    )


def test_derive_epic_from_label() -> None:
    """epic-1 / epic-p0 / epic-9 all resolve to the right Epic option."""
    deriver = FieldDeriver()
    assert deriver.derive_epic(["epic-1"]) == "1"
    assert deriver.derive_epic(["epic-p0"]) == "P0"
    assert deriver.derive_epic(["epic-9", "other"]) == "9"
    assert deriver.derive_epic(["not-an-epic"]) is None


def test_derive_risk_from_label() -> None:
    """risk:critical/high/normal/low all return the lowercase enum."""
    deriver = FieldDeriver()
    assert deriver.derive_risk(["risk:critical"]) == "critical"
    assert deriver.derive_risk(["risk:high"]) == "high"
    assert deriver.derive_risk(["risk:normal"]) == "normal"
    assert deriver.derive_risk(["risk:low"]) == "low"
    assert deriver.derive_risk(["risk:weird"]) is None


def test_derive_guard_defaults_to_none() -> None:
    """No guard-flip:* label -> 'none' (not None)."""
    deriver = FieldDeriver()
    assert deriver.derive_guard([]) == "none"
    assert deriver.derive_guard(["guard-flip:live_adapter"]) == "live_adapter"
    assert deriver.derive_guard(["guard-flip:support_widening"]) == "support_widening"
    assert deriver.derive_guard(["guard-flip:production_platform_claim"]) == "production_platform_claim"


def test_derive_dependency_from_body_collects_multiple_refs() -> None:
    """Multiple 'Depends on #N' / 'Blocked by #M' refs become a comma list."""
    deriver = FieldDeriver()
    body = "## Scope\n\nDepends on #774. Blocked by #775. Depends on #774 again."
    assert deriver.derive_dependency(body) == "#774,#775"


def test_derive_dependency_returns_none_when_absent() -> None:
    """Empty body -> no dependency derived."""
    deriver = FieldDeriver()
    assert deriver.derive_dependency("") is None
    assert deriver.derive_dependency("no dependency anchor here") is None


def test_derive_estimate_uses_risk_default_map() -> None:
    """Risk -> Estimate mapping: low=1, normal=2, high=5, critical=10."""
    deriver = FieldDeriver()
    assert deriver.derive_estimate("low") == 1.0
    assert deriver.derive_estimate("normal") == 2.0
    assert deriver.derive_estimate("high") == 5.0
    assert deriver.derive_estimate("critical") == 10.0
    assert deriver.derive_estimate(None) is None


def test_derive_release_impact_maps_risk() -> None:
    """Risk -> Release impact: low/normal=patch, high=minor, critical=major."""
    deriver = FieldDeriver()
    assert deriver.derive_release_impact("low") == "patch"
    assert deriver.derive_release_impact("normal") == "patch"
    assert deriver.derive_release_impact("high") == "minor"
    assert deriver.derive_release_impact("critical") == "major"


def test_derive_all_fields_happy_path() -> None:
    """All four convention labels resolve together."""
    issue = _issue(
        labels=["epic-1", "risk:high", "guard-flip:live_adapter", "status:in_progress"],
        body="Depends on #774",
    )
    result = derive_all_fields(issue)
    assert isinstance(result, DerivedFields)
    assert result.epic == "1"
    assert result.risk == "high"
    assert result.guard == "live_adapter"
    assert result.estimate == 5.0
    assert result.release_impact == "minor"
    assert result.status == "in_progress"
    assert result.dependency == "#774"


def test_derive_all_fields_requires_epic_label() -> None:
    """Missing epic-* label raises FieldDerivationError by default."""
    issue = _issue(labels=["risk:high"])
    with pytest.raises(FieldDerivationError) as exc_info:
        derive_all_fields(issue)
    assert "epic-" in str(exc_info.value)


def test_derive_all_fields_optional_when_require_false() -> None:
    """Caller can disable epic/risk requirement (drift healer path)."""
    issue = _issue(labels=[])
    result = derive_all_fields(issue, require_epic=False, require_risk=False)
    assert result.epic is None
    assert result.risk is None
    assert "epic_label_missing" in result.warnings
    assert "risk_label_missing" in result.warnings


def test_derive_kanban_column_maps_status_to_column_name() -> None:
    """status:in_progress -> 'In Progress' kanban column."""
    deriver = FieldDeriver()
    assert deriver.derive_kanban_column("planned") == "Todo"
    assert deriver.derive_kanban_column("in_progress") == "In Progress"
    assert deriver.derive_kanban_column("review") == "Review"
    assert deriver.derive_kanban_column("blocked") == "Blocked"
    assert deriver.derive_kanban_column("done") == "Done"
    assert deriver.derive_kanban_column(None) is None
