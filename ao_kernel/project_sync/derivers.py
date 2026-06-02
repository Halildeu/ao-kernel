"""Field derivation from issue metadata.

These derivers map repo-side conventions (labels, title prefixes, body
sections) to GitHub Projects v2 custom-field values. Pure functions — no
network, no globals — so tests can drive them with crafted ``IssueRecord``
instances and verify each rule in isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ao_kernel.project_sync.errors import FieldDerivationError
from ao_kernel.project_sync.issues import IssueRecord

_EPIC_LABEL_RE = re.compile(r"^epic-(?P<id>p0|[0-9]+)$", re.IGNORECASE)
_RISK_LABEL_RE = re.compile(r"^risk:(?P<level>critical|high|normal|low)$", re.IGNORECASE)
_GUARD_LABEL_RE = re.compile(
    r"^guard-flip:(?P<name>live_adapter|support_widening|production_platform_claim)$",
    re.IGNORECASE,
)
_STATUS_LABEL_RE = re.compile(r"^status:(?P<name>planned|in_progress|review|blocked|done)$", re.IGNORECASE)
_DEPENDS_RE = re.compile(r"(?:depends on|blocked by)\s+#(?P<num>\d+)", re.IGNORECASE)
_RISK_TO_ESTIMATE = {
    "low": 1.0,
    "normal": 2.0,
    "high": 5.0,
    "critical": 10.0,
}
_RISK_TO_RELEASE_IMPACT = {
    "low": "patch",
    "normal": "patch",
    "high": "minor",
    "critical": "major",
}
_STATUS_TO_KANBAN = {
    "planned": "Todo",
    "in_progress": "In Progress",
    "review": "Review",
    "blocked": "Blocked",
    "done": "Done",
}


@dataclass(frozen=True)
class DerivedFields:
    """Result of :func:`derive_all_fields`.

    ``warnings`` collects soft signals (missing optional fields, fallback
    defaults applied). The slice adder treats them as advisory; the drift
    healer surfaces them in its report.
    """

    epic: str | None
    risk: str | None
    guard: str
    dependency: str | None
    estimate: float | None
    release_impact: str | None
    status: str | None
    warnings: list[str]


class FieldDeriver:
    """Stateless deriver object — fields → values.

    Encapsulates the per-rule helpers so that callers can subclass to add
    additional derivations (e.g. site-local label conventions) without
    reaching into module-level regexes.
    """

    def derive_epic(self, labels: Iterable[str]) -> str | None:
        for label in labels:
            match = _EPIC_LABEL_RE.match(label)
            if match:
                epic_id = match.group("id").lower()
                return "P0" if epic_id == "p0" else epic_id
        return None

    def derive_risk(self, labels: Iterable[str]) -> str | None:
        for label in labels:
            match = _RISK_LABEL_RE.match(label)
            if match:
                return match.group("level").lower()
        return None

    def derive_guard(self, labels: Iterable[str]) -> str:
        for label in labels:
            match = _GUARD_LABEL_RE.match(label)
            if match:
                return match.group("name").lower()
        return "none"

    def derive_status(self, labels: Iterable[str]) -> str | None:
        for label in labels:
            match = _STATUS_LABEL_RE.match(label)
            if match:
                return match.group("name").lower()
        return None

    def derive_kanban_column(self, status: str | None) -> str | None:
        if status is None:
            return None
        return _STATUS_TO_KANBAN.get(status)

    def derive_dependency(self, body: str) -> str | None:
        matches = _DEPENDS_RE.findall(body or "")
        if not matches:
            return None
        # Preserve repo-side ordering (first occurrence wins per slice); the
        # text field stores a comma-joined list so the project surface keeps
        # the full picture.
        seen: list[str] = []
        for num in matches:
            ref = f"#{num}"
            if ref not in seen:
                seen.append(ref)
        return ",".join(seen)

    def derive_estimate(self, risk: str | None) -> float | None:
        if risk is None:
            return None
        return _RISK_TO_ESTIMATE.get(risk.lower())

    def derive_release_impact(self, risk: str | None) -> str | None:
        if risk is None:
            return None
        return _RISK_TO_RELEASE_IMPACT.get(risk.lower())


def derive_all_fields(
    issue: IssueRecord,
    *,
    deriver: FieldDeriver | None = None,
    require_epic: bool = True,
    require_risk: bool = True,
) -> DerivedFields:
    """Top-level deriver: walk an issue and return all fields at once.

    ``require_*`` flags drive fail-closed behaviour. The slice adder asks
    for ``require_epic=True`` so the operator cannot accidentally add a
    slice missing the epic label; ``ao-kernel project field-set`` asks for
    ``False`` because the operator is updating a single field on purpose.
    """
    d = deriver or FieldDeriver()
    warnings: list[str] = []
    epic = d.derive_epic(issue.labels)
    risk = d.derive_risk(issue.labels)
    guard = d.derive_guard(issue.labels)
    status = d.derive_status(issue.labels)
    dependency = d.derive_dependency(issue.body)
    estimate = d.derive_estimate(risk)
    release_impact = d.derive_release_impact(risk)
    if epic is None and require_epic:
        raise FieldDerivationError(f"issue #{issue.number} missing 'epic-*' label (required for Epic field)")
    if risk is None and require_risk:
        raise FieldDerivationError(f"issue #{issue.number} missing 'risk:*' label (required for Risk field)")
    if epic is None:
        warnings.append("epic_label_missing")
    if risk is None:
        warnings.append("risk_label_missing")
    if status is None:
        warnings.append("status_label_missing")
    return DerivedFields(
        epic=epic,
        risk=risk,
        guard=guard,
        dependency=dependency,
        estimate=estimate,
        release_impact=release_impact,
        status=status,
        warnings=warnings,
    )
