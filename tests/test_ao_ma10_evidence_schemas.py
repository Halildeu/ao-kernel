"""AO-MA-10a2 evidence-bundle schema and builder tests."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from ao_kernel.ao_release_gate import diff_digest
from ao_kernel.config import load_default
from scripts.ao_ma10_evidence_bundle import build_bundle


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ao_ma_10a2"
PROVIDER_SCHEMA = "ao-ma-10-provider-consensus.schema.v1.json"
BUNDLE_SCHEMA = "ao-ma-10-evidence-bundle.schema.v1.json"
SCRIPT = ROOT / "scripts" / "ao_ma10_evidence_bundle.py"


def _schema(name: str) -> dict[str, Any]:
    return load_default("schemas", name)


def _fixture(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def _is_invalid(schema_name: str, payload: dict[str, Any]) -> bool:
    return bool(list(Draft202012Validator(_schema(schema_name)).iter_errors(payload)))


def test_ao_ma10a2_schemas_are_valid_draft_2020_12() -> None:
    for schema_name in (PROVIDER_SCHEMA, BUNDLE_SCHEMA):
        schema = _schema(schema_name)
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("urn:ao:ao-ma-10-")


def test_ao_ma10a2_valid_fixtures_validate_against_schema() -> None:
    provider_validator = Draft202012Validator(_schema(PROVIDER_SCHEMA))
    bundle_validator = Draft202012Validator(_schema(BUNDLE_SCHEMA))
    assert list(provider_validator.iter_errors(_fixture("provider_consensus.openai.valid.json"))) == []
    assert list(provider_validator.iter_errors(_fixture("provider_consensus.anthropic.valid.json"))) == []
    assert list(bundle_validator.iter_errors(_fixture("evidence_bundle.valid.json"))) == []


def test_ao_ma10a2_bundle_requires_openai_and_anthropic_reviewers() -> None:
    bundle = _fixture("evidence_bundle.valid.json")
    bundle["reviewer_providers"] = ["openai", "openai"]
    assert _is_invalid(BUNDLE_SCHEMA, bundle)


def test_ao_ma10a2_bundle_rejects_missing_head_sha() -> None:
    bundle = _fixture("evidence_bundle.valid.json")
    bundle["context_binding"].pop("head_sha")
    assert _is_invalid(BUNDLE_SCHEMA, bundle)


def test_ao_ma10a2_bundle_rejects_stale_freshness_status() -> None:
    bundle = _fixture("evidence_bundle.valid.json")
    bundle["freshness"]["status"] = "stale"
    assert _is_invalid(BUNDLE_SCHEMA, bundle)


def test_ao_ma10a2_bundle_rejects_guard_flag_or_ai_authority_flip() -> None:
    bundle = _fixture("evidence_bundle.valid.json")
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        mutated = copy.deepcopy(bundle)
        mutated["guard_flags"][flag] = True
        assert _is_invalid(BUNDLE_SCHEMA, mutated)

    ai_authority = copy.deepcopy(bundle)
    ai_authority["ai_output_release_authority"] = True
    assert _is_invalid(BUNDLE_SCHEMA, ai_authority)


def test_ao_ma10a2_provider_consensus_rejects_secret_or_live_flags() -> None:
    provider = _fixture("provider_consensus.openai.valid.json")
    secret = copy.deepcopy(provider)
    secret["secrets_recorded"] = True
    assert _is_invalid(PROVIDER_SCHEMA, secret)

    live = copy.deepcopy(provider)
    live["live_adapter_execution"] = True
    assert _is_invalid(PROVIDER_SCHEMA, live)


def test_ao_ma10a2_builder_emits_context_bound_bundle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True, text=True)
    (repo / "tracked.txt").write_text("base\nchange\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "change"], check=True, capture_output=True, text=True)

    head_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    context = {
        "repository_full_name": "Halildeu/ao-kernel",
        "base_ref": "HEAD~1",
        "head_ref": "HEAD",
        "head_sha": head_sha,
        "diff_digest": diff_digest(["tracked.txt"]),
        "changed_files_count": 1,
    }

    provider_paths: list[Path] = []
    for provider, agent in (("openai", "codex-reviewer"), ("anthropic", "claude-reviewer")):
        payload = _fixture(f"provider_consensus.{provider}.valid.json")
        payload["provider_id"] = provider
        payload["agent_id"] = agent
        payload["context_binding"] = context
        path = tmp_path / f"{provider}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        provider_paths.append(path)

    bundle = build_bundle(
        repository="Halildeu/ao-kernel",
        work_package="AO-MA-10a2",
        base_ref="HEAD~1",
        head_ref="HEAD",
        repo_root=repo,
        provider_consensus_paths=provider_paths,
        max_age_seconds=3600,
        generated_at="2026-05-28T00:00:00Z",
    )

    assert bundle["consensus_status"] == "AGREE"
    assert bundle["reviewer_providers"] == ["anthropic", "openai"]
    assert bundle["context_binding"] == context
    Draft202012Validator(_schema(BUNDLE_SCHEMA)).validate(bundle)


def test_ao_ma10a2_builder_rejects_provider_context_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True, text=True)
    (repo / "tracked.txt").write_text("base\nchange\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "change"], check=True, capture_output=True, text=True)
    head_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    context = {
        "repository_full_name": "Halildeu/ao-kernel",
        "base_ref": "HEAD~1",
        "head_ref": "HEAD",
        "head_sha": head_sha,
        "diff_digest": diff_digest(["tracked.txt"]),
        "changed_files_count": 1,
    }
    openai = _fixture("provider_consensus.openai.valid.json")
    anthropic = _fixture("provider_consensus.anthropic.valid.json")
    openai["context_binding"] = context
    anthropic["context_binding"] = {**context, "changed_files_count": 3}

    openai_path = tmp_path / "openai.json"
    anthropic_path = tmp_path / "anthropic.json"
    openai_path.write_text(json.dumps(openai), encoding="utf-8")
    anthropic_path.write_text(json.dumps(anthropic), encoding="utf-8")

    try:
        build_bundle(
            repository="Halildeu/ao-kernel",
            work_package="AO-MA-10a2",
            base_ref="HEAD~1",
            head_ref="HEAD",
            repo_root=repo,
            provider_consensus_paths=[openai_path, anthropic_path],
            max_age_seconds=3600,
            generated_at="2026-05-28T00:00:00Z",
        )
    except ValueError as exc:
        assert "context mismatch" in str(exc)
    else:
        raise AssertionError("expected provider context mismatch to fail closed")


def test_ao_ma10a2_script_is_read_only_and_has_no_github_write_or_merge_tokens() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    forbidden = [
        "gh pr merge",
        "gh api --method POST",
        "gh api --method PATCH",
        "gh api --method PUT",
        "gh api --method DELETE",
        "updateBranchProtectionRule",
        "updateRepositoryRuleset",
        "bypass_actors",
        "--admin",
    ]
    for token in forbidden:
        assert token not in text
