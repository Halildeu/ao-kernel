"""Doc smoke test for ``docs/MIGRATION-V5.md`` (V5 Epic 8 E-8-6).

Pins shape invariants that operator-facing migration guide MUST carry
to be a useful, non-stale runbook:

- Document exists at canonical path.
- Required top-level sections are present (TL;DR, upgrade steps,
  OTEL config, V5 mirror discipline, plan-approval gate, known
  gotchas, references).
- Public claim language is conservative: NO ``production-ready``
  marketing claim, NO unauthorized guard-flag flip language, NO
  promise that v5.0.0 is shipped.
- OTEL env var documentation covers all 9 tunables exposed by
  ``ao_kernel/telemetry_config.py`` (Epic 5 E-5-1, PR #791).
- Cross-doc links resolve to existing repo paths.
"""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _doc_path() -> Path:
    return _repo_root() / "docs" / "MIGRATION-V5.md"


def _doc_text() -> str:
    return _doc_path().read_text(encoding="utf-8")


def test_migration_v5_exists_at_canonical_path() -> None:
    assert _doc_path().exists(), "docs/MIGRATION-V5.md must exist (Epic 8 E-8-6)"


def test_migration_v5_top_header_is_correct() -> None:
    text = _doc_text()
    first_line = text.splitlines()[0]
    assert first_line.startswith("# Migration Guide: v4.x → v5.0.0"), first_line


def test_migration_v5_required_sections_present() -> None:
    """Each section must surface so operators can find core info quickly."""
    text = _doc_text()
    required_sections = [
        "## 1. TL;DR",
        "## 2. What changed",
        "## 3. Upgrade steps",
        "## 4. OTEL production tunables quick start",
        "## 5. V5 mirror discipline",
        "## 6. Plan-approval gate discipline",
        "## 7. Known migration gotchas",
        "## 8. References",
        "## 9. Document status",
    ]
    missing = [s for s in required_sections if s not in text]
    assert not missing, f"Missing required sections: {missing}"


def test_migration_v5_conservative_public_claim() -> None:
    """Guard the migration guide from premature production-ready language.

    v5.0.0 is a PLANNED promotion; until Epic 9 final supersession PR
    lands with explicit operator authorization, the guide must NOT
    claim ``production-ready``, ``GA``, ``stable production``, or
    suggest the three guard flags are flipped.
    """
    text = _doc_text().lower()
    forbidden = [
        "production-ready release",
        "ga release",
        "live_adapter_execution=true is the default",
        "support_widening=true is the default",
        "production_platform_claim=true is the default",
    ]
    for phrase in forbidden:
        assert phrase not in text, f"Forbidden marketing claim found: {phrase!r}"


def test_migration_v5_otel_env_vars_complete() -> None:
    """All 9 OTEL prod tunables from Epic 5 E-5-1 (PR #791) documented.

    Source of truth: ``ao_kernel/telemetry_config.py`` env vars.
    """
    text = _doc_text()
    required_env_vars = [
        "AO_KERNEL_OTEL_ENABLED",
        "AO_KERNEL_OTEL_EXPORTER_OTLP_ENDPOINT",
        "AO_KERNEL_OTEL_SAMPLING_RATE",
        "AO_KERNEL_OTEL_BATCH_SIZE",
        "AO_KERNEL_OTEL_SERVICE_NAME",
        "AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES",
        "AO_KERNEL_OTEL_INSECURE",
        "AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS",
        "AO_KERNEL_OTEL_HEADERS",
    ]
    missing = [v for v in required_env_vars if v not in text]
    assert not missing, f"Missing OTEL env vars: {missing}"


def test_migration_v5_downgrade_path_pinned() -> None:
    """Operator must always know how to roll back. Pin the downgrade
    pin (``pip install ao-kernel==4.1.0``) is callable verbatim."""
    text = _doc_text()
    assert "pip install ao-kernel==4.1.0" in text, "Downgrade pin must reference v4.1.0"
    assert "Downgrade path" in text or "downgrade path" in text


def test_migration_v5_cross_doc_links_resolve() -> None:
    """Each markdown link (``[label](relative/path)``) under docs/
    must resolve to an existing repo file. External (http*) links and
    placeholder ``TBD`` links are skipped.
    """
    text = _doc_text()
    repo = _repo_root()
    docs_dir = _doc_path().parent
    pattern = re.compile(r"\]\(([^)]+)\)")

    missing: list[str] = []
    for match in pattern.finditer(text):
        target = match.group(1).strip()
        # Skip external links + anchors + placeholders
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target in {"TBD", "tbd"}:
            continue
        # Strip in-doc anchor fragment
        target_path_str = target.split("#", 1)[0]
        if not target_path_str:
            continue
        target_path = (docs_dir / target_path_str).resolve()
        # Allow ``../something`` traversal up to repo root
        try:
            target_path.relative_to(repo)
        except ValueError:
            missing.append(f"{target} (escapes repo)")
            continue
        if not target_path.exists():
            missing.append(target)

    assert not missing, f"Migration guide has broken cross-doc links: {missing}"


def test_migration_v5_guard_flag_constant_false_pinned() -> None:
    """v5.0.0 keeps all three guard flags ``const false`` unless and
    until Epic 9 ships. This invariant must be visible in the guide.
    """
    text = _doc_text()
    assert "const false" in text, "Guard flag const-false claim must be present"
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in text, f"Guard flag {flag} must be named in migration guide"
