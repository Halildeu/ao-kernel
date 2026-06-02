"""Sphinx configuration for ao-kernel API reference (V5 Epic 8 E-8-4).

Scaffold-only: this file is the canonical Sphinx ``conf.py`` for the
optional API-reference documentation build. The build is **operator-
invoked** (not scheduled in CI in this slice). Run from the repo root:

  pip install ao-kernel[docs]
  sphinx-build -b html docs/api docs/api/_build/html

The build is opt-in via the ``[docs]`` extra. Without the extra
installed, this file is dead weight; with it, ``sphinx-build`` produces
an HTML API reference derived from docstrings in the
``ao_kernel`` public-facade modules.

Discipline preserved:
- No live provider client import (Sphinx + autodoc + sphinx-autodoc-typehints only)
- ``live_adapter_execution`` guard flag stays ``const false``
- API reference is **descriptive** of the public facade only; it does
  NOT claim production-readiness or override any operator boundary
- The bundled JSON resources and ``_internal`` namespace are excluded
  from the rendered output by design (private implementation)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo's `ao_kernel` importable when running sphinx-build from
# `docs/api/`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

# -- Project information ----------------------------------------------------

project = "ao-kernel"
author = "Halil Kocoglu"
copyright_owner = author  # avoid shadowing the Python builtin
# Read version from the canonical __version__ string without importing the
# full package (which would pull in optional extras).
_VERSION_FILE = _REPO_ROOT / "ao_kernel" / "__init__.py"
_VERSION = "0.0.0"
for _line in _VERSION_FILE.read_text().splitlines():
    if _line.startswith("__version__"):
        _VERSION = _line.split("=", 1)[1].strip().strip("'\"")
        break
release = _VERSION
version = _VERSION

# -- General configuration --------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

# Exclude private namespace + bundled JSON + tests from autodoc by default.
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "exclude-members": "_internal",
}
autodoc_mock_imports = [
    # Optional extras: keep autodoc working in a minimal env that only
    # has core + sphinx installed (no `[llm,mcp,otel]`).
    "tenacity",
    "tiktoken",
    "mcp",
    "starlette",
    "uvicorn",
    "opentelemetry",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "_static", "Thumbs.db", ".DS_Store"]

# -- HTML output ------------------------------------------------------------

html_theme = "alabaster"
html_static_path: list[str] = []  # operator may add custom static assets later

# Set this in the build environment if you customize the canonical URL.
html_baseurl = os.environ.get("AO_KERNEL_DOCS_BASE_URL", "")

# -- Guard flag posture (rendered into the API ref index) -------------------

# This dict is consumed by the index.rst preamble; do not change without
# touching V5 roadmap E-8-4 + a fresh cross-AI peer review.
rst_prolog = """
.. note::

   The ao-kernel public facade documented here remains a **governed
   runtime**, not a general-purpose agent framework or a production
   platform claim. The three V5 guard flags (``support_widening``,
   ``production_platform_claim``, ``live_adapter_execution``) remain
   ``const false``. Promotion authority lives in the final operator-bound
   supersession PR at the end of the V5 roadmap.
"""
