"""AO-MA-4 runner report writer.

Emits ``runner_report.v1.json`` under ``<base_dir>/<task_graph_id>/`` with
manifest hash + base sync verification + per-worker outcome. Schema-valid
against ``ao-ma-runner-report.schema.v1``; writer fails closed when the
payload does not match.

No agent execution, no LLM call, no GitHub write.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"


class RunnerReportWriterError(RuntimeError):
    """Raised when the runner report cannot be persisted fail-closed."""


def sha256_of(path: Path) -> str:
    """Return ``sha256:<hex>`` for the bytes at ``path``."""

    data = path.read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMAS_DIR / name
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerReportWriterError(f"bundled schema {name!r} could not be loaded: {exc}") from exc


@dataclass
class RunnerReportWriter:
    """Serialize a schema-valid runner report under ``<base_dir>/<task_graph_id>/``."""

    base_dir: Path

    def emit(
        self,
        *,
        task_graph_id: str,
        manifest_sha256: str,
        base_sha: str,
        conflict_check: str,
        base_sync_check: str,
        workers: list[dict[str, Any]],
        utc_now: _dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Build, validate, atomically write the runner report. Returns the dict."""

        now = utc_now or _dt.datetime.now(_dt.UTC)
        report = {
            "schema_version": "ao-ma-runner-report.v1",
            "task_graph_id": task_graph_id,
            "manifest_sha256": manifest_sha256,
            "base_sha": base_sha,
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "conflict_check": conflict_check,
            "base_sync_check": base_sync_check,
            "workers": workers,
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }

        schema = _load_schema("ao-ma-runner-report.schema.v1.json")
        try:
            Draft202012Validator(schema).validate(report)
        except ValidationError as exc:
            raise RunnerReportWriterError(f"runner report fails schema validation: {exc.message}") from exc

        resolved_base = self.base_dir.resolve()
        out_dir = (resolved_base / task_graph_id).resolve()
        try:
            out_dir.relative_to(resolved_base)
        except ValueError as exc:
            raise RunnerReportWriterError(
                f"task_graph_id {task_graph_id!r} escapes base_dir {resolved_base!s}"
            ) from exc
        out_dir.mkdir(parents=True, exist_ok=True)

        report_path = out_dir / "runner_report.v1.json"
        tmp = out_dir / ".runner_report.v1.json.tmp"
        tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(report_path)
        return report
