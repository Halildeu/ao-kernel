"""Workflow subsystem exceptions.

Typed hierarchy for workflow run lifecycle errors. Callers switch on exception
type rather than parse messages. `WorkflowSchemaValidationError` carries a
structured error list compatible with the `ao_kernel/_internal/shared/utils.py`
validation pattern.

Exception hierarchy:

    WorkflowError
        WorkflowTransitionError
        WorkflowRunNotFoundError
        WorkflowRunCorruptedError
        WorkflowCASConflictError
        WorkflowBudgetExhaustedError
        WorkflowSchemaValidationError
        WorkflowTokenInvalidError
        WorkflowRunIdInvalidError

Design notes:
- Keyword-only constructor arguments. Callers pass context explicitly; no
  positional conventions to drift.
- Token values are truncated in `__str__` output to avoid leaking opaque
  resume tokens into log streams verbatim.
- Run IDs are redacted via `!r` repr so any path-like payloads are quoted,
  making path-traversal attempts visible.
"""

from __future__ import annotations

from typing import Any


class WorkflowError(Exception):
    """Base for all workflow-related errors."""


class WorkflowTransitionError(WorkflowError):
    """Illegal state transition attempted by ``validate_transition``."""

    def __init__(
        self,
        *,
        current_state: str,
        attempted_state: str,
        allowed_next: frozenset[str],
    ) -> None:
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.allowed_next = allowed_next
        super().__init__(
            f"Illegal transition {current_state!r} -> {attempted_state!r}; "
            f"allowed: {sorted(allowed_next)}"
        )


class WorkflowRunNotFoundError(WorkflowError):
    """Run record does not exist at the expected store path."""

    def __init__(self, *, run_id: str, store_path: str) -> None:
        self.run_id = run_id
        self.store_path = store_path
        super().__init__(f"Run {run_id!r} not found at {store_path!r}")


class WorkflowRunCorruptedError(WorkflowError):
    """Run record exists but fails JSON decode or schema validation.

    ``reason`` enumerates the failure mode: one of ``json_decode``,
    ``schema_invalid``, ``hash_mismatch``.
    """

    _REASONS = frozenset({"json_decode", "schema_invalid", "hash_mismatch"})

    def __init__(self, *, run_id: str, reason: str, details: str = "") -> None:
        self.run_id = run_id
        self.reason = reason
        self.details = details
        super().__init__(f"Run {run_id!r} corrupted ({reason}): {details}")


class WorkflowCASConflictError(WorkflowError):
    """Expected revision did not match current revision on CAS update.

    Retryable: caller may re-load and re-apply the mutation against the
    fresh revision. ``update_run`` handles this automatically up to
    ``max_retries``.
    """

    def __init__(
        self,
        *,
        run_id: str,
        expected_revision: str,
        actual_revision: str,
    ) -> None:
        self.run_id = run_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            f"CAS conflict for {run_id!r}: expected={expected_revision[:12]}..., "
            f"actual={actual_revision[:12]}..."
        )


class WorkflowBudgetExhaustedError(WorkflowError):
    """A budget axis was overspent (post-spend remaining < 0).

    Raised by ``budget.record_spend``. Callers should transition the run
    to ``failed`` with ``error.category='budget_exhausted'`` in the same
    CAS mutation so no partial state is persisted.

    ``axis`` is one of ``tokens``, ``time_seconds``, ``cost_usd``.
    """

    def __init__(
        self,
        *,
        run_id: str | None,
        axis: str,
        limit: Any,
        attempted_spend: Any,
    ) -> None:
        self.run_id = run_id
        self.axis = axis
        self.limit = limit
        self.attempted_spend = attempted_spend
        rid = run_id if run_id else "<no-run>"
        super().__init__(
            f"Budget exhausted for {rid!r} axis={axis}: "
            f"limit={limit}, attempted_spend={attempted_spend}"
        )


class WorkflowSchemaValidationError(WorkflowError):
    """Payload does not match ``workflow-run.schema.v1.json`` at a persist boundary.

    ``errors`` is a structured list; each entry is a ``dict[str, str]`` with keys:
    - ``json_path``: JSONPath-style path to the invalid field (e.g. ``$.state``).
    - ``message``: human-readable jsonschema error message.
    - ``validator``: name of the schema validator that failed (e.g. ``enum``,
      ``required``, ``type``).

    The ``__str__`` form summarises up to the first three errors; callers who
    need the full list inspect ``self.errors`` directly.
    """

    def __init__(
        self,
        *,
        run_id: str | None,
        errors: list[dict[str, str]],
    ) -> None:
        self.run_id = run_id
        self.errors = errors
        rid = run_id if run_id else "<no-run>"
        summary_parts = [
            f"{e.get('json_path', '?')}: {e.get('message', '?')}"
            for e in errors[:3]
        ]
        summary = "; ".join(summary_parts)
        if len(errors) > 3:
            summary = f"{summary} (+{len(errors) - 3} more)"
        super().__init__(f"Schema validation failed for {rid!r}: {summary}")


