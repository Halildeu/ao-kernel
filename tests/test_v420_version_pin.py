"""v4.2.0 release version + dependency pin tests.

Single source-of-truth pin: pyproject.toml::project.version,
ao_kernel.__version__, and the Keep-a-Changelog [4.2.0] entry MUST
all agree. PyYAML runtime dependency MUST stay declared. This release
cuts the 117 commits of post-4.1.0 work (V5 governed-control-plane
hardening: observability, security, docs, install lifecycle, AO-MA
orchestration, the Epic 9 supersession reframe, and the consumer
onboarding guide) onto PyPI as a minor release. It is a governed
control-plane readiness release, NOT a production-platform promotion:
the three guard flags remain const false.

Semantic discipline (carried from the v4.1.0 lane, Codex thread
019e809a): a release PR may only change project.version +
project.dependencies + (optional) project.description; project.scripts,
[build-system], [tool.setuptools.*], entrypoint, and tool config
changes belong to a separate review lane.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"


def _load_pyproject() -> dict:
    with _PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def test_pyproject_version_is_4_2_0() -> None:
    data = _load_pyproject()
    assert data["project"]["version"] == "4.2.0"


def test_ao_kernel_dunder_version_is_4_2_0() -> None:
    import ao_kernel

    assert ao_kernel.__version__ == "4.2.0"


def test_version_consistency_pyproject_matches_dunder() -> None:
    """Single source-of-truth pin: pyproject.toml::project.version ==
    ao_kernel.__version__. Drift breaks `pip install ao-kernel==X.Y.Z`
    + import-time version reporting."""

    import ao_kernel

    data = _load_pyproject()
    assert data["project"]["version"] == ao_kernel.__version__


def test_pyyaml_runtime_dependency_declared() -> None:
    """quality_profile.py ADR parse path requires PyYAML. Runtime
    declaration (NOT a [quality] extra) so `pip install ao-kernel`
    alone is sufficient to run `ao-kernel quality validate-adr`."""

    data = _load_pyproject()
    deps = data["project"]["dependencies"]
    assert any(dep.lower().startswith("pyyaml") for dep in deps), (
        f"PyYAML runtime dependency missing from project.dependencies: {deps}"
    )


def test_changelog_has_4_2_0_entry() -> None:
    """Keep-a-Changelog [4.2.0] - YYYY-MM-DD entry MUST exist; release
    discipline (ADR-0005) enforced at release time."""

    text = _CHANGELOG.read_text(encoding="utf-8")
    assert "## [4.2.0]" in text, "CHANGELOG.md missing [4.2.0] release entry"


def test_changelog_preserves_prior_4_1_0_entry() -> None:
    """The prior [4.1.0] entry MUST remain (history is append-only)."""

    text = _CHANGELOG.read_text(encoding="utf-8")
    assert "## [4.1.0]" in text, "CHANGELOG.md must preserve the [4.1.0] history entry"


def test_changelog_section_order_unreleased_then_4_2_0_then_4_1_0() -> None:
    """Heading order MUST be [Unreleased] above [4.2.0] above [4.1.0] so
    future PRs keep dogfooding the per-PR Keep-a-Changelog discipline and
    release history stays newest-first."""

    text = _CHANGELOG.read_text(encoding="utf-8")
    unreleased_idx = text.find("## [Unreleased]")
    v420_idx = text.find("## [4.2.0]")
    v410_idx = text.find("## [4.1.0]")
    assert unreleased_idx >= 0
    assert v420_idx > unreleased_idx, "[Unreleased] heading MUST appear above [4.2.0]"
    assert v410_idx > v420_idx, "[4.2.0] heading MUST appear above [4.1.0]"


def test_release_keeps_guard_flags_false() -> None:
    """A governed control-plane readiness release must not flip any guard
    flag. gpp_status remains keep_narrow_stable_runtime."""

    gpp = _REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
    import json

    data = json.loads(gpp.read_text(encoding="utf-8"))
    flags = data.get("guard_flags", data)
    for key in ("support_widening_allowed", "production_platform_claim_allowed", "live_adapter_execution_allowed"):
        # Search nested if needed.
        val = flags.get(key) if isinstance(flags, dict) else None
        if val is None and isinstance(data, dict):
            val = data.get(key)
        assert val is False, f"{key} must be False for a control-plane readiness release"


def test_release_facing_install_surfaces_match_version() -> None:
    """Active operator/consumer install instructions MUST track the release
    version, so a release never ships pointing users/operators at the prior
    version. Pins the surfaces Codex flagged on the v4.2.0 review (thread
    019ea0f0): consumer onboarding exact pin, Helm default image tag, and the
    operator publish-dispatch ref/checklist."""

    import json

    version = _load_pyproject()["project"]["version"]

    onboarding = (_REPO_ROOT / "docs" / "USING-AO-KERNEL-IN-YOUR-PROJECT.md").read_text(encoding="utf-8")
    assert f"ao-kernel=={version}" in onboarding, f"onboarding exact-pin example must be ao-kernel=={version}"

    values = (_REPO_ROOT / "deploy" / "helm" / "ao-kernel" / "values.yaml").read_text(encoding="utf-8")
    assert f'tag: "{version}"' in values, f"Helm values default image tag must be {version}"

    checklist = json.loads(
        (_REPO_ROOT / "docs" / "operator-runbooks" / "operator-action-checklist.v1.json").read_text(encoding="utf-8")
    )
    publish = next(a for a in checklist["actions"] if a["id"] == "p0-1-pypi-publish")
    assert publish["dispatch_inputs"]["ref"] == f"refs/tags/v{version}", (
        f"operator publish-dispatch ref must be refs/tags/v{version}"
    )
    assert any(f"/{version}/" in art for art in publish["expected_artifacts"]), (
        f"operator publish expected PyPI artifact must reference {version}"
    )
