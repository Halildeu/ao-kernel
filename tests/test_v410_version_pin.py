"""v4.1.0 release version + dependency pin tests.

Single source-of-truth pin: pyproject.toml::project.version,
ao_kernel.__version__, and the Keep-a-Changelog [4.1.0] entry MUST
all agree. Pyyaml runtime dependency MUST be declared. Tests added
by PR-B (AO-MA-11G-2b) for the v4.1.0 release lifecycle.

Codex thread 019e809a (CNS-20260601-003) iter-3 AGREE contract:
PR-B may only change project.version + project.dependencies +
(optional) project.description; project.scripts, [build-system],
[tool.setuptools.*], entrypoint, and tool config changes belong to
a separate review lane (semantic discipline).
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


def test_pyproject_version_is_4_1_0() -> None:
    data = _load_pyproject()
    assert data["project"]["version"] == "4.1.0"


def test_ao_kernel_dunder_version_is_4_1_0() -> None:
    import ao_kernel

    assert ao_kernel.__version__ == "4.1.0"


def test_version_consistency_pyproject_matches_dunder() -> None:
    """Single source-of-truth pin: pyproject.toml::project.version ==
    ao_kernel.__version__. Drift breaks `pip install ao-kernel==X.Y.Z`
    + import-time version reporting."""

    import ao_kernel

    data = _load_pyproject()
    assert data["project"]["version"] == ao_kernel.__version__


def test_pyyaml_runtime_dependency_declared() -> None:
    """AO-MA-11G-1 quality_profile.py ADR parse path requires PyYAML.
    Runtime declaration (NOT [quality] extras) chosen by Codex thread
    019e809a iter-2 absorb so `pip install ao-kernel` alone is
    sufficient to run `ao-kernel quality validate-adr`."""

    data = _load_pyproject()
    deps = data["project"]["dependencies"]
    assert any(dep.lower().startswith("pyyaml") for dep in deps), (
        f"PyYAML runtime dependency missing from project.dependencies: {deps}"
    )


def test_changelog_has_4_1_0_entry() -> None:
    """Keep-a-Changelog [4.1.0] - YYYY-MM-DD entry MUST exist; release
    discipline (ADR-0005) enforced at release time."""

    text = _CHANGELOG.read_text(encoding="utf-8")
    assert "## [4.1.0]" in text, "CHANGELOG.md missing [4.1.0] release entry"


def test_changelog_has_unreleased_above_4_1_0() -> None:
    """The [Unreleased] heading MUST stay above [4.1.0] so future PRs
    can keep dogfooding the Keep-a-Changelog per-PR discipline."""

    text = _CHANGELOG.read_text(encoding="utf-8")
    unreleased_idx = text.find("## [Unreleased]")
    v410_idx = text.find("## [4.1.0]")
    assert unreleased_idx >= 0
    assert v410_idx > unreleased_idx, "[Unreleased] heading MUST appear above [4.1.0]"