class WorkflowTokenInvalidError(WorkflowError):
    """Interrupt token or approval token is not recognized or mismatched.

    The two token domains (``interrupt`` from adapter HITL and ``approval``
    from governance gates) are distinct by schema; this exception keeps
    them distinguishable via ``token_kind``.

    ``reason`` is one of:
    - ``token_mismatch``: token value does not match the recorded token.
    - ``resumed_with_different_payload``: token matched but the response
      payload differs from a previously accepted resume (idempotency
      boundary crossed).
    - ``cross_domain_use``: an interrupt token was passed to
      ``resume_approval`` or vice versa.
    """

    _KINDS = frozenset({"interrupt", "approval"})
    _REASONS = frozenset({
        "token_mismatch",
        "resumed_with_different_payload",
        "cross_domain_use",
    })

    def __init__(
        self,
        *,
        run_id: str | None,
        token_kind: str,
        token_value: str,
        reason: str,
    ) -> None:
        self.run_id = run_id
        self.token_kind = token_kind
        self.token_value = token_value
        self.reason = reason
        rid = run_id if run_id else "<no-run>"
        redacted = token_value[:8] if token_value else ""
        super().__init__(
            f"Invalid {token_kind} token for {rid!r}: reason={reason} "
            f"token={redacted}..."
        )


class WorkflowRunIdInvalidError(WorkflowError):
    """run_id is not a valid UUID string (path-traversal guard).

    Raised by ``_run_path`` before any filesystem access. Prevents
    ``../etc/passwd``-style traversal attacks by validating that ``run_id``
    parses as a UUID (schema declares ``format: uuid`` on ``run_id``).
    """

    def __init__(self, *, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(
            f"run_id {run_id!r} is not a valid UUID; refusing to build path"
        )


# ---------------------------------------------------------------------------
# PR-A2 additions — workflow registry + intent router errors.
# ---------------------------------------------------------------------------


class WorkflowDefinitionNotFoundError(WorkflowError):
    """Registry has no workflow matching the requested (workflow_id, version).

    Raised by ``WorkflowRegistry.get`` when the key does not exist.
    ``version=None`` lookups raise when no entry for ``workflow_id`` exists
    at all; explicit-version lookups raise when the pinned version is
    missing even if other versions of the same id are loaded.
    """

    def __init__(self, *, workflow_id: str, version: str | None) -> None:
        self.workflow_id = workflow_id
        self.version = version
        pinned = f" (version={version!r})" if version is not None else ""
        super().__init__(
            f"Workflow {workflow_id!r} not found in registry{pinned}"
        )


class WorkflowDefinitionCorruptedError(WorkflowError):
    """Workflow definition file fails JSON decode or schema validation.

    ``reason`` enumerates the load-time failure mode.
    """

    _REASONS = frozenset({
        "json_decode",
        "schema_invalid",
        "duplicate_workflow_key",
        "read_error",
    })

    def __init__(self, *, source_path: str, reason: str, details: str = "") -> None:
        self.source_path = source_path
        self.reason = reason
        self.details = details
        super().__init__(
            f"Workflow definition at {source_path!r} corrupted "
            f"({reason}): {details}"
        )


class WorkflowDefinitionCrossRefError(WorkflowError):
    """Raised when cross-reference validation surfaces non-empty issues.

    Callers that want structured access use
    ``WorkflowRegistry.validate_cross_refs`` which returns a
    ``list[CrossRefIssue]``. This exception is for fail-closed consumers
    (e.g. PR-A3 executor) that want a single raise with the aggregated
    issue list attached.
    """

    def __init__(self, *, workflow_id: str, issues: tuple[object, ...]) -> None:
        self.workflow_id = workflow_id
        self.issues = issues
        super().__init__(
            f"Cross-reference validation failed for workflow {workflow_id!r}: "
            f"{len(issues)} issue(s)"
        )


class IntentRulesCorruptedError(WorkflowError):
    """Intent classifier rules fail load-time invariants.

    ``reason`` enumerates the failure mode. Schema-level violations
    (missing fields, wrong types, unknown enum values, conditional
    validation misses) surface as ``schema_invalid``; loader-level
    invariants (duplicate rule_id, regex compile failure) have their
    own reasons so audit logs can distinguish.
    """

    _REASONS = frozenset({
        "schema_invalid",
        "duplicate_rule_id",
        "regex_compile",
        "duplicate_priority_match",
        "read_error",
    })

    def __init__(
        self,
        *,
        source_path: str | None,
        reason: str,
        details: str = "",
    ) -> None:
        self.source_path = source_path
        self.reason = reason
        self.details = details
        where = f" at {source_path!r}" if source_path else ""
        super().__init__(
            f"Intent rules{where} corrupted ({reason}): {details}"
        )


class IntentClassificationError(WorkflowError):
    """Runtime intent classification failed (PR-A6 B4).

    Raised by ``IntentRouter.classify`` when the ``llm_fallback``
    strategy cannot produce a valid workflow_id (LLM response
    outside available ids, transport error, or ``[llm]`` extra not
    installed). Distinct from ``IntentRulesCorruptedError`` which
    is a load-time validation failure.
    """

    def __init__(
        self,
        *,
        intent_text: str,
        reason: str,
        details: str = "",
    ) -> None:
        self.intent_text = intent_text
        self.reason = reason
        self.details = details
        super().__init__(
            f"Intent classification failed ({reason}): {details}"
        )
