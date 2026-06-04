"""V5 Epic 4 E-4-2b write-set and boundary invariants."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "E-4-2b-MULTI-TENANT-FINAL-SEAL.v1.json"
_EVIDENCE_REPO_PATH = _EVIDENCE_PATH.relative_to(_REPO_ROOT).as_posix()


def _run_git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _changed_files_against_origin_main() -> list[str]:
    outputs = [
        _run_git("diff", "--name-only", "origin/main...HEAD"),
        _run_git("diff", "--name-only"),
        _run_git("diff", "--cached", "--name-only"),
        _run_git("ls-files", "--others", "--exclude-standard"),
    ]
    return sorted({line.strip() for output in outputs for line in output.splitlines() if line.strip()})


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected object at {path}; got {type(data).__name__}"
    return data


def _skip_unless_current_e42b_pr(changed: list[str]) -> None:
    if _EVIDENCE_REPO_PATH not in changed:
        pytest.skip("E-4-2b write-set invariant only applies to active E-4-2b PR diffs")


def test_write_set_exactly_matches_git_diff() -> None:
    changed = _changed_files_against_origin_main()
    _skip_unless_current_e42b_pr(changed)
    evidence = _load_json(_EVIDENCE_PATH)
    evidence_write_set = sorted(set(evidence["write_set"]))
    assert evidence_write_set == changed, (
        "E-4-2b evidence.write_set must exactly match committed + staged + unstaged + untracked files\n"
        f"evidence={evidence_write_set}\n"
        f"git_diff={changed}\n"
        f"missing_from_evidence={sorted(set(changed) - set(evidence_write_set))}\n"
        f"extra_in_evidence={sorted(set(evidence_write_set) - set(changed))}"
    )


def test_no_workflow_or_pyproject_mutation() -> None:
    changed = _changed_files_against_origin_main()
    _skip_unless_current_e42b_pr(changed)
    workflow_changes = [path for path in changed if path.startswith(".github/workflows/")]
    assert workflow_changes == [], f"E-4-2b must not mutate workflows: {workflow_changes}"
    assert "pyproject.toml" not in changed, "E-4-2b must not mutate pyproject.toml"


def test_no_runtime_python_module_mutation() -> None:
    changed = _changed_files_against_origin_main()
    _skip_unless_current_e42b_pr(changed)
    ao_kernel_paths = [path for path in changed if path.startswith("ao_kernel/")]
    illegal = [
        path
        for path in ao_kernel_paths
        if not (path.startswith("ao_kernel/defaults/schemas/") and path.endswith(".json"))
    ]
    assert illegal == [], (
        "E-4-2b may only touch schema JSON under ao_kernel/defaults/schemas/; "
        f"illegal ao_kernel paths: {illegal}"
    )


def test_evidence_boundary_flags_are_false() -> None:
    evidence = _load_json(_EVIDENCE_PATH)
    assert evidence["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    assert evidence["no_workflow_mutation"] is True
    assert evidence["no_pyproject_change"] is True
    assert evidence["no_runtime_module_change"] is True
