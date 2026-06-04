"""AO-MA-11E-2a — Generic GitHub mirror drift checker (read-only).

Compares actual GitHub mirror state (Milestone + Issues + Project items) against
a projection manifest's expected state. Pure stdlib core; network access via
dependency-injected `gh_api_caller` callable.

Disiplin (HARD RULE pinned):
- No `import requests`/`httpx`/`urllib`/`subprocess`/`gh` in this module.
- `gh_api_caller(method, path)` callable injected by CLI layer (testlerde mock).
- Token value NEVER appears in DriftReport (only env-var name + boolean presence).
- All semantic drift is fail-closed (exit_decision != "synced"); severity tier
  is for report ergonomics only and does NOT change exit behavior.

Public API:
    check_github_mirror_drift(...) -> DriftReport
    DriftReport (dataclass) / DriftFinding (dataclass) / ExitDecision (Enum)
    parse_issue_anchor(body: str) -> AnchorParseResult (strict markdown parser)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# --- Public types ---------------------------------------------------------------


class ExitDecision(str, Enum):
    """Top-level decision driving CLI exit code."""

    SYNCED = "synced"
    MIRROR_DRIFT_DETECTED = "mirror_drift_detected"
    NETWORK_NOT_ALLOWED = "network_not_allowed"
    API_ERROR = "api_error"
    USAGE_ERROR = "usage_error"


# Drift categories (exhaustive enum mirrored in schema):
_DRIFT_CATEGORIES = frozenset(
    {
        "missing_milestone",
        "milestone_metadata_mismatch",
        "missing_issue",
        "extra_issue",
        "label_mismatch",
        "anchor_mismatch",
        "anchor_schema_mismatch",
        "anchor_sha_format_invalid",
        "anchor_placeholder_unresolved",
        "project_missing",
        "project_item_count_mismatch",
        "project_item_url_mismatch",
    }
)

_ANCHOR_REQUIRED_FIELDS = (
    "spm_anchor",
    "slice_id",
    "ao_authority_artifact",
    "artifact_sha256",
    "plan_digest",
)
_ANCHOR_KNOWN_OPTIONAL_FIELDS = (
    "risk_class_source",
    "evidence_classes",
    "consensus_state",
)
_ANCHOR_KNOWN_FIELDS = frozenset(
    (*_ANCHOR_REQUIRED_FIELDS, *_ANCHOR_KNOWN_OPTIONAL_FIELDS)
)

_SHA_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_PLACEHOLDER_PATTERN = re.compile(r"^\{[^}]+\}$")


@dataclass
class DriftFinding:
    """Single drift entry; serializes to schema's `drift[]` item."""

    category: str
    severity: str  # "blocker" | "info"
    object_type: str  # "milestone" | "issue" | "label" | "project" | "project_item" | "anchor"
    object_id: str
    expected: Any
    actual: Any

    def __post_init__(self) -> None:
        if self.category not in _DRIFT_CATEGORIES:
            raise ValueError(f"Unknown drift category: {self.category!r}")
        if self.severity not in {"blocker", "info"}:
            raise ValueError(f"Unknown severity: {self.severity!r}")
        if self.object_type not in {
            "milestone",
            "issue",
            "label",
            "project",
            "project_item",
            "anchor",
        }:
            raise ValueError(f"Unknown object_type: {self.object_type!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class DriftReport:
    """Schema-conformant report (ao-ma-github-mirror-drift-report.v1)."""

    projection_manifest: str
    manifest_sha256: str
    checked_at: str  # ISO-8601 UTC
    network_allowed: bool
    token_env: str
    token_present: bool
    github_owner: str
    github_repo: str
    expected_counts: dict[str, int]
    drift: list[DriftFinding] = field(default_factory=list)
    exit_decision: ExitDecision = ExitDecision.SYNCED

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ao-ma-github-mirror-drift-report.v1",
            "projection_manifest": self.projection_manifest,
            "manifest_sha256": self.manifest_sha256,
            "checked_at": self.checked_at,
            "network_allowed": self.network_allowed,
            "token_env": self.token_env,
            "token_present": self.token_present,
            "github_owner": self.github_owner,
            "github_repo": self.github_repo,
            "expected_counts": dict(self.expected_counts),
            "drift": [d.to_dict() for d in self.drift],
            "exit_decision": self.exit_decision.value,
        }

    def to_exit_code(self) -> int:
        if self.exit_decision == ExitDecision.SYNCED:
            return 0
        if self.exit_decision == ExitDecision.MIRROR_DRIFT_DETECTED:
            return 1
        if self.exit_decision in (
            ExitDecision.NETWORK_NOT_ALLOWED,
            ExitDecision.USAGE_ERROR,
        ):
            return 2
        if self.exit_decision == ExitDecision.API_ERROR:
            return 3
        raise ValueError(f"Unknown ExitDecision: {self.exit_decision!r}")


