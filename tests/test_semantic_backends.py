"""V5 Epic 7 E-7-5 invariants: semantic backend protocol + 2 impls.

In-memory backend is exercised in full. pgvector backend is structural
+ lazy-import + extras-missing only; live DB-backed tests are operator
opt-in via AO_KERNEL_PGVECTOR_DSN env var.

Discipline: live_adapter_execution + support_widening +
production_platform_claim remain const false; pgvector backend is a
building block, not a production claim.
"""

from __future__ import annotations

import importlib.util
import os
from importlib import import_module

import pytest

from ao_kernel.context.semantic_backends import (
    InMemoryBackend,
    SemanticBackend,
    SemanticBackendError,
    SemanticSearchResult,
)
from ao_kernel.context.semantic_backends.pgvector import PgVectorBackend


def _module_installed(name: str) -> bool:
    """Helper: check whether a module is importable WITHOUT actually
    importing it (avoids ``except ImportError: pass`` in test bodies
    which the BLK-003 conftest rule blocks)."""
    return importlib.util.find_spec(name) is not None


# ---- 1. Protocol shape (4) ---------------------------------------------


def test_in_memory_backend_conforms_to_protocol() -> None:
    backend = InMemoryBackend()
    assert isinstance(backend, SemanticBackend)
    assert backend.backend_name == "in_memory"


def test_pgvector_backend_conforms_to_protocol() -> None:
    backend = PgVectorBackend()
    assert isinstance(backend, SemanticBackend)
    assert backend.backend_name == "pgvector"


def test_search_result_dataclass_shape() -> None:
    r = SemanticSearchResult("d1", 0.85, {"k": "v"})
    assert r.decision_id == "d1"
    assert r.score == 0.85
    assert r.payload == {"k": "v"}


def test_backend_error_is_exception() -> None:
    assert issubclass(SemanticBackendError, Exception)


# ---- 2. In-memory upsert + search + delete + count (8) ------------------


def test_in_memory_starts_empty() -> None:
    b = InMemoryBackend()
    assert b.count() == 0
    assert b.search([0.1, 0.2, 0.3]) == []


def test_in_memory_upsert_and_count() -> None:
    b = InMemoryBackend()
    b.upsert("d1", [1.0, 0.0, 0.0], {"text": "alpha"})
    b.upsert("d2", [0.0, 1.0, 0.0], {"text": "beta"})
    assert b.count() == 2


def test_in_memory_upsert_replaces_same_id() -> None:
    b = InMemoryBackend()
    b.upsert("d1", [1.0, 0.0, 0.0], {"v": 1})
    b.upsert("d1", [0.0, 1.0, 0.0], {"v": 2})
    assert b.count() == 1
    results = b.search([0.0, 1.0, 0.0])
    assert results[0].payload["v"] == 2


def test_in_memory_search_returns_sorted_by_score() -> None:
    b = InMemoryBackend()
    b.upsert("d1", [1.0, 0.0, 0.0], {})
    b.upsert("d2", [0.0, 1.0, 0.0], {})
    b.upsert("d3", [0.5, 0.5, 0.0], {})
    # Query close to d1
    results = b.search([0.9, 0.1, 0.0], limit=3)
    assert results[0].decision_id == "d1"
    assert results[0].score >= results[1].score
    assert results[1].score >= results[2].score


def test_in_memory_search_respects_min_score() -> None:
    b = InMemoryBackend()
    b.upsert("d1", [1.0, 0.0, 0.0], {})
    b.upsert("d2", [0.0, 1.0, 0.0], {})
    # Query orthogonal to d2 -> cosine = 0; min_score 0.5 filters it
    results = b.search([1.0, 0.0, 0.0], min_score=0.5)
    ids = {r.decision_id for r in results}
    assert ids == {"d1"}


def test_in_memory_search_respects_limit() -> None:
    b = InMemoryBackend()
    for i in range(5):
        b.upsert(f"d{i}", [1.0, float(i), 0.0], {"i": i})
    results = b.search([1.0, 1.0, 0.0], limit=2)
    assert len(results) == 2


def test_in_memory_delete_removes_entry() -> None:
    b = InMemoryBackend()
    b.upsert("d1", [1.0, 0.0, 0.0], {})
    b.upsert("d2", [0.0, 1.0, 0.0], {})
    b.delete("d1")
    assert b.count() == 1
    ids = {r.decision_id for r in b.search([1.0, 1.0, 0.0])}
    assert ids == {"d2"}


def test_in_memory_rejects_bad_inputs() -> None:
    b = InMemoryBackend()
    with pytest.raises(ValueError):
        b.upsert("", [1.0], {})
    with pytest.raises(ValueError):
        b.upsert("d1", [], {})
    with pytest.raises(ValueError):
        b.search([1.0, 0.0], limit=0)


