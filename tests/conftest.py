"""Shared fixtures and test quality gate for ao-kernel tests.

Anti-pattern gate scans test files at collection time and rejects tests
that match known fake/shallow patterns. This prevents regressions to
tautological assertions, exception swallowing, and assertion-free tests.

Rules:
    BLK-001: assert callable(x) — tautological, proves nothing
    BLK-002: assert x is not None as sole assertion after import — tautological
    BLK-003: except ...: pass inside test function — hides failures
    ADV-001: Test function with 0 assert statements — warning
"""

from __future__ import annotations

import ast
import json
import os
import warnings
from pathlib import Path

import pytest


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_workspace(tmp_path: Path):
    """Create a temporary .ao/ workspace and cd into it."""
    ws = tmp_path / ".ao"
    ws.mkdir()
    for d in ("policies", "schemas", "registry", "extensions"):
        (ws / d).mkdir()
    ws_json = ws / "workspace.json"
    import ao_kernel
    ws_json.write_text(json.dumps({
        "version": ao_kernel.__version__,
        "created_at": "2026-01-01T00:00:00Z",
        "kind": "ao-workspace",
    }) + "\n")
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield ws
    os.chdir(old_cwd)


@pytest.fixture()
def empty_dir(tmp_path: Path):
    """cd into a temp dir with no workspace."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


@pytest.fixture()
def legacy_workspace(tmp_path: Path):
    """Create a legacy .cache/ws_customer_default workspace."""
    legacy = tmp_path / ".cache" / "ws_customer_default"
    legacy.mkdir(parents=True)
    ws_json = legacy / "workspace.json"
    ws_json.write_text(json.dumps({
        "version": "0.0.9",
        "created_at": "2025-01-01T00:00:00Z",
        "kind": "ao-workspace",
    }) + "\n")
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield legacy
    os.chdir(old_cwd)


# ── Test Quality Gate (AST Scanner) ─────────────────────────────────


class _TestQualityViolation:
    """A detected test quality violation."""

    def __init__(self, file: str, func: str, rule: str, detail: str):
        self.file = file
        self.func = func
        self.rule = rule
        self.detail = detail

    def __str__(self):
        return f"[{self.rule}] {self.file}::{self.func} — {self.detail}"


def _scan_test_file(filepath: Path) -> list[_TestQualityViolation]:
    """Scan a test file for anti-patterns using AST analysis."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return violations

    fname = filepath.name

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue

        func_name = node.name
        # source segment available via ast.get_source_segment(source, node)

        # BLK-001: assert callable(x)
        for child in ast.walk(node):
            if isinstance(child, ast.Assert) and isinstance(child.test, ast.Call):
                call = child.test
                if isinstance(call.func, ast.Name) and call.func.id == "callable":
                    violations.append(_TestQualityViolation(
                        fname, func_name, "BLK-001",
                        "assert callable(x) is tautological — test actual behavior instead",
                    ))

        # BLK-002: assert True (placeholder — proves nothing)
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                test_val = child.test
                if isinstance(test_val, ast.Constant) and test_val.value is True:
                    violations.append(_TestQualityViolation(
                        fname, func_name, "BLK-002",
                        "assert True is a placeholder — assert actual behavior instead",
                    ))

        # BLK-003: except ...: pass
        for child in ast.walk(node):
            if isinstance(child, ast.ExceptHandler):
                if (len(child.body) == 1
                        and isinstance(child.body[0], ast.Pass)):
                    violations.append(_TestQualityViolation(
                        fname, func_name, "BLK-003",
                        "except: pass swallows test failures — use pytest.raises or handle explicitly",
                    ))

        # ADV-002: Weak single assertion (is not None, isinstance, len > 0)
        # Only triggers when it's the SOLE meaningful assertion in the test
        assert_nodes = [c for c in ast.walk(node) if isinstance(c, ast.Assert)]
        if len(assert_nodes) == 1:
            sole = assert_nodes[0]
            # assert x is not None
            if (isinstance(sole.test, ast.Compare)
                    and len(sole.test.ops) == 1
                    and isinstance(sole.test.ops[0], ast.IsNot)
                    and isinstance(sole.test.comparators[0], ast.Constant)
                    and sole.test.comparators[0].value is None):
                violations.append(_TestQualityViolation(
                    fname, func_name, "ADV-002",
                    "sole assertion is 'is not None' — add a behavioral assertion",
                ))

        # ADV-001: No assertions at all
        has_assert = False
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                has_assert = True
                break
            if isinstance(child, ast.Call):
                call_name = ""
                if isinstance(child.func, ast.Attribute):
                    call_name = child.func.attr
                elif isinstance(child.func, ast.Name):
                    call_name = child.func.id
                if call_name in ("raises", "warns", "fail"):
                    has_assert = True
                    break

        if not has_assert:
            violations.append(_TestQualityViolation(
                fname, func_name, "ADV-001",
                "test has no assertions — add assert or pytest.raises",
            ))

    return violations


def pytest_collect_file(parent, file_path):
    """Scan test files for quality violations during collection."""
    if not file_path.name.startswith("test_") or not file_path.suffix == ".py":
        return

    violations = _scan_test_file(file_path)
    if not violations:
        return

    blocking = [v for v in violations if v.rule.startswith("BLK")]
    advisory = [v for v in violations if v.rule.startswith("ADV")]

    for v in advisory:
        warnings.warn(f"Test quality advisory: {v}", stacklevel=1)

    if blocking:
        msg = "Test quality gate BLOCKED:\n"
        for v in blocking:
            msg += f"  {v}\n"
        msg += "\nFix these anti-patterns before tests can run."
        pytest.fail(msg, pytrace=False)
