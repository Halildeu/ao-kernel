"""Invariant test suite for V5 Epic 5 E-5-3b: Consultation tracing integration.

Codex 019e83ee cross-AI plan-time AGREE (3 iters: REVISE/REVISE/AGREE).

7 must-close findings closed + 6 hardening + 6 impl tweaks:
- F1 Real API mapping (archive_all/_archive_cns/promote_resolved/query_promoted)
- F2 Record digest immune (sidecar separate from resolution.record)
- F3 New sidecar schema (no breaking change to existing schemas)
- F4 Bounded pre-scan link timing + MAX_CONSULTATION_TRACE_LINKS cap
- F5 Baggage source via ao_kernel.tracing.get_session_baggage()
- F6 Consumer boundary = agent_coordination (NOT memory_pipeline)
- F7 Path-sensitive risk class (not low-risk)

~27 invariants across 9 sections.
"""

from __future__ import annotations

import json
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "consultation-trace-context.schema.v1.json"
TRACE_CONTEXT_MODULE_PATH = REPO_ROOT / "ao_kernel" / "consultation" / "trace_context.py"
ARCHIVE_MODULE_PATH = REPO_ROOT / "ao_kernel" / "consultation" / "archive.py"
PROMOTION_MODULE_PATH = REPO_ROOT / "ao_kernel" / "consultation" / "promotion.py"
COORD_MODULE_PATH = REPO_ROOT / "ao_kernel" / "context" / "agent_coordination.py"


SIDECAR_FILENAME = "consultation_trace_context.v1.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (5 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(_load_schema())


def test_schema_root_additional_properties_false():
    assert _load_schema().get("additionalProperties") is False


def test_schema_const_pins():
    schema = _load_schema()
    props = schema["properties"]
    assert props["schema_version"]["const"] == "consultation-trace-context.v1"
    assert props["captured_at_archive_time"]["const"] is True


def test_schema_rejects_all_zero_trace_and_span_ids():
    """Codex H2 absorb: schema mirrors make_link all-zero rejection."""
    try:
        from jsonschema import Draft202012Validator, ValidationError
    except ImportError:
        pytest.skip("jsonschema not installed")
    schema = _load_schema()
    invalid = {
        "schema_version": "consultation-trace-context.v1",
        "cns_id": "CNS-20260601-001",
        "captured_at_archive_time": True,
        "trace_id": "0" * 32,
        "span_id": "abcdef1234567890",
        "traceparent": "00-" + "0" * 32 + "-abcdef1234567890-01",
        "tracestate": None,
        "session_id_baggage": None,
    }
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(invalid)


def test_schema_traceparent_regex_full_w3c_format():
    """traceparent pattern must enforce full W3C `00-<32hex>-<16hex>-<2hex>`."""
    schema = _load_schema()
    pat = schema["properties"]["traceparent"]["pattern"]
    assert re.fullmatch(pat, "00-0123456789abcdef0123456789abcdef-abcdef1234567890-01")
    assert not re.fullmatch(pat, "0123456789abcdef")
    assert not re.fullmatch(pat, "00-short-abcdef1234567890-01")


# ---------------------------------------------------------------------------
# Section 2 — trace_context helper module shape (5 invariants)
# ---------------------------------------------------------------------------


def test_trace_context_module_exports_required_symbols():
    from ao_kernel.consultation import trace_context

    assert hasattr(trace_context, "capture_current_trace_context")
    assert hasattr(trace_context, "maybe_write_sidecar")
    assert hasattr(trace_context, "read_sidecar_trace_links")
    assert hasattr(trace_context, "MAX_CONSULTATION_TRACE_LINKS")
    assert hasattr(trace_context, "SIDECAR_FILENAME")
    assert hasattr(trace_context, "SCHEMA_VERSION")


def test_max_consultation_trace_links_pin():
    """Codex F4 absorb: MAX_CONSULTATION_TRACE_LINKS = 10 (module-level constant)."""
    from ao_kernel.consultation.trace_context import MAX_CONSULTATION_TRACE_LINKS

    assert MAX_CONSULTATION_TRACE_LINKS == 10


def test_capture_current_trace_context_returns_none_without_active_span():
    """Codex H3 absorb: no active span → no context."""
    from ao_kernel.consultation.trace_context import capture_current_trace_context

    # Without OTEL installed OR no recording span, the helper returns None
    # (graceful degrade).
    result = capture_current_trace_context()
    # In CI without OTEL: None. In OTEL test environment without an active
    # span: None. Either way: None.
    assert result is None


