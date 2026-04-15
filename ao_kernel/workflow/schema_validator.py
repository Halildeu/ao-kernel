"""Runtime schema validator for workflow run records.

Thin wrapper around ``jsonschema.Draft202012Validator`` bound to the
bundled ``workflow-run.schema.v1.json`` schema. Validation only runs at
persist boundaries (load / save) — the runtime call path (state
transitions, budget updates) does NOT re-validate, per the schema
boundary invariant in plan v2 §6 and ``workflow-run.schema`` contract.

Both the schema document and the compiled validator are
``functools.lru_cache`` -ed once per process (plan v2 W5 fix). Downstream
callers should treat the returned schema mapping as read-only.

Error output is structured: ``WorkflowSchemaValidationError.errors`` is a
``list[dict[str, str]]`` with ``json_path``, ``message``, and ``validator``
keys (plan v2 W7 fix). This mirrors the repo's shared validator pattern
(``ao_kernel/_internal/shared/utils.py::validate_with_schema``).
"""

from __future__ import annotations

import functools
import json
from importlib import resources
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.workflow.errors import WorkflowSchemaValidationError

_SCHEMA_PACKAGE = "ao_kernel.defaults.schemas"
_SCHEMA_FILENAME = "workflow-run.schema.v1.json"


@functools.lru_cache(maxsize=1)
def load_workflow_run_schema() -> Mapping[str, Any]:
    """Return the bundled ``workflow-run.schema.v1.json`` as a mapping.

    Loaded once per process via ``importlib.resources`` (wheel-safe per
    architecture decision D4). Cached; callers MUST NOT mutate the
    returned mapping.
    """
    text = (
        resources.files(_SCHEMA_PACKAGE)
        .joinpath(_SCHEMA_FILENAME)
        .read_text(encoding="utf-8")
    )
    schema: Mapping[str, Any] = json.loads(text)
    return schema


@functools.lru_cache(maxsize=1)
def _get_validator() -> Draft202012Validator:
    """Return the compiled Draft 2020-12 validator for the workflow-run schema.

    Cached once per process. The validator does NOT enforce ``format``
    keywords (e.g. ``format: uuid`` on ``run_id``); ``run_id`` format is
    separately enforced by ``run_store._run_path`` via ``uuid.UUID(...)``
    parse (plan v2 B3 fix for path-traversal guard).
    """
    return Draft202012Validator(load_workflow_run_schema())


def validate_workflow_run(
    record: Mapping[str, Any],
    *,
    run_id: str | None = None,
) -> None:
    """Validate ``record`` against ``workflow-run.schema.v1.json``.

    Collects all validation errors and raises
    ``WorkflowSchemaValidationError`` once with the structured list.
    Returns ``None`` on success.

    Parameters
    ----------
    record : Mapping[str, Any]
        The workflow run record payload to validate. Typically the dict
        returned from ``json.loads`` at a load boundary, or the dict
        prepared by a mutator just before a save boundary.
    run_id : str | None
        Optional run identifier propagated into the exception for
        downstream logging / audit. Not validated here.
    """
    validator = _get_validator()
    structured_errors: list[dict[str, str]] = []
    for ve in validator.iter_errors(record):
        structured_errors.append(_format_error(ve))
    if structured_errors:
        # Sort by json_path so tests can make stable assertions.
        structured_errors.sort(key=lambda e: e["json_path"])
        raise WorkflowSchemaValidationError(
            run_id=run_id,
            errors=structured_errors,
        )


def _format_error(ve: ValidationError) -> dict[str, str]:
    """Project a ``jsonschema.ValidationError`` to our structured dict.

    Keys mirror the repo shared validator pattern:
    - ``json_path``: JSONPath-style pointer (e.g. ``$.state``).
    - ``message``: human-readable message from jsonschema.
    - ``validator``: the failing validator keyword (``enum``, ``required``,
      ``type``, etc).
    """
    return {
        "json_path": ve.json_path,
        "message": ve.message,
        "validator": str(ve.validator) if ve.validator is not None else "",
    }
