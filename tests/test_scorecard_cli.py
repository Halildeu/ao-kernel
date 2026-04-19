"""v3.5 D3: scorecard CLI tests (8 pins)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel import cli as cli_module
from ao_kernel.cli import main


def _scorecard(*entries: dict[str, Any], git_sha: str = "abc1234") -> dict:
    return {
        "schema_version": "v1",
        "generated_at": "2026-04-18T10:00:00Z",
        "git_sha": git_sha,
        "pr_number": None,
        "benchmarks": list(entries),
    }


def _entry(
    scenario: str,
    *,
    status: str = "pass",
    duration_ms: int | None = 100,
    cost_consumed_usd: float | None = 0.01,
    cost_source: str | None = "mock_shim",
    review_score: float | None = None,
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "status": status,
        "workflow_completed": status == "pass",
        "duration_ms": duration_ms,
        "cost_consumed_usd": cost_consumed_usd,
        "cost_source": cost_source,
        "review_score": review_score,
    }


class TestRender:
    def test_render_prints_markdown_and_exits_0(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        head_path = tmp_path / "head.json"
        head_path.write_text(
            json.dumps(_scorecard(_entry("s"))),
            encoding="utf-8",
        )
        exit_code = main(["scorecard", "render", "--input", str(head_path)])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "<!-- ao-scorecard -->" in captured.out
        assert "Baseline: _(not found)_" in captured.out


class TestCompare:
    def test_compare_no_regression_exits_0(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sc_path = tmp_path / "head.json"
        sc_path.write_text(
            json.dumps(_scorecard(_entry("s", duration_ms=100))),
            encoding="utf-8",
        )
        exit_code = main(
            [
                "scorecard",
                "compare",
                "--baseline",
                str(sc_path),
                "--head",
                str(sc_path),
            ],
        )
        assert exit_code == 0

    def test_compare_block_regression_exits_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        baseline = tmp_path / "base.json"
        head = tmp_path / "head.json"
        baseline.write_text(
            json.dumps(_scorecard(_entry("s", duration_ms=100))),
            encoding="utf-8",
        )
        head.write_text(
            json.dumps(_scorecard(_entry("s", duration_ms=300))),
            encoding="utf-8",
        )
        # Patch policy loader to return block action
        monkeypatch.setattr(
            cli_module,
            "_resolve_scorecard_policy",
            lambda _root: {
                "fail_action": "block",
                "regression_threshold": {
                    "duration_ms_relative_pct": 30.0,
                    "cost_usd_relative_pct": 20.0,
                    "review_score_min_delta": -0.1,
                },
            },
        )
        exit_code = main(
            [
                "scorecard",
                "compare",
                "--baseline",
                str(baseline),
                "--head",
                str(head),
            ],
        )
        assert exit_code == 1

    def test_compare_warn_regression_exits_0_with_stderr_banner(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        baseline = tmp_path / "base.json"
        head = tmp_path / "head.json"
        baseline.write_text(
            json.dumps(_scorecard(_entry("s", duration_ms=100))),
            encoding="utf-8",
        )
        head.write_text(
            json.dumps(_scorecard(_entry("s", duration_ms=300))),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            cli_module,
            "_resolve_scorecard_policy",
            lambda _root: {
                "fail_action": "warn",
                "regression_threshold": {
                    "duration_ms_relative_pct": 30.0,
                    "cost_usd_relative_pct": 20.0,
                    "review_score_min_delta": -0.1,
                },
            },
        )
        exit_code = main(
            [
                "scorecard",
                "compare",
                "--baseline",
                str(baseline),
                "--head",
                str(head),
            ],
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "WARN" in captured.err

    def test_missing_baseline_file_handled_gracefully(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        head = tmp_path / "head.json"
        head.write_text(
            json.dumps(_scorecard(_entry("s"))),
            encoding="utf-8",
        )
        # Absent baseline path still exits 0 (advisory diff).
        exit_code = main(
            [
                "scorecard",
                "compare",
                "--baseline",
                str(tmp_path / "missing.json"),
                "--head",
                str(head),
            ],
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Baseline: _(not found)_" in captured.out


class TestRenderIgnoresPolicy:
    def test_render_never_consults_policy(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        head = tmp_path / "head.json"
        head.write_text(
            json.dumps(_scorecard(_entry("s", duration_ms=500))),
            encoding="utf-8",
        )

        def _boom(_root: Any) -> dict[str, Any]:
            raise AssertionError("render must not consult _resolve_scorecard_policy")

        monkeypatch.setattr(cli_module, "_resolve_scorecard_policy", _boom)
        exit_code = main(["scorecard", "render", "--input", str(head)])
        assert exit_code == 0


class TestPostComment:
    def test_post_comment_advisory_on_missing_body(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exit_code = main(
            [
                "scorecard",
                "post-comment",
                "--pr",
                "1",
                "--body-file",
                str(tmp_path / "missing.md"),
                "--sentinel",
                "<!-- ao-scorecard -->",
                "--repo",
                "owner/repo",
            ],
        )
        assert exit_code == 0

    def test_post_comment_routes_to_upsert_helper(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        body = tmp_path / "body.md"
        body.write_text(
            "<!-- ao-scorecard -->\nhello",
            encoding="utf-8",
        )

        captured: dict[str, Any] = {}

        def _fake_upsert(
            *,
            repo: str,
            pr: int,
            body: str,
            sentinel: str,
        ):
            from ao_kernel._internal.scorecard.post_comment import (
                PostCommentResult,
            )

            captured["repo"] = repo
            captured["pr"] = pr
            captured["sentinel"] = sentinel
            return PostCommentResult("posted", 42, "created")

        # Patch at the cli module import site (the cli imports inside
        # the handler, so patch the source module).
        from ao_kernel._internal.scorecard import post_comment as pc_module

        monkeypatch.setattr(pc_module, "upsert_sticky_comment", _fake_upsert)
        exit_code = main(
            [
                "scorecard",
                "post-comment",
                "--pr",
                "7",
                "--body-file",
                str(body),
                "--sentinel",
                "<!-- ao-scorecard -->",
                "--repo",
                "owner/repo",
            ],
        )
        assert exit_code == 0
        assert captured == {
            "repo": "owner/repo",
            "pr": 7,
            "sentinel": "<!-- ao-scorecard -->",
        }

    def test_post_comment_missing_repo_exits_0(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        body = tmp_path / "body.md"
        body.write_text("<!-- ao-scorecard -->", encoding="utf-8")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        exit_code = main(
            [
                "scorecard",
                "post-comment",
                "--pr",
                "1",
                "--body-file",
                str(body),
                "--sentinel",
                "<!-- ao-scorecard -->",
            ],
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "GITHUB_REPOSITORY" in captured.err
