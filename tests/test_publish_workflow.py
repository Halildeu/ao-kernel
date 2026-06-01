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


def test_publish_workflow_twine_args_are_strict_whitelist() -> None:
    """P0-GATE-1 (Codex iter-1 absorb): `twine check` args MUST be the strict
    whitelist `dist/*.whl dist/*.tar.gz` ONLY — nothing more, nothing less.

    Stronger than `no_naked_dist_glob`: rejects ANY broader glob like
    `dist/*.*` (would match JSON), `dist/**` (recursive), `dist/` (entire dir),
    or extra unrelated args. Pin exactly the wheel + sdist whitelist so future
    drift cannot reintroduce JSON-matching surface.
    """
    content = _publish_workflow().read_text(encoding="utf-8")
    twine_lines = [line for line in content.splitlines() if "twine check" in line and not line.lstrip().startswith("#")]
    assert twine_lines, "no executable `twine check` line found in publish.yml"
    for line in twine_lines:
        # Capture everything after `twine check` on the executable line.
        # Strip leading YAML scalar prefix (e.g. `run: `).
        idx = line.find("twine check")
        args = line[idx + len("twine check") :].strip()
        # The strict whitelist (both globs in either order).
        allowed = {"dist/*.whl dist/*.tar.gz", "dist/*.tar.gz dist/*.whl"}
        assert args in allowed, (
            f"publish.yml `twine check` args NOT in strict whitelist:\n"
            f"  got: {args!r}\n"
            f"  allowed: {sorted(allowed)!r}\n"
            f"Any broader glob (dist/*, dist/*.*, dist/**) matches non-distribution files "
            f"(e.g. JSON evidence) and causes InvalidDistribution on PyPI publish."
        )


def test_publish_workflow_dispatch_ref_is_required_and_v_tag_guarded() -> None:
    """P0-GATE-1 (Codex iter-3 absorb): workflow_dispatch.inputs.ref MUST be
    `required: true` AND a fail-closed guard step MUST reject non-v* refs.

    Without these guards, operator could trigger workflow_dispatch with no
    `ref` input (empty default) and accidentally publish the dispatch branch
    HEAD to PyPI instead of the intended version tag. Defense-in-depth:
    (a) `required: true` makes the field mandatory in the GitHub UI,
    (b) shell guard validates the ref matches `v*` semver tag pattern.
    """
    content = _publish_workflow().read_text(encoding="utf-8")
    # inputs.ref must be marked required: true (not optional/default empty).
    assert re.search(
        r"inputs:\s*\n\s*ref:[\s\S]{0,300}?required:\s*true",
        content,
    ), (
        "publish.yml `workflow_dispatch.inputs.ref` NOT marked `required: true` — "
        "operator could trigger with empty ref and publish branch HEAD to PyPI."
    )
    # A fail-closed guard step must check the ref pattern before checkout.
    # Look for shell logic that exits non-zero for non-v* refs.
    has_v_pattern_check = re.search(
        r"if:\s*github\.event_name\s*==\s*'workflow_dispatch'"
        r"[\s\S]{0,800}?"
        r"(?:v\[0-9\]|v\*|refs/tags/v|=~.{0,40}v\d)",
        content,
    )
    assert has_v_pattern_check, (
        "publish.yml missing fail-closed ref guard step — workflow_dispatch ref "
        "is not validated against v* tag pattern before checkout/publish."
    )


def test_publish_workflow_has_workflow_dispatch_with_ref_input() -> None:
    """P0-GATE-1 (Codex iter-1 absorb): publish workflow MUST expose
    `workflow_dispatch` with optional `ref` input for manual re-trigger.

    When an existing tag's first publish failed (as v4.1.0 did 2026-06-01)
    and the `archive/**` ruleset blocks tag delete/force-update, the only
    safe re-publish path is `workflow_dispatch` with `inputs.ref` pointing
    at the existing tag. The checkout step MUST honor that input.
    """
    content = _publish_workflow().read_text(encoding="utf-8")
    assert "workflow_dispatch:" in content, (
        "publish.yml missing `workflow_dispatch:` — manual re-trigger path absent; "
        "failed-tag re-publish blocked when `archive/**` ruleset prevents tag delete."
    )
    assert re.search(r"inputs:\s*\n\s*ref:", content), (
        "publish.yml `workflow_dispatch` missing `inputs.ref` — operator cannot specify the tag/commit to re-publish."
    )
    # The checkout step must use that input (not hardcoded github.ref only).
    assert re.search(r"ref:\s*\$\{\{\s*inputs\.ref\s*\|\|", content), (
        "publish.yml checkout step does NOT honor `inputs.ref` — manual dispatch "
        "with a ref input would still checkout the dispatching branch HEAD."
    )


def test_publish_workflow_strips_non_distribution_files_from_dist() -> None:
    """P0-GATE-1 (Codex iter-2 absorb): publish workflow MUST strip non-
    distribution files from `dist/` BEFORE twine check + pypa publish.

    When `workflow_dispatch` republishes an existing tag, the tag's older
    `packaging_smoke.py` may still write evidence (JSON) to `dist/`. Defense-
    in-depth: even if the tag predates the path-migration fix, the workflow
    itself removes anything that is not `.whl` or `.tar.gz` from `dist/`
    before twine + pypa publish. Without this step, existing-tag republish
    via workflow_dispatch would reintroduce the InvalidDistribution failure.
    """
    content = _publish_workflow().read_text(encoding="utf-8")
    # Multi-line shell scripts in YAML `run: |` blocks split `find ... \` across
    # lines, so match with DOTALL. Require dist/ scope + both exclusion patterns
    # + a delete action within a bounded window (no false-positive across job
    # boundaries — cap at 800 chars to avoid spanning unrelated steps).
    cleanup_block = re.search(
        r"find\s+dist\b[\s\S]{0,800}?-name\s+['\"]\*\.whl['\"][\s\S]{0,800}?"
        r"-name\s+['\"]\*\.tar\.gz['\"][\s\S]{0,800}?(?:-delete|-exec\s+rm)",
        content,
    )
    assert cleanup_block, (
        "publish.yml missing `find dist ! -name '*.whl' ! -name '*.tar.gz' "
        "-delete` cleanup step — existing-tag republish via workflow_dispatch "
        "would re-pollute dist/ with JSON evidence from the tag's older "
        "packaging_smoke.py."
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
