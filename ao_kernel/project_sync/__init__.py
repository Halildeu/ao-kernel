"""Public facade for the ``ao_kernel.project_sync`` package.

This package binds GitHub Projects v2 to repo-side projection manifests.
Tests + CLI consume the symbols re-exported here; downstream callers
should NOT import the implementation submodules directly.
"""

from __future__ import annotations

from ao_kernel.project_sync.derivers import (
    DerivedFields,
    FieldDeriver,
    derive_all_fields,
)
from ao_kernel.project_sync.drift_healer import (
    DriftFinding,
    DriftHealer,
    DriftReport,
)
from ao_kernel.project_sync.errors import (
    FieldDerivationError,
    GhCliNotAvailableError,
    ManifestDriftError,
    ProjectSyncError,
    ProjectV2APIError,
)
from ao_kernel.project_sync.issues import IssueClient, IssueRecord
from ao_kernel.project_sync.label_migrator import (
    LabelMigrator,
    MigrationEntry,
    MigrationReport,
)
from ao_kernel.project_sync.manifest import ProjectionManifest
from ao_kernel.project_sync.project_v2 import (
    ProjectField,
    ProjectFieldId,
    ProjectItemId,
    ProjectOptionId,
    ProjectV2Client,
)
from ao_kernel.project_sync.slice_adder import (
    AddSliceRequest,
    AddSliceResult,
    SliceAdder,
)

__all__ = [
    "AddSliceRequest",
    "AddSliceResult",
    "DerivedFields",
    "DriftFinding",
    "DriftHealer",
    "DriftReport",
    "FieldDerivationError",
    "FieldDeriver",
    "GhCliNotAvailableError",
    "IssueClient",
    "IssueRecord",
    "LabelMigrator",
    "ManifestDriftError",
    "MigrationEntry",
    "MigrationReport",
    "ProjectField",
    "ProjectFieldId",
    "ProjectItemId",
    "ProjectOptionId",
    "ProjectSyncError",
    "ProjectV2APIError",
    "ProjectV2Client",
    "ProjectionManifest",
    "SliceAdder",
    "derive_all_fields",
]
