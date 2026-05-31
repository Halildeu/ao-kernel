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


def _write_pr_reviews(path: Path) -> None:
    """Write a stub ``gh pr view --json reviews,author`` response."""

    path.write_text(
        json.dumps(
            {
                "author": {"login": "Halildeu"},
                "reviews": [
                    {
                        "author": {"login": "gladyatore-lab"},
                        "state": "APPROVED",
                        "commit": {"oid": "abc1230000000000000000000000000000000000"},
                    },
                    {
                        "author": {"login": "gladyatore-lab"},
                        "state": "DISMISSED",
                        "commit": {"oid": "f" * 40},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_gpp_status(
    path: Path,
    *,
    wp_id: str = "GPP-2",
    issue: str = "https://github.com/Halildeu/ao-kernel/issues/539",
) -> None:
    path.write_text(
        json.dumps(
            {
                "current_wp": {"id": wp_id, "status": "blocked", "issue": issue},
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
    pr_reviews = tmp_path / "pr-reviews.json"
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
    _write_pr_reviews(pr_reviews)
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
        "--pr-reviews-json",
        str(pr_reviews),
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
    assert payload["pull_request"]["author"]["login"] == "Halildeu"
    assert payload["pull_request"]["base"]["ref"] == "main"
    assert payload["pull_request"]["head"]["sha"] == "abc1230000000000000000000000000000000000"
    assert payload["pull_request"]["head"]["repo"]["fork"] is False
    # issue_url is derived from base-ref gpp_status.current_wp.issue,
    # NOT from any workflow env var or PR-supplied field.
    assert payload["issue_url"] == "https://github.com/Halildeu/ao-kernel/issues/539"
    assert payload["branch_up_to_date"] is True
    assert payload["event_name"] == "pull_request"
    assert payload["reviewed_slice"] == "GPP-2"
    assert payload["pr_author"] == "Halildeu"
    assert payload["human_reviews"] == [
        {
            "author": "gladyatore-lab",
            "state": "APPROVED",
            "commit_oid": "abc1230000000000000000000000000000000000",
        },
        {
            "author": "gladyatore-lab",
            "state": "DISMISSED",
            "commit_oid": "f" * 40,
        },
    ]
    assert payload["path_sensitive_human_review_enabled"] is True
    assert payload["low_risk_autonomous_merge_requested"] is False


def test_build_payload_can_request_ao_ma10_autonomous_merge_from_trusted_cli(tmp_path: Path) -> None:
    mod = _load_module()
    output = tmp_path / "payload.json"
    argv = _build_argv(tmp_path, output=output)
    argv.extend(["--ao-ma10-autonomous-merge-requested", "true"])

    rc = mod.main(argv)

    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["low_risk_autonomous_merge_requested"] is True


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


def test_build_payload_required_check_allowlist_fails_closed_on_missing_name(tmp_path: Path) -> None:
    """When the workflow passes `--required-check` with a name the
    GitHub API never returned (e.g. `typecheck` never started), the
    builder must surface a synthetic `status: "missing"` placeholder so
    the decision core's `_required_checks_are_green` returns False.
    Without this, a payload where one required job is silently absent
    would be approved by the gate.
    """
    mod = _load_module()
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    # API returns only `lint` and `test (3.13)`; `typecheck` never
    # appeared. The builder must still emit `typecheck` with
    # status=missing so it fails the required-checks-are-green check.
    _write_check_runs(
        check_runs,
        [
            {"name": "lint", "status": "completed", "conclusion": "success"},
            {"name": "test (3.13)", "status": "completed", "conclusion": "success"},
        ],
    )
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
            "--required-check",
            "lint",
            "--required-check",
            "test (3.13)",
            "--required-check",
            "typecheck",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    by_name = {c["name"]: c for c in payload["required_checks"]}
    # The two API-present names are carried with their real status.
    assert by_name["lint"]["conclusion"] == "success"
    assert by_name["test (3.13)"]["conclusion"] == "success"
    # The allowlisted-but-absent name is surfaced as a not-green
    # placeholder so the decision core fails closed.
    assert by_name["typecheck"]["status"] == "missing"
    assert by_name["typecheck"]["conclusion"] is None


def test_build_payload_dedupes_check_runs_keeping_latest(tmp_path: Path) -> None:
    """gh api .../check-runs returns every run on the commit, including
    cancelled ones from a previous workflow attempt. The builder must
    de-duplicate by check-run name keeping the most recent
    completed_at / started_at entry, so a stale cancelled run does not
    permanently mark a check as not-green (GPP-2D-3 observation note b)."""
    mod = _load_module()
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    # Two check-runs for the same check name: the older one was cancelled
    # in_progress, the newer one is the green completion. The builder
    # must surface the newer one only.
    check_runs.write_text(
        json.dumps(
            {
                "check_runs": [
                    {
                        "id": 100,
                        "name": "test (3.13)",
                        "status": "completed",
                        "conclusion": "cancelled",
                        "started_at": "2026-05-23T06:00:00Z",
                        "completed_at": "2026-05-23T06:02:00Z",
                    },
                    {
                        "id": 200,
                        "name": "test (3.13)",
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-05-23T07:00:00Z",
                        "completed_at": "2026-05-23T07:05:00Z",
                    },
                    {
                        "id": 300,
                        "name": "lint",
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-05-23T07:00:00Z",
                        "completed_at": "2026-05-23T07:01:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
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
    names = [c["name"] for c in payload["required_checks"]]
    # `test (3.13)` appears exactly once, and it is the newer success run.
    assert names.count("test (3.13)") == 1
    by_name = {c["name"]: c for c in payload["required_checks"]}
    assert by_name["test (3.13)"]["conclusion"] == "success"
    # `lint` is also present with its single run.
    assert by_name["lint"]["conclusion"] == "success"


def test_build_payload_dedupes_later_event_gate_skipped_duplicate(tmp_path: Path) -> None:
    """A later event-gate-only workflow attempt can mark downstream
    required jobs as skipped on the same SHA. The builder must not let that
    skipped duplicate shadow a real success from the full workflow run."""

    mod = _load_module()
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    check_runs.write_text(
        json.dumps(
            {
                "check_runs": [
                    {
                        "id": 100,
                        "name": "lint",
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-05-28T11:54:06Z",
                        "completed_at": "2026-05-28T11:54:12Z",
                    },
                    {
                        "id": 200,
                        "name": "lint",
                        "status": "completed",
                        "conclusion": "skipped",
                        "started_at": "2026-05-28T11:55:34Z",
                        "completed_at": "2026-05-28T11:55:34Z",
                    },
                    {
                        "id": 300,
                        "name": "typecheck",
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-05-28T11:54:06Z",
                        "completed_at": "2026-05-28T11:54:34Z",
                    },
                    {
                        "id": 400,
                        "name": "typecheck",
                        "status": "completed",
                        "conclusion": "skipped",
                        "started_at": "2026-05-28T11:55:34Z",
                        "completed_at": "2026-05-28T11:55:34Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
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
            "--required-check",
            "lint",
            "--required-check",
            "typecheck",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    by_name = {c["name"]: c for c in payload["required_checks"]}
    assert by_name["lint"]["conclusion"] == "success"
    assert by_name["typecheck"]["conclusion"] == "success"


def test_build_payload_required_check_skipped_only_still_fails_closed(tmp_path: Path) -> None:
    """Ignoring skipped duplicates must not convert a skipped-only
    required check into a pass. If GitHub only returned skipped for a
    required job, the decision core must still see the not-green status."""

    mod = _load_module()
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    _write_check_runs(
        check_runs,
        [
            {
                "id": 100,
                "name": "lint",
                "status": "completed",
                "conclusion": "skipped",
                "started_at": "2026-05-28T11:55:34Z",
                "completed_at": "2026-05-28T11:55:34Z",
            },
        ],
    )
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
            "--required-check",
            "lint",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["required_checks"] == [{"name": "lint", "status": "completed", "conclusion": "skipped"}]


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
    # GPP-2D-3c bootstrap prerequisite: the ao-release-gate enforce
    # job reads the raw reviewer evidence file committed at the repo
    # head and generates the head-bound gate evidence file at CI
    # runtime. The decision core's diff_scope check requires every
    # committed path to be in this allowlist, so any PR that ships
    # either file at the repo root must find it pinned here.
    assert "local-ai-review-evidence.v1.json" in prefixes
    assert "local-gpp-gate-evidence.v1.json" in prefixes
    assert "ao-ma-10-high-risk-reviews/" in prefixes
    assert "ao-ma-10-high-risk-supersession-evidence.v1.json" not in prefixes
    # Repo hygiene file (.gitignore) is the same trust tier as
    # docs/README/CLAUDE.md: PR-author edits cannot reach the
    # runtime adapter surface, claim production readiness, or widen
    # support. Keeping it in the allowlist lets AO-MA / docs PRs
    # register new ignore rules (e.g. `.ao/orchestration/` AO-MA-4
    # worker_runner runtime artifacts) without `ao_release_gate_
    # diff_out_of_scope` mis-blocking. The path-sensitive human-
    # review gate still applies to the diff itself.
    assert ".gitignore" in prefixes


def test_build_payload_allowed_path_prefixes_includes_gitignore(tmp_path: Path) -> None:
    """`.gitignore` is pinned to the base-ref allowlist so repo hygiene
    edits (e.g. registering AO-MA-4 worktree runtime artifact ignores)
    do not trigger ao_release_gate_diff_out_of_scope.

    Regression for PR #648 (AO-MA-4 parallel worktree runner) which
    failed ao-release-gate-technical with ao_release_gate_diff_out_of_scope
    until this path was added.
    """
    mod = _load_module()
    output = tmp_path / "payload.json"
    mod.main(_build_argv(tmp_path, output=output))
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert ".gitignore" in payload["allowed_path_prefixes"]


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


def test_build_payload_issue_url_comes_from_base_ref_gpp_status(tmp_path: Path) -> None:
    """The issue_url must be derived from base-ref gpp_status.current_wp.issue,
    NOT from any PR webhook field. Otherwise the gpp_issue_consistency check
    would systematically deny by comparing the PR's own API URL against the
    GPP work-package issue URL.
    """
    mod = _load_module()
    output = tmp_path / "payload.json"
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    _write_check_runs(check_runs, [])
    _write_gpp_status(gpp_status, issue="https://github.com/Halildeu/ao-kernel/issues/567")
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
    assert payload["issue_url"] == "https://github.com/Halildeu/ao-kernel/issues/567"


def test_build_payload_raises_when_gpp_status_missing_issue(tmp_path: Path) -> None:
    """If the base-ref gpp_status.current_wp lacks an `issue` field, the
    builder fails fast rather than silently emitting an empty issue_url."""
    import pytest

    mod = _load_module()
    output = tmp_path / "payload.json"
    pr_files = tmp_path / "pr-files.json"
    check_runs = tmp_path / "check-runs.json"
    gpp_status = tmp_path / "gpp_status.json"
    _write_pr_files(pr_files, ["a.py"])
    _write_check_runs(check_runs, [])
    gpp_status.write_text(
        json.dumps({"current_wp": {"id": "GPP-2", "status": "blocked"}}),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
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
