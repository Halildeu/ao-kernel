"""Migrate convention labels into project fields, then drop the labels.

V5 used labels (``epic-*``, ``risk:*``, ``guard-flip:*``, ``status:*``) as
the carrier for slice metadata. With custom fields now wired, those labels
duplicate state. The migrator copies each label's information into the
matching project field on every issue, then removes the label.

Cross-cutting labels (``mirror:authority``, ``area:*``, ``type:*``) are
preserved — only convention labels that map to fields are dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ao_kernel.project_sync.derivers import (
    DerivedFields,
    FieldDeriver,
    derive_all_fields,
)
from ao_kernel.project_sync.errors import ProjectSyncError
from ao_kernel.project_sync.issues import IssueClient, IssueRecord
from ao_kernel.project_sync.manifest import ProjectionManifest
from ao_kernel.project_sync.project_v2 import (
    ProjectField,
    ProjectV2Client,
)

# Labels managed by the migrator. Anything outside this set is preserved.
_MIGRATABLE_LABEL_PREFIXES = ("epic-", "risk:", "guard-flip:", "status:")


@dataclass(frozen=True)
class MigrationEntry:
    """One label → field migration per issue."""

    issue_number: int
    label: str
    target_field: str
    target_value: str
    dropped: bool


@dataclass(frozen=True)
class MigrationReport:
    """Aggregate migration outcome."""

    entries: list[MigrationEntry] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def dropped_count(self) -> int:
        return sum(1 for entry in self.entries if entry.dropped)


class LabelMigrator:
    """Drive the label → field migration with safety rails.

    The migrator never drops a label until it has confirmed via a fresh
    GraphQL fetch that the field is set on the project board. This is the
    "verify before drop" rule operators asked for.
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

    def migrate(
        self,
        issues: Iterable[IssueRecord],
        *,
        dry_run: bool = True,
    ) -> MigrationReport:
        project_node_id = self._manifest.project_node_id()
        if project_node_id is None:
            raise ProjectSyncError("manifest has no runtime project_board.node_id; run mirror creation first")
        fields_map = self._project.fetch_fields(project_node_id)
        entries: list[MigrationEntry] = []
        warnings: list[str] = []
        skipped: list[str] = []
        for issue in issues:
            migratable_labels = [
                lbl for lbl in issue.labels if any(lbl.startswith(p) for p in _MIGRATABLE_LABEL_PREFIXES)
            ]
            if not migratable_labels:
                continue
            try:
                derived = derive_all_fields(
                    issue,
                    deriver=self._deriver,
                    require_epic=False,
                    require_risk=False,
                )
            except Exception:  # noqa: BLE001 - per-issue derive failures stay non-fatal
                warnings.append(f"derive_failed:{issue.number}")
                continue
            issue_entries = self._process_issue(
                issue=issue,
                derived=derived,
                migratable_labels=migratable_labels,
                fields_map=fields_map,
                project_node_id=project_node_id,
                dry_run=dry_run,
                warnings=warnings,
                skipped=skipped,
            )
            entries.extend(issue_entries)
        return MigrationReport(entries=entries, skipped=skipped, warnings=warnings)

    def _process_issue(
        self,
        *,
        issue: IssueRecord,
        derived: DerivedFields,
        migratable_labels: list[str],
        fields_map: dict[str, ProjectField],
        project_node_id: str,
        dry_run: bool,
        warnings: list[str],
        skipped: list[str],
    ) -> list[MigrationEntry]:
        entries: list[MigrationEntry] = []
        item_id = self._project.find_item_for_issue(project_node_id, issue.node_id)
        actual: dict[str, str] = {}
        if item_id is not None:
            actual = self._project.fetch_field_values(project_node_id, item_id)
        for label in migratable_labels:
            target_field, target_value = self._label_target(label, derived)
            if target_field is None or target_value is None:
                skipped.append(f"{issue.number}:{label}:no_target")
                continue
            field_obj = fields_map.get(target_field)
            if field_obj is None:
                skipped.append(f"{issue.number}:{label}:field_absent")
                continue
            current = actual.get(target_field)
            if current is None or not self._values_match(current, target_value):
                # Field not yet at the target — refuse to drop until set.
                skipped.append(f"{issue.number}:{label}:field_not_set")
                continue
            if dry_run:
                entries.append(
                    MigrationEntry(
                        issue_number=issue.number,
                        label=label,
                        target_field=target_field,
                        target_value=target_value,
                        dropped=False,
                    )
                )
                continue
            try:
                self._issues.remove_label(issue.number, label)
            except Exception as exc:  # noqa: BLE001 - per-label rollback friendly
                warnings.append(f"{issue.number}:{label}:remove_failed:{exc}")
                continue
            entries.append(
                MigrationEntry(
                    issue_number=issue.number,
                    label=label,
                    target_field=target_field,
                    target_value=target_value,
                    dropped=True,
                )
            )
        return entries

    def _label_target(
        self,
        label: str,
        derived: DerivedFields,
    ) -> tuple[str | None, str | None]:
        if label.startswith("epic-"):
            return "Epic", derived.epic
        if label.startswith("risk:"):
            return "Risk", derived.risk
        if label.startswith("guard-flip:"):
            return "Guard", derived.guard
        if label.startswith("status:"):
            # Status maps to the built-in Status field; the manifest treats
            # it as a kanban column, not a custom field. We still surface
            # it as an entry so the operator can audit the cleanup.
            return "Status", derived.status
        return None, None

    @staticmethod
    def _values_match(actual: str, expected: str) -> bool:
        if actual == expected:
            return True
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
