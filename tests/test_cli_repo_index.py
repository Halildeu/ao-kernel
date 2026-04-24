from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_kernel.cli import main
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import CONFIRM_VECTOR_INDEX


def _make_cli_project(tmp_path: Path) -> Path:
    project = tmp_path / "cli-index-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"cli-index-project\"\n[project.scripts]\ncli-index-project = \"pkg.cli:main\"\n",
        encoding="utf-8",
    )
    return project


def test_repo_index_dry_run_writes_vector_write_plan_only_after_scan(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    scan_rc = main(["repo", "scan", "--project-root", str(project), "--output", "json"])
    capsys.readouterr()
    index_rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--dry-run",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert scan_rc == 0
    assert index_rc == 0
    assert captured.err == ""
    assert payload["status"] == "ok"
    assert payload["command"] == "repo index"
    assert payload["dry_run"] is True
    assert payload["summary"]["embedding_calls"] == 0
    assert payload["summary"]["vector_writes"] == 0
    assert payload["artifacts"] and payload["artifacts"][0]["path"] == ".ao/context/repo_vector_write_plan.json"
    assert (project / ".ao" / "context" / "repo_vector_write_plan.json").is_file()
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / "ARCHITECTURE.md").exists()
    assert not (project / "CODEX_CONTEXT.md").exists()


def test_repo_index_dry_run_default_output_is_text(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    rc = main(["repo", "index", "--project-root", str(project), "--dry-run"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert "repo index dry-run complete" in captured.out
    assert ".ao/context/repo_vector_write_plan.json" in captured.out


def test_repo_index_missing_chunk_manifest_fails_closed(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
            "--dry-run",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "repo chunk manifest not found" in captured.err
    assert not (project / ".ao" / "context" / "repo_vector_write_plan.json").exists()


def test_repo_index_invalid_chunk_manifest_fails_closed(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)
    context_dir = project / ".ao" / "context"
    context_dir.mkdir(parents=True)
    (context_dir / "repo_chunks.json").write_text('{"artifact_kind": "not_repo_chunks"}', encoding="utf-8")

    rc = main(["repo", "index", "--project-root", str(project), "--dry-run", "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "invalid repo chunk manifest" in captured.err
    assert not (context_dir / "repo_vector_write_plan.json").exists()


class _FakeVectorStore:
    def __init__(self) -> None:
        self.closed = False
        self.stored: dict[str, dict[str, Any]] = {}

    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        self.stored[key] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }

    def delete(self, key: str) -> bool:
        return False

    def close(self) -> None:
        self.closed = True


def test_repo_index_requires_explicit_mode(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "index", "--project-root", str(project), "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "requires --dry-run or --write-vectors" in captured.err


def test_repo_index_write_vectors_requires_confirmation(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "index", "--project-root", str(project), "--write-vectors"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert f"--confirm-vector-index {CONFIRM_VECTOR_INDEX}" in captured.err


def test_repo_index_write_vectors_fails_closed_without_vector_backend(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    monkeypatch.delenv("AO_KERNEL_VECTOR_BACKEND", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            CONFIRM_VECTOR_INDEX,
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "requires a configured vector backend" in captured.err


def test_repo_index_write_vectors_fails_closed_without_embedding_key(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("AO_KERNEL_VECTOR_BACKEND", "inmemory")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            CONFIRM_VECTOR_INDEX,
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "embedding API key is required" in captured.err
    assert not (project / ".ao" / "context" / "repo_vector_write_plan.json").exists()
    assert not (project / ".ao" / "context" / "repo_vector_index_manifest.json").exists()


def test_repo_index_write_vectors_uses_mocked_embedding_and_vector_store(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store = _FakeVectorStore()
    embed_calls: list[dict[str, Any]] = []

    def fake_resolve_vector_store(*, workspace: Path | None = None, injected: Any | None = None) -> tuple[Any, bool]:
        return store, True

    def fake_embed_text(*_args: Any, **kwargs: Any) -> list[float]:
        embed_calls.append(kwargs)
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr("ao_kernel.context.vector_store_resolver.resolve_vector_store", fake_resolve_vector_store)
    monkeypatch.setattr("ao_kernel.context.semantic_retrieval.embed_text", fake_embed_text)

    rc = main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            CONFIRM_VECTOR_INDEX,
            "--embedding-provider",
            "openai",
            "--embedding-model",
            "test-embedding-model",
            "--embedding-dimension",
            "3",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload["status"] == "ok"
    assert payload["dry_run"] is False
    assert payload["summary"]["vector_writes"] == payload["summary"]["indexed_keys"]
    assert payload["summary"]["embedding_calls"] == payload["summary"]["indexed_keys"]
    assert embed_calls
    assert {call["provider_id"] for call in embed_calls} == {"openai"}
    assert {call["model"] for call in embed_calls} == {"test-embedding-model"}
    assert [item["path"] for item in payload["artifacts"]] == [
        ".ao/context/repo_vector_write_plan.json",
        ".ao/context/repo_vector_index_manifest.json",
    ]
    assert store.stored
    assert store.closed is True
    assert (project / ".ao" / "context" / "repo_vector_index_manifest.json").is_file()
    assert not (project / "CLAUDE.md").exists()
