from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel._internal.repo_intelligence.artifacts import (
    REPO_ROOT_EXPORT_RESULT_SCHEMA_NAME,
    validate_repo_root_export_result,
    write_repo_export_plan_artifact,
)
from ao_kernel._internal.repo_intelligence.context_pack_builder import build_agent_context_pack
from ao_kernel._internal.repo_intelligence.export_plan import (
    CONFIRM_RI5B_ROOT_EXPORT,
    DEFAULT_TARGET_SPECS,
    build_repo_export_plan,
    render_repo_export_target_content,
)
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.root_exporter import (
    RepoRootExportError,
    export_repo_roots,
)
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel.config import load_default
from ao_kernel.repo_intelligence import write_repo_scan_artifacts


ROOT_FILES = ("CODEX_CONTEXT.md", "AGENTS.md")


def _repo_with_workspace(tmp_path: Path) -> Path:
    project = tmp_path / "root-export-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "main.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname = \"root-export-project\"\n", encoding="utf-8")
    return project


def _write_repo_sources(project: Path) -> None:
    repo_map = scan_repo(project)
    import_graph, symbol_index = build_python_ast_indexes(project, repo_map)
    repo_chunks = build_repo_chunks(
        project,
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
    )
    agent_pack = build_agent_context_pack(
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
        repo_chunks=repo_chunks,
    )
    write_repo_scan_artifacts(
        context_dir=project / ".ao" / "context",
        repo_map=repo_map,
        import_graph=import_graph,
        symbol_index=symbol_index,
        repo_chunks=repo_chunks,
        agent_pack=agent_pack,
    )


def _write_enabled_coordination_policy(project: Path) -> None:
    policy_dir = project / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 10,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_plan(project: Path, targets: list[str] | None = None) -> dict[str, Any]:
    plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=targets or ["codex", "agents"],
    )
    write_repo_export_plan_artifact(
        context_dir=project / ".ao" / "context",
        export_plan=plan,
    )
    return plan


