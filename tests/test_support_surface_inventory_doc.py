"""V5 Epic 3 E-3-4 invariants: support surface inventory document.

A docs-only slice: restates today's narrow-stable boundary (does not re-claim or
widen it) + inventories the five future-widening surface dimensions with their
prerequisites + a boundary disclaimer. Machine-enforced: presence, the five
surface classes, the disclaimer, a reference to the authoritative boundary doc,
absence of "production-ready" claim language, and no guard-flag flip.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC = _REPO_ROOT / "docs" / "SUPPORT-SURFACE-INVENTORY.md"


def _text() -> str:
    return _DOC.read_text(encoding="utf-8")


def _without_fenced_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


# ---- 1. presence + structure (3) ----------------------------------------


def test_doc_present() -> None:
    assert _DOC.is_file(), "docs/SUPPORT-SURFACE-INVENTORY.md missing (E-3-4)"


def test_doc_inventories_all_five_surface_classes() -> None:
    text = _text()
    for sclass in ("provider", "python_version", "os_platform", "db_backend", "deployment_topology"):
        assert f"`{sclass}`" in text, f"inventory must name surface_class {sclass}"


def test_doc_references_authoritative_boundary() -> None:
    text = _text()
    assert "SUPPORT-BOUNDARY.md" in text, "must point to the authoritative boundary doc"
    assert "ST-2" in text and "freeze" in text.lower(), "must restate the ST-2 boundary freeze"


# ---- 2. prerequisites, not promises (1) ---------------------------------


def test_doc_states_prerequisites_per_dimension() -> None:
    low = _text().lower()
    assert "prerequisite" in low, "must frame widening requirements as prerequisites"
    # at least the key per-class thresholds are named
    for needle in ("live integration test", "pytest matrix", "smoke per", "round-trip", "isolation test"):
        assert needle in low, f"prerequisite list missing: {needle!r}"


# ---- 3. boundary disclaimer — announces no widening (1) ------------------


def test_doc_has_no_announcement_disclaimer() -> None:
    text = _text()
    expected = (
        "This inventory does not announce any widening; it names what would be required "
        "if widening were authorized."
    )
    assert expected in text, "must carry the E-3-4 verbatim no-widening disclaimer"
    assert "Epic 9" in text, "disclaimer must defer widening authority to Epic 9 supersession"


# ---- 4. no production-claim language (1) ---------------------------------


def test_doc_has_no_production_claim_language() -> None:
    text = _without_fenced_code(_text())
    forbidden = [
        re.compile(r"production[- ]ready", re.IGNORECASE),
        re.compile(r"production[- ]safe", re.IGNORECASE),
        re.compile(r"production[- ]certified", re.IGNORECASE),
        re.compile(r"production[- ]grade", re.IGNORECASE),
        re.compile(r"fully[- ]supported", re.IGNORECASE),
        re.compile(r"\bGA\b"),
        re.compile(r"generally available", re.IGNORECASE),
        re.compile(r"officially supported", re.IGNORECASE),
        re.compile(r"stable support", re.IGNORECASE),
        re.compile(r"beta exit", re.IGNORECASE),
        re.compile(r"supported today", re.IGNORECASE),
        re.compile(r"ready for production", re.IGNORECASE),
    ]
    for pattern in forbidden:
        assert not pattern.search(text), f"inventory must not contain claim pattern {pattern.pattern!r}"


# ---- 5. no guard-flag flip (1) ------------------------------------------


def test_doc_flips_no_guard_flag() -> None:
    text = _text()
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert f"{flag}: true" not in text and f"{flag}=true" not in text, f"must not flip {flag}"
    assert "const false" in text, "must affirm the guard flags stay const false"


# ---- 6. governance: no tier/workflow mutation (2) -----------------------


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_support_surface_inventory_doc.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-3-4 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-3-4 must not touch .github/workflows/. Touched: {touched}"


def test_no_public_boundary_or_beta_tier_mutation_in_diff() -> None:
    proc = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "docs/SUPPORT-BOUNDARY.md",
            "docs/PUBLIC-BETA.md",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-3-4 must not mutate support boundary or public beta tier docs: {touched}"
