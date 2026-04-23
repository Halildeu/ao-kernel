"""Tests for extension loader and registry (B3, CNS-008)."""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel.extensions.loader import ExtensionRegistry, LoadReport


def _valid_manifest(ext_id: str, *, enabled: bool = True, **overrides: object) -> dict:
    """Helper — schema-conformant manifest skeleton."""
    base = {
        "version": "v1",
        "extension_id": ext_id,
        "semver": "1.0.0",
        "origin": "CUSTOMER",
        "owner": "CUSTOMER",
        "enabled": enabled,
        "layer_contract": {"write_roots_allowlist": []},
        "entrypoints": {"ops": [], "kernel_api_actions": [], "cockpit_sections": []},
        "policies": [],
        "ui_surfaces": [],
        "compat": {"core_min": "0.0.0", "core_max": "", "notes": []},
    }
    base.update(overrides)
    return base


class TestBundledDefaults:
    def test_load_from_defaults_returns_report(self):
        reg = ExtensionRegistry()
        report = reg.load_from_defaults()
        assert isinstance(report, LoadReport)
        assert report.loaded >= 15  # 18 bundled, a few may be skipped

    def test_get_known_extension(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-KERNEL-API")
        assert ext is not None
        assert ext.extension_id == "PRJ-KERNEL-API"
        assert ext.version == "v1"
        # B3a: lossless parse — owner/ui_surfaces/compat must be populated.
        assert ext.owner in ("CORE", "CUSTOMER")
        assert isinstance(ext.ui_surfaces, list)
        assert "core_min" in ext.compat

    def test_manifest_carries_provenance(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-KERNEL-API")
        assert ext is not None
        assert ext.source == "bundled"
        assert ext.manifest_path.endswith("extension.manifest.v1.json")
        # SHA256 hex == 64 chars.
        assert len(ext.content_hash) == 64

    def test_truth_summary_exposes_runtime_backed_and_quarantined_inventory(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        summary = reg.truth_summary()
        assert summary.total_extensions >= 1
        assert summary.runtime_backed >= 2
        assert "PRJ-HELLO" in summary.runtime_backed_ids
        assert "PRJ-KERNEL-API" in summary.runtime_backed_ids
        assert summary.quarantined >= 1
        assert summary.missing_runtime_refs >= 1

    def test_kernel_api_manifest_is_minimum_runtime_backed(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-KERNEL-API")
        assert ext is not None
        assert ext.truth_tier == "runtime_backed"
        assert ext.runtime_handler_registered is True
        assert ext.remap_candidate_refs == ()
        assert ext.missing_runtime_refs == ()
        assert ext.entrypoints.get("kernel_api_actions") == [
            "system_status",
            "doc_nav_check",
        ]
        assert ext.guardrails == {"offline": True, "network_default": False}
        assert ext.policy_files == (
            "defaults/policies/policy_kernel_api_guardrails.v1.json",
        )
        for action in ("project_status", "roadmap_follow", "roadmap_finish"):
            assert action not in ext.entrypoints.get("kernel_api_actions", [])

    def test_truth_summary_pins_kernel_api_promotion_metrics(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        summary = reg.truth_summary()
        assert summary.runtime_backed == 2
        assert summary.quarantined == 17
        assert summary.runtime_backed_ids == ("PRJ-HELLO", "PRJ-KERNEL-API")

    def test_list_enabled_filters_disabled_and_blocked(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        for ext in reg.list_enabled():
            assert ext.enabled is True
            assert not ext.activation_blockers

    def test_find_by_entrypoint_airunner(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        results = reg.find_by_entrypoint("airunner-run")
        assert "PRJ-AIRUNNER" in [r.extension_id for r in results]

    def test_no_duplicate_entrypoints_in_bundled_set(self):
        """PR-C7a removed the intake_* duplicates between PRJ-KERNEL-API
        and PRJ-WORK-INTAKE; the bundled registry must now be conflict-free."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        assert reg.find_conflicts() == []

    def test_first_wins_is_deterministic(self):
        """Sorted iteration guarantees deterministic registration order, even
        when no conflicts are present — we still compare the registered
        extension IDs between two independent loads."""
        r1 = ExtensionRegistry()
        r1.load_from_defaults()
        r2 = ExtensionRegistry()
        r2.load_from_defaults()
        ids1 = sorted(r1.find_by_entrypoint("intake_create_plan") or [], key=lambda e: e.extension_id)
        ids2 = sorted(r2.find_by_entrypoint("intake_create_plan") or [], key=lambda e: e.extension_id)
        assert [e.extension_id for e in ids1] == [e.extension_id for e in ids2]

    def test_intake_actions_owned_by_work_intake(self):
        """After PR-C7a, intake_* entrypoints belong to PRJ-WORK-INTAKE alone."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        for name in ("intake_create_plan", "intake_next", "intake_status"):
            matches = reg.find_by_entrypoint(name)
            ids = [m.extension_id for m in matches]
            assert ids == ["PRJ-WORK-INTAKE"], f"{name!r} should be owned solely by PRJ-WORK-INTAKE, got {ids}"

    def test_workspace_override_reintroduces_conflict(self, tmp_path: Path):
        """Loading a workspace extension that re-adds intake_create_plan
        must trigger find_conflicts() again — proves the detector is not
        silently bypassed after PR-C7a."""
        ext_dir = tmp_path / ".ao" / "extensions" / "PRJ-CUSTOMER-INTAKE"
        ext_dir.mkdir(parents=True)
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps({
                "version": "v1",
                "extension_id": "PRJ-CUSTOMER-INTAKE",
                "semver": "0.1.0",
                "origin": "CUSTOMER",
                "owner": "CUSTOMER",
                "entrypoints": {
                    "ops": [], "kernel_api_actions": ["intake_create_plan"],
                    "cockpit_sections": [],
                },
                "layer_contract": {"write_roots_allowlist": []},
                "policies": [], "ui_surfaces": [],
                "compat": {"core_min": "0.0.0", "core_max": "", "notes": []},
            }),
            encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        reg.load_from_workspace(tmp_path)
        conflicts = reg.find_conflicts()
        entrypoints = {c.entrypoint for c in conflicts}
        assert "intake_create_plan" in entrypoints

    def test_zanzibar_openfga_manifest_valid_after_hygiene(self):
        """PR-C7a filled in semver/origin/owner/layer_contract/ui_surfaces."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        zanzibar = reg.get("PRJ-ZANZIBAR-OPENFGA")
        assert zanzibar is not None
        assert zanzibar.semver == "1.0.0"
        assert zanzibar.origin == "CORE"
        assert zanzibar.owner == "CORE"

    def test_airunner_manifest_is_quarantined_candidate(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ext = reg.get("PRJ-AIRUNNER")
        assert ext is not None
        assert ext.truth_tier == "quarantined"
        assert ext.runtime_handler_registered is False
        assert ext.remap_candidate_refs
        assert ext.missing_runtime_refs


class TestWorkspaceOverride:
    def test_load_from_workspace_reads_ao_extensions(self, tmp_path: Path):
        """B3e: workspace loader expects <project_root>/.ao/extensions/."""
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "MY-EXT"
        ext_dir.mkdir(parents=True)
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(_valid_manifest("MY-EXT")), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_root)
        assert report.loaded == 1
        ext = reg.get("MY-EXT")
        assert ext is not None
        assert ext.source == "workspace"

    def test_workspace_overrides_bundled(self, tmp_path: Path):
        """Same extension_id in workspace replaces bundled entry."""
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "PRJ-AIRUNNER"
        ext_dir.mkdir(parents=True)
        overridden = _valid_manifest("PRJ-AIRUNNER", semver="9.9.9")
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(overridden), encoding="utf-8",
        )
        reg.load_from_workspace(project_root)
        ext = reg.get("PRJ-AIRUNNER")
        assert ext is not None
        assert ext.semver == "9.9.9"
        assert ext.source == "workspace"

    def test_missing_workspace_dir_returns_zero(self, tmp_path: Path):
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(tmp_path)  # no .ao/extensions present
        assert report.loaded == 0

    def test_ref_audit_normalizes_anchor_and_dedupes_existing_targets(self, tmp_path: Path):
        docs_dir = tmp_path / "docs"
        tests_dir = tmp_path / "tests"
        docs_dir.mkdir()
        tests_dir.mkdir()
        (docs_dir / "live.md").write_text("ok", encoding="utf-8")
        (tests_dir / "contract_test.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        ext_dir = tmp_path / ".ao" / "extensions" / "REFS-NORMALIZED"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "REFS-NORMALIZED",
            docs_ref="docs/live.md#section-a",
            ai_context_refs=[
                "docs/live.md",
                "docs/live.md#section-b",
                "tests/contract_test.py",
            ],
            tests_entrypoints=[
                "tests/contract_test.py",
                "tests/contract_test.py#case-a",
            ],
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )

        reg = ExtensionRegistry()
        reg.load_from_workspace(tmp_path)
        ext = reg.get("REFS-NORMALIZED")
        assert ext is not None
        assert ext.remap_candidate_refs == ()
        assert ext.missing_runtime_refs == ()

    def test_ref_audit_dedupes_missing_targets_by_normalized_path(self, tmp_path: Path):
        ext_dir = tmp_path / ".ao" / "extensions" / "REFS-MISSING"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "REFS-MISSING",
            docs_ref="docs/missing.md#ext-refs-missing",
            ai_context_refs=[
                "docs/missing.md",
                "docs/missing.md#overview",
                "tests/missing_contract_test.py",
            ],
            tests_entrypoints=[
                "tests/missing_contract_test.py",
                "tests/missing_contract_test.py#case-a",
            ],
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )

        reg = ExtensionRegistry()
        reg.load_from_workspace(tmp_path)
        ext = reg.get("REFS-MISSING")
        assert ext is not None
        assert ext.missing_runtime_refs == (
            "docs/missing.md",
            "tests/missing_contract_test.py",
        )


class TestSchemaValidation:
    def test_invalid_manifest_is_skipped_with_report(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "BROKEN"
        ext_dir.mkdir(parents=True)
        # Missing required fields.
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps({"extension_id": "BROKEN"}), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_root)
        assert report.loaded == 0
        assert len(report.skipped) == 1
        assert "schema_invalid" in report.skipped[0]["reason"]

    def test_json_parse_error_is_skipped_with_report(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "GARBAGE"
        ext_dir.mkdir(parents=True)
        (ext_dir / "extension.manifest.v1.json").write_text("{not json")
        reg = ExtensionRegistry()
        report = reg.load_from_workspace(project_root)
        assert report.loaded == 0
        assert "json_error" in report.skipped[0]["reason"]


class TestCompatGating:
    def test_core_min_too_high_blocks_activation(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "FUTURE-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "FUTURE-EXT",
            compat={"core_min": "99.0.0", "core_max": "", "notes": []},
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root)
        ext = reg.get("FUTURE-EXT")
        assert ext is not None
        # Present in list_all, absent from list_enabled.
        assert ext.extension_id in [e.extension_id for e in reg.list_all()]
        assert ext.extension_id not in [e.extension_id for e in reg.list_enabled()]
        assert any("core_min" in b for b in ext.activation_blockers)

    def test_compat_healthy_is_enabled(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "OK-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "OK-EXT",
            compat={"core_min": "0.0.0", "core_max": "999.0.0", "notes": []},
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root)
        ext = reg.get("OK-EXT")
        assert ext is not None
        assert not ext.activation_blockers


class TestStaleRefs:
    def test_missing_ai_context_refs_flagged(self, tmp_path: Path):
        project_root = tmp_path
        ext_dir = project_root / ".ao" / "extensions" / "STALE-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "STALE-EXT",
            ai_context_refs=["nonexistent/file.md", "also-missing.txt"],
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root, refs_base=project_root)
        ext = reg.get("STALE-EXT")
        assert ext is not None
        assert "nonexistent/file.md" in ext.stale_refs
        assert "also-missing.txt" in ext.stale_refs

    def test_existing_refs_not_flagged(self, tmp_path: Path):
        project_root = tmp_path
        (project_root / "real.md").write_text("present")
        ext_dir = project_root / ".ao" / "extensions" / "FRESH-EXT"
        ext_dir.mkdir(parents=True)
        manifest = _valid_manifest(
            "FRESH-EXT",
            ai_context_refs=["real.md"],
        )
        (ext_dir / "extension.manifest.v1.json").write_text(
            json.dumps(manifest), encoding="utf-8",
        )
        reg = ExtensionRegistry()
        reg.load_from_workspace(project_root, refs_base=project_root)
        ext = reg.get("FRESH-EXT")
        assert ext is not None
        assert ext.stale_refs == ()


class TestQueries:
    def test_get_unknown_returns_none(self):
        reg = ExtensionRegistry()
        assert reg.get("NONEXISTENT") is None

    def test_list_all_is_sorted(self):
        reg = ExtensionRegistry()
        reg.load_from_defaults()
        ids = [m.extension_id for m in reg.list_all()]
        assert ids == sorted(ids)
