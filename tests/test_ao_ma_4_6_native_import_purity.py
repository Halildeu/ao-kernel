"""AST import-allowlist test for ao_kernel.orchestration.native_worker_import.

AO-MA-4.6-1 (CNS-20260601-001, Codex thread 019e8000 AGREE) pins the
native worker result importer to a stdlib-only + jsonschema set of
imports. A forbidden module (subprocess/socket/requests/httpx/urllib/
asyncio.subprocess/os.popen/anthropic/openai/MCP client/mavis client)
cannot be used without importing it; this test makes the allowlist the
binding structural guarantee, mirroring the
``test_ao_ma_11h_notifier_purity`` and
``test_ao_ma_11i_run_governor_purity`` patterns.
"""

from __future__ import annotations

import ast
from importlib import resources
from pathlib import Path


ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__future__",
        "hashlib",
        "json",
        "os",
        "pathlib",
        "re",
        "typing",
        "collections",
        "collections.abc",
        "jsonschema",
    }
)
"""Allowed top-level imports for native_worker_import.py.

``os`` is allowed only for ``os.fsync`` (atomic write). ``jsonschema`` is
the project's core dep. Everything else MUST be stdlib. Note: any new
import here MUST be reviewed against the Codex AGREE contract for
4.6-1 — the slice is import-only and adding a new transport would
violate that boundary.
"""

ALLOWED_OS_ATTRS: frozenset[str] = frozenset({"fsync"})
"""Allowed ``os.<attr>`` access. ``os.system``, ``os.popen``,
``os.execv``, ``os.exec*``, ``os.spawn*``, ``os.fork*`` are all
forbidden — they would all spawn a subprocess."""


def _module_path() -> Path:
    pkg = resources.files("ao_kernel.orchestration")
    return Path(str(pkg.joinpath("native_worker_import.py")))


def _parsed() -> ast.Module:
    text = _module_path().read_text(encoding="utf-8")
    return ast.parse(text, filename=str(_module_path()))


def test_imports_within_allowlist() -> None:
    """All Import / ImportFrom nodes target an allowed module."""

    tree = _parsed()
    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    offending.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            # ImportFrom may have module=None for `from . import x`; reject.
            module = node.module or ""
            root = module.split(".")[0]
            if not module or root not in ALLOWED_MODULES:
                offending.append(f"from {module or '.'} import ...")
    assert not offending, f"native_worker_import.py imports outside the allowlist: {offending}"


def test_no_subprocess_socket_network_modules() -> None:
    """Belt-and-suspenders: explicitly reject the canonical transport modules."""

    text = _module_path().read_text(encoding="utf-8")
    forbidden_names = (
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "anthropic",
        "openai",
        "asyncio.subprocess",
        "asyncio",
        "mavis",
        "mcp.client",
    )
    for name in forbidden_names:
        assert f"import {name}" not in text and f"from {name}" not in text, (
            f"native_worker_import.py contains forbidden import {name!r}"
        )


def test_no_os_system_popen_exec_spawn_fork() -> None:
    """``os`` is allowed only for ``os.fsync``; reject the spawn surface."""

    tree = _parsed()
    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            # Only check ``os.<attr>`` patterns.
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                if node.attr not in ALLOWED_OS_ATTRS:
                    offending.append(f"os.{node.attr}")
    assert not offending, f"native_worker_import.py uses non-allowlisted os.* attributes: {offending}"


def test_module_exports_pinned_constants() -> None:
    """Structural pin: SCHEMA_VERSION and IMPORT_MODE consts must exist."""

    from ao_kernel.orchestration.native_worker_import import (
        IMPORT_MODE,
        SCHEMA_VERSION,
    )

    assert SCHEMA_VERSION == "ao-ma-native-worker-import-report.v1"
    assert IMPORT_MODE == "import_only"


def test_module_exports_default_allowlist() -> None:
    """Canonical full allowlist is a 4-element tuple (audit transparency)."""

    from ao_kernel.orchestration.native_worker_import import (
        DEFAULT_SOURCE_INTERFACE_ALLOWLIST,
    )

    assert set(DEFAULT_SOURCE_INTERFACE_ALLOWLIST) == {
        "claude-cli",
        "codex-cli",
        "mavis-cli",
        "local-file",
    }
