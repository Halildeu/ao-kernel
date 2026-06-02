"""V5 Epic 8 E-8-4 invariants: Sphinx API-reference scaffold.

Scaffold only: tests verify the scaffold files exist and pin the
discipline (no _internal autodoc, opt-in build, no live provider
import, guard flags const false). The actual Sphinx HTML build is
operator-invoked and NOT exercised here (would require [docs] extra
install which is opt-in).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "docs" / "api"
CONF_PATH = API_DIR / "conf.py"
INDEX_PATH = API_DIR / "index.rst"
README_PATH = API_DIR / "README.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


# ---- 1. Scaffold presence + structure (4) -------------------------------


def test_api_dir_exists() -> None:
    assert API_DIR.exists() and API_DIR.is_dir()


def test_conf_py_exists() -> None:
    assert CONF_PATH.exists()


def test_index_rst_exists() -> None:
    assert INDEX_PATH.exists()


def test_readme_md_exists() -> None:
    assert README_PATH.exists()


# ---- 2. conf.py discipline (6) ------------------------------------------


def test_conf_uses_autodoc_napoleon() -> None:
    text = CONF_PATH.read_text()
    assert "sphinx.ext.autodoc" in text
    assert "sphinx.ext.napoleon" in text


def test_conf_excludes_internal_from_autodoc() -> None:
    text = CONF_PATH.read_text()
    assert "_internal" in text
    assert "exclude" in text.lower()


def test_conf_mocks_optional_extras() -> None:
    """autodoc_mock_imports must list optional extras so the build works
    with only the core install."""
    text = CONF_PATH.read_text()
    for extra in ("tenacity", "tiktoken", "mcp", "starlette", "opentelemetry"):
        assert extra in text, f"autodoc_mock_imports missing {extra!r}"


def test_conf_reads_version_without_importing_full_package() -> None:
    """conf.py must read __version__ via text parse, not by importing
    `ao_kernel` (which would pull optional extras)."""
    text = CONF_PATH.read_text()
    # Must reference __version__ AND must not unconditionally
    # `from ao_kernel import` at module level (autodoc may import on
    # demand later, but conf must stay lazy).
    assert "__version__" in text
    assert not re.search(r"^\s*import ao_kernel\b", text, re.MULTILINE)


def test_conf_pins_guard_flag_disclaimer_via_rst_prolog() -> None:
    text = CONF_PATH.read_text()
    assert "rst_prolog" in text
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text
    assert "const false" in text or "``const false``" in text


def test_conf_does_not_import_live_providers() -> None:
    text = CONF_PATH.read_text()
    forbidden = (
        "import anthropic",
        "from anthropic",
        "import openai",
        "from openai",
        "import requests",
        "import httpx",
    )
    for token in forbidden:
        assert token not in text, f"conf.py must not import live provider: {token!r}"


# ---- 3. index.rst content (4) -------------------------------------------


def test_index_lists_public_facade_modules() -> None:
    text = INDEX_PATH.read_text()
    for module in (
        "ao_kernel",
        "ao_kernel.client",
        "ao_kernel.governance",
        "ao_kernel.llm",
        "ao_kernel.context",
    ):
        assert module in text, f"index.rst missing {module}"


def test_index_excludes_internal_namespace() -> None:
    text = INDEX_PATH.read_text()
    assert "_internal" in text
    assert "Out of Scope" in text


def test_index_disclaims_guard_flags_const_false() -> None:
    text = INDEX_PATH.read_text()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text
    assert "const false" in text


def test_index_references_other_docs_slices() -> None:
    text = INDEX_PATH.read_text()
    assert "PRODUCTION-DEPLOYMENT-GUIDE.md" in text  # E-8-1
    assert "OPERATOR-RUNBOOK.md" in text  # E-8-3
    assert "TUTORIAL-BUILD-AO-MA-SPM-PROGRAM.md" in text  # E-8-5


# ---- 4. pyproject [docs] extra (3) --------------------------------------


def test_pyproject_has_docs_extra() -> None:
    data = tomllib.loads(PYPROJECT_PATH.read_text())
    extras = data["project"]["optional-dependencies"]
    assert "docs" in extras, "pyproject must declare [docs] extra"


def test_docs_extra_pins_sphinx() -> None:
    data = tomllib.loads(PYPROJECT_PATH.read_text())
    docs = data["project"]["optional-dependencies"]["docs"]
    assert any("sphinx" in pkg.lower() for pkg in docs)


def test_docs_extra_does_not_include_live_providers() -> None:
    data = tomllib.loads(PYPROJECT_PATH.read_text())
    docs = data["project"]["optional-dependencies"]["docs"]
    forbidden = ("anthropic", "openai", "requests", "httpx")
    for pkg in docs:
        for f in forbidden:
            assert f not in pkg.lower(), f"[docs] extra must not pull live provider: {pkg!r}"


# ---- 5. Governance ZERO TOUCH (1) ---------------------------------------
