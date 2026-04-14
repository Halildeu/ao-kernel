"""Vector store backend resolver — env + policy + constructor precedence.

Fail-closed selection flow:

    1. Constructor-injected backend (if provided)           → use it
    2. Policy.semantic_retrieval.enabled is False           → disabled (None)
    3. Env AO_KERNEL_VECTOR_BACKEND=disabled                → disabled (None)
    4. Env AO_KERNEL_VECTOR_BACKEND=pgvector
         - Missing DSN                                      → raise VectorStoreConfigError
         - Connect fails + strict=True                      → raise VectorStoreConnectError
         - Connect fails + strict=False                     → warn + None (deterministic fallback)
         - Connect OK                                       → PgvectorBackend
    5. Env=inmemory or absent (with enabled=True)           → InMemoryVectorStore
    6. Library mode (.ao/ absent) with no env               → disabled (None)

The resolver never returns a broken backend. Callers treat None as
"semantic search disabled — deterministic scoring is authoritative".

Precedence rationale (CLAUDE.md D8 fail-closed, D11 secrets env-var only):
    - Constructor injection wins (tests/advanced).
    - Policy gates feature enablement (enable/strict/fail_action).
    - Env resolves backend instance and secrets (DSN).
    - Library mode defaults to disabled (no durable store by policy).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from ao_kernel.errors import VectorStoreConfigError, VectorStoreConnectError

logger = logging.getLogger(__name__)

_ENV_BACKEND = "AO_KERNEL_VECTOR_BACKEND"
_ENV_DSN = "AO_KERNEL_PGVECTOR_DSN"
_ENV_STRICT = "AO_KERNEL_VECTOR_STRICT"
_ENV_TABLE = "AO_KERNEL_PGVECTOR_TABLE"
_ENV_DIMENSION = "AO_KERNEL_EMBEDDING_DIMENSION"

_VALID_BACKENDS = frozenset({"inmemory", "pgvector", "disabled"})


def _resolve_env_strict(policy_strict: bool) -> bool:
    """Env override for strict mode. Default to policy value if env unset."""
    env = os.environ.get(_ENV_STRICT, "").strip().lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    return policy_strict


def _load_policy(workspace: Path | None) -> dict[str, Any]:
    """Load memory tiers policy. Returns empty dict if load fails (fail-open for config)."""
    try:
        from ao_kernel.config import load_with_override
        policy = load_with_override(
            "policies",
            "policy_context_memory_tiers.v1.json",
            workspace=workspace,
        )
        section = policy.get("semantic_retrieval", {})
        return section if isinstance(section, dict) else {}
    except Exception as exc:  # noqa: BLE001 — config load best-effort
        logger.warning("vector_store_resolver: policy load failed (%s); using defaults", exc)
        return {}


def resolve_vector_store(
    *,
    workspace: Path | None = None,
    injected: Any | None = None,
) -> tuple[Any | None, bool]:
    """Resolve which vector store backend to use.

    Args:
        workspace: Workspace root (None = library mode).
        injected: Constructor-passed backend instance (highest precedence).

    Returns:
        (backend, owned) tuple where:
            - backend is a VectorStoreBackend instance or None (disabled)
            - owned indicates whether the client should close() the backend
              at __exit__ (True = resolver created it, False = caller passed it)

    Raises:
        VectorStoreConfigError: Env requests pgvector but DSN missing,
                                or backend type is invalid.
        VectorStoreConnectError: pgvector connect fails AND strict mode is on.
    """
    # (1) Constructor injection wins — never owned by client.
    if injected is not None:
        return injected, False

    policy = _load_policy(workspace)
    enabled = bool(policy.get("enabled", False))
    backend_cfg = policy.get("backend", {}) if isinstance(policy.get("backend"), dict) else {}
    policy_strict = bool(backend_cfg.get("strict", False))
    fail_action = backend_cfg.get("fail_action", "warn_fallback")
    if fail_action not in ("raise", "warn_fallback"):
        fail_action = "warn_fallback"

    env_backend = os.environ.get(_ENV_BACKEND, "").strip().lower()

    # (2) Env explicit disable overrides everything (except constructor).
    if env_backend == "disabled":
        return None, False

    # (3) Policy gate — disabled when not explicitly enabled AND no env override.
    if not enabled and env_backend == "":
        return None, False

    strict = _resolve_env_strict(policy_strict)

    # (4) Backend selection: env takes precedence over policy type when both present.
    backend_type = env_backend or backend_cfg.get("type", "inmemory")
    if backend_type not in _VALID_BACKENDS:
        raise VectorStoreConfigError(
            f"Invalid vector backend: {backend_type!r}. "
            f"Allowed: {sorted(_VALID_BACKENDS)}"
        )
    if backend_type == "disabled":
        return None, False

    # (5) pgvector path
    if backend_type == "pgvector":
        dsn = os.environ.get(_ENV_DSN, "").strip()
        if not dsn:
            raise VectorStoreConfigError(
                f"{_ENV_BACKEND}=pgvector requires {_ENV_DSN} (connection string)."
            )
        try:
            from ao_kernel.context.vector_store_pgvector import PgvectorBackend
            dimension = _parse_dimension(os.environ.get(_ENV_DIMENSION))
            table = os.environ.get(_ENV_TABLE, "ao_embeddings")
            backend = PgvectorBackend(dsn=dsn, table_name=table, dimension=dimension)
            return backend, True
        except VectorStoreConfigError:
            raise
        except Exception as exc:
            msg = f"pgvector backend instantiation failed: {exc}"
            if strict or fail_action == "raise":
                raise VectorStoreConnectError(msg) from exc
            logger.warning("%s; falling back to deterministic ordering", msg)
            return None, False

    # (6) inmemory path
    if backend_type == "inmemory":
        from ao_kernel.context.vector_store import InMemoryVectorStore
        return InMemoryVectorStore(), True

    # Unreachable due to _VALID_BACKENDS check above.
    raise VectorStoreConfigError(f"Unreachable backend type: {backend_type!r}")


def _parse_dimension(raw: str | None) -> int:
    """Parse embedding dimension from env. Default 1536 (text-embedding-3-small)."""
    if not raw:
        return 1536
    try:
        dim = int(raw)
    except ValueError as exc:
        raise VectorStoreConfigError(
            f"{_ENV_DIMENSION} must be a positive integer, got {raw!r}"
        ) from exc
    if dim <= 0:
        raise VectorStoreConfigError(
            f"{_ENV_DIMENSION} must be positive, got {dim}"
        )
    return dim


__all__ = ["resolve_vector_store"]
