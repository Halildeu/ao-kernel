"""AO-MA-5 integration report writer.

Emits ``integration_report.v1.json`` under ``<base_dir>/<task_graph_id>/``
with accepted/rejected/not_integratable worker decisions, optional
pending_worker_results / worker_decisions / assembly_plan extension
fields (AO-MA-5 schema extension PR #653 merged), and the const
``release_authority = "ao-release-gate+github-ruleset"`` pinning that
the integrator is NOT release authority.

No agent execution, no LLM call, no GitHub write, no git push, no
shell-out helpers (HARD RULE pin enforced by Integrator class).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"


class IntegrationReportWriterError(RuntimeError):
    """Raised when the integration report cannot be persisted fail-closed."""


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMAS_DIR / name
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrationReportWriterError(f"bundled schema {name!r} could not be loaded: {exc}") from exc


@dataclass
class IntegrationReportWriter:
    """Serialize a schema-valid integration report under ``<base_dir>/<task_graph_id>/``."""

    base_dir: Path

    def emit(
        self,
        *,
        task_graph_id: str,
        integrator: dict[str, Any],
        base_ref: str,
        base_sha: str,
        head_ref: str,
        head_sha: str,
        accepted_worker_results: list[str],
        rejected_worker_results: list[str],
        final_changed_files: list[str],
        conflicts: list[dict[str, Any]],
        review_verdict_refs: list[str],
        verification_report_refs: list[str],
        pending_worker_results: list[str] | None = None,
        worker_decisions: list[dict[str, Any]] | None = None,
        assembly_plan: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build, validate, atomically write the integration report. Returns the dict."""

        report: dict[str, Any] = {
            "schema_version": "ao-ma-integration-report.v1",
            "task_graph_id": task_graph_id,
            "integrator": integrator,
            "base_ref": base_ref,
            "base_sha": base_sha,
            "head_ref": head_ref,
            "head_sha": head_sha,
            "accepted_worker_results": accepted_worker_results,
            "rejected_worker_results": rejected_worker_results,
            "final_changed_files": final_changed_files,
            "conflicts": conflicts,
            "review_verdict_refs": review_verdict_refs,
            "verification_report_refs": verification_report_refs,
            "release_authority": "ao-release-gate+github-ruleset",
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }

        # AO-MA-5 extension fields (Codex iter-4 AGREE): optional in
        # schema, always emitted by AO-MA-5 v1 producer when the trust
        # boundary is valid. Schema validation enforces shape on read +
        # write paths uniformly.
        if pending_worker_results is not None:
            report["pending_worker_results"] = pending_worker_results
        if worker_decisions is not None:
            report["worker_decisions"] = worker_decisions
        if assembly_plan is not None:
            report["assembly_plan"] = assembly_plan

        schema = _load_schema("ao-ma-integration-report.schema.v1.json")
        try:
            Draft202012Validator(schema).validate(report)
        except ValidationError as exc:
            raise IntegrationReportWriterError(
                f"integration report fails schema validation: {exc.message} (at {list(exc.absolute_path)})"
            ) from exc

        resolved_base = self.base_dir.resolve()
        out_dir = (resolved_base / task_graph_id).resolve()
        try:
            out_dir.relative_to(resolved_base)
        except ValueError as exc:
            raise IntegrationReportWriterError(
                f"task_graph_id {task_graph_id!r} escapes base_dir {resolved_base!s}"
            ) from exc
        out_dir.mkdir(parents=True, exist_ok=True)

        report_path = out_dir / "integration_report.v1.json"
        tmp = out_dir / ".integration_report.v1.json.tmp"
        tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(report_path)
        return report