# --- Anchor parser (strict markdown) --------------------------------------------


@dataclass
class AnchorParseResult:
    """Parsed anchor fields from an issue body."""

    fields: dict[str, str]
    missing: list[str]
    duplicates: list[str]
    unknown: list[str]
    sha_format_invalid: list[str]
    placeholders_unresolved: list[str]


# Markdown anchor pattern: `- **field_name:** ` value (optionally backticked).
# Strict: line MUST start with "- **<name>:** " (allow whitespace tolerance).
_ANCHOR_LINE_PATTERN = re.compile(
    r"^\s*-\s+\*\*(?P<field>[a-z_][a-z0-9_]*)\:\*\*\s+(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
# Strip optional surrounding backticks for value normalization.
_BACKTICK_STRIP = re.compile(r"^`(.+)`$")


def _normalize_anchor_value(value: str) -> str:
    """Normalize a markdown anchor value.

    GitHub mirror bodies may include an inline explanation after a backticked
    value, for example:
        `sha256:<digest>` (manifest `.claude/plans/...`)

    The digest validator should evaluate the bound value, not the explanatory
    prose that follows it.
    """
    value = value.strip()
    if value.startswith("`"):
        closing = value.find("`", 1)
        if closing > 1:
            return value[1:closing]
    bt = _BACKTICK_STRIP.match(value)
    if bt:
        return bt.group(1)
    return value


def parse_issue_anchor(body: str) -> AnchorParseResult:
    """Strict-parse anchor fields from an issue body markdown list.

    Looks for top-level list items of the form:
        - **spm_anchor:** `AO-MA-SPM-V5-EPIC-1`
    Within the first occurrence of a "## V5 Anchor" heading (or document start
    if the heading is absent).
    """
    fields: dict[str, str] = {}
    duplicates: list[str] = []
    unknown: list[str] = []
    sha_format_invalid: list[str] = []
    placeholders_unresolved: list[str] = []

    # Scope: lines from "## V5 Anchor" until next "## " heading (or EOF).
    lines = body.splitlines()
    scope_start = 0
    scope_end = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("## ") and "anchor" in line.lower():
            scope_start = i + 1
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    scope_end = j
                    break
            break

    for line in lines[scope_start:scope_end]:
        m = _ANCHOR_LINE_PATTERN.match(line)
        if not m:
            continue
        field_name = m.group("field").lower()
        value = m.group("value").strip()
        value = _normalize_anchor_value(value)
        if field_name not in _ANCHOR_KNOWN_FIELDS:
            unknown.append(field_name)
            continue
        if field_name in fields:
            duplicates.append(field_name)
            continue
        fields[field_name] = value

        # SHA format + placeholder validation for digest fields.
        if field_name in ("artifact_sha256", "plan_digest"):
            if _PLACEHOLDER_PATTERN.match(value):
                placeholders_unresolved.append(field_name)
            elif not _SHA_PATTERN.match(value):
                sha_format_invalid.append(field_name)

    missing = [f for f in _ANCHOR_REQUIRED_FIELDS if f not in fields]

    return AnchorParseResult(
        fields=fields,
        missing=missing,
        duplicates=duplicates,
        unknown=unknown,
        sha_format_invalid=sha_format_invalid,
        placeholders_unresolved=placeholders_unresolved,
    )


# --- Main drift checker ---------------------------------------------------------


def _utcnow_isoformat() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _resolve_manifest_ref(projection_manifest_path: Path, manifest_ref: str) -> Path | None:
    """Resolve a manifest-relative path from the projection manifest.

    Historical V5 manifests store refs as repo-root relative paths such as
    `.claude/plans/v5_subissues_mirror.v1.json`. The core module only receives
    the projection manifest path, so resolve conservatively by walking ancestors
    and returning the first existing candidate.
    """
    ref_path = Path(manifest_ref)
    if ref_path.is_absolute():
        return ref_path if ref_path.is_file() else None
    for ancestor in (projection_manifest_path.parent, *projection_manifest_path.parents):
        candidate = ancestor / ref_path
        if candidate.is_file():
            return candidate
    return None


def _load_optional_subissues_manifest(
    projection_manifest_path: Path,
    runtime_state: dict[str, Any],
) -> dict[str, Any] | None:
    ref = runtime_state.get("sub_issues_mirror_ref", {})
    manifest_ref = ref.get("mirror_manifest_path")
    if not isinstance(manifest_ref, str) or not manifest_ref.strip():
        return None
    subissues_path = _resolve_manifest_ref(projection_manifest_path, manifest_ref)
    if subissues_path is None:
        return None
    return _load_manifest(subissues_path)


def _expected_issue_inventory(
    projection_manifest_path: Path,
    manifest: dict[str, Any],
    runtime_state: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    """Build expected issue metadata from parent + optional sub-issue manifests.

    `v5_issue_projection.v1.json` originally carried only the first-wave parent
    issues. `v5_subissues_mirror.v1.json` later became repo authority for the
    retroactive sub-slice issue mirror. The drift checker must include both, or
    it will incorrectly classify canonical sub-issues as `extra_issue`.
    """
    expected_first_wave_by_id = {
        issue["id"]: issue for issue in manifest.get("first_wave_issues", [])
    }
    inventory: dict[int, dict[str, Any]] = {}

    for anchor_id, issue_number in runtime_state.get("issues_created", {}).items():
        if not isinstance(issue_number, int):
            continue
        expected_meta = expected_first_wave_by_id.get(anchor_id, {})
        inventory[issue_number] = {
            "id": anchor_id,
            "labels": list(expected_meta.get("labels", [])),
            "anchor_required": True,
        }

    subissues_manifest = _load_optional_subissues_manifest(
        projection_manifest_path, runtime_state
    )
    if subissues_manifest is None:
        return inventory

    subissues = subissues_manifest.get("sub_issues", {})
    if not isinstance(subissues, dict):
        return inventory
    for slice_id, meta in subissues.items():
        if not isinstance(meta, dict):
            continue
        issue_number = meta.get("issue_number")
        if not isinstance(issue_number, int):
            continue
        inventory[issue_number] = {
            "id": slice_id,
            "labels": list(meta.get("labels", [])),
            # Retroactive sub-slice mirror issues were created from a compact
            # body template, not the parent V5 Anchor block. Keep label/inventory
            # checking strict without manufacturing anchor drift for canonical
            # sub-issues.
            "anchor_required": False,
        }

    return inventory


def _safe_call(gh_api_caller: Callable[[str, str], Any], method: str, api_path: str) -> tuple[Any, Optional[str]]:
    """Call gh_api_caller and capture API errors.

    Returns (result, error_message_or_None).
    """
    try:
        return gh_api_caller(method, api_path), None
    except Exception as exc:  # noqa: BLE001 — catch any API error
        return None, str(exc)


def check_github_mirror_drift(
    *,
    projection_manifest_path: Path,
    gh_api_caller: Callable[[str, str], Any],
    repo_owner: str = "Halildeu",
    repo_name: str = "ao-kernel",
    network_allowed: bool = False,
    token_env: str = "GH_TOKEN",
    token_present: bool = False,
    now_iso: Optional[str] = None,
) -> DriftReport:
    """Compare GitHub mirror state vs projection manifest. Read-only.

    Args:
        projection_manifest_path: Path to v5_issue_projection.v1.json (or similar).
        gh_api_caller: Callable(method, path) -> JSON dict. Network adapter.
        repo_owner / repo_name: GitHub repo identifiers.
        network_allowed: Must be True to actually call gh_api_caller.
        token_env: Env-var name (recorded; value NEVER read here).
        token_present: Boolean — whether env-var is set in caller's env.
        now_iso: Override timestamp for deterministic tests.
    """
    checked_at = now_iso or _utcnow_isoformat()
    manifest_sha = _file_sha256(projection_manifest_path)
    manifest = _load_manifest(projection_manifest_path)
    runtime_state = manifest.get("runtime_created_state", {})
    expected_issue_inventory = _expected_issue_inventory(
        projection_manifest_path, manifest, runtime_state
    )

    expected_counts = {
        "issues": len(expected_issue_inventory),
        "labels": len(manifest.get("labels", [])),
        "project_items": (manifest.get("runtime_created_state", {}).get("project_board", {}).get("items_count", 0)),
    }

    report = DriftReport(
        projection_manifest=str(projection_manifest_path),
        manifest_sha256=manifest_sha,
        checked_at=checked_at,
        network_allowed=network_allowed,
        token_env=token_env,
        token_present=token_present,
        github_owner=repo_owner,
        github_repo=repo_name,
        expected_counts=expected_counts,
    )

    if not network_allowed:
        report.exit_decision = ExitDecision.NETWORK_NOT_ALLOWED
        return report

    # 1. Milestone presence + metadata
    expected_ms = runtime_state.get("milestone", {})
    expected_ms_number = expected_ms.get("number")
    if expected_ms_number is None:
        report.drift.append(
            DriftFinding(
                category="missing_milestone",
                severity="blocker",
                object_type="milestone",
                object_id="<manifest>",
                expected="runtime_created_state.milestone.number set",
                actual=None,
            )
        )
    else:
        ms_actual, err = _safe_call(
            gh_api_caller,
            "GET",
            f"/repos/{repo_owner}/{repo_name}/milestones/{expected_ms_number}",
        )
        if err is not None:
            report.exit_decision = ExitDecision.API_ERROR
            return report
        if ms_actual is None or ms_actual.get("number") != expected_ms_number:
            report.drift.append(
                DriftFinding(
                    category="missing_milestone",
                    severity="blocker",
                    object_type="milestone",
                    object_id=str(expected_ms_number),
                    expected=expected_ms,
                    actual=ms_actual,
                )
            )
        else:
            exp_title = expected_ms.get("title")
            act_title = ms_actual.get("title")
            if exp_title and act_title != exp_title:
                report.drift.append(
                    DriftFinding(
                        category="milestone_metadata_mismatch",
                        severity="blocker",
                        object_type="milestone",
                        object_id=str(expected_ms_number),
                        expected={"title": exp_title},
                        actual={"title": act_title},
                    )
                )

    # 2. Issue inventory + 3. labels + 4. anchors
    expected_issue_numbers = set(expected_issue_inventory)

    if expected_ms_number is not None:
        issues_resp, err = _safe_call(
            gh_api_caller,
            "GET",
            f"/repos/{repo_owner}/{repo_name}/issues?milestone={expected_ms_number}&state=all&per_page=100",
        )
        if err is not None:
            report.exit_decision = ExitDecision.API_ERROR
            return report
        actual_issues = issues_resp or []
        actual_issue_numbers = {iss["number"] for iss in actual_issues}

        # missing
        for missing_num in expected_issue_numbers - actual_issue_numbers:
            report.drift.append(
                DriftFinding(
                    category="missing_issue",
                    severity="blocker",
                    object_type="issue",
                    object_id=str(missing_num),
                    expected=missing_num,
                    actual=None,
                )
            )
        # extra (only if in milestone scope; pure expected vs actual)
        for extra_num in actual_issue_numbers - expected_issue_numbers:
            report.drift.append(
                DriftFinding(
                    category="extra_issue",
                    severity="blocker",
                    object_type="issue",
                    object_id=str(extra_num),
                    expected=None,
                    actual=extra_num,
                )
            )

        # Per-issue label + anchor checks (intersection)
        for iss in actual_issues:
            num = iss["number"]
            if num not in expected_issue_numbers:
                continue
            expected_meta = expected_issue_inventory.get(num)
            if expected_meta is None:
                continue
            expected_labels = set(expected_meta.get("labels", []))
            actual_labels = {lab["name"] for lab in iss.get("labels", [])}
            if expected_labels != actual_labels:
                report.drift.append(
                    DriftFinding(
                        category="label_mismatch",
                        severity="blocker",
                        object_type="issue",
                        object_id=str(num),
                        expected=sorted(expected_labels),
                        actual=sorted(actual_labels),
                    )
                )

            if not expected_meta.get("anchor_required", True):
                continue

            # Anchor parse
            anchor = parse_issue_anchor(iss.get("body", "") or "")
            if anchor.missing or anchor.duplicates:
                report.drift.append(
                    DriftFinding(
                        category="anchor_mismatch",
                        severity="blocker",
                        object_type="anchor",
                        object_id=str(num),
                        expected=list(_ANCHOR_REQUIRED_FIELDS),
                        actual={
                            "missing": anchor.missing,
                            "duplicates": anchor.duplicates,
                        },
                    )
                )
            if anchor.unknown:
                report.drift.append(
                    DriftFinding(
                        category="anchor_schema_mismatch",
                        severity="blocker",
                        object_type="anchor",
                        object_id=str(num),
                        expected=list(_ANCHOR_REQUIRED_FIELDS),
                        actual={"unknown_fields": anchor.unknown},
                    )
                )
            if anchor.sha_format_invalid:
                report.drift.append(
                    DriftFinding(
                        category="anchor_sha_format_invalid",
                        severity="blocker",
                        object_type="anchor",
                        object_id=str(num),
                        expected="sha256:<64-hex>",
                        actual={"invalid_fields": anchor.sha_format_invalid},
                    )
                )
            if anchor.placeholders_unresolved:
                report.drift.append(
                    DriftFinding(
                        category="anchor_placeholder_unresolved",
                        severity="blocker",
                        object_type="anchor",
                        object_id=str(num),
                        expected="resolved sha256:<hex>",
                        actual={"placeholder_fields": anchor.placeholders_unresolved},
                    )
                )

    # 5. Project presence + items
    expected_project = runtime_state.get("project_board", {})
    expected_project_node_id = expected_project.get("node_id")
    expected_item_count = expected_project.get("items_count", 0)
    if expected_project_node_id:
        # Use GraphQL via the same caller — pass a structured "path" by convention:
        # caller("POST", "graphql:project_items:<node_id>") returns list of items.
        items_resp, err = _safe_call(
            gh_api_caller,
            "POST",
            f"graphql:project_items:{expected_project_node_id}",
        )
        if err is not None:
            report.exit_decision = ExitDecision.API_ERROR
            return report
        if items_resp is None:
            report.drift.append(
                DriftFinding(
                    category="project_missing",
                    severity="blocker",
                    object_type="project",
                    object_id=expected_project_node_id,
                    expected=expected_project,
                    actual=None,
                )
            )
        else:
            # ProjectV2 can contain non-issue items such as drafts. The V5
            # mirror manifest's `items_count` tracks issue-backed mirror items,
            # so ignore non-issue project entries here.
            actual_item_count = sum(
                1
                for item in items_resp.get("items", [])
                if (item.get("content") or {}).get("number") is not None
            )
            if actual_item_count != expected_item_count:
                report.drift.append(
                    DriftFinding(
                        category="project_item_count_mismatch",
                        severity="blocker",
                        object_type="project",
                        object_id=expected_project_node_id,
                        expected=expected_item_count,
                        actual=actual_item_count,
                    )
                )

    report.exit_decision = ExitDecision.MIRROR_DRIFT_DETECTED if report.drift else ExitDecision.SYNCED
    return report
