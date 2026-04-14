"""ao-kernel doctor — workspace health check.

Runs 8 checks and reports OK/WARN/FAIL for each.
"""

from __future__ import annotations

import sys
from typing import Callable

import ao_kernel
from ao_kernel.config import workspace_root
from ao_kernel.errors import WorkspaceNotFoundError


def _check(label: str, fn: Callable[[], object]) -> str:
    """Run a check function, return OK/WARN/FAIL."""
    try:
        result = fn()
        if result is True:
            return "OK"
        if result == "WARN":
            return "WARN"
        return "FAIL"
    except Exception:
        return "FAIL"


def _check_workspace(ws_override: str | None) -> bool:
    ws = workspace_root(override=ws_override)
    if ws is None:
        raise WorkspaceNotFoundError("No workspace found (.ao/ or legacy)")
    return ws.is_dir()


def _check_workspace_json(ws_override: str | None) -> bool:
    from ao_kernel.config import load_workspace_json
    ws = workspace_root(override=ws_override)
    if ws is None:
        return False
    load_workspace_json(ws)
    return True


def _check_bundled_defaults() -> bool:
    from ao_kernel.config import load_default
    load_default("policies", "policy_autonomy.v1.json")
    return True


def _check_python_version() -> bool:
    return sys.version_info >= (3, 11)


def _check_required_deps() -> bool:
    import jsonschema  # noqa: F401
    return True


def _check_optional_deps() -> bool | str:
    """Check optional dependencies. Returns True if all present, 'WARN' if some missing."""
    missing = []
    for mod in ("tenacity", "tiktoken"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    return True if not missing else "WARN"


def _check_internal_import() -> bool:
    """v2.0.0: Check ao_kernel._internal modules (src.* removed)."""
    import importlib
    for mod in (
        "ao_kernel._internal.shared.utils",
        "ao_kernel._internal.prj_kernel_api.llm_router",
        "ao_kernel._internal.providers.capability_model",
    ):
        importlib.import_module(mod)
    return True


def _check_extension_manifests() -> bool:
    """Discover and validate ALL bundled extension manifests."""
    from importlib.resources import files

    extensions_pkg = files("ao_kernel.defaults.extensions")
    found = 0
    for item in extensions_pkg.iterdir():
        if item.is_dir() and item.name.startswith("PRJ-"):
            manifest = item.joinpath("extension.manifest.v1.json")
            try:
                manifest.read_text(encoding="utf-8")
                found += 1
            except (FileNotFoundError, TypeError):
                return False
    return found > 0


def run(workspace_root_override: str | None = None) -> int:
    """Run all health checks and print report."""
    checks = [
        ("Workspace found", lambda: _check_workspace(workspace_root_override)),
        ("workspace.json valid", lambda: _check_workspace_json(workspace_root_override)),
        ("Bundled defaults access", _check_bundled_defaults),
        ("Python >= 3.11", _check_python_version),
        ("jsonschema installed", _check_required_deps),
        ("tenacity/tiktoken (optional)", _check_optional_deps),
        ("Internal modules import", _check_internal_import),
        ("Extension manifest discovery", _check_extension_manifests),
    ]

    print(f"ao-kernel doctor v{ao_kernel.__version__}")
    print("-" * 50)

    results = []
    for label, fn in checks:
        status = _check(label, fn)
        results.append((label, status))
        icon = {"OK": "+", "WARN": "~", "FAIL": "!"}[status]
        print(f"  [{icon}] {label:<35} {status}")

    print("-" * 50)

    fail_count = sum(1 for _, s in results if s == "FAIL")
    warn_count = sum(1 for _, s in results if s == "WARN")
    ok_count = sum(1 for _, s in results if s == "OK")

    print(f"  {ok_count} OK, {warn_count} WARN, {fail_count} FAIL")

    return 1 if fail_count > 0 else 0
