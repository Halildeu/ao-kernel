"""Shared fixtures and test quality gate for ao-kernel tests.

Anti-pattern gate scans test files at collection time and rejects tests
that match known fake/shallow patterns. This prevents regressions to
tautological assertions, exception swallowing, and assertion-free tests.

Rules:
    BLK-001: assert callable(x) — tautological, proves nothing
    BLK-002: assert True placeholder — proves nothing
    BLK-003: except ...: pass inside test function — hides failures
    BLK-004: Mock return-value direct-echo tautology (same test function)
             Detects narrow form: <var>.<method>.return_value = <expr>
             followed by assert <var>.<method>(...) == <expr> OR
             result = <var>.<method>(...); assert result == <expr>.
             Behavioral signals (assert_called_*, call_count, etc.) in the
             same function downgrade to advisory.
             Out of scope (first release): patch(..., return_value=...),
             patch.object, mocker.patch, AsyncMock, side_effect, service
             pass-through (assert service.f(mock) == VALUE), and attribute
             projection (assert result.id == VALUE). Future PRs.
    ADV-001: Test function with 0 assert statements — warning
    ADV-002: sole assertion is 'is not None' — weak behavioral signal
"""

from __future__ import annotations

import ast
import json
import os
import warnings
from collections.abc import Generator
from pathlib import Path

import pytest


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary .ao/ workspace and cd into it."""
    ws = tmp_path / ".ao"
    ws.mkdir()
    for d in ("policies", "schemas", "registry", "extensions"):
        (ws / d).mkdir()
    ws_json = ws / "workspace.json"
    import ao_kernel

    ws_json.write_text(
        json.dumps(
            {
                "version": ao_kernel.__version__,
                "created_at": "2026-01-01T00:00:00Z",
                "kind": "ao-workspace",
            }
        )
        + "\n"
    )
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield ws
    os.chdir(old_cwd)


@pytest.fixture()
def empty_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """cd into a temp dir with no workspace."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


