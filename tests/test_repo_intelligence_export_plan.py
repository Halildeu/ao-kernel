from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel._internal.repo_intelligence.artifacts import (
    REPO_EXPORT_PLAN_SCHEMA_NAME,
    validate_repo_export_plan,
    write_repo_export_plan_artifact,
)
from ao_kernel._internal.repo_intelligence.context_pack_builder import build_agent_context_pack
from ao_kernel._internal.repo_intelligence.export_plan import (
    DEFAULT_TARGET_SPECS,
    ExportTargetSpec,
    build_repo_export_plan,
    render_repo_export_target_content,
    supported_repo_export_targets,
)
from ao_kernel._internal.repo_intelligence.python_ast_indexer import build_python_ast_indexes
from ao_kernel._internal.repo_intelligence.repo_chunker import build_repo_chunks
from ao_kernel._internal.repo_intelligence.scanner import scan_repo
from ao_kernel.config import load_default
from ao_kernel.repo_intelligence import write_repo_scan_artifacts


def _repo_with_workspace(tmp_path: Path) -> Path:
    project = tmp_path / "export-plan-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "main.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname = \"export-plan-project\"\n", encoding="utf-8")
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


def _normalized(plan: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(plan))
    clone["generator"]["generated_at"] = "<normalized>"
    return clone


def _target(plan: dict[str, Any], target: str) -> dict[str, Any]:
    return next(item for item in plan["targets"] if item["target"] == target)


def test_bundled_repo_export_plan_schema_is_valid() -> None:
    schema = load_default("schemas", REPO_EXPORT_PLAN_SCHEMA_NAME)

    Draft202012Validator.check_schema(schema)

    assert schema["$id"] == "urn:ao:repo-export-plan:v1"


def test_export_plan_is_schema_backed_and_deterministic(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)

    first = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["agents", "codex"],
    )
    second = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex", "agents"],
    )

    validate_repo_export_plan(first)
    validate_repo_export_plan(second)
    assert _normalized(first) == _normalized(second)
    assert [item["target"] for item in first["targets"]] == ["codex", "agents"]
    assert first["summary"] == {
        "target_count": 2,
        "create": 2,
        "update": 0,
        "unchanged": 0,
        "blocked": 0,
        "missing_required_source_artifacts": 0,
    }
    assert all(record["path"].startswith(".ao/context/") for record in first["source_artifacts"].values())
    assert supported_repo_export_targets() == ("codex", "agents")


def test_export_plan_blocks_targets_when_required_sources_are_missing(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)

    plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
    )
    target = _target(plan, "codex")

    validate_repo_export_plan(plan)
    assert target["action"] == "blocked"
    assert plan["summary"]["blocked"] == 1
    assert plan["summary"]["missing_required_source_artifacts"] == 2
    assert {item["code"] for item in target["diagnostics"]} == {"required_source_missing"}
    assert plan["source_artifacts"]["repo_map"]["present"] is False
    assert plan["source_artifacts"]["agent_pack"]["present"] is False


def test_export_plan_marks_existing_matching_root_as_unchanged(tmp_path: Path) -> None:
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

    plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
    )
    target = _target(plan, "codex")

    validate_repo_export_plan(plan)
    assert target["action"] == "unchanged"
    assert target["existing_file"] is True
    assert target["existing_sha256"] == target["generated_content_sha256"]


def test_export_plan_blocks_existing_different_root_file(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    (project / "AGENTS.md").write_text("human maintained instructions\n", encoding="utf-8")

    plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["agents"],
    )
    target = _target(plan, "agents")

    validate_repo_export_plan(plan)
    assert target["action"] == "blocked"
    assert target["existing_file"] is True
    assert target["existing_sha256"] != target["generated_content_sha256"]
    assert {item["code"] for item in target["diagnostics"]} == {"root_file_conflict"}


def test_export_plan_blocks_symlink_and_escape_targets(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (project / "CODEX_CONTEXT.md").symlink_to(outside)

    symlink_plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
    )
    escape_plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
        target_specs=[
            ExportTargetSpec(
                target="codex",
                root_path="../CODEX_CONTEXT.md",
                title="Codex Context",
                content_source="repo-intelligence-agent-pack.v1",
            )
        ],
    )

    assert _target(symlink_plan, "codex")["action"] == "blocked"
    assert {item["code"] for item in _target(symlink_plan, "codex")["diagnostics"]} == {"target_path_symlink"}
    assert _target(escape_plan, "codex")["action"] == "blocked"
    assert {item["code"] for item in _target(escape_plan, "codex")["diagnostics"]} == {"target_path_invalid"}


def test_write_repo_export_plan_artifact_writes_schema_backed_output(tmp_path: Path) -> None:
    project = _repo_with_workspace(tmp_path)
    _write_repo_sources(project)
    plan = build_repo_export_plan(
        project_root=project,
        workspace_root=project / ".ao",
        targets=["codex"],
    )

    result = write_repo_export_plan_artifact(
        context_dir=project / ".ao" / "context",
        export_plan=plan,
    )
    written = json.loads((project / ".ao" / "context" / "repo_export_plan.json").read_text(encoding="utf-8"))

    validate_repo_export_plan(written)
    assert result["artifact_kind"] == "repo_export_plan_write_result"
    assert result["artifacts"][0]["path"] == ".ao/context/repo_export_plan.json"
    assert result["artifacts"][0]["schema_ref"] == REPO_EXPORT_PLAN_SCHEMA_NAME
