from __future__ import annotations

from ao_kernel._internal.repo_intelligence.ignore_rules import should_ignore_path


def test_default_ignore_matches_exact_segments() -> None:
    assert should_ignore_path(".git/config", is_dir=False).ignored is True
    assert should_ignore_path("pkg/__pycache__/mod.pyc", is_dir=False).ignored is True
    assert should_ignore_path(".ao/context/repo_map.json", is_dir=False).ignored is True
    assert should_ignore_path("dist/wheel.whl", is_dir=False).ignored is True


def test_default_ignore_matches_egg_info_glob() -> None:
    decision = should_ignore_path("ao_kernel.egg-info/PKG-INFO", is_dir=False)

    assert decision.ignored is True
    assert decision.reason == "default_ignore:*.egg-info:file"


def test_non_ignored_source_path_is_allowed() -> None:
    decision = should_ignore_path("ao_kernel/repo_intelligence/__init__.py", is_dir=False)

    assert decision.ignored is False
    assert decision.reason is None
