"""Tests for the conftest.py test-quality gate AST scanner.

Validates the scanner contract:
    - BLK-001 (assert callable) — blocking
    - BLK-002 (assert True) — blocking
    - BLK-003 (except: pass in test) — blocking
    - BLK-004 (mock-return direct-echo tautology) — blocking
    - ADV-001 (no assertions) — advisory
    - ADV-002 (sole 'is not None') — advisory
    - ADV-003 (BLK-004 downgraded by behavioral signal) — advisory

Fixtures are written to ``tmp_path`` to avoid pytest auto-collection of the
sample sources as real tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import the scanner directly from the conftest module; pytest discovery and
# direct imports both resolve to the same module instance.
from tests.conftest import (  # noqa: E402
    _TestQualityViolation,
    _scan_test_file,
)


def _scan_source(tmp_path: Path, source: str, filename: str = "snippet_test.py") -> list[_TestQualityViolation]:
    p = tmp_path / filename
    p.write_text(source, encoding="utf-8")
    return _scan_test_file(p)


def _rules(violations: list[_TestQualityViolation]) -> list[str]:
    return [v.rule for v in violations]


# ── BLK-001..003 regression ────────────────────────────────────────────


def test_blk001_assert_callable(tmp_path: Path) -> None:
    source = "def test_thing():\n    def f():\n        return 1\n    assert callable(f)\n"
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-001" in rules


def test_blk002_assert_true(tmp_path: Path) -> None:
    source = "def test_thing():\n    assert True\n"
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-002" in rules


def test_blk003_except_pass(tmp_path: Path) -> None:
    source = "def test_thing():\n    try:\n        raise ValueError(1)\n    except Exception:\n        pass\n"
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-003" in rules


# ── BLK-004 positive (blocking) ────────────────────────────────────────


def test_blk004_form_a_direct_call_literal_int(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 42\n"
        "    assert m.method() == 42\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" in rules
    assert "ADV-003" not in rules


def test_blk004_form_a_with_arg(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 'alpha'\n"
        "    assert m.method('ignored') == 'alpha'\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" in rules


def test_blk004_form_b_via_result_binding(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 7\n"
        "    result = m.method()\n"
        "    assert result == 7\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" in rules


def test_blk004_struct_equality_literal_string(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 'hello'\n"
        "    assert m.method() == 'hello'\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" in rules


# ── ADV-003 (BLK-004 downgraded by behavioral signal) ──────────────────


def test_adv003_when_assert_called_present(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 42\n"
        "    result = m.method('x')\n"
        "    assert result == 42\n"
        "    m.method.assert_called_once_with('x')\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "ADV-003" in rules
    assert "BLK-004" not in rules


def test_adv003_when_call_count_present(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 5\n"
        "    m.method()\n"
        "    m.method()\n"
        "    assert m.method.call_count == 2\n"
        "    assert m.method() == 5\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "ADV-003" in rules
    assert "BLK-004" not in rules


def test_blk004_unrelated_behavioral_signal_does_not_downgrade(tmp_path: Path) -> None:
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    other = Mock()\n"
        "    m.method.return_value = 42\n"
        "    assert m.method() == 42\n"
        "    other.save.assert_called_once()\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" in rules
    assert "ADV-003" not in rules


# ── BLK-004 negative (out of scope, must NOT trigger) ─────────────────


def test_blk004_negative_service_pass_through(tmp_path: Path) -> None:
    # service pass-through: out of scope per Codex CNS-20260529-001
    source = (
        "from unittest.mock import Mock\n"
        "def fetch(repo):\n"
        "    return repo.get_user()\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.get_user.return_value = 42\n"
        "    assert fetch(m) == 42\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" not in rules
    assert "ADV-003" not in rules


def test_blk004_negative_attribute_projection(tmp_path: Path) -> None:
    # assert result.id == 42 (attribute projection): out of scope
    source = (
        "from unittest.mock import Mock\n"
        "class _Obj:\n"
        "    id = 42\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.get_user.return_value = _Obj()\n"
        "    result = m.get_user()\n"
        "    assert result.id == 42\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" not in rules


def test_blk004_negative_patch_kwarg(tmp_path: Path) -> None:
    # patch(..., return_value=...) kwargs: out of scope (future PR)
    source = (
        "from unittest.mock import patch\n"
        "def test_thing():\n"
        "    with patch('os.getpid', return_value=99) as p:\n"
        "        assert p() == 99\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" not in rules


def test_blk004_negative_side_effect(tmp_path: Path) -> None:
    # side_effect is out of scope first release
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.side_effect = [1, 2, 3]\n"
        "    assert m.method() == 1\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" not in rules


def test_blk004_negative_cache_state_check(tmp_path: Path) -> None:
    # mock return_value set, but assertion is on different state
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    cache = {}\n"
        "    m = Mock()\n"
        "    m.method.return_value = 42\n"
        "    cache['x'] = m.method()\n"
        "    assert len(cache) == 1\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" not in rules


def test_blk004_negative_different_expr_compared(tmp_path: Path) -> None:
    # return_value set to 42, but assert compares to 43 (mismatch)
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m = Mock()\n"
        "    m.method.return_value = 42\n"
        "    assert m.method() == 43\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    assert "BLK-004" not in rules


def test_blk004_negative_different_mock_var(tmp_path: Path) -> None:
    # return_value on one mock, assertion on different mock call
    source = (
        "from unittest.mock import Mock\n"
        "def test_thing():\n"
        "    m1 = Mock()\n"
        "    m2 = Mock()\n"
        "    m1.method.return_value = 42\n"
        "    m2.method.return_value = 99\n"
        "    assert m2.method() == 99\n"
        "    assert m1.method() == 42\n"
    )
    rules = _rules(_scan_source(tmp_path, source))
    # Both ARE BLK-004 in narrow scope; just verify per-mock not cross-mock
    assert rules.count("BLK-004") == 2


# ── Cross-function isolation ────────────────────────────────────────


def test_blk004_does_not_cross_functions(tmp_path: Path) -> None:
    # return_value set in fn A, asserted in fn B → must NOT fire
    source = (
        "from unittest.mock import Mock\n"
        "_M = Mock()\n"
        "_M.method.return_value = 42\n"
        "def test_a():\n"
        "    _M.method.return_value = 42\n"
        "    _M.method()\n"
        "    _M.method.assert_called()\n"
        "def test_b():\n"
        "    # different test function — return_value not set HERE\n"
        "    assert _M.method() == 42\n"
    )
    rules_per_fn = _rules(_scan_source(tmp_path, source))
    # test_a: return_value set + assert_called → ADV-003 may fire if direct echo
    #         present; here no direct echo assertion in test_a.
    # test_b: NO return_value assignment in this function → no BLK-004.
    # Ensure test_b alone does NOT see BLK-004.
    # We just assert that BLK-004 count <= 1 (only test_a if at all).
    assert rules_per_fn.count("BLK-004") == 0


# ── ADV-001, ADV-002 regression ────────────────────────────────────────


def test_adv001_no_assertions(tmp_path: Path) -> None:
    source = "def test_thing():\n    x = 1 + 1\n    pass\n"
    rules = _rules(_scan_source(tmp_path, source))
    assert "ADV-001" in rules


def test_adv002_sole_is_not_none(tmp_path: Path) -> None:
    source = "def make_obj():\n    return 1\ndef test_thing():\n    obj = make_obj()\n    assert obj is not None\n"
    rules = _rules(_scan_source(tmp_path, source))
    assert "ADV-002" in rules


# ── Whole-suite dry-run audit ──────────────────────────────────────────


def test_blk004_zero_hits_in_current_suite() -> None:
    """Lock-in: BLK-004 must have 0 hits in the current tests/ tree.

    This forcing function ensures the rule stays narrow. If a future PR
    introduces a direct-echo mock tautology, this test fails first; that PR
    must either fix the test or extend BLK-004 scope intentionally.
    """
    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = repo_root / "tests"
    blk004_hits: list[str] = []
    for p in sorted(tests_dir.rglob("test_*.py")):
        if p.name == "test_conftest_quality_gate.py":
            # Skip THIS file — we intentionally include BLK-004 fixtures.
            continue
        for v in _scan_test_file(p):
            if v.rule == "BLK-004":
                blk004_hits.append(f"{p.name}::{v.func}")
    assert blk004_hits == [], (
        "BLK-004 violations introduced in current tests/ tree: "
        f"{blk004_hits}. Either fix the test or extend the rule deliberately."
    )


# ── Negative: ensure self-fixtures don't leak into the rest of the suite ──


@pytest.mark.parametrize(
    "filename",
    [
        "snippet_test.py",
    ],
)
def test_fixture_files_isolated_to_tmp_path(tmp_path: Path, filename: str) -> None:
    """Sanity: tmp_path fixture files don't get auto-collected by pytest."""
    fixture_path = tmp_path / filename
    fixture_path.write_text("def test_x():\n    assert True\n", encoding="utf-8")
    # tmp_path is OUTSIDE tests/ — pytest_collect_file would not touch it
    # during normal collection. Verify by direct file existence + scanning.
    assert fixture_path.exists()
    rules = _rules(_scan_test_file(fixture_path))
    assert "BLK-002" in rules  # the assert True placeholder
