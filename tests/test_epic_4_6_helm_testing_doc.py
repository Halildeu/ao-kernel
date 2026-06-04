"""V5 Epic 4 E-4-6 invariants: helm-unittest CI doc + runbook + idempotency.

Delivers the chart testing runbook + helm-unittest render suites. The Python
invariant tests remain the CI source-of-truth (CI does not install Helm);
helm-unittest suites are operator-run.

Machine-enforced invariants:
  - docs/HELM-TESTING.md present + covers CI invocation, helm-unittest, idempotency
  - helm-unittest suites present under deploy/helm/ao-kernel/tests/
  - suites are valid YAML with a 'suite' + 'tests' shape
  - doc documents the epic-wide idempotency + default-safe contract
  - no guard-flag key; no .github/workflows/ mutation
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC = _REPO_ROOT / "docs" / "HELM-TESTING.md"
_SUITE_DIR = _REPO_ROOT / "deploy" / "helm" / "ao-kernel" / "tests"


# ---- 1. doc present + coverage (3) --------------------------------------


def test_doc_present() -> None:
    assert _DOC.is_file(), "docs/HELM-TESTING.md missing (E-4-6)"


def test_doc_covers_ci_and_helm_unittest() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert "pytest" in text, "doc must document the Python CI invariant layer"
    assert "helm unittest" in text, "doc must document the helm-unittest invocation"
    assert "helm template" in text, "doc must document local render smoke"


def test_doc_documents_idempotency_contract() -> None:
    text = _DOC.read_text(encoding="utf-8").lower()
    assert "idempoten" in text, "doc must cover the epic-wide idempotency contract"
    assert "default" in text and ("least-privilege" in text or "default-safe" in text)


# ---- 2. helm-unittest suites (3) ----------------------------------------


def test_suite_dir_has_suites() -> None:
    assert _SUITE_DIR.is_dir(), "helm-unittest suite dir missing"
    suites = list(_SUITE_DIR.glob("*_test.yaml"))
    assert len(suites) >= 2, f"expected >=2 helm-unittest suites, got {len(suites)}"


def test_suites_have_valid_shape() -> None:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    for suite in _SUITE_DIR.glob("*_test.yaml"):
        doc = yaml.safe_load(suite.read_text(encoding="utf-8"))
        assert "suite" in doc, f"{suite.name}: missing 'suite' key"
        assert "templates" in doc, f"{suite.name}: missing 'templates' key"
        assert isinstance(doc.get("tests"), list) and doc["tests"], f"{suite.name}: empty tests"


def test_deployment_suite_asserts_replicas_min_one() -> None:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    suite_path = _SUITE_DIR / "deployment_test.yaml"
    assert suite_path.is_file()
    text = suite_path.read_text(encoding="utf-8")
    # The suite must assert the HARD RULE replicas>=1 + non-root security.
    assert "replicas" in text and "runAsNonRoot" in text


# ---- 3. governance (2) --------------------------------------------------


def test_no_guard_flag_key_in_suites() -> None:
    for suite in _SUITE_DIR.glob("*_test.yaml"):
        text = suite.read_text(encoding="utf-8")
        for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
            assert flag not in text, f"guard-flag key in {suite.name}: {flag}"


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_4_6_helm_testing_doc.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-4-6 test not ADDED by this PR (introducer pattern); invariant N/A")
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
    assert not touched, f"E-4-6 must not touch .github/workflows/. Touched: {touched}"
