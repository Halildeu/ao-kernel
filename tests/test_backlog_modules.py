"""Behavioral tests for v0.2.0 backlog modules — evidence, session, secrets, tool_gateway, utils."""

from __future__ import annotations

import json
from pathlib import Path



class TestEvidenceWriter:
    def test_writer_has_run_dir(self, tmp_path: Path):
        from src.evidence.writer import EvidenceWriter
        writer = EvidenceWriter(out_dir=tmp_path, run_id="test-001")
        assert writer.run_dir.name == "test-001"
        # run_dir created lazily on first write, not on init

    def test_write_request_creates_file(self, tmp_path: Path):
        from src.evidence.writer import EvidenceWriter
        writer = EvidenceWriter(out_dir=tmp_path, run_id="test-002")
        writer.write_request({"intent": "FAST_TEXT", "provider": "openai"})
        files = list(writer.run_dir.rglob("*"))
        assert any(f.is_file() and f.stat().st_size > 0 for f in files)

    def test_write_summary_creates_file(self, tmp_path: Path):
        from src.evidence.writer import EvidenceWriter
        writer = EvidenceWriter(out_dir=tmp_path, run_id="test-003")
        writer.write_summary({"status": "OK", "elapsed_ms": 150})
        files = list(writer.run_dir.rglob("*summary*"))
        assert len(files) >= 1

    def test_write_node_input_output(self, tmp_path: Path):
        from src.evidence.writer import EvidenceWriter
        writer = EvidenceWriter(out_dir=tmp_path, run_id="test-004")
        writer.write_node_input("node_1", {"input": "data"})
        writer.write_node_output("node_1", {"output": "result"})
        files = list(writer.run_dir.rglob("*"))
        assert len([f for f in files if f.is_file()]) >= 2


class TestEvidenceIntegrity:
    def test_verify_empty_dir_returns_dict(self, tmp_path: Path):
        from src.evidence.integrity_verify import verify_run_dir
        result = verify_run_dir(tmp_path)
        assert isinstance(result, dict)


class TestSecretsProvider:
    def test_abstract_provider_has_get_method(self):
        from src.secrets.provider import SecretsProvider
        assert hasattr(SecretsProvider, "get")

    def test_env_provider_reads_mapped_key(self, monkeypatch):
        from src.secrets.env_provider import EnvSecretsProvider
        # OPENAI_API_KEY is mapped in _SECRET_ID_TO_ENV
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-backlog")
        provider = EnvSecretsProvider()
        assert provider.get("OPENAI_API_KEY") == "sk-test-backlog"

    def test_env_provider_missing_key_returns_none(self):
        from src.secrets.env_provider import EnvSecretsProvider
        provider = EnvSecretsProvider(environ={})
        result = provider.get("NONEXISTENT_KEY")
        assert result is None


class TestSessionContextStore:
    def test_new_context_returns_dict(self, tmp_path: Path):
        from src.session.context_store import new_context
        ctx = new_context(
            session_id="test-session-001",
            workspace_root=str(tmp_path),
            ttl_seconds=3600,
        )
        assert isinstance(ctx, dict)
        assert len(ctx) > 0

    def test_new_context_has_session_id(self, tmp_path: Path):
        from src.session.context_store import new_context
        ctx = new_context(
            session_id="ctx-id-test",
            workspace_root=str(tmp_path),
            ttl_seconds=3600,
        )
        assert ctx.get("session_id") == "ctx-id-test"


class TestSessionMemoryDistiller:
    def test_consolidate_facts_returns_dict(self, tmp_path: Path):
        from src.session.memory_distiller import consolidate_facts
        result = consolidate_facts(workspace_root=tmp_path, distilled=[])
        assert isinstance(result, dict)


class TestLegacyToolGateway:
    def test_legacy_import_warns_deprecated(self):
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import importlib
            importlib.reload(importlib.import_module("src.prj_kernel_api.tool_gateway"))
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) >= 1
            assert "deprecated" in str(dep_warnings[0].message).lower()


class TestUtils:
    def test_save_json_creates_valid_file(self, tmp_path: Path):
        from src.utils.jsonio import save_json
        f = tmp_path / "output.json"
        save_json(f, {"key": "value", "num": 42})
        assert f.exists()
        data = json.loads(f.read_text())
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_save_json_overwrites(self, tmp_path: Path):
        from src.utils.jsonio import save_json
        f = tmp_path / "output.json"
        save_json(f, {"v": 1})
        save_json(f, {"v": 2})
        assert json.loads(f.read_text())["v"] == 2
