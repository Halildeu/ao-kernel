"""V5 Epic 8 E-8-2 invariants: multi-tenant production config recipe.

A delegating recipe doc: namespace-per-tenant isolation that wires the Epic 4
chart surfaces (E-4-2a boundary, E-4-3 PG/secret, E-4-4 monitoring, E-4-5
netpol/PSS). It introduces no new chart features and flips no guard flag.

Machine-enforced invariants:
  - recipe doc present + covers the namespace-per-tenant model
  - delegates to E-4-2a/E-4-3/E-4-4/E-4-5 (no new chart feature invented here)
  - per-tenant overlay uses secretKeyRef (secretName), never inline password
  - isolation checklist present (dedicated ns/db/secret/netpol/quota)
  - referenced delegate docs exist in the repo
  - no guard-flag key; no .github/workflows/ mutation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC = _REPO_ROOT / "docs" / "MULTI-TENANT-CONFIG-RECIPE.md"


# ---- 1. doc present + model (3) -----------------------------------------


def test_recipe_doc_present() -> None:
    assert _DOC.is_file(), "docs/MULTI-TENANT-CONFIG-RECIPE.md missing (E-8-2)"


def test_recipe_namespace_per_tenant_model() -> None:
    text = _DOC.read_text(encoding="utf-8").lower()
    assert "namespace" in text and "per tenant" in text
    assert "deployment-level isolation" in text or "namespace-level" in text


def test_recipe_has_isolation_checklist() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert "Isolation checklist" in text
    # checklist must require dedicated DB + secret + netpol + quota
    low = text.lower()
    for item in ("dedicated namespace", "dedicated postgresql", "networkpolicy", "resourcequota"):
        assert item in low, f"checklist missing: {item}"


# ---- 2. delegation (2) --------------------------------------------------


def test_recipe_delegates_to_epic4_slices() -> None:
    text = _DOC.read_text(encoding="utf-8")
    for slice_id in ("E-4-2a", "E-4-3", "E-4-4", "E-4-5"):
        assert slice_id in text, f"recipe must delegate to {slice_id}"


def test_recipe_referenced_docs_exist() -> None:
    docs = _REPO_ROOT / "docs"
    for fname in ("MULTI-TENANT-DEPLOYMENT.md", "OPERATOR-SECRET-MANAGEMENT.md", "PRODUCTION-DEPLOYMENT-GUIDE.md"):
        assert (docs / fname).is_file(), f"delegate doc missing: {fname}"


# ---- 3. secret discipline (1) -------------------------------------------


def test_recipe_overlay_uses_secretkeyref_not_inline() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert "secretName" in text, "overlay must reference a Secret by name"
    # No inline password literal in the recipe overlay.
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("password:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            assert value == "", f"recipe must not show inline password: {line!r}"


# ---- 4. governance (2) --------------------------------------------------


def test_no_guard_flag_enable_in_recipe() -> None:
    """The recipe may NAME guard flags only in a 'not touched' affirmation,
    never set one to true."""
    text = _DOC.read_text(encoding="utf-8")
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert f"{flag}: true" not in text, f"recipe must not enable guard flag {flag}"
        assert f"{flag}=true" not in text, f"recipe must not enable guard flag {flag}"


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_8_2_multitenant_config_recipe.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-8-2 test not ADDED by this PR (introducer pattern); invariant N/A")
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
    assert not touched, f"E-8-2 must not touch .github/workflows/. Touched: {touched}"