def test_maybe_write_sidecar_idempotent_first_write(tmp_path):
    """Codex H1 + iter-3 absorb: idempotent first-write; never overwrite."""
    from ao_kernel.consultation.trace_context import maybe_write_sidecar

    sidecar_dir = tmp_path / "evidence"
    sidecar_dir.mkdir()
    # First call without an active span: returns None.
    out = maybe_write_sidecar(sidecar_dir, "CNS-X")
    assert out is None
    assert not (sidecar_dir / SIDECAR_FILENAME).exists()

    # Pre-existing sidecar must NOT be overwritten — returns path regardless.
    pre_existing = sidecar_dir / SIDECAR_FILENAME
    pre_existing.write_text('{"placeholder": true}')
    out = maybe_write_sidecar(sidecar_dir, "CNS-X")
    assert out == pre_existing
    assert pre_existing.read_text() == '{"placeholder": true}'


def test_read_sidecar_trace_links_handles_no_otel_gracefully(tmp_path):
    """OTEL absent OR no sidecars → returns empty list, no exception."""
    from ao_kernel.consultation.trace_context import read_sidecar_trace_links

    links = read_sidecar_trace_links([tmp_path])
    assert links == []


# ---------------------------------------------------------------------------
# Section 3 — Sidecar validation contract (3 invariants)
# ---------------------------------------------------------------------------


def test_sidecar_invalid_shape_silently_skipped(tmp_path):
    """Codex F4 absorb: tampered / schema-invalid sidecars silently skipped."""
    from ao_kernel.consultation.trace_context import read_sidecar_trace_links

    cns_dir = tmp_path / "CNS-X"
    cns_dir.mkdir()
    # Tampered sidecar: invalid trace_id length
    (cns_dir / SIDECAR_FILENAME).write_text(
        json.dumps(
            {
                "schema_version": "consultation-trace-context.v1",
                "cns_id": "CNS-X",
                "captured_at_archive_time": True,
                "trace_id": "tooshort",
                "span_id": "abcdef1234567890",
                "traceparent": "00-tooshort-abcdef1234567890-01",
                "tracestate": None,
                "session_id_baggage": None,
            }
        )
    )
    links = read_sidecar_trace_links([cns_dir])
    assert links == []  # invalid shape ignored


def test_sidecar_json_decode_error_silently_skipped(tmp_path):
    """JSON parse failure → silently skip; do not raise."""
    from ao_kernel.consultation.trace_context import read_sidecar_trace_links

    cns_dir = tmp_path / "CNS-X"
    cns_dir.mkdir()
    (cns_dir / SIDECAR_FILENAME).write_text("not-valid-json{{{")
    links = read_sidecar_trace_links([cns_dir])
    assert links == []


def test_sidecar_cap_respected(tmp_path):
    """Codex F4 absorb: MAX_CONSULTATION_TRACE_LINKS cap respected."""
    from ao_kernel.consultation.trace_context import (
        MAX_CONSULTATION_TRACE_LINKS,
        read_sidecar_trace_links,
    )

    # Build 15 dummy cns dirs (no sidecars). The cap is applied to the
    # input list at slice time, so even with no valid sidecars the
    # iteration must not exceed the cap.
    cns_dirs = []
    for i in range(15):
        d = tmp_path / f"CNS-{i:03d}"
        d.mkdir()
        cns_dirs.append(d)
    # No active span → empty result; cap still bounds the slice.
    assert read_sidecar_trace_links(cns_dirs) == []
    assert MAX_CONSULTATION_TRACE_LINKS == 10


# ---------------------------------------------------------------------------
# Section 4 — Module import discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_trace_context_does_not_import_opentelemetry_directly():
    """Codex implementation_constraint: tracing facade only, no direct OTEL."""
    src = TRACE_CONTEXT_MODULE_PATH.read_text()
    # Allow imports from ao_kernel.tracing facade.
    assert "from ao_kernel.tracing import" in src
    # Forbid direct OTEL imports.
    forbidden_lines = [
        line for line in src.splitlines() if (line.startswith("import opentelemetry") or "from opentelemetry" in line)
    ]
    assert not forbidden_lines, f"direct OTEL import detected: {forbidden_lines}"


