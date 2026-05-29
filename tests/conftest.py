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
from collections.abc import Generator, Iterator
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


def _walk_outside_nested_scopes(node: ast.AST) -> Iterator[ast.AST]:
    """Yield ``node`` and all descendants in source order without entering nested
    function/lambda/class scopes.

    This is a same-function precision boundary for BLK-004. A nested helper
    inside ``def test_xxx`` should NOT contribute return-value assignments or
    asserts to the outer test scan.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef),
        ):
            continue
        yield from _walk_outside_nested_scopes(child)


def _collect_behavioral_signal_keys(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[tuple[str, str]]:
    """Return the set of ``(mock_name, method)`` keys that have a real
    behavioral assertion in the test function body.

    A behavioral signal is one of:
      - a *call* to ``<var>.<method>.<assert_called_*>(...)``
      - a behavioral attribute (``call_count``, ``called``, ``call_args``...)
        appearing *inside an ``ast.Assert``* (or other check context — we
        scope to Assert/Call comparison here for precision).

    Bare expressions like ``_ = m.method.call_count`` outside an Assert do
    NOT count, so a direct-echo BLK stays blocking. Unrelated mocks (different
    ``(mock_name, method)`` key) also do NOT downgrade the targeted echo.
    """
    keys: set[tuple[str, str]] = set()
    for child in _walk_outside_nested_scopes(node):
        # Behavioral method call: <mock>.<method>.assert_called*(...)
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in _BLK004_BEHAVIORAL_METHODS
            and isinstance(child.func.value, ast.Attribute)
            and isinstance(child.func.value.value, ast.Name)
        ):
            keys.add((child.func.value.value.id, child.func.value.attr))
        # Behavioral attr inside Assert: assert m.method.call_count == 2 etc.
        if isinstance(child, ast.Assert):
            for sub in ast.walk(child):
                if (
                    isinstance(sub, ast.Attribute)
                    and sub.attr in _BLK004_BEHAVIORAL_ATTRS
                    and isinstance(sub.value, ast.Attribute)
                    and isinstance(sub.value.value, ast.Name)
                ):
                    keys.add((sub.value.value.id, sub.value.attr))
    return keys


def _blk004_scan(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    fname: str,
    func_name: str,
    violations: list[_TestQualityViolation],
) -> None:
    """Detect BLK-004 mock-return direct-echo tautology in a test function.

    Narrow scope per Codex CNS-20260529-001 (iter-1 REVISE absorbed):
      - assignment form: ``<Name>.<attr>.return_value = <expr>``
      - echo form A:     ``assert <Name>.<attr>(...) == <expr>``
      - echo form B:     ``<result> = <Name>.<attr>(...); assert <result> == <expr>``
      - BLK iff direct echo AND no per-key behavioral signal in the same
        function.
      - Per-key behavioral signal present → emit ADV-003 (advisory) instead.

    Out of scope (first release): patch/patch.object/mocker.patch kwargs,
    AsyncMock, side_effect, service pass-through, attribute projection.

    Precision (Codex post-impl iter-2 BLOCKING fixes absorbed):
      - Nested function/lambda/class bodies are pruned from the scan, so a
        helper inside the test cannot leak return_value/assert events to the
        outer scope.
      - Statement order is preserved: ``return_value`` reassignments and
        ``result = m.method()`` rebindings are evaluated in source order, so
        a stale value or a reassigned ``result`` does not produce a hit.
      - Behavioral-signal downgrade is per-``(mock_name, method)`` key.
        Bare references like ``_ = m.method.call_count`` outside an Assert
        do not demote a sibling direct echo.
    """
    # Pre-pass: collect per-key behavioral signals for the downgrade rule.
    behavioral_keys = _collect_behavioral_signal_keys(node)

    # Main pass: walk function body in source order, maintaining a
    # point-in-time state of return_value bindings and result aliases.
    return_value_state: dict[tuple[str, str], ast.expr] = {}
    result_active: dict[str, tuple[str, str]] = {}
    seen_keys: set[tuple[str, str]] = set()

    def _emit(key: tuple[str, str], via: str) -> None:
        if key in seen_keys:
            return
        seen_keys.add(key)
        has_beh = key in behavioral_keys
        rule, label = ("ADV-003", "advisory") if has_beh else ("BLK-004", "blocking")
        detail = (
            f"mock-return tautology ({label}): "
            f"{key[0]}.{key[1]}.return_value was set to the same expression "
            f"asserted via {via}"
        )
        violations.append(_TestQualityViolation(fname, func_name, rule, detail))

    def _process(stmt: ast.AST) -> None:
        # Order-aware: handle Assign FIRST so result alias updates before any
        # nested Asserts in the same statement, then Assert.
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            tgt = stmt.targets[0]

            # <var>.<attr>.return_value = <expr>
            if (
                isinstance(tgt, ast.Attribute)
                and tgt.attr == "return_value"
                and isinstance(tgt.value, ast.Attribute)
                and isinstance(tgt.value.value, ast.Name)
            ):
                return_value_state[(tgt.value.value.id, tgt.value.attr)] = stmt.value
                return

            # <result> = <var>.<attr>(...)  → bind alias
            # any other RHS → clear alias (Codex iter-2 finding #2)
            if isinstance(tgt, ast.Name):
                if (
                    isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Attribute)
                    and isinstance(stmt.value.func.value, ast.Name)
                ):
                    call_func = stmt.value.func
                    call_recv = call_func.value
                    assert isinstance(call_func, ast.Attribute)
                    assert isinstance(call_recv, ast.Name)
                    result_active[tgt.id] = (call_recv.id, call_func.attr)
                else:
                    result_active.pop(tgt.id, None)
                return

        if isinstance(stmt, ast.Assert):
            test = stmt.test
            if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
                return
            lhs = test.left
            rhs = test.comparators[0]

            # Form A: assert <var>.<attr>(...) == <expr>
            if (
                isinstance(lhs, ast.Call)
                and isinstance(lhs.func, ast.Attribute)
                and isinstance(lhs.func.value, ast.Name)
            ):
                key = (lhs.func.value.id, lhs.func.attr)
                if key in return_value_state and _ast_eq(rhs, return_value_state[key]):
                    _emit(key, "direct call")
                    return

            # Form B: assert <result_name> == <expr> (result currently aliased)
            if isinstance(lhs, ast.Name) and lhs.id in result_active:
                key = result_active[lhs.id]
                if key in return_value_state and _ast_eq(rhs, return_value_state[key]):
                    _emit(key, lhs.id)
                    return

    # Source-order body traversal (with nested-scope pruning).
    for top in node.body:
        if isinstance(
            top,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef),
        ):
            continue
        for sub in _walk_outside_nested_scopes(top):
            _process(sub)


# ── Test Quality Gate (Scanner Entrypoint) ──────────────────────────────


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
