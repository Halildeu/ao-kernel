from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_kernel.cli import main
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import CONFIRM_VECTOR_INDEX
from ao_kernel.context.semantic_retrieval import cosine_similarity


class _FakeVectorStore:
    def __init__(self) -> None:
        self.closed = False
        self.stored: dict[str, dict[str, Any]] = {}

    def store(self, key: str, embedding: list[float], *, metadata: dict[str, Any] | None = None) -> None:
        self.stored[key] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[dict[str, Any]]:
        results = []
        for key, record in self.stored.items():
            similarity = cosine_similarity(query_embedding, record["embedding"])
            if similarity >= min_similarity:
                results.append(
                    {
                        "key": key,
                        "similarity": round(similarity, 4),
                        "metadata": record["metadata"],
                    }
                )
        results.sort(key=lambda item: (-float(item["similarity"]), str(item["key"])))
        return results[:top_k]

    def delete(self, key: str) -> bool:
        return self.stored.pop(key, None) is not None

    def close(self) -> None:
        self.closed = True


def _make_cli_project(tmp_path: Path) -> Path:
    project = tmp_path / "cli-query-project"
    (project / ".ao").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"cli-query-project\"\n[project.scripts]\ncli-query-project = \"pkg.cli:main\"\n",
        encoding="utf-8",
    )
    return project


def _fake_embed_text(*_args: Any, **_kwargs: Any) -> list[float]:
    return [0.1, 0.2, 0.3]


def _context_snapshot(project: Path) -> dict[str, bytes]:
    context_dir = project / ".ao" / "context"
    return {
        item.relative_to(context_dir).as_posix(): item.read_bytes()
        for item in sorted(context_dir.rglob("*"))
        if item.is_file()
    }


def _scan_and_write_vectors(project: Path, store: _FakeVectorStore, capsys: Any, monkeypatch: Any) -> None:
    def fake_resolve_vector_store(*, workspace: Path | None = None, injected: Any | None = None) -> tuple[Any, bool]:
        return store, True

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("ao_kernel.context.vector_store_resolver.resolve_vector_store", fake_resolve_vector_store)
    monkeypatch.setattr("ao_kernel.context.semantic_retrieval.embed_text", _fake_embed_text)
    assert main(["repo", "scan", "--project-root", str(project), "--output", "json"]) == 0
    capsys.readouterr()
    assert main(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--workspace-root",
            ".ao",
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
    ) == 0
    capsys.readouterr()


def test_repo_query_missing_vector_index_manifest_fails_closed(tmp_path: Path, capsys) -> None:
    project = _make_cli_project(tmp_path)

    rc = main(["repo", "query", "--project-root", str(project), "--query", "main", "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "repo vector index manifest not found" in captured.err


def test_repo_query_fails_closed_without_embedding_key(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    store = _FakeVectorStore()
    _scan_and_write_vectors(project, store, capsys, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    rc = main(["repo", "query", "--project-root", str(project), "--query", "main", "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "embedding API key is required for repo vector query" in captured.err


def test_repo_query_fails_closed_without_vector_backend(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    store = _FakeVectorStore()
    _scan_and_write_vectors(project, store, capsys, monkeypatch)

    def disabled_resolver(*, workspace: Path | None = None, injected: Any | None = None) -> tuple[Any, bool]:
        return None, False

    monkeypatch.setattr("ao_kernel.context.vector_store_resolver.resolve_vector_store", disabled_resolver)

    rc = main(["repo", "query", "--project-root", str(project), "--query", "main", "--output", "json"])
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "repo query requires a configured vector backend" in captured.err


def test_repo_query_returns_matches_without_writing_root_files(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    store = _FakeVectorStore()
    _scan_and_write_vectors(project, store, capsys, monkeypatch)
    context_before = _context_snapshot(project)

    rc = main(
        [
            "repo",
            "query",
            "--project-root",
            str(project),
            "--query",
            "where is main",
            "--top-k",
            "3",
            "--candidate-limit",
            "10",
            "--path-prefix",
            "pkg/",
            "--output",
            "json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert captured.err == ""
    assert payload["status"] == "ok"
    assert payload["command"] == "repo query"
    assert payload["summary"]["matches"] >= 1
    assert payload["query_result"]["artifact_kind"] == "repo_vector_query_result"
    assert all(item["source_path"].startswith("pkg/") for item in payload["results"])
    assert _context_snapshot(project) == context_before
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / "ARCHITECTURE.md").exists()
    assert not (project / "CODEX_CONTEXT.md").exists()


def test_repo_query_markdown_output_is_agent_readable_and_read_only(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    store = _FakeVectorStore()
    _scan_and_write_vectors(project, store, capsys, monkeypatch)
    context_before = _context_snapshot(project)

    rc = main(
        [
            "repo",
            "query",
            "--project-root",
            str(project),
            "--query",
            "where is main",
            "--path-prefix",
            "pkg/",
            "--output",
            "markdown",
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert captured.out.startswith("# Repo Query Context Pack\n")
    assert "## Generation Boundary" in captured.out
    assert "## Handoff Contract" in captured.out
    assert "stdout-only Markdown" in captured.out
    assert "No hidden injection" in captured.out
    assert "context_compiler" in captured.out
    assert "| Text | where is main |" in captured.out
    assert "```python\n" in captured.out
    assert "def main():" in captured.out
    assert _context_snapshot(project) == context_before
    assert not (project / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / "ARCHITECTURE.md").exists()
    assert not (project / "CODEX_CONTEXT.md").exists()


def test_repo_query_default_output_is_text(tmp_path: Path, capsys, monkeypatch) -> None:
    project = _make_cli_project(tmp_path)
    store = _FakeVectorStore()
    _scan_and_write_vectors(project, store, capsys, monkeypatch)

    rc = main(["repo", "query", "--project-root", str(project), "--query", "main"])
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    assert "repo query complete" in captured.out
    assert "matches:" in captured.out