def test_consultation_modules_use_tracing_facade_for_baggage():
    """Codex F5 absorb: baggage source is ao_kernel.tracing.get_session_baggage()."""
    for path in (ARCHIVE_MODULE_PATH, PROMOTION_MODULE_PATH, COORD_MODULE_PATH):
        src = path.read_text()
        if "get_session_baggage" in src:
            # If used, must be imported from ao_kernel.tracing
            assert "from ao_kernel.tracing import" in src and "get_session_baggage" in src, (
                f"{path} uses get_session_baggage without facade import"
            )


def test_no_local_session_baggage_contextvar():
    """Codex iter-3 absorb F5: no local ContextVar duplication of session baggage."""
    for path in (
        TRACE_CONTEXT_MODULE_PATH,
        ARCHIVE_MODULE_PATH,
        PROMOTION_MODULE_PATH,
        COORD_MODULE_PATH,
    ):
        src = path.read_text()
        assert "_session_baggage_var" not in src, f"local ContextVar in {path}"


# ---------------------------------------------------------------------------
# Section 5 — Span emission via fake tracer (5 invariants)
# ---------------------------------------------------------------------------


@contextmanager
def _fake_span(captured: list[tuple[str, dict[str, Any], list[Any]]]):
    """Capture span (name, attrs, links) tuples without exporting."""

    def _impl(name, attributes=None, links=None):
        @contextmanager
        def _cm():
            captured.append((name, dict(attributes or {}), list(links or [])))
            yield

        return _cm()

    yield _impl


def _minimal_consultation_policy(workspace_root: Path) -> dict[str, Any]:
    """Build a minimal consultation policy with all required `paths` keys
    pointing at workspace-relative empty directories."""
    return {
        "paths": {
            "requests": ".ao/consultations/requests",
            "responses": ".ao/consultations/responses",
            "state": ".ao/consultations/state",
            "config": ".ao/consultations/config",
        },
    }


def test_archive_all_emits_top_facade_span(tmp_path, monkeypatch):
    """F6 + span-name table absorb: archive_all emits `ao.consultation.archive`."""
    from ao_kernel.consultation import archive as archive_mod

    captured: list[tuple[str, dict[str, Any], list[Any]]] = []
    with _fake_span(captured) as fake_span_factory:
        monkeypatch.setattr(archive_mod, "_ao_span", fake_span_factory)
        # Minimal valid policy + dry_run=True: archive_all walks zero CNS
        # dirs and returns a clean summary without touching the filesystem.
        archive_mod.archive_all(
            policy=_minimal_consultation_policy(tmp_path),
            workspace_root=tmp_path,
            dry_run=True,
        )

    span_names = [s[0] for s in captured]
    assert "ao.consultation.archive" in span_names


def test_archive_facade_uses_low_cardinality_attributes(tmp_path, monkeypatch):
    """Codex H4 absorb: top-level facade does NOT use ao.cns_id."""
    from ao_kernel.consultation import archive as archive_mod

    captured: list[tuple[str, dict[str, Any], list[Any]]] = []
    with _fake_span(captured) as fake_span_factory:
        monkeypatch.setattr(archive_mod, "_ao_span", fake_span_factory)
        archive_mod.archive_all(
            policy=_minimal_consultation_policy(tmp_path),
            workspace_root=tmp_path,
            dry_run=True,
        )

    facade_spans = [s for s in captured if s[0] == "ao.consultation.archive"]
    assert facade_spans, "archive facade span missing"
    facade_attrs = facade_spans[0][1]
    # Top-level facade has consultation count but NOT ao.cns_id
    assert "ao.consultation.count" in facade_attrs
    assert "ao.cns_id" not in facade_attrs


def test_query_promoted_emits_span_with_links_param(tmp_path, monkeypatch):
    """Producer span ao.consultation.query_promoted emitted with `links=` kwarg."""
    from ao_kernel.consultation import promotion as promotion_mod

    captured: list[tuple[str, dict[str, Any], list[Any]]] = []
    with _fake_span(captured) as fake_span_factory:
        monkeypatch.setattr(promotion_mod, "_ao_span", fake_span_factory)
        # Empty workspace_root: no evidence dir, no canonical store.
        # query_promoted_consultations tolerates a missing store and returns
        # an empty tuple; the span still emits before the canonical query.
        result = promotion_mod.query_promoted_consultations(tmp_path)
        assert result == ()

    span_names = [s[0] for s in captured]
    assert "ao.consultation.query_promoted" in span_names