# ---- 3. pgvector lazy-import + extras + env discipline (5) --------------


def test_pgvector_does_not_import_extras_at_construction() -> None:
    """Construction must succeed even when psycopg2 + pgvector are
    NOT installed; lazy import only happens on first DB call."""
    backend = PgVectorBackend()
    # No DB call happened yet; private flag is False
    assert backend._extras_imported is False


def test_pgvector_is_available_without_env_returns_false(monkeypatch) -> None:
    monkeypatch.delenv("AO_KERNEL_PGVECTOR_DSN", raising=False)
    backend = PgVectorBackend()
    # If extras present: returns False because env missing.
    # If extras absent: also returns False.
    assert backend.is_available() is False


def test_pgvector_raises_typed_error_when_extras_missing() -> None:
    """When psycopg2 is missing, the first DB call must raise
    SemanticBackendError with the install-hint message."""
    if _module_installed("psycopg2"):
        pytest.skip("psycopg2 installed; cannot exercise missing-extras branch")
    backend = PgVectorBackend()
    with pytest.raises(SemanticBackendError) as excinfo:
        # Force the lazy import path
        backend._import_extras()
    assert "ao-kernel[pgvector]" in str(excinfo.value)


def test_pgvector_raises_typed_error_when_dsn_missing(monkeypatch) -> None:
    """If the extras are present but the DSN env var is missing, the
    connection attempt must raise the typed error with an actionable
    message."""
    if not _module_installed("psycopg2"):
        pytest.skip("psycopg2 not installed; covered by previous test")
    monkeypatch.delenv("AO_KERNEL_PGVECTOR_DSN", raising=False)
    backend = PgVectorBackend()
    with pytest.raises(SemanticBackendError) as excinfo:
        backend._connect()
    assert "AO_KERNEL_PGVECTOR_DSN" in str(excinfo.value)
    assert "operator-bound" in str(excinfo.value)


def test_pgvector_embedding_dim_validated() -> None:
    backend = PgVectorBackend(embedding_dim=384)
    with pytest.raises(ValueError):
        backend.upsert("d1", [1.0, 0.0], {})  # length 2 != 384


# ---- 4. Live pgvector exercise (operator opt-in; usually skipped) ------


def _has_live_pgvector_dsn() -> bool:
    return bool(os.environ.get("AO_KERNEL_PGVECTOR_DSN"))


@pytest.mark.skipif(
    not _has_live_pgvector_dsn(),
    reason="AO_KERNEL_PGVECTOR_DSN not set; operator opt-in live test",
)
def test_pgvector_live_roundtrip() -> None:
    """Exercised only when the operator sets AO_KERNEL_PGVECTOR_DSN +
    has provisioned the schema. Default CI skips this."""
    if not _module_installed("psycopg2"):
        pytest.skip("psycopg2 not installed despite DSN env; install [pgvector] extra")
    backend = PgVectorBackend(embedding_dim=3)
    backend.upsert("test_d1", [1.0, 0.0, 0.0], {"text": "alpha"})
    backend.upsert("test_d2", [0.0, 1.0, 0.0], {"text": "beta"})
    results = backend.search([1.0, 0.0, 0.0], limit=1)
    assert results
    assert results[0].decision_id == "test_d1"
    backend.delete("test_d1")
    backend.delete("test_d2")


# ---- 5. Module structure + guard flag discipline (4) -------------------


def test_semantic_backends_module_exposes_public_api() -> None:
    mod = import_module("ao_kernel.context.semantic_backends")
    for name in ("SemanticBackend", "SemanticBackendError", "SemanticSearchResult", "InMemoryBackend"):
        assert hasattr(mod, name), f"public API missing {name}"


def test_pgvector_module_does_not_import_psycopg2_at_top_level() -> None:
    """The module-level import section must NOT pull psycopg2/pgvector
    so the [pgvector] extra stays opt-in."""
    from ao_kernel.context.semantic_backends import pgvector as pg_mod

    src = open(pg_mod.__file__).read()
    # The imports inside _import_extras / _connect bodies are OK; the
    # module-level import section must not reference psycopg2 / pgvector
    module_top = src.split("class PgVectorBackend")[0]
    assert "import psycopg2" not in module_top
    assert "from pgvector" not in module_top


def test_module_docstring_pins_guard_flag_constraints() -> None:
    from ao_kernel.context import semantic_backends as mod

    doc = mod.__doc__ or ""
    assert "live_adapter_execution" in doc
    assert "support_widening" in doc
    assert "production_platform_claim" in doc
    assert "const false" in doc


def test_no_workflow_mutation() -> None:
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    workflow_changes = proc.stdout.split()
    assert workflow_changes == [], f"E-7-5 must not touch workflows: {workflow_changes}"
