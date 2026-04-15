"""Public facade for ``ao_kernel.workflow``.

Workflow run lifecycle primitives:

- **Errors** — typed exception hierarchy for all failure modes.
- **State machine** — 9-state transition table + pure validation helpers.
- **Schema validator** — Draft 2020-12 validator wrapper for
  ``workflow-run.schema.v1.json`` at persist boundaries.
- **Budget** — immutable dataclasses for token / time / cost accounting
  with fail-closed exhaustion semantic.
- **Primitives** — ``InterruptRequest`` / ``Approval`` records plus
  mint / create / resume helpers with idempotent resume.
- **Run store** — CAS-backed CRUD for workflow run records under
  ``.ao/runs/<run_id>/state.v1.json``.

Narrow surface (plan v2 W2): private helpers — ``_mutate_with_cas``,
``_run_path``, ``_lock_path``, ``_get_validator``,
``load_workflow_run_schema`` — are NOT re-exported. Callers that need
them import from the submodule directly; the public facade intentionally
hides implementation plumbing.
"""

from __future__ import annotations

from ao_kernel.workflow.budget import (
    Budget,
    BudgetAxis,
    budget_from_dict,
    budget_to_dict,
    is_exhausted,
    record_spend,
)
from ao_kernel.workflow.errors import (
    WorkflowBudgetExhaustedError,
    WorkflowCASConflictError,
    WorkflowError,
    WorkflowRunCorruptedError,
    WorkflowRunIdInvalidError,
    WorkflowRunNotFoundError,
    WorkflowSchemaValidationError,
    WorkflowTokenInvalidError,
    WorkflowTransitionError,
)
from ao_kernel.workflow.primitives import (
    Approval,
    InterruptRequest,
    create_approval,
    create_interrupt,
    mint_approval_token,
    mint_interrupt_token,
    resume_approval,
    resume_interrupt,
)
from ao_kernel.workflow.run_store import (
    create_run,
    load_run,
    run_revision,
    save_run_cas,
    update_run,
)
from ao_kernel.workflow.schema_validator import validate_workflow_run
from ao_kernel.workflow.state_machine import (
    TERMINAL_STATES,
    TRANSITIONS,
    WorkflowState,
    allowed_next,
    is_terminal,
    validate_transition,
)

__all__ = [
    # Errors
    "WorkflowError",
    "WorkflowTransitionError",
    "WorkflowRunNotFoundError",
    "WorkflowRunCorruptedError",
    "WorkflowCASConflictError",
    "WorkflowBudgetExhaustedError",
    "WorkflowSchemaValidationError",
    "WorkflowTokenInvalidError",
    "WorkflowRunIdInvalidError",
    # State machine
    "WorkflowState",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "is_terminal",
    "allowed_next",
    "validate_transition",
    # Schema validator
    "validate_workflow_run",
    # Budget
    "Budget",
    "BudgetAxis",
    "budget_from_dict",
    "budget_to_dict",
    "record_spend",
    "is_exhausted",
    # Primitives
    "InterruptRequest",
    "Approval",
    "mint_interrupt_token",
    "mint_approval_token",
    "create_interrupt",
    "create_approval",
    "resume_interrupt",
    "resume_approval",
    # Run store
    "create_run",
    "load_run",
    "save_run_cas",
    "update_run",
    "run_revision",
]