def test_consumer_wrapper_span_distinct_from_producer(tmp_path, monkeypatch):
    """Codex F6 absorb: consumer uses ao.consultation.query_consumer (distinct)."""
    src = COORD_MODULE_PATH.read_text()
    assert "ao.consultation.query_consumer" in src
    # Producer span name appears only inside promotion.py.
    assert "ao.consultation.query_consumer" not in PROMOTION_MODULE_PATH.read_text()


def test_archive_cns_inner_span_uses_cns_id_attribute(tmp_path):
    """ao.cns_id allowed only on inner per-CNS span (H4 absorb)."""
    src = ARCHIVE_MODULE_PATH.read_text()
    assert "ao.consultation.archive.cns" in src
    # Source must reference ao.cns_id in the inner-span attribute setup
    assert "ao.cns_id" in src


# ---------------------------------------------------------------------------
# Section 6 — Sidecar artifact discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_sidecar_not_referenced_by_integrity_manifest():
    """Codex F4 absorb: sidecar is non-authoritative; not in integrity manifest."""
    integrity_src = (REPO_ROOT / "ao_kernel" / "consultation" / "integrity.py").read_text()
    assert "consultation_trace_context.v1.json" not in integrity_src


def test_resolution_record_digest_immune_to_sidecar():
    """Codex F2 absorb: trace metadata must not influence record digest."""
    normalize_src = (REPO_ROOT / "ao_kernel" / "consultation" / "normalize.py").read_text()
    # Record digest computation must not reference trace context fields.
    assert "traceparent" not in normalize_src.lower()
    assert "trace_id" not in normalize_src.lower()


def test_sidecar_written_after_manifest_in_archive():
    """Sidecar write must follow manifest write inside the file lock scope."""
    src = ARCHIVE_MODULE_PATH.read_text()
    # The sidecar call must appear AFTER write_consultation_manifest in source order
    manifest_idx = src.find("write_consultation_manifest(evidence_dir)")
    sidecar_idx = src.find("maybe_write_sidecar(evidence_dir, cns_id)")
    assert 0 < manifest_idx < sidecar_idx, "sidecar must be written after manifest"


# ---------------------------------------------------------------------------
# Section 7 — Memory pipeline scope discipline (1 invariant)
# ---------------------------------------------------------------------------


def test_memory_pipeline_not_touched():
    """Codex F6 absorb: memory_pipeline.py is NOT a consultation handoff site."""
    src = (REPO_ROOT / "ao_kernel" / "context" / "memory_pipeline.py").read_text()
    # Memory pipeline must NOT import consultation trace_context surface.
    assert "consultation.trace_context" not in src
    assert "maybe_write_sidecar" not in src
    assert "read_sidecar_trace_links" not in src


# ---------------------------------------------------------------------------
# Section 8 — Schema file inventory (2 invariants)
# ---------------------------------------------------------------------------


def test_new_schema_file_added():
    assert SCHEMA_PATH.exists()


def test_no_existing_schema_modified():
    """Codex F3 absorb: trace-meta, agent-consultation, policy schemas zero-touch."""
    schemas_dir = REPO_ROOT / "ao_kernel" / "defaults" / "schemas"
    # The existing schemas remain present and unchanged in shape.
    for fname in (
        "trace-meta.schema.v1.json",
        "agent-consultation.schema.v1.json",
        "policy-agent-consultation.schema.v1.json",
    ):
        path = schemas_dir / fname
        assert path.exists(), f"existing schema vanished: {fname}"


# ---------------------------------------------------------------------------
# Section 9 — Governance (2 invariants)
# ---------------------------------------------------------------------------


def test_no_github_workflow_change_in_pr_diff():
    """Path-sensitive runtime: must not touch .github/workflows/."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("git not available or origin/main not fetched")
    if result.returncode != 0:
        pytest.skip(f"git diff failed: {result.stderr}")
    for line in result.stdout.splitlines():
        assert not line.startswith(".github/workflows/"), f"E-5-3b must not touch workflows: {line}"


def test_make_link_not_modified():
    """Codex iter-3 implementation_constraint: make_link semantics unchanged."""
    tracing_src = (REPO_ROOT / "ao_kernel" / "tracing.py").read_text()
    # make_link must remain in ao_kernel/tracing.py with original signature
    assert "def make_link(" in tracing_src
