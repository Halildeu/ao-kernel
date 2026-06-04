"""Static native-bypass denylist for the E-2-4 dry-run harness."""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TARGETS = [
    _REPO_ROOT / "ao_kernel" / "_internal" / "live_adapter_dryrun.py",
    _REPO_ROOT / "scripts" / "run_live_adapter_dryrun.py",
]


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def test_dryrun_harness_does_not_call_native_network_bypass_primitives() -> None:
    offenders: list[str] = []
    for target in _TARGETS:
        tree = ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name == "cffi.FFI":
                offenders.append(f"{target}: cffi.FFI()")
            if name == "ctypes.CDLL":
                literal = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
                if isinstance(literal, str) and "curl" in literal.lower():
                    offenders.append(f"{target}: ctypes.CDLL({literal!r})")
    assert not offenders, "dry-run harness must not call native network bypass primitives: " + ", ".join(offenders)


def test_dryrun_script_is_thin_wrapper_only() -> None:
    script = (_REPO_ROOT / "scripts" / "run_live_adapter_dryrun.py").read_text(encoding="utf-8")
    assert "subprocess" not in script
    assert "socket" not in script
    assert "urllib" not in script
    assert "httpx" not in script
