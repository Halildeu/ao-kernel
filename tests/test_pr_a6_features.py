"""Tests for PR-A6 features: bundled adapters, llm_fallback, gh_pr_stub."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.adapters import AdapterRegistry


class TestBundledAdapters:
    def test_load_bundled_discovers_three_manifests(self) -> None:
        reg = AdapterRegistry()
        report = reg.load_bundled()
        ids = {m.adapter_id for m in report.loaded}
        assert "codex-stub" in ids
        assert "claude-code-cli" in ids
        assert "gh-cli-pr" in ids

    def test_workspace_overrides_bundled(self, tmp_path: Path) -> None:
        reg = AdapterRegistry()
        reg.load_bundled()
        # Create workspace override with same adapter_id but different display_name
        # Read bundled codex-stub, modify version to prove override
        from importlib import resources as _res

        bundled_pkg = _res.files("ao_kernel.defaults.adapters")
        with _res.as_file(bundled_pkg.joinpath("codex-stub.manifest.v1.json")) as bp:
            override = json.loads(bp.read_text(encoding="utf-8"))
        override["version"] = "99.0.0"
        adapters_dir = tmp_path / ".ao" / "adapters"
        adapters_dir.mkdir(parents=True)
        (adapters_dir / "codex-stub.manifest.v1.json").write_text(
            json.dumps(override, indent=2),
        )
        reg.load_workspace(tmp_path)
        manifest = reg.get("codex-stub")
        assert manifest.version == "99.0.0"  # overridden

    def test_bundled_load_idempotent(self) -> None:
        reg = AdapterRegistry()
        r1 = reg.load_bundled()
        r2 = reg.load_bundled()
        assert len(r1.loaded) == len(r2.loaded) + len(r2.skipped)


class TestGhPrStub:
    def test_gh_pr_stub_runs_and_outputs_json(self) -> None:
        from ao_kernel.fixtures.gh_pr_stub import main
        import io
        import sys

        old_stdout = sys.stdout
        sys.stdout = buf = io.StringIO()
        try:
            exit_code = main(["--run-id", "test-123"])
        finally:
            sys.stdout = old_stdout
        assert exit_code == 0
        output = json.loads(buf.getvalue())
        assert output["status"] == "ok"
        assert "pr_url" in output
        assert output["finish_reason"] == "normal"


class TestLlmFallback:
    def test_llm_fallback_without_llm_extra_raises_classification_error(self) -> None:
        """When [llm] extra is not installed, llm_fallback raises
        IntentClassificationError with reason llm_extra_missing."""
        from ao_kernel.workflow.errors import IntentClassificationError
        from ao_kernel.workflow.intent_router import IntentRouter, IntentRule

        rule = IntentRule(
            rule_id="r1",
            priority=1,
            match_type="keyword",
            keywords=("impossible_match_xyz",),
            regex_any=(),
            workflow_id="bug_fix_flow",
            workflow_version=None,
            confidence=1.0,
            description="test rule",
        )
        router = IntentRouter(
            rules=[rule],
            fallback_strategy="llm_fallback",
        )
        with pytest.raises(IntentClassificationError) as exc_info:
            router.classify("something that does not match any rule")
        assert exc_info.value.reason in ("llm_extra_missing", "llm_transport_error")


class TestVersionBump:
    def test_version_is_3_6_0(self) -> None:
        import ao_kernel

        assert ao_kernel.__version__ == "3.6.0"

    def test_pyproject_version_matches(self) -> None:
        import tomllib

        pyproject = Path("pyproject.toml")
        if not pyproject.exists():
            pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["version"] == "3.6.0"


class TestMetaExtras:
    def test_coding_extra_defined(self) -> None:
        import tomllib

        pyproject = Path("pyproject.toml")
        if not pyproject.exists():
            pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        assert "coding" in data["project"]["optional-dependencies"]
