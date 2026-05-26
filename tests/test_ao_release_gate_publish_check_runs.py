"""Tests for scripts/ao_release_gate_publish_check_runs.py (RG-CONCLUSION-SEMANTICS dual publish)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module() -> Any:
    module_path = _repo_root() / "scripts" / "ao_release_gate_publish_check_runs.py"
    spec = importlib.util.spec_from_file_location("ao_release_gate_publish_check_runs", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_artifact(directory: Path, name: str, *, conclusion: str = "success") -> Path:
    path = directory / f"{name}.check-run.json"
    path.write_text(
        json.dumps(
            {
                "name": name,
                "status": "completed",
                "conclusion": conclusion,
                "title": f"{name}: allow_autonomous_merge",
                "summary": "All release-gate checks passed.",
                "text": "Findings: none",
            }
        ),
        encoding="utf-8",
    )
    return path


class _FakeRunner:
    """Subprocess runner double; records calls and raises on demand."""

    def __init__(self, *, raise_on_call: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raise_on_call = raise_on_call

    def __call__(
        self,
        args: list[str],
        *,
        input: bytes,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(
            {
                "args": args,
                "input": json.loads(input.decode("utf-8")),
                "check": check,
            }
        )
        if self.raise_on_call:
            raise subprocess.CalledProcessError(returncode=1, cmd=args)
        return subprocess.CompletedProcess(args=args, returncode=0)


def test_build_check_run_body_shape() -> None:
    mod = _load_module()
    body = mod.build_check_run_body(
        {
            "name": "ao-release-gate-technical",
            "status": "completed",
            "conclusion": "success",
            "title": "ao-release-gate-technical: allow_autonomous_merge",
            "summary": "All technical release-gate checks passed.",
            "text": "extra detail",
        },
        head_sha="abc1234567890abcdef1234567890abcdef1234567890",
    )
    assert body["name"] == "ao-release-gate-technical"
    assert body["head_sha"] == "abc1234567890abcdef1234567890abcdef1234567890"
    assert body["status"] == "completed"
    assert body["conclusion"] == "success"
    assert body["output"]["title"].startswith("ao-release-gate-technical:")
    assert body["output"]["text"] == "extra detail"


def test_load_check_run_rejects_malformed_json(tmp_path: Path) -> None:
    mod = _load_module()
    bad = tmp_path / "bad.json"
    bad.write_text("not a json document", encoding="utf-8")
    try:
        mod._load_check_run(bad)
    except ValueError as exc:
        assert "not valid JSON" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("expected ValueError for malformed JSON")


def test_load_check_run_rejects_unknown_conclusion(tmp_path: Path) -> None:
    mod = _load_module()
    path = tmp_path / "bogus_conclusion.json"
    path.write_text(
        json.dumps(
            {
                "name": "ao-release-gate-technical",
                "status": "completed",
                "conclusion": "rainbow",
                "title": "x",
                "summary": "y",
            }
        ),
        encoding="utf-8",
    )
    try:
        mod._load_check_run(path)
    except ValueError as exc:
        assert "conclusion='rainbow'" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unknown conclusion")


def test_load_check_run_accepts_all_valid_conclusions(tmp_path: Path) -> None:
    mod = _load_module()
    for conclusion in ("success", "failure", "neutral", "action_required", "stale"):
        path = _write_artifact(tmp_path, f"ao-release-gate-{conclusion}", conclusion=conclusion)
        payload = mod._load_check_run(path)
        assert payload["conclusion"] == conclusion


def test_publish_dir_publishes_both_artifacts(tmp_path: Path) -> None:
    mod = _load_module()
    _write_artifact(tmp_path, "ao-release-gate-technical", conclusion="success")
    _write_artifact(tmp_path, "ao-release-gate-review", conclusion="action_required")
    runner = _FakeRunner()
    published = mod.publish_dir(
        tmp_path,
        repo="Halildeu/ao-kernel",
        head_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        runner=runner,
    )
    assert published == 2
    assert [call["input"]["name"] for call in runner.calls] == [
        "ao-release-gate-technical",
        "ao-release-gate-review",
    ]
    # Each call targets the same repo head_sha; conclusions preserved.
    for call in runner.calls:
        assert call["args"][:2] == ["gh", "api"]
        assert call["args"][3] == "POST"
        assert call["input"]["head_sha"] == "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        assert call["check"] is True


def test_publish_dir_skips_missing_artifacts_without_failing(tmp_path: Path) -> None:
    # Only the technical artifact exists; the review artifact is absent.
    # Skipping is non-fatal: this can happen when an upstream decision
    # crash truncated the emit step. The script logs a warning, returns
    # the published count, and lets the workflow continue.
    mod = _load_module()
    _write_artifact(tmp_path, "ao-release-gate-technical", conclusion="failure")
    runner = _FakeRunner()
    log_path = tmp_path / "log.txt"
    with log_path.open("w", encoding="utf-8") as log:
        published = mod.publish_dir(
            tmp_path,
            repo="Halildeu/ao-kernel",
            head_sha="cafebabecafebabecafebabecafebabecafebabe",
            runner=runner,
            log=log,
        )
    assert published == 1
    log_contents = log_path.read_text(encoding="utf-8")
    assert "ao-release-gate-review.check-run.json missing" in log_contents


def test_publish_dir_dry_run_does_not_call_gh_api(tmp_path: Path) -> None:
    mod = _load_module()
    _write_artifact(tmp_path, "ao-release-gate-technical", conclusion="success")
    _write_artifact(tmp_path, "ao-release-gate-review", conclusion="success")
    runner = _FakeRunner(raise_on_call=True)  # would raise if called
    published = mod.publish_dir(
        tmp_path,
        repo="Halildeu/ao-kernel",
        head_sha="0" * 40,
        dry_run=True,
        runner=runner,
    )
    assert published == 2
    assert runner.calls == []  # dry-run path never invokes subprocess


def test_publish_dir_gh_api_failure_raises(tmp_path: Path) -> None:
    mod = _load_module()
    _write_artifact(tmp_path, "ao-release-gate-technical", conclusion="failure")
    runner = _FakeRunner(raise_on_call=True)
    with pytest.raises(subprocess.CalledProcessError):
        mod.publish_dir(
            tmp_path,
            repo="Halildeu/ao-kernel",
            head_sha="0" * 40,
            runner=runner,
        )


def test_main_returns_one_when_dir_missing(tmp_path: Path) -> None:
    mod = _load_module()
    missing = tmp_path / "no_such_dir"
    rc = mod.main(
        [
            "--dir",
            str(missing),
            "--repo",
            "Halildeu/ao-kernel",
            "--head-sha",
            "0" * 40,
        ]
    )
    # Missing dir -> publish_dir treats as nothing to publish (warning), returns 0.
    # This is intentional: we never block the workflow on absent artifacts.
    assert rc == 0


def test_main_dry_run_succeeds(tmp_path: Path) -> None:
    mod = _load_module()
    _write_artifact(tmp_path, "ao-release-gate-technical", conclusion="success")
    _write_artifact(tmp_path, "ao-release-gate-review", conclusion="success")
    rc = mod.main(
        [
            "--dir",
            str(tmp_path),
            "--repo",
            "Halildeu/ao-kernel",
            "--head-sha",
            "0" * 40,
            "--dry-run",
        ]
    )
    assert rc == 0
