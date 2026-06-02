"""Drift detection + heal loop between manifest and GitHub state.

The healer is pure-Python over fetched data. Strict mode raises
:class:`ManifestDriftError` so CI workflows can wire the exit code, while
heal mode shells back through the injected ``SliceAdder``-style helpers
to bring GitHub in line with the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ao_kernel.project_sync.derivers import (
    DerivedFields,
    FieldDeriver,
    derive_all_fields,
)
from ao_kernel.project_sync.errors import ManifestDriftError
from ao_kernel.project_sync.issues import IssueClient, IssueRecord
from ao_kernel.project_sync.manifest import ProjectionManifest
from ao_kernel.project_sync.project_v2 import (
    ProjectField,
    ProjectV2Client,
)


@dataclass(frozen=True)
class DriftFinding:
    """A single drift entry."""

    issue_number: int
    field_name: str
    expected: str
    actual: str
    kind: str  # "missing", "mismatch", "extra"


@dataclass(frozen=True)
class DriftReport:
    """Aggregate drift report for the sync surface.

    ``healed`` lists field/value pairs the healer mutated (empty in
    check-only mode). ``warnings`` collects deriver warnings encountered
    while normalising each issue.
    """

    findings: list[DriftFinding] = field(default_factory=list)
    healed: list[DriftFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.findings)


class DriftHealer:
    """Compares per-issue expected derivation vs project board state.

    Construction is deliberately wide: callers pass the clients + manifest
    + the list of issues to scan. The healer never goes hunting for issues
    on its own — that's the sync surface's job.
    """

    def __init__(
        self,
        *,
        issue_client: IssueClient,
        project_client: ProjectV2Client,
        manifest: ProjectionManifest,
        deriver: FieldDeriver | None = None,
    ) -> None:
        self._issues = issue_client
        self._project = project_client
        self._manifest = manifest
        self._deriver = deriver or FieldDeriver()

    def check(
        self,
        issues: Iterable[IssueRecord],
        *,
        strict: bool = False,
    ) -> DriftReport:
        """Check drift without mutating GitHub state.

        ``strict=True`` raises :class:`ManifestDriftError` after the full
        scan so callers see every finding before the error fires.
        """
        report = self._scan(issues)
        if strict and report.has_drift:
            raise ManifestDriftError(f"{len(report.findings)} drift finding(s); first: {report.findings[0]}")
        return report

    def heal(self, issues: Iterable[IssueRecord]) -> DriftReport:
        """Bring GitHub in line with manifest-derived expectations."""
        report = self._scan(issues)
        if not report.has_drift:
            return report
        project_node_id = self._manifest.project_node_id()
        if project_node_id is None:
            return report
        fields_map = self._project.fetch_fields(project_node_id)
        healed: list[DriftFinding] = []
        for finding in report.findings:
            field_obj = fields_map.get(finding.field_name)
            if field_obj is None:
                # Field isn't even present on the board — out of healer
                # scope; manifest projection bootstrap owns those.
                continue
            issue_record = next((i for i in issues if i.number == finding.issue_number), None)
            if issue_record is None:
                continue
            item_id = self._project.find_item_for_issue(project_node_id, issue_record.node_id)
            if item_id is None:
                item_id = self._project.add_issue_to_project(project_node_id, issue_record.node_id)
            value: str | float = finding.expected
            if field_obj.data_type.upper() == "NUMBER":
                try:
                    value = float(finding.expected)
                except ValueError:
                    continue
            self._project.set_field_value(
                project_node_id=project_node_id,
                item_id=item_id,
                field=field_obj,
                value=value,
            )
            healed.append(finding)
        return DriftReport(
            findings=report.findings,
            healed=healed,
            warnings=report.warnings,
        )

    def _scan(self, issues: Iterable[IssueRecord]) -> DriftReport:
        project_node_id = self._manifest.project_node_id()
        findings: list[DriftFinding] = []
        warnings: list[str] = []
        if project_node_id is None:
            return DriftReport(findings=findings, warnings=warnings)
        fields_map = self._project.fetch_fields(project_node_id)
        for issue in issues:
            try:
                derived = derive_all_fields(
                    issue,
                    deriver=self._deriver,
                    require_epic=False,
                    require_risk=False,
                )
            except Exception:  # noqa: BLE001 - deriver errors become per-issue findings
                warnings.append(f"derive_failed:{issue.number}")
                continue
            warnings.extend(f"{issue.number}:{w}" for w in derived.warnings)
            item_id = self._project.find_item_for_issue(project_node_id, issue.node_id)
            actual: dict[str, str] = {}
            if item_id is not None:
                actual = self._project.fetch_field_values(project_node_id, item_id)
            findings.extend(self._compare(issue, derived, fields_map, actual, has_item=item_id is not None))
        return DriftReport(findings=findings, warnings=warnings)

    def _compare(
        self,
        issue: IssueRecord,
        derived: DerivedFields,
        fields_map: dict[str, ProjectField],
        actual: dict[str, str],
        *,
        has_item: bool,
    ) -> list[DriftFinding]:
        expected: dict[str, str] = {}
        if derived.epic is not None and "Epic" in fields_map:
            expected["Epic"] = derived.epic
        if derived.risk is not None and "Risk" in fields_map:
            expected["Risk"] = derived.risk
        if "Guard" in fields_map:
            expected["Guard"] = derived.guard
        if derived.dependency is not None and "Dependency" in fields_map:
            expected["Dependency"] = derived.dependency
        if derived.estimate is not None and "Estimate" in fields_map:
            expected["Estimate"] = str(derived.estimate)
        if derived.release_impact is not None and "Release impact" in fields_map:
            expected["Release impact"] = derived.release_impact
        findings: list[DriftFinding] = []
        for name, value in expected.items():
            if not has_item:
                findings.append(
                    DriftFinding(
                        issue_number=issue.number,
                        field_name=name,
                        expected=value,
                        actual="",
                        kind="missing",
                    )
                )
                continue
            current = actual.get(name)
            if current is None:
                findings.append(
                    DriftFinding(
                        issue_number=issue.number,
                        field_name=name,
                        expected=value,
                        actual="",
                        kind="missing",
                    )
                )
            elif not self._values_match(current, value):
                findings.append(
                    DriftFinding(
                        issue_number=issue.number,
                        field_name=name,
                        expected=value,
                        actual=current,
                        kind="mismatch",
                    )
                )
        return findings

    @staticmethod
    def _values_match(actual: str, expected: str) -> bool:
        """Loose comparison for numeric/string fields.

        Numbers come back as ``"1.0"`` while expected is often ``"1"``;
        coerce both to float when both parse.
        """
        if actual == expected:
            return True
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
