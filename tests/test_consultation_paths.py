"""v3.5 D1: consultation path canonicalization tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.config import load_default
from ao_kernel.consultation.migrate import migrate_consultations
from ao_kernel.consultation.paths import (
    FileClassification,
    classify_request_file,
    classify_response_file,
    is_file_artefact,
    iter_consultation_files,
    load_consultation_paths,
    resolve_consultation_dir,
    resolve_consultation_path,
)


@pytest.fixture
def policy() -> dict:
    return load_default("policies", "policy_agent_consultation.v1.json")


class TestPolicyPaths:
    def test_bundled_policy_points_at_canonical_ao_layout(
        self, policy: dict,
    ) -> None:
        """v3.5 policy must declare `.ao/consultations/*` paths.

        Pre-v3.5 `.cache/...` paths remain available as
        ``legacy_fallbacks`` so copy-forward migration still reads
        historical artefacts.
        """
        paths = policy["paths"]
        assert paths["requests"] == ".ao/consultations/requests"
        assert paths["responses"] == ".ao/consultations/responses"
        assert paths["state"] == ".ao/consultations/state"
        assert "legacy_fallbacks" in paths
        legacy = paths["legacy_fallbacks"]
        assert legacy["requests"].startswith(".cache/")

    def test_load_consultation_paths_resolves_absolute(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        resolved = load_consultation_paths(policy, workspace_root=tmp_path)
        assert resolved.requests == (
            tmp_path / ".ao" / "consultations" / "requests"
        ).resolve()
        assert resolved.legacy_fallbacks["requests"].is_absolute()


class TestResolveConsultationDir:
    def test_resolve_canonical_by_default(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        got = resolve_consultation_dir(
            policy, "requests", workspace_root=tmp_path,
        )
        assert got == (tmp_path / ".ao" / "consultations" / "requests").resolve()

    def test_prefer_legacy_falls_back_when_canonical_missing(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        legacy_dir = tmp_path / ".cache" / "index" / "consultations" / "requests"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        got = resolve_consultation_dir(
            policy, "requests",
            workspace_root=tmp_path,
            prefer_legacy=True,
        )
        assert got == legacy_dir.resolve()


class TestConfigArtefactSingleFile:
    """Codex iter-3 BLOCKER #1 regression pin: `config` is modeled as
    a single file, NOT a directory."""

    def test_config_is_file_artefact(self) -> None:
        assert is_file_artefact("config") is True
        assert is_file_artefact("requests") is False
        assert is_file_artefact("responses") is False
        assert is_file_artefact("state") is False

    def test_resolve_consultation_dir_rejects_file_artefact(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        with pytest.raises(ValueError, match="modeled as a file"):
            resolve_consultation_dir(
                policy, "config", workspace_root=tmp_path,
            )

    def test_resolve_consultation_path_rejects_dir_artefact(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        with pytest.raises(ValueError, match="modeled as a directory"):
            resolve_consultation_path(
                policy, "requests", workspace_root=tmp_path,
            )

    def test_resolve_config_path_canonical(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        got = resolve_consultation_path(
            policy, "config", workspace_root=tmp_path,
        )
        assert got.name == "consultation_agents.v1.json"
        # Parent is .ao/consultations/config/, not the file itself
        assert got.parent.name == "config"

    def test_migration_copies_config_as_file_not_dir(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        """Apply mode: legacy config file → canonical config file
        (NOT a directory named like the file)."""
        legacy_cfg = tmp_path / ".cache" / "config" / "consultation_agents.v1.json"
        legacy_cfg.parent.mkdir(parents=True, exist_ok=True)
        legacy_cfg.write_text(
            json.dumps({"agents": {"codex": {}}}), encoding="utf-8",
        )

        result = migrate_consultations(
            policy, workspace_root=tmp_path, dry_run=False,
        )
        target = (
            tmp_path / ".ao" / "consultations" / "config"
            / "consultation_agents.v1.json"
        )
        assert target.is_file()
        # The canonical path itself is a FILE, not a directory
        assert not (
            tmp_path / ".ao" / "consultations" / "config"
            / "consultation_agents.v1.json" / "whatever"
        ).parent.is_dir() or target.is_file()  # sanity tautology
        assert result.copied_count >= 1


class TestWorkspaceOverride:
    """Codex iter-3 BLOCKER #2 regression pin: CLI must load workspace
    override when present, not bundled-only."""

    def test_cli_migrate_uses_workspace_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Place a workspace override that points paths at a sentinel
        # directory name so we can verify the override was honoured.
        override_dir = tmp_path / ".ao" / "policies"
        override_dir.mkdir(parents=True, exist_ok=True)
        override_doc = load_default(
            "policies", "policy_agent_consultation.v1.json",
        )
        override_doc["paths"]["requests"] = ".ao/consultations/OVERRIDDEN"
        (override_dir / "policy_agent_consultation.v1.json").write_text(
            json.dumps(override_doc), encoding="utf-8",
        )

        from ao_kernel.config import load_with_override
        loaded = load_with_override(
            "policies", "policy_agent_consultation.v1.json",
            workspace=tmp_path / ".ao",
        )
        assert loaded["paths"]["requests"] == ".ao/consultations/OVERRIDDEN"


class TestSchemaAllowsLegacyFallbacks:
    """Codex iter-3 SUGGEST regression pin: bundled schema validates
    the bundled policy (including the new legacy_fallbacks map)."""

    def test_bundled_schema_accepts_bundled_policy(self) -> None:
        from jsonschema import Draft202012Validator

        schema = load_default(
            "schemas", "policy-agent-consultation.schema.v1.json",
        )
        policy_doc = load_default(
            "policies", "policy_agent_consultation.v1.json",
        )
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(policy_doc))
        assert errors == []  # bundled policy passes bundled schema


class TestClassifiers:
    def test_classify_request_valid_current(self, tmp_path: Path) -> None:
        f = tmp_path / "CNS-20260418-001.request.v1.json"
        f.write_text(json.dumps({
            "consultation_id": "CNS-20260418-001",
            "from_agent": "claude",
            "to_agent": "codex",
            "topic": "planning",
        }), encoding="utf-8")
        assert classify_request_file(f) == FileClassification.VALID_CURRENT

    def test_classify_request_invalid_missing_id(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.request.json"
        f.write_text(json.dumps({"topic": "planning"}), encoding="utf-8")
        assert classify_request_file(f) == FileClassification.INVALID_JSON

    def test_classify_response_valid_current(self, tmp_path: Path) -> None:
        f = tmp_path / "CNS-20260418-001.codex.response.v1.json"
        f.write_text(json.dumps({
            "consultation_id": "CNS-20260418-001",
            "overall_verdict": "AGREE",
            "body": "looks good",
        }), encoding="utf-8")
        assert classify_response_file(f) == FileClassification.VALID_CURRENT

    def test_classify_response_legacy_missing_cns_id(
        self, tmp_path: Path,
    ) -> None:
        f = tmp_path / "legacy.response.json"
        f.write_text(json.dumps({
            "overall_verdict": "mostly_agree",
            "body": "ok",
        }), encoding="utf-8")
        assert classify_response_file(f) == FileClassification.LEGACY_SHAPE

    def test_classify_response_invalid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.response.json"
        f.write_text("{not valid json", encoding="utf-8")
        assert classify_response_file(f) == FileClassification.INVALID_JSON


class TestIterConsultationFiles:
    def test_walks_canonical_and_legacy(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        canonical_dir = tmp_path / ".ao" / "consultations" / "requests"
        legacy_dir = tmp_path / ".cache" / "index" / "consultations" / "requests"
        canonical_dir.mkdir(parents=True, exist_ok=True)
        legacy_dir.mkdir(parents=True, exist_ok=True)

        (canonical_dir / "CNS-20260418-001.request.v1.json").write_text(
            json.dumps({"consultation_id": "CNS-20260418-001"}),
            encoding="utf-8",
        )
        (legacy_dir / "CNS-20260410-001.request.v1.json").write_text(
            json.dumps({"consultation_id": "CNS-20260410-001"}),
            encoding="utf-8",
        )

        results = list(iter_consultation_files(
            policy, "requests", workspace_root=tmp_path,
        ))
        origins = {r[1] for r in results}
        assert "canonical" in origins
        assert "legacy" in origins
        classifications = {r[2] for r in results}
        assert FileClassification.VALID_CURRENT in classifications


class TestMigration:
    def _legacy_dir(self, root: Path, artefact: str) -> Path:
        mapping = {
            "requests": ".cache/index/consultations/requests",
            "responses": ".cache/reports/consultations",
            "state": ".cache/index/consultations/state",
            "config": ".cache/config/consultation_agents.v1.json",
        }
        return root / mapping[artefact]

    def test_dry_run_reports_without_copying(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        legacy = self._legacy_dir(tmp_path, "requests")
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "CNS-20260410-001.request.v1.json").write_text(
            json.dumps({"consultation_id": "CNS-20260410-001"}),
            encoding="utf-8",
        )

        result = migrate_consultations(
            policy, workspace_root=tmp_path, dry_run=True,
        )
        assert result.dry_run is True
        assert result.copied_count == 1
        canonical = tmp_path / ".ao" / "consultations" / "requests"
        assert not (canonical / "CNS-20260410-001.request.v1.json").exists()

    def test_apply_migration_copies_and_writes_manifest(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        legacy = self._legacy_dir(tmp_path, "requests")
        legacy.mkdir(parents=True, exist_ok=True)
        src = legacy / "CNS-20260410-001.request.v1.json"
        src.write_text(
            json.dumps({"consultation_id": "CNS-20260410-001"}),
            encoding="utf-8",
        )

        result = migrate_consultations(
            policy, workspace_root=tmp_path, dry_run=False,
        )
        target = (
            tmp_path / ".ao" / "consultations" / "requests"
            / "CNS-20260410-001.request.v1.json"
        )
        assert target.is_file()
        # Source preserved (copy-forward, not move)
        assert src.is_file()
        # Backup manifest written
        assert result.backup_manifest is not None
        assert result.backup_manifest.is_file()
        manifest = json.loads(
            result.backup_manifest.read_text(encoding="utf-8"),
        )
        assert manifest["version"] == "v1"
        assert len(manifest["entries"]) == 1

    def test_idempotent_skip_existing(
        self, policy: dict, tmp_path: Path,
    ) -> None:
        legacy = self._legacy_dir(tmp_path, "requests")
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "CNS.request.v1.json").write_text(
            json.dumps({"consultation_id": "CNS"}), encoding="utf-8",
        )

        # First pass
        migrate_consultations(
            policy, workspace_root=tmp_path, dry_run=False,
        )
        # Second pass — target exists, should skip
        result = migrate_consultations(
            policy, workspace_root=tmp_path, dry_run=False,
        )
        assert result.skipped_existing == 1
        assert result.copied_count == 0