@pytest.fixture()
def legacy_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a legacy .cache/ws_customer_default workspace."""
    legacy = tmp_path / ".cache" / "ws_customer_default"
    legacy.mkdir(parents=True)
    ws_json = legacy / "workspace.json"
    ws_json.write_text(
        json.dumps(
            {
                "version": "0.0.9",
                "created_at": "2025-01-01T00:00:00Z",
                "kind": "ao-workspace",
            }
        )
        + "\n"
    )
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield legacy
    os.chdir(old_cwd)


# ── Test Quality Gate (AST Scanner) ─────────────────────────────────


class _TestQualityViolation:
    """A detected test quality violation."""

    def __init__(self, file: str, func: str, rule: str, detail: str) -> None:
        self.file = file
        self.func = func
        self.rule = rule
        self.detail = detail

    def __str__(self) -> str:
        return f"[{self.rule}] {self.file}::{self.func} — {self.detail}"


# Method names that, when called or referenced inside a test function,
# indicate the test verifies mock-call behavior beyond return-value echo.
# Presence of any of these in the function downgrades BLK-004 → ADV-003.
_BLK004_BEHAVIORAL_METHODS = frozenset(
    {
        "assert_called",
        "assert_called_once",
        "assert_called_with",
        "assert_called_once_with",
        "assert_any_call",
        "assert_has_calls",
        "assert_not_called",
    }
)
_BLK004_BEHAVIORAL_ATTRS = frozenset(
    {
        "call_count",
        "called",
        "call_args",
        "call_args_list",
        "mock_calls",
        "method_calls",
    }
)


def _ast_eq(a: ast.AST, b: ast.AST) -> bool:
    """Structural AST equality (location-insensitive)."""
    return ast.dump(a, annotate_fields=True, include_attributes=False) == ast.dump(
        b, annotate_fields=True, include_attributes=False
    )


def _blk004_method_key(expr: ast.AST) -> tuple[str, str] | None:
    """Return ``(<mock_name>, <method>)`` for ``mock.method`` expressions."""
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        return (expr.value.id, expr.attr)
    return None


def _blk004_scan(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    fname: str,
    func_name: str,
    violations: list[_TestQualityViolation],
) -> None:
    """Detect BLK-004 mock-return direct-echo tautology in a test function.

    Narrow scope per Codex CNS-20260529-001:
      - assignment form: ``<Name>.<attr>.return_value = <expr>``
      - echo form A:     ``assert <Name>.<attr>(...) == <expr>``
      - echo form B:     ``<result> = <Name>.<attr>(...); assert <result> == <expr>``
      - BLK iff sole/primary outcome assertion is direct echo AND no
        behavioral signals (assert_called_*, call_count, ...) present.
      - Behavioral signals present → emit ADV-003 (advisory) instead.

    Out of scope (first release): patch/patch.object/mocker.patch kwargs,
    AsyncMock, side_effect, service pass-through, attribute projection.
    """
    # Pass 1: gather return_value assignments and result bindings.
    # Use ast.dump of the return_expr as the canonical key, so AST structural
    # equality decides matches.
    return_value_map: dict[tuple[str, str], ast.expr] = {}
    result_call_map: dict[str, tuple[str, str]] = {}

    for stmt in ast.walk(node):
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        tgt = stmt.targets[0]

        # <name>.<attr>.return_value = <expr>
        if (
            isinstance(tgt, ast.Attribute)
            and tgt.attr == "return_value"
            and isinstance(tgt.value, ast.Attribute)
            and isinstance(tgt.value.value, ast.Name)
        ):
            mock_name = tgt.value.value.id
            method = tgt.value.attr
            return_value_map[(mock_name, method)] = stmt.value

        # <result> = <name>.<attr>(...)
        if (
            isinstance(tgt, ast.Name)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)
        ):
            call_func = stmt.value.func
            assert isinstance(call_func, ast.Attribute)  # narrows for mypy
            call_recv = call_func.value
            assert isinstance(call_recv, ast.Name)  # narrows for mypy
            result_call_map[tgt.id] = (call_recv.id, call_func.attr)

    if not return_value_map:
        return

    # Pass 2: behavioral signals tied to a specific mock method suppress
    # BLK to ADV-003 for that method only. An unrelated mock assertion must
    # not downgrade a direct-echo tautology.
    behavioral_keys: set[tuple[str, str]] = set()
    for stmt in ast.walk(node):
        if (
            isinstance(stmt, ast.Call)
            and isinstance(stmt.func, ast.Attribute)
            and stmt.func.attr in _BLK004_BEHAVIORAL_METHODS
        ):
            key = _blk004_method_key(stmt.func.value)
            if key is not None:
                behavioral_keys.add(key)
        if isinstance(stmt, ast.Attribute) and stmt.attr in _BLK004_BEHAVIORAL_ATTRS:
            key = _blk004_method_key(stmt.value)
            if key is not None:
                behavioral_keys.add(key)

    # Pass 3: scan asserts for direct echo.
    seen_keys: set[tuple[str, str]] = set()
    for stmt in ast.walk(node):
        if not isinstance(stmt, ast.Assert):
            continue
        test = stmt.test
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
            continue
        lhs = test.left
        rhs = test.comparators[0]

        # Form A: assert <var>.<attr>(...) == <expr>
        if isinstance(lhs, ast.Call) and isinstance(lhs.func, ast.Attribute) and isinstance(lhs.func.value, ast.Name):
            key = (lhs.func.value.id, lhs.func.attr)
            if key in return_value_map and _ast_eq(rhs, return_value_map[key]):
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                rule, label = ("ADV-003", "advisory") if key in behavioral_keys else ("BLK-004", "blocking")
                detail = (
                    f"mock-return tautology ({label}): {key[0]}.{key[1]}.return_value "
                    "was set to the same expression asserted via direct call"
                )
                violations.append(_TestQualityViolation(fname, func_name, rule, detail))
                continue

        # Form B: assert <result_name> == <expr> (result bound from mock call)
        if isinstance(lhs, ast.Name) and lhs.id in result_call_map:
            key = result_call_map[lhs.id]
            if key in return_value_map and _ast_eq(rhs, return_value_map[key]):
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                rule, label = ("ADV-003", "advisory") if key in behavioral_keys else ("BLK-004", "blocking")
                detail = (
                    f"mock-return tautology ({label}): {key[0]}.{key[1]}.return_value "
                    f"was set to the same expression asserted via {lhs.id}"
                )
                violations.append(_TestQualityViolation(fname, func_name, rule, detail))


def _scan_test_file(filepath: Path) -> list[_TestQualityViolation]:
    """Scan a test file for anti-patterns using AST analysis."""
    violations: list[_TestQualityViolation] = []
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
                    violations.append(
                        _TestQualityViolation(
                            fname,
                            func_name,
                            "BLK-001",
                            "assert callable(x) is tautological — test actual behavior instead",
                        )
                    )

        # BLK-002: assert True (placeholder — proves nothing)
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                test_val = child.test
                if isinstance(test_val, ast.Constant) and test_val.value is True:
                    violations.append(
                        _TestQualityViolation(
                            fname,
                            func_name,
                            "BLK-002",
                            "assert True is a placeholder — assert actual behavior instead",
                        )
                    )

        # BLK-003: except ...: pass
        for child in ast.walk(node):
            if isinstance(child, ast.ExceptHandler):
                if len(child.body) == 1 and isinstance(child.body[0], ast.Pass):
                    violations.append(
                        _TestQualityViolation(
                            fname,
                            func_name,
                            "BLK-003",
                            "except: pass swallows test failures — use pytest.raises or handle explicitly",
                        )
                    )

        # BLK-004: Mock return-value direct-echo tautology
        # Narrow scope (per Codex CNS-20260529-001 REVISE+impl-ready):
        #   <Name>.<attr>.return_value = <expr>
        # then either:
        #   assert <Name>.<attr>(...) == <expr>   (form A: direct call)
        #   <result> = <Name>.<attr>(...)
        #   assert <result> == <expr>             (form B: one-hop via result)
        # AST structural equality (ast.dump w/o attrs) decides match.
        # Behavioral signals in same function downgrade BLK → ADV-003.
        # Out of scope: patch/patch.object/mocker.patch, AsyncMock, side_effect,
        # service pass-through, attribute projection. Future PRs.
        _blk004_scan(node, fname, func_name, violations)

        # ADV-002: Weak single assertion (is not None, isinstance, len > 0)
        # Only triggers when it's the SOLE meaningful assertion in the test
        assert_nodes = [c for c in ast.walk(node) if isinstance(c, ast.Assert)]
        if len(assert_nodes) == 1:
            sole = assert_nodes[0]
            # assert x is not None
            if (
                isinstance(sole.test, ast.Compare)
                and len(sole.test.ops) == 1
                and isinstance(sole.test.ops[0], ast.IsNot)
                and isinstance(sole.test.comparators[0], ast.Constant)
                and sole.test.comparators[0].value is None
            ):
                violations.append(
                    _TestQualityViolation(
                        fname,
                        func_name,
                        "ADV-002",
                        "sole assertion is 'is not None' — add a behavioral assertion",
                    )
                )

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
            violations.append(
                _TestQualityViolation(
                    fname,
                    func_name,
                    "ADV-001",
                    "test has no assertions — add assert or pytest.raises",
                )
            )

    return violations


def pytest_collect_file(parent: object, file_path: Path) -> None:
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
