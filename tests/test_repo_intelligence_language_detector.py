from __future__ import annotations

from ao_kernel._internal.repo_intelligence.language_detector import detect_language, language_extensions


def test_detect_language_by_extension_and_filename() -> None:
    assert detect_language("ao_kernel/cli.py") == "python"
    assert detect_language("web/src/App.tsx") == "typescript"
    assert detect_language("README.md") == "markdown"
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language("Makefile") == "makefile"
    assert detect_language("types/package.d.ts") == "typescript"
    assert detect_language("assets/image.bin") == "unknown"


def test_language_extensions_returns_sorted_copy() -> None:
    extensions = language_extensions()

    assert ".py" in extensions
    assert extensions[".py"] == "python"
    assert list(extensions) == sorted(extensions)
