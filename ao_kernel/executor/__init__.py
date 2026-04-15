"""Public facade for ``ao_kernel.executor``.

Runtime adapter invocation + policy enforcement + evidence emission.
PR-A3 ships the primitive; PR-A4 drives multi-step orchestration over
this primitive.

Narrow surface (plan v2 W2): internal helpers (``_build_env``,
``_parse_stdout``, ``_substitute_args``, ``_jsonpath_dotted``,
``_SENTINEL_MISSING``, private subprocess wrappers) are NOT
re-exported. Tests that need them import from submodules directly.
"""

from __future__ import annotations

from ao_kernel.executor.adapter_invoker import (
    InvocationResult,
    invoke_cli,
    invoke_http,
)
from ao_kernel.executor.errors import (
    AdapterInvocationFailedError,
    AdapterOutputParseError,
    EvidenceEmitError,
    ExecutorError,
    PolicyViolation,
    PolicyViolationError,
    WorktreeBuilderError,
)
from ao_kernel.executor.evidence_emitter import (
    EvidenceEvent,
    emit_adapter_log,
    emit_event,
)
from ao_kernel.executor.executor import Executor, ExecutionResult
from ao_kernel.executor.multi_step_driver import (
    DriverBudgetExhaustedError,
    DriverResult,
    DriverStateConflictError,
    DriverStateInconsistencyError,
    DriverTokenRequiredError,
    MultiStepDriver,
    WorkflowStateCorruptedError,
)
from ao_kernel.executor.policy_enforcer import (
    RedactionConfig,
    SandboxedEnvironment,
    build_sandbox,
    check_http_header_exposure,
    resolve_allowed_secrets,
    validate_command,
    validate_cwd,
)
from ao_kernel.executor.worktree_builder import (
    WorktreeHandle,
    cleanup_worktree,
    create_worktree,
)

__all__ = [
    # Errors
    "ExecutorError",
    "PolicyViolation",
    "PolicyViolationError",
    "AdapterInvocationFailedError",
    "AdapterOutputParseError",
    "WorktreeBuilderError",
    "EvidenceEmitError",
    # Evidence
    "EvidenceEvent",
    "emit_event",
    "emit_adapter_log",
    # Policy enforcement
    "SandboxedEnvironment",
    "RedactionConfig",
    "build_sandbox",
    "validate_command",
    "validate_cwd",
    "resolve_allowed_secrets",
    "check_http_header_exposure",
    # Worktree
    "WorktreeHandle",
    "create_worktree",
    "cleanup_worktree",
    # Adapter invocation
    "InvocationResult",
    "invoke_cli",
    "invoke_http",
    # Orchestrator
    "Executor",
    "ExecutionResult",
    # Multi-step driver (PR-A4b)
    "MultiStepDriver",
    "DriverResult",
    "DriverStateConflictError",
    "DriverBudgetExhaustedError",
    "DriverTokenRequiredError",
    "DriverStateInconsistencyError",
    "WorkflowStateCorruptedError",
]