def _replace_plan(project: Path, plan: dict[str, Any]) -> None:
    (project / ".ao" / "context" / "repo_export_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _root_snapshot(project: Path) -> dict[str, bytes | None]:
    return {
        name: (project / name).read_bytes() if (project / name).is_file() else None
        for name in ROOT_FILES
    }


def _target(plan: dict[str, Any], target: str) -> dict[str, Any]:
    return next(item for item in plan["targets"] if item["target"] == target)


def test_bundled_repo_root_export_result_schema_is_valid() -> None:
    schema = load_default("schemas", REPO_ROOT_EXPORT_RESULT_SCHEMA_NAME)

    Draft202012Validator.check_schema(schema)

    assert schema["$id"] == "urn:ao:repo-root-export-result:v1"


@pytest.mark.parametrize("token", ["", "CONFIRM_RI5B_ROOT_EXPORT_v1"])
def test_root_export_requires_exact_confirmation_without_writes(
    tmp_path: Path,
    token: str,
) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    _write_plan(project, ["codex"])
    before = _root_snapshot(project)

    with pytest.raises(RepoRootExportError, match="exact confirmation token"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=token,
        )

    assert _root_snapshot(project) == before


def test_root_export_requires_existing_valid_export_plan_without_writes(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)

    with pytest.raises(RepoRootExportError, match="repo export plan not found"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    assert _root_snapshot(project) == {"CODEX_CONTEXT.md": None, "AGENTS.md": None}

    (project / ".ao" / "context" / "repo_export_plan.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RepoRootExportError, match="repo export plan is invalid"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    assert _root_snapshot(project) == {"CODEX_CONTEXT.md": None, "AGENTS.md": None}


def test_root_export_rejects_stale_source_artifact_without_writes(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    _write_plan(project, ["codex"])
    (project / ".ao" / "context" / "agent_pack.md").write_text("stale\n", encoding="utf-8")

    with pytest.raises(RepoRootExportError, match="source artifact stale"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    assert _root_snapshot(project)["CODEX_CONTEXT.md"] is None


def test_root_export_rejects_unsupported_or_absent_targets_without_writes(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    _write_plan(project, ["codex"])
    before = _root_snapshot(project)

    with pytest.raises(RepoRootExportError, match="unsupported root export target"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["claude"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )
    with pytest.raises(RepoRootExportError, match="absent from repo export plan"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["agents"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    assert _root_snapshot(project) == before


def test_root_export_rejects_blocked_update_and_conflict_without_partial_writes(
    tmp_path: Path,
) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    (project / "AGENTS.md").write_text("human instructions\n", encoding="utf-8")
    _write_plan(project, ["codex", "agents"])
    before = _root_snapshot(project)

    with pytest.raises(RepoRootExportError, match="is blocked"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex", "agents"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )
    assert _root_snapshot(project) == before

    plan = _write_plan(project, ["codex"])
    mutated = copy.deepcopy(plan)
    _target(mutated, "codex")["action"] = "update"
    _replace_plan(project, mutated)
    with pytest.raises(RepoRootExportError, match="create-only"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )
    assert _root_snapshot(project) == before


def test_root_export_rejects_symlink_and_path_escape_without_writes(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    _write_plan(project, ["codex"])
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (project / "CODEX_CONTEXT.md").symlink_to(outside)

    with pytest.raises(RepoRootExportError, match="symlink"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    (project / "CODEX_CONTEXT.md").unlink()
    plan = _write_plan(project, ["codex"])
    escaped = copy.deepcopy(plan)
    _target(escaped, "codex")["root_path"] = "../CODEX_CONTEXT.md"
    _replace_plan(project, escaped)
    with pytest.raises(RepoRootExportError, match="escape"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    assert _root_snapshot(project)["CODEX_CONTEXT.md"] is None


def test_root_export_requires_path_ownership_before_write(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    _write_plan(project, ["codex"])

    with pytest.raises(RepoRootExportError, match="path ownership unavailable"):
        export_repo_roots(
            project_root=project,
            workspace_root=project / ".ao",
            targets=["codex"],
            confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
        )

    assert _root_snapshot(project)["CODEX_CONTEXT.md"] is None


def test_root_export_create_only_happy_path_emits_schema_backed_result(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    _write_plan(project, ["codex"])
    _write_enabled_coordination_policy(project)

    result = export_repo_roots(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
        confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
    )
    written = project / "CODEX_CONTEXT.md"

    validate_repo_root_export_result(result)
    assert written.is_file()
    assert result["support_widening"] is False
    assert result["summary"] == {
        "target_count": 1,
        "written_count": 1,
        "unchanged_count": 0,
        "denied_count": 0,
        "skipped_count": 0,
    }
    assert result["targets"][0]["result"] == "written"
    assert result["targets"][0]["before"] == {"exists": False, "sha256": None}
    assert result["targets"][0]["after"]["sha256"] == result["targets"][0]["generated_content_sha256"]
    assert result["targets"][0]["ownership"]["status"] == "released"
    assert not (project / "AGENTS.md").exists()


def test_root_export_matching_existing_file_is_unchanged_noop(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    initial = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
    )
    content = render_repo_export_target_content(
        target="codex",
        title=DEFAULT_TARGET_SPECS[0].title,
        source_artifacts=initial["source_artifacts"],
    )
    (project / "CODEX_CONTEXT.md").write_text(content, encoding="utf-8")
    _write_plan(project, ["codex"])
    _write_enabled_coordination_policy(project)

    result = export_repo_roots(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
        confirm_root_export=CONFIRM_RI5B_ROOT_EXPORT,
    )

    validate_repo_root_export_result(result)
    assert result["summary"]["written_count"] == 0
    assert result["summary"]["unchanged_count"] == 1
    assert result["targets"][0]["result"] == "unchanged"
