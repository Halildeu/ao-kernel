"""Tests for the ao-release-gate payload builder (GPP-2D-2c)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module() -> Any:
    module_path = _repo_root() / "scripts" / "ao_release_gate_build_payload.py"
    spec = importlib.util.spec_from_file_location("ao_release_gate_build_payload", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_pr_files(path: Path, paths: list[str]) -> None:
    """Write a stub ``gh pr view --json files`` response."""

    payload = {"files": [{"path": p} for p in paths]}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_check_runs(path: Path, runs: list[dict[str, str]]) -> None:
    """Write a stub ``gh api .../check-runs`` response."""

    path.write_text(json.dumps({"check_runs": runs}), encoding="utf-8")


def _write_gpp_status(path: Path, *, wp_id: str = "GPP-2") -> None:
    path.write_text(
        json.dumps(
            {
                "current_wp": {"id": wp_id, "status": "blocked"},
                "support_widening_allowed": False,
                "production_platform_claim_allowed": False,
                "live_adapter_execution_allowed": False,
            }
        ),
        encoding="utf-8",
    )


def _build_argv(tmp_path: Path, *, output: Path) -> list[str]:
    """Compose a fully populated CLI argv with fixture inputs in tmp_path."""

    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["ao_kernel/foo.py", "tests/test_foo.py"])
    _write_check_runs(
        check_runs,
        [
            {"name": "lint", "status": "completed", "conclusion": "success"},
            {"name": "test (3.13)", "status": "completed", "conclusion": "success"},
            # Self-name must be excluded by the builder.
            {"name": "ao-release-gate-shadow", "status": "in_progress", "conclusion": None},
            {"name": "ao-release-gate", "status": "queued", "conclusion": None},
        ],
    )
    _write_gpp_status(gpp_status)
    return [
        "--repository",
        "Halildeu/ao-kernel",
        "--pr-number",
        "999",
        "--base-ref",
        "main",
        "--head-ref",
        "codex/test-feature",
        "--head-sha",
        "abc1230000000000000000000000000000000000",
        "--issue-url",
        "https://github.com/Halildeu/ao-kernel/issues/999",
        "--from-fork",
        "false",
        "--branch-up-to-date",
        "true",
        "--gpp-status",
        str(gpp_status),
        "--pr-files-json",
        str(pr_files),
        "--check-runs-json",
        str(check_runs),
        "--output",
        str(output),
    ]


def test_build_payload_emits_expected_shape(tmp_path: Path) -> None:
    mod = _load_module()
    output = tmp_path / "payload.json"
    rc = mod.main(_build_argv(tmp_path, output=output))
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["repository"] == {"full_name": "Halildeu/ao-kernel"}
    assert payload["pull_request"]["number"] == 999
    assert payload["pull_request"]["base"]["ref"] == "main"
    assert payload["pull_request"]["head"]["sha"] == "abc1230000000000000000000000000000000000"
    assert payload["pull_request"]["head"]["repo"]["fork"] is False
    assert payload["issue_url"] == "https://github.com/Halildeu/ao-kernel/issues/999"
    assert payload["branch_up_to_date"] is True
    assert payload["event_name"] == "pull_request"
    assert payload["reviewed_slice"] == "GPP-2"


def test_build_payload_sorts_and_carries_changed_paths(tmp_path: Path) -> None:
    mod = _load_module()
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["z.py", "a.py", "m.py"])
    _write_check_runs(check_runs, [])
    _write_gpp_status(gpp_status)
    output = tmp_path / "payload.json"
    mod.main(
        [
            "--repository",
            "Halildeu/ao-kernel",
            "--pr-number",
            "1",
            "--base-ref",
            "main",
            "--head-ref",
            "x",
            "--head-sha",
            "f" * 40,
            "--issue-url",
            "https://x",
            "--from-fork",
            "false",
            "--branch-up-to-date",
            "true",
            "--gpp-status",
            str(gpp_status),
            "--pr-files-json",
            str(pr_files),
            "--check-runs-json",
            str(check_runs),
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["changed_paths"] == ["a.py", "m.py", "z.py"]


def test_build_payload_excludes_self_check_runs(tmp_path: Path) -> None:
    """The builder must never include `ao-release-gate` or
    `ao-release-gate-shadow` in required_checks; otherwise the gate
    would see its own pending status as a missing required check."""
    mod = _load_module()
    output = tmp_path / "payload.json"
    mod.main(_build_argv(tmp_path, output=output))
    payload = json.loads(output.read_text(encoding="utf-8"))
    names = [check["name"] for check in payload["required_checks"]]
    assert "ao-release-gate" not in names
    assert "ao-release-gate-shadow" not in names
    assert "lint" in names
    assert "test (3.13)" in names


def test_build_payload_defaults_dangerous_flags_to_false(tmp_path: Path) -> None:
    """PR-author-supplied admin_bypass / forbidden_secret / bot / agent /
    live-adapter flags would let a PR self-approve; the builder never
    reads them from the PR and always emits false."""
    mod = _load_module()
    output = tmp_path / "payload.json"
    mod.main(_build_argv(tmp_path, output=output))
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["forbidden_secret_context_detected"] is False
    assert payload["admin_bypass_requested"] is False
    assert payload["pat_backed_bot_actor"] is False
    assert payload["codex_or_claude_release_authority"] is False
    assert payload["live_adapter_execution_requested"] is False


def test_build_payload_reviewed_slice_comes_from_base_ref_gpp_status(tmp_path: Path) -> None:
    """The reviewed slice is the base-ref-trusted current_wp.id, not any
    PR-author-supplied value."""
    mod = _load_module()
    output = tmp_path / "payload.json"
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    _write_check_runs(check_runs, [])
    _write_gpp_status(gpp_status, wp_id="GPP-2D-2c")
    mod.main(
        [
            "--repository",
            "Halildeu/ao-kernel",
            "--pr-number",
            "1",
            "--base-ref",
            "main",
            "--head-ref",
            "x",
            "--head-sha",
            "f" * 40,
            "--issue-url",
            "https://x",
            "--from-fork",
            "false",
            "--branch-up-to-date",
            "true",
            "--gpp-status",
            str(gpp_status),
            "--pr-files-json",
            str(pr_files),
            "--check-runs-json",
            str(check_runs),
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["reviewed_slice"] == "GPP-2D-2c"


def test_build_payload_allowed_path_prefixes_repo_owned_not_pr_supplied(tmp_path: Path) -> None:
    """allowed_path_prefixes is fixed in the base-ref builder, never read
    from the PR head or a PR-committed JSON. The set must include the
    documented active surfaces."""
    mod = _load_module()
    output = tmp_path / "payload.json"
    mod.main(_build_argv(tmp_path, output=output))
    payload = json.loads(output.read_text(encoding="utf-8"))
    prefixes = payload["allowed_path_prefixes"]
    assert "ao_kernel/" in prefixes
    assert "scripts/" in prefixes
    assert "tests/" in prefixes
    assert ".claude/plans/" in prefixes
    assert ".github/workflows/" in prefixes


def test_build_payload_from_fork_is_carried(tmp_path: Path) -> None:
    """A fork-context PR must surface from_fork=true so the core's
    fork_boundary check fails closed."""
    mod = _load_module()
    output = tmp_path / "payload.json"
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    _write_check_runs(check_runs, [])
    _write_gpp_status(gpp_status)
    mod.main(
        [
            "--repository",
            "Halildeu/ao-kernel",
            "--pr-number",
            "1",
            "--base-ref",
            "main",
            "--head-ref",
            "x",
            "--head-sha",
            "f" * 40,
            "--issue-url",
            "https://x",
            "--from-fork",
            "true",
            "--branch-up-to-date",
            "true",
            "--gpp-status",
            str(gpp_status),
            "--pr-files-json",
            str(pr_files),
            "--check-runs-json",
            str(check_runs),
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["pull_request"]["head"]["repo"]["fork"] is True
