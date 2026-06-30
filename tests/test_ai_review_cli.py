from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ao_kernel import ai_review
from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _repo_with_high_risk_change(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    target = repo / "ao_kernel" / "ao_release_gate.py"
    target.parent.mkdir(parents=True)
    target.write_text("# base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature")
    target.write_text("# base\n# high-risk change\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    return repo


def _fake_provider(tmp_path: Path, *, mode: str = "agree", provider_stateful: bool = False) -> Path:
    script = tmp_path / f"fake_provider_{mode}_{'stateful' if provider_stateful else 'plain'}.py"
    state_block = [
        "state_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None",
        "count = 0",
        "if state_path is not None and state_path.exists():",
        "    count = int(state_path.read_text())",
        "if state_path is not None:",
        "    state_path.write_text(str(count + 1))",
    ]
    if provider_stateful:
        verdict_expr = "'REVISE' if count == 0 else 'AGREE'"
        finding_expr = "'needs one more round' if count == 0 else 'review clean'"
    elif mode == "revise":
        verdict_expr = "'REVISE'"
        finding_expr = "'needs fix'"
    else:
        verdict_expr = "'AGREE'"
        finding_expr = "'review clean'"
    script.write_text(
        "\n".join(
            [
                "import json, pathlib, sys",
                "request = json.load(sys.stdin)",
                "provider = sys.argv[1]",
                *state_block,
                f"verdict = {verdict_expr}",
                f"finding = {finding_expr}",
                "json.dump({",
                "  'agent': provider + '-fake-reviewer',",
                "  'verdict': verdict,",
                "  'checks_considered': [",
                "    {'name': 'tests', 'status': 'pass'},",
                "    {'name': 'secret_scan', 'status': 'pass'},",
                "  ],",
                "  'findings': [finding, 'round=' + str(request['context']['round_index'])],",
                "}, sys.stdout)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script


def _cmd(provider: str, script: Path, state: Path | None = None) -> str:
    parts = [sys.executable, str(script), provider]
    if state is not None:
        parts.append(str(state))
    return " ".join(parts)


def _run_cli(args: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "ao_kernel.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check:
        assert proc.returncode == 0, proc.stderr + proc.stdout
    return proc


def _validate(schema_name: str, payload: dict[str, object]) -> None:
    Draft202012Validator(load_default("schemas", schema_name)).validate(payload)


def _round_result(
    *,
    provider: str = "openai",
    verdict: ai_review.Verdict = "AGREE",
    checks: list[dict[str, str]] | None = None,
    findings: list[str] | None = None,
) -> ai_review.ProviderRoundResult:
    return ai_review.ProviderRoundResult(
        provider=provider,
        agent=f"{provider}-fake-reviewer",
        verdict=verdict,
        checks_considered=checks
        if checks is not None
        else [
            {"name": "tests", "status": "pass"},
            {"name": "secret_scan", "status": "pass"},
        ],
        findings=findings if findings is not None else ["review clean"],
        prompt_sha256="sha256:" + "1" * 64,
        command=ai_review.ProviderCommand(provider=provider, argv=("python", "review.py"), source="test"),
    )


def test_ai_review_collect_writes_raw_reviews_and_provenance(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    fake = _fake_provider(tmp_path)
    output_dir = tmp_path / "reviews"

    proc = _run_cli(
        [
            "ai-review",
            "collect",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10X",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--implementer-provider",
            "google",
            "--provider",
            f"openai={_cmd('openai', fake)}",
            "--provider",
            f"anthropic={_cmd('anthropic', fake)}",
        ]
    )

    summary = json.loads(proc.stdout)
    assert summary == {
        "artifact_kind": "ai_review_collection_evidence",
        "evidence_written": True,
        "raw_review_providers": ["openai", "anthropic"],
        "status": "collected",
    }
    payload = json.loads((output_dir / "ai_review_collection.v1.json").read_text())
    _validate("ai-review-collection-evidence.schema.v1.json", payload)
    assert payload["collection_status"] == "collected"
    assert payload["ai_output_release_authority"] is False
    assert payload["guard_flags"] == {
        "live_adapter_execution": False,
        "production_platform_claim": False,
        "support_widening": False,
    }
    assert set(payload["raw_review_paths"]) == {"anthropic", "openai"}
    assert len(payload["provider_provenance"]) == 2
    for provenance in payload["provider_provenance"]:
        assert provenance["command_argv_sha256"].startswith("sha256:")
        assert provenance["prompt_sha256"].startswith("sha256:")


def test_ai_review_python_api_covers_productized_main_paths(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    fake = _fake_provider(tmp_path)
    collect_dir = tmp_path / "api-collect"

    collection = ai_review.run_collect(
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10X",
        implementer_agent="codex",
        implementer_provider="google",
        base_ref="main",
        head_ref="feature",
        repo_root=repo,
        output_dir=collect_dir,
        provider_values=[
            f"openai={_cmd('openai', fake)}",
            f"anthropic={_cmd('anthropic', fake)}",
        ],
        max_diff_bytes=200_000,
        timeout_seconds=30,
    )
    _validate("ai-review-collection-evidence.schema.v1.json", collection)
    assert collection["collection_status"] == "collected"
    assert collection["required_reviewer_providers"] == ["openai", "anthropic"]

    consensus_dir = tmp_path / "api-consensus"
    consensus = ai_review.run_consensus(
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10X",
        implementer_agent="codex",
        implementer_provider="google",
        base_ref="main",
        head_ref="feature",
        repo_root=repo,
        output_dir=consensus_dir,
        provider_values=[
            f"openai={_cmd('openai', fake)}",
            f"anthropic={_cmd('anthropic', fake)}",
        ],
        max_diff_bytes=200_000,
        timeout_seconds=30,
        max_rounds=1,
    )
    _validate("ai-review-consensus-evidence.schema.v1.json", consensus)
    assert consensus["consensus_status"] == "AGREE"
    assert consensus["collection_evidence_path"].endswith("ai_review_collection.v1.json")

    raw_paths = [
        collect_dir / "openai.local-ai-review-evidence.v1.json",
        collect_dir / "anthropic.local-ai-review-evidence.v1.json",
    ]
    dry_run = ai_review.run_high_risk_dry_run(
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10X",
        implementer_provider="google",
        base_ref="main",
        head_ref="feature",
        repo_root=repo,
        output_dir=tmp_path / "api-dry-run",
        raw_review_paths=raw_paths,
        max_age_seconds=3600,
    )
    _validate("ai-review-high-risk-dry-run-evidence.schema.v1.json", dry_run)
    assert dry_run["dry_run_status"] == "pass"
    assert dry_run["ao_release_gate_allow"] is True
    assert dry_run["merge_attempted"] is False
    assert dry_run["github_mutation_performed"] is False


def test_ai_review_fail_closed_parser_and_reviewer_output_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_secret = "token=" + "gh" + "p_" + ("1" * 36)
    with pytest.raises(ValueError, match="secret-like"):
        ai_review.assert_no_secret_like_text(fake_secret, label="prompt")
    with pytest.raises(ValueError, match="provider=command"):
        ai_review.parse_provider_commands(["openai"], required_providers=("openai",))
    with pytest.raises(ValueError, match="unsupported provider"):
        ai_review.parse_provider_commands(["google=python review.py"], required_providers=("openai",))
    with pytest.raises(ValueError, match="empty command"):
        ai_review.parse_provider_commands(["openai="], required_providers=("openai",))
    with pytest.raises(ValueError, match="missing required provider"):
        ai_review.parse_provider_commands([], required_providers=("openai",))

    monkeypatch.setenv("AO_MA10_OPENAI_REVIEW_CMD", f"{sys.executable} review.py")
    parsed = ai_review.parse_provider_commands(None, required_providers=("openai",))
    assert parsed["openai"].source == "env:AO_MA10_OPENAI_REVIEW_CMD"

    with pytest.raises(ValueError, match="not valid JSON"):
        ai_review._load_provider_output("{", "openai")
    with pytest.raises(ValueError, match="JSON object"):
        ai_review._load_provider_output("[]", "openai")
    with pytest.raises(ValueError, match="checks_considered"):
        ai_review._checks_from_output({}, "openai")
    with pytest.raises(ValueError, match="check entry"):
        ai_review._checks_from_output({"checks_considered": ["bad"]}, "openai")
    with pytest.raises(ValueError, match="include string"):
        ai_review._checks_from_output({"checks_considered": [{"name": "tests"}]}, "openai")
    with pytest.raises(ValueError, match="pass or fail"):
        ai_review._checks_from_output({"checks_considered": [{"name": "tests", "status": "skip"}]}, "openai")
    with pytest.raises(ValueError, match="findings"):
        ai_review._findings_from_output({"findings": [""]}, "openai")
    with pytest.raises(ValueError, match="verdict"):
        ai_review._verdict_from_output({"verdict": "MAYBE"}, "openai")
    assert ai_review._agent_from_output({}, "openai") == "openai-reviewer"

    failing = tmp_path / "failing_provider.py"
    failing.write_text("import sys\nprint('plain stderr', file=sys.stderr)\nsys.exit(2)\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="failed with exit 2"):
        ai_review.run_provider_command(
            ai_review.ProviderCommand(provider="openai", argv=(sys.executable, str(failing)), source="test"),
            review_request="{}",
            timeout_seconds=5,
        )


def test_ai_review_raw_review_fail_closed_edges(tmp_path: Path) -> None:
    implementer = {"agent": "codex", "provider": "google"}
    with pytest.raises(ValueError, match="not AGREE"):
        ai_review.raw_review_from_round(
            result=_round_result(verdict="REVISE"),
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10X",
            implementer=implementer,
            base_ref="main",
            head_ref="feature",
            changed=["ao_kernel/ao_release_gate.py"],
        )
    with pytest.raises(ValueError, match="forbidden finding"):
        ai_review.raw_review_from_round(
            result=_round_result(findings=["FORBIDDEN: simulated reviewer verdict"]),
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10X",
            implementer=implementer,
            base_ref="main",
            head_ref="feature",
            changed=["ao_kernel/ao_release_gate.py"],
        )
    with pytest.raises(ValueError, match="passing tests"):
        ai_review.raw_review_from_round(
            result=_round_result(checks=[{"name": "secret_scan", "status": "pass"}]),
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10X",
            implementer=implementer,
            base_ref="main",
            head_ref="feature",
            changed=["ao_kernel/ao_release_gate.py"],
        )
    with pytest.raises(ValueError, match="passing secret_scan"):
        ai_review.raw_review_from_round(
            result=_round_result(checks=[{"name": "tests", "status": "pass"}]),
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10X",
            implementer=implementer,
            base_ref="main",
            head_ref="feature",
            changed=["ao_kernel/ao_release_gate.py"],
        )

    context = {
        "base_ref": "main",
        "head_ref": "feature",
        "head_sha": "a" * 40,
        "diff_digest": "sha256:" + "b" * 64,
        "changed_files_count": 1,
    }
    with pytest.raises(ValueError, match="reviewer block"):
        ai_review.provider_verdict_from_raw_review(
            raw_review={"findings": ["ok"]},
            provider="openai",
            context=context,
            round_index=1,
            binding_mode="added",
        )
    with pytest.raises(ValueError, match="findings"):
        ai_review.provider_verdict_from_raw_review(
            raw_review={"reviewer": {"agent": "x", "provider": "openai"}},
            provider="openai",
            context=context,
            round_index=1,
            binding_mode="added",
        )

    with pytest.raises(ValueError, match="missing raw review"):
        ai_review.build_high_risk_supersession_from_raw_reviews(
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10X",
            implementer_provider="google",
            context_binding=context,
            high_risk_changed_paths=["ao_kernel/ao_release_gate.py"],
            raw_review_paths={},
            max_age_seconds=3600,
            round_index=1,
        )

    raw = ai_review.raw_review_from_round(
        result=_round_result(provider="openai"),
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10X",
        implementer=implementer,
        base_ref="main",
        head_ref="feature",
        changed=["ao_kernel/ao_release_gate.py"],
    )
    raw_path = tmp_path / "openai.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    bad = dict(raw)
    bad["reviewer"] = {**bad["reviewer"], "provider": "anthropic"}
    mismatch = tmp_path / "mismatch.json"
    mismatch.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="provider mismatch"):
        ai_review.build_high_risk_supersession_from_raw_reviews(
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10X",
            implementer_provider="google",
            context_binding=context,
            high_risk_changed_paths=["ao_kernel/ao_release_gate.py"],
            raw_review_paths={"openai": mismatch, "anthropic": raw_path},
            max_age_seconds=3600,
            round_index=1,
        )


def test_ai_review_safe_console_and_missing_command_paths(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "dry_run_status": "blocked",
        "raw_review_paths": {"anthropic": "/secret/path", "openai": "/other/path"},
    }
    ai_review._print_payload(payload, output="text")
    out = capsys.readouterr().out
    assert "status: blocked" in out
    assert "anthropic" in out
    assert "/secret/path" not in out

    assert ai_review.dispatch_ai_review(Namespace(ai_review_command=None)) == 1
    err = capsys.readouterr().err
    assert "Usage: ao-kernel ai-review" in err


def test_ai_review_consensus_runs_bounded_ping_pong_until_agree(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    fake = _fake_provider(tmp_path, provider_stateful=True)
    openai_state = tmp_path / "openai.state"
    anthropic_state = tmp_path / "anthropic.state"
    output_dir = tmp_path / "consensus"

    proc = _run_cli(
        [
            "ai-review",
            "consensus",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10X",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--implementer-provider",
            "google",
            "--max-rounds",
            "2",
            "--provider",
            f"openai={_cmd('openai', fake, openai_state)}",
            "--provider",
            f"anthropic={_cmd('anthropic', fake, anthropic_state)}",
        ]
    )

    summary = json.loads(proc.stdout)
    assert summary == {
        "artifact_kind": "ai_review_consensus_evidence",
        "evidence_written": True,
        "raw_review_providers": ["openai", "anthropic"],
        "status": "AGREE",
    }
    payload = json.loads((output_dir / "ai_review_consensus.v1.json").read_text())
    _validate("ai-review-consensus-evidence.schema.v1.json", payload)
    assert payload["consensus_status"] == "AGREE"
    assert [round_payload["round_index"] for round_payload in payload["rounds"]] == [1, 2]
    assert {result["verdict"] for result in payload["rounds"][0]["provider_results"]} == {"REVISE"}
    assert {result["verdict"] for result in payload["rounds"][1]["provider_results"]} == {"AGREE"}
    assert set(payload["raw_review_paths"]) == {"anthropic", "openai"}
    assert payload["collection_evidence_path"].endswith("ai_review_collection.v1.json")


def test_ai_review_consensus_fails_closed_when_max_rounds_exhausted(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    fake = _fake_provider(tmp_path, mode="revise")

    output_dir = tmp_path / "blocked"
    proc = _run_cli(
        [
            "ai-review",
            "consensus",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10X",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--implementer-provider",
            "google",
            "--max-rounds",
            "1",
            "--provider",
            f"openai={_cmd('openai', fake)}",
            "--provider",
            f"anthropic={_cmd('anthropic', fake)}",
        ],
        check=False,
    )

    assert proc.returncode == 1
    summary = json.loads(proc.stdout)
    assert summary == {
        "artifact_kind": "ai_review_consensus_evidence",
        "evidence_written": True,
        "raw_review_providers": [],
        "status": "not_agreed",
    }
    payload = json.loads((output_dir / "ai_review_consensus.v1.json").read_text())
    _validate("ai-review-consensus-evidence.schema.v1.json", payload)
    assert payload["consensus_status"] == "not_agreed"
    assert payload["raw_review_paths"] == {}
    assert payload["collection_evidence_path"] is None


def test_ai_review_high_risk_dry_run_proves_gate_allow_without_github_mutation(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    fake = _fake_provider(tmp_path)
    output_dir = tmp_path / "reviews"
    collect = _run_cli(
        [
            "ai-review",
            "collect",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10X",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--implementer-provider",
            "google",
            "--provider",
            f"openai={_cmd('openai', fake)}",
            "--provider",
            f"anthropic={_cmd('anthropic', fake)}",
        ]
    )
    assert json.loads(collect.stdout)["raw_review_providers"] == ["openai", "anthropic"]
    raw_paths = {
        "openai": str(output_dir / "openai.local-ai-review-evidence.v1.json"),
        "anthropic": str(output_dir / "anthropic.local-ai-review-evidence.v1.json"),
    }

    dry_run_output_dir = tmp_path / "dry-run"
    dry_run = _run_cli(
        [
            "ai-review",
            "high-risk-dry-run",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10X",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(dry_run_output_dir),
            "--implementer-provider",
            "google",
            "--review-evidence",
            raw_paths["openai"],
            "--review-evidence",
            raw_paths["anthropic"],
        ]
    )

    summary = json.loads(dry_run.stdout)
    assert summary == {
        "artifact_kind": "ai_review_high_risk_dry_run_evidence",
        "evidence_written": True,
        "github_mutation_performed": False,
        "merge_attempted": False,
        "raw_review_providers": ["openai", "anthropic"],
        "status": "pass",
    }
    payload = json.loads((dry_run_output_dir / "ai_review_high_risk_dry_run.v1.json").read_text())
    _validate("ai-review-high-risk-dry-run-evidence.schema.v1.json", payload)
    assert payload["dry_run_status"] == "pass"
    assert payload["ao_release_gate_allow"] is True
    assert payload["merge_attempted"] is False
    assert payload["github_mutation_performed"] is False
