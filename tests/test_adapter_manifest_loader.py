"""Tests for ``ao_kernel.adapters.manifest_loader``.

Covers happy-path load (cli + http fixtures), filename strict-dash
match (B6), 6-reason SkippedManifest taxonomy (W9), capability lookup
(``supports_capabilities`` + ``missing_capabilities``), and registry
lookup errors.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ao_kernel.adapters import (
    AdapterManifest,
    AdapterManifestNotFoundError,
    AdapterRegistry,
)
from ao_kernel.adapters.manifest_loader import _expected_id_from_filename


_FIXTURE_SRC = Path(__file__).parent / "fixtures" / "adapter_manifests"


def _copy_fixtures(
    dest_workspace: Path,
    names: list[str],
) -> None:
    """Copy named fixtures into ``<dest_workspace>/.ao/adapters/``."""
    adapters_dir = dest_workspace / ".ao" / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(_FIXTURE_SRC / name, adapters_dir / name)


# ---------------------------------------------------------------------------
# Filename-derived id
# ---------------------------------------------------------------------------


class TestExpectedIdFromFilename:
    def test_stem_strips_suffix(self) -> None:
        p = Path(".ao/adapters/codex-stub.manifest.v1.json")
        assert _expected_id_from_filename(p) == "codex-stub"

    def test_dashed_id_preserved(self) -> None:
        p = Path("/tmp/gh-cli-pr.manifest.v1.json")
        assert _expected_id_from_filename(p) == "gh-cli-pr"


# ---------------------------------------------------------------------------
# Empty / missing directory
# ---------------------------------------------------------------------------


class TestEmptyWorkspace:
    def test_no_adapter_dir_returns_empty_report(self, tmp_path: Path) -> None:
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert rpt.loaded == ()
        assert rpt.skipped == ()

    def test_empty_adapter_dir_returns_empty_report(self, tmp_path: Path) -> None:
        (tmp_path / ".ao" / "adapters").mkdir(parents=True)
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert rpt.loaded == ()
        assert rpt.skipped == ()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_cli_adapter_loads(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["codex-stub.manifest.v1.json"])
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert len(rpt.loaded) == 1
        assert rpt.skipped == ()
        manifest = rpt.loaded[0]
        assert isinstance(manifest, AdapterManifest)
        assert manifest.adapter_id == "codex-stub"
        assert manifest.adapter_kind == "codex-stub"
        assert "read_repo" in manifest.capabilities

    def test_http_adapter_loads(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["custom-http-example.manifest.v1.json"])
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert len(rpt.loaded) == 1
        manifest = rpt.loaded[0]
        assert manifest.invocation["transport"] == "http"

    def test_three_adapters_load(self, tmp_path: Path) -> None:
        _copy_fixtures(
            tmp_path,
            [
                "codex-stub.manifest.v1.json",
                "gh-cli-pr.manifest.v1.json",
                "claude-code-cli.manifest.v1.json",
            ],
        )
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert len(rpt.loaded) == 3
        ids = {m.adapter_id for m in rpt.loaded}
        assert ids == {"codex-stub", "gh-cli-pr", "claude-code-cli"}

    def test_list_adapters_sorted(self, tmp_path: Path) -> None:
        _copy_fixtures(
            tmp_path,
            [
                "codex-stub.manifest.v1.json",
                "gh-cli-pr.manifest.v1.json",
                "claude-code-cli.manifest.v1.json",
            ],
        )
        reg = AdapterRegistry()
        reg.load_workspace(tmp_path)
        ids = [m.adapter_id for m in reg.list_adapters()]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# SkippedManifest reason taxonomy (6 reasons, plan v2 W9)
# ---------------------------------------------------------------------------


class TestReasonTaxonomy:
    def test_adapter_id_mismatch(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["bad-id-mismatch.manifest.v1.json"])
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        assert rpt.loaded == ()
        reasons = [s.reason for s in rpt.skipped]
        assert "adapter_id_mismatch" in reasons

    def test_schema_invalid(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["bad-schema.manifest.v1.json"])
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "schema_invalid" in reasons

    def test_not_an_object(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["bad-not-object.manifest.v1.json"])
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "not_an_object" in reasons

    def test_json_decode(self, tmp_path: Path) -> None:
        adapters_dir = tmp_path / ".ao" / "adapters"
        adapters_dir.mkdir(parents=True)
        (adapters_dir / "broken.manifest.v1.json").write_text(
            "{ not json",
            encoding="utf-8",
        )
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        reasons = [s.reason for s in rpt.skipped]
        assert "json_decode" in reasons

    def test_duplicate_adapter_id_unreachable_under_strict_filename_match(self, tmp_path: Path) -> None:
        """With strict filename↔adapter_id matching, two files cannot
        share an ``adapter_id`` because filenames are unique per
        directory — any second file declaring the same id will have a
        different filename and therefore fail ``adapter_id_mismatch``
        before reaching the duplicate branch.

        The ``duplicate_adapter_id`` reason is defensive / future-proofed
        for operators who relax filename matching.
        """
        _copy_fixtures(
            tmp_path,
            [
                "bad-duplicate-alpha.manifest.v1.json",
                "bad-duplicate-beta.manifest.v1.json",
            ],
        )
        reg = AdapterRegistry()
        rpt = reg.load_workspace(tmp_path)
        # Alpha loads (filename matches its declared id). Beta is skipped
        # with adapter_id_mismatch because its filename is 'bad-duplicate-beta'
        # but the manifest declares 'bad-duplicate-alpha'.
        assert len(rpt.loaded) == 1
        assert rpt.loaded[0].adapter_id == "bad-duplicate-alpha"
        reasons = [s.reason for s in rpt.skipped]
        assert "adapter_id_mismatch" in reasons


# ---------------------------------------------------------------------------
# Lookup / capability helpers
# ---------------------------------------------------------------------------


class TestLookup:
    def test_get_returns_manifest(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["codex-stub.manifest.v1.json"])
        reg = AdapterRegistry()
        reg.load_workspace(tmp_path)
        manifest = reg.get("codex-stub")
        assert manifest.adapter_id == "codex-stub"

    def test_get_raises_for_unknown(self, tmp_path: Path) -> None:
        reg = AdapterRegistry()
        with pytest.raises(AdapterManifestNotFoundError):
            reg.get("does-not-exist")


class TestCapabilities:
    def test_supports_all(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["codex-stub.manifest.v1.json"])
        reg = AdapterRegistry()
        reg.load_workspace(tmp_path)
        assert reg.supports_capabilities("codex-stub", ["read_repo", "write_diff"])

    def test_supports_missing_returns_false(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["codex-stub.manifest.v1.json"])
        reg = AdapterRegistry()
        reg.load_workspace(tmp_path)
        assert not reg.supports_capabilities("codex-stub", ["open_pr"])

    def test_missing_capabilities_returns_gap(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["codex-stub.manifest.v1.json"])
        reg = AdapterRegistry()
        reg.load_workspace(tmp_path)
        gap = reg.missing_capabilities("codex-stub", ["read_repo", "open_pr", "run_tests"])
        assert gap == frozenset({"open_pr", "run_tests"})

    def test_missing_capabilities_empty_when_subset(self, tmp_path: Path) -> None:
        _copy_fixtures(tmp_path, ["codex-stub.manifest.v1.json"])
        reg = AdapterRegistry()
        reg.load_workspace(tmp_path)
        assert reg.missing_capabilities("codex-stub", ["read_repo"]) == frozenset()

    def test_capability_lookup_unknown_adapter_raises(self, tmp_path: Path) -> None:
        reg = AdapterRegistry()
        with pytest.raises(AdapterManifestNotFoundError):
            reg.supports_capabilities("no-such", ["read_repo"])


class TestClaudeCodeCliReviewFindingsV310A1:
    """v3.10 A1 — `claude-code-cli` review_findings capability advertise.

    Bundled manifest (`claude-code-cli.manifest.v1.json`) declares
    `review_findings` capability (version 1.1.0) plus an `output_parse`
    rule pointing at `review-findings.schema.v1.json`. This lets the
    upcoming `governed_review_claude_code_cli` workflow variant pick a
    real adapter instead of the codex-stub placeholder.

    Contract (enforced at runtime by adapter_invoker output_parse walker):
    the real `claude` CLI output MUST contain a `$.review_findings`
    array matching the schema — see A3 runbook for the prompt contract
    that the operator is expected to pass in.
    """

    def test_bundled_manifest_declares_review_findings_capability(
        self,
    ) -> None:
        reg = AdapterRegistry()
        reg.load_bundled()
        manifest = reg.get("claude-code-cli")
        assert "review_findings" in manifest.capabilities

    def test_bundled_manifest_output_parse_rule_for_review_findings(
        self,
    ) -> None:
        # The rule must point the capability at the bundled schema.
        # Walker downstream resolves schema_ref + json_path at runtime.
        reg = AdapterRegistry()
        reg.load_bundled()
        manifest = reg.get("claude-code-cli")
        assert manifest.output_parse is not None
        rules = manifest.output_parse.get("rules", [])
        assert any(
            r.get("capability") == "review_findings"
            and r.get("json_path") == "$.review_findings"
            and r.get("schema_ref") == "review-findings.schema.v1.json"
            for r in rules
        ), f"expected review_findings output_parse rule; got {rules!r}"

    def test_bundled_manifest_output_parse_schema_ref_resolves_to_bundled(
        self,
    ) -> None:
        # The schema_ref must actually resolve to the bundled schema
        # file — catches typo/rename at manifest-load time before a
        # real workflow would fail opaquely inside the output_parse
        # walker (Codex A1 post-impl expected: "manifestteki schema_ref'ler
        # bundled schema'ya resolve oluyor" pini).
        from importlib import resources as _res

        reg = AdapterRegistry()
        reg.load_bundled()
        manifest = reg.get("claude-code-cli")
        rules = manifest.output_parse.get("rules", []) if manifest.output_parse else []
        for r in rules:
            schema_ref = r.get("schema_ref", "")
            if not schema_ref:
                continue
            schema_pkg = _res.files("ao_kernel.defaults.schemas")
            with _res.as_file(schema_pkg.joinpath(schema_ref)) as sp:
                assert sp.exists(), f"schema_ref {schema_ref!r} not bundled"

    def test_bundled_manifest_version_bumped_to_1_1_0(self) -> None:
        # Capability surface widened — minor bump per SemVer.
        reg = AdapterRegistry()
        reg.load_bundled()
        manifest = reg.get("claude-code-cli")
        assert manifest.version == "1.1.0"

    def test_bundled_manifest_supports_capabilities_covers_review(
        self,
    ) -> None:
        reg = AdapterRegistry()
        reg.load_bundled()
        # Regression: existing capabilities still present + new one.
        assert reg.supports_capabilities(
            "claude-code-cli",
            ["read_repo", "write_diff", "run_tests", "stream_output", "review_findings"],
        )
