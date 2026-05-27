"""AO-MA-6 review_verdict.v1.json writer.

Emits a schema-valid ``review_verdict.v1.json`` under the per-task
worker subdir (``<manifest_dir>/workers/<task_id>/review_verdict.v1.json``).
Atomic tmp + replace; Draft202012Validator runs on the payload before
disk write so an emit failure is a true I/O / schema error (not a
silent malformed file).

No agent execution, no LLM call, no GitHub write — the writer is pure
data persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"


class ReviewVerdictWriterError(RuntimeError):
    """Raised when the review verdict cannot be persisted fail-closed."""


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMAS_DIR / name
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewVerdictWriterError(f"bundled schema {name!r} could not be loaded: {exc}") from exc


@dataclass
class ReviewVerdictWriter:
    """Serialize a schema-valid review verdict to ``<output_dir>/review_verdict.v1.json``."""

    output_dir: Path

    def emit(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate + atomically write the review verdict. Returns the payload."""

        schema = _load_schema("ao-ma-review-verdict.schema.v1.json")
        try:
            Draft202012Validator(schema).validate(payload)
        except ValidationError as exc:
            raise ReviewVerdictWriterError(
                f"review_verdict payload fails schema validation: {exc.message} (at {list(exc.absolute_path)})"
            ) from exc

        resolved = self.output_dir.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        out_path = resolved / "review_verdict.v1.json"
        tmp = resolved / ".review_verdict.v1.json.tmp"
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(out_path)
        return payload
