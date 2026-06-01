"""Invariant tests for .github/workflows/publish.yml (PyPI trusted publishing).

P0-GATE-1 (V5-PR #783) regression guard: twine check glob MUST be distribution-
specific. Naked `dist/*` matches packaging_smoke.py-emitted JSON evidence and
triggers `InvalidDistribution: Unknown distribution format` on PyPI publish.
"""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _publish_workflow() -> Path:
    return _repo_root() / ".github" / "workflows" / "publish.yml"


def test_publish_workflow_exists() -> None:
    """publish.yml MUST exist at the canonical path (PyPI trusted publishing)."""
    assert _publish_workflow().is_file(), "publish.yml missing — PyPI trusted publishing workflow not defined"


def test_publish_workflow_has_twine_check_step() -> None:
    """Publish workflow MUST include a `twine check` step (distribution validation)."""
    content = _publish_workflow().read_text(encoding="utf-8")
    assert "twine check" in content, "publish.yml missing `twine check` step — distribution validation absent"


def test_publish_workflow_twine_glob_is_distribution_specific() -> None:
    """P0-GATE-1 invariant: `twine check` glob MUST be `dist/*.whl dist/*.tar.gz`.

    Regression guard: bare `twine check dist/*` matches packaging_smoke.py-emitted
    JSON evidence (ri7-packaging-smoke-evidence.v1.json) and causes:
        InvalidDistribution: Unknown distribution format: dist/<evidence>.json
    triggering PyPI publish FAIL. v4.1.0 publish failed exactly this way on
    2026-06-01; fix pins glob to wheel + sdist only.
    """
    content = _publish_workflow().read_text(encoding="utf-8")
    # Must contain explicit globs for both distribution formats.
    assert re.search(r"twine check.*dist/\*\.whl", content), (
        "publish.yml twine check missing `dist/*.whl` glob — wheel validation skipped"
    )
    assert re.search(r"twine check.*dist/\*\.tar\.gz", content), (
        "publish.yml twine check missing `dist/*.tar.gz` glob — sdist validation skipped"
    )


def test_publish_workflow_no_naked_dist_glob() -> None:
    """P0-GATE-1 regression guard: `twine check dist/*` (bare wildcard) FORBIDDEN.

    `dist/*` matches non-distribution files (JSON evidence emitted by
    packaging_smoke.py) and causes InvalidDistribution PyPI publish failure.
    """
    content = _publish_workflow().read_text(encoding="utf-8")
    # Reject any line containing exactly `twine check dist/*` followed by
    # whitespace, end-of-line, or another non-glob-extension character.
    # Matches `dist/*` NOT followed by a `.` (file-extension qualifier).
    forbidden_pattern = re.compile(r"twine check[^\n]*\bdist/\*(?![.\w])")
    matches = forbidden_pattern.findall(content)
    assert not matches, (
        f"publish.yml uses forbidden naked glob `dist/*` (matches JSON evidence): {matches}. "
        "Use `dist/*.whl dist/*.tar.gz` instead (distribution-specific globs)."
    )


def test_publish_workflow_has_pypi_environment() -> None:
    """Publish job MUST target `pypi` environment (trusted publishing OIDC scope)."""
    content = _publish_workflow().read_text(encoding="utf-8")
    assert re.search(r"environment:\s*pypi", content), (
        "publish.yml missing `environment: pypi` — trusted publishing OIDC scope not configured"
    )


def test_publish_workflow_has_id_token_write() -> None:
    """Publish job MUST grant `id-token: write` (OIDC for trusted publishing)."""
    content = _publish_workflow().read_text(encoding="utf-8")
    assert re.search(r"id-token:\s*write", content), (
        "publish.yml missing `id-token: write` permission — OIDC publishing will fail"
    )


def test_publish_workflow_trigger_is_version_tag() -> None:
    """Publish workflow MUST trigger on `v*` tags (semantic version release)."""
    content = _publish_workflow().read_text(encoding="utf-8")
    assert re.search(r'tags:\s*\["v\*"\]', content) or re.search(r"tags:\s*\n\s*-\s*['\"]v\*['\"]", content), (
        "publish.yml not triggered by v* tag push — release automation broken"
    )
