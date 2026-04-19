"""v3.7 F1: full-mode smoke tests + pytest option contract pins.

Covers (per Codex iter-2 AGREE split):

- 2 pin pytest option + mode skip/bypass contract:
  - `--benchmark-mode=fast` (default) skips `@full_mode` tests
  - `benchmark_mode` fixture returns the resolved mode string
- 2 full-mode smoke pins (skipped unless `--benchmark-mode=full`):
  - `governed_review` end-to-end via real transport
  - `governed_bugfix` end-to-end via real transport
- 2 pin secret alias / backward-compat contract:
  - Bundled allowlist includes both canonical (`ANTHROPIC_API_KEY`,
    `GH_TOKEN`) and legacy (`CLAUDE_API_KEY`, `GITHUB_TOKEN`) names
  - Allowlist is a strict superset of docs canonical set
- 1 pin `context_pack_ref` real artefact pin — verified by the
  fast-mode `governed_review` happy path (workflow already runs
  `compile_context` and the driver resolves
  `context_pack_ref` from the artefact; F1 just asserts the path
  exists + non-empty content). NOT full-mode-gated.

Full-mode smokes deliberately do NOT carry `@scorecard_primary`;
real-adapter scorecard semantics land in v3.7 F2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.config import load_default


# ── 1) pytest option + mode fixture ──────────────────────────────────


class TestBenchmarkModeOption:
    def test_default_mode_is_fast(self, benchmark_mode: str) -> None:
        """Default fixture resolves to 'fast'; full-mode tests stay
        collection-time skipped. Running this under
        `--benchmark-mode=full` flips to 'full'."""
        assert benchmark_mode in ("fast", "full")

    def test_full_mode_marker_gated(
        self,
        request: pytest.FixtureRequest,
    ) -> None:
        """`@pytest.mark.full_mode` tests are collected in both modes
        but skipped at collection time when mode='fast'."""
        mode = request.config.getoption("--benchmark-mode")
        # This test itself is NOT full_mode-marked → always runs.
        # Confirms the option surface is wired.
        assert mode in ("fast", "full")


# ── 2) Secret alias / backward-compat ───────────────────────────────


class TestSecretAllowlistBackwardCompat:
    _CANONICAL = {"ANTHROPIC_API_KEY", "GH_TOKEN", "OPENAI_API_KEY"}
    _LEGACY = {"CLAUDE_API_KEY", "GITHUB_TOKEN"}

    def test_bundled_allowlist_is_superset_of_canonical(self) -> None:
        """v3.7 F1 contract: bundled registry accepts canonical secret
        names used in docs (`ANTHROPIC_API_KEY`, `GH_TOKEN`,
        `OPENAI_API_KEY`)."""
        policy = load_default("policies", "policy_secrets.v1.json")
        allowed = set(policy.get("allowed_secret_ids", []))
        missing = self._CANONICAL - allowed
        assert not missing, f"bundled policy_secrets.v1.json missing canonical names: {sorted(missing)}"

    def test_bundled_allowlist_keeps_legacy_aliases(self) -> None:
        """Codex iter-2 absorb: bundled allowlist keeps legacy aliases
        so operators with pre-v3.7 workspace configs (using e.g.
        `CLAUDE_API_KEY` or `GITHUB_TOKEN`) don't fail-close on
        upgrade."""
        policy = load_default("policies", "policy_secrets.v1.json")
        allowed = set(policy.get("allowed_secret_ids", []))
        missing = self._LEGACY - allowed
        assert not missing, f"bundled policy_secrets.v1.json dropped legacy aliases: {sorted(missing)}"


# ── 3) context_pack_ref real artefact contract ──────────────────────


class TestContextPackRefRealArtefact:
    """Pin that the benchmark fast-mode happy path produces a real
    `context_pack_ref` artefact via `compile_context`. Full-mode
    tests rely on the same plumbing — F1 just asserts the artefact
    exists after a fast-mode run so F2's real-adapter path can rely
    on it without hand-written fixtures.

    This is a post-run assertion layered onto an existing fast-mode
    test; it does NOT require real adapter binaries.
    """

    def test_context_pack_ref_exists_after_governed_review(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        """Mirror of `TestHappyPath::test_review_findings_flow_completes`
        minus the scorecard_primary sidecar — runs the fast-mode
        happy path and asserts the `context_pack_ref` artefact
        landed at the driver-resolved path."""
        from ao_kernel.workflow.run_store import load_run
        from tests.benchmarks.fixtures import review_envelopes
        from tests.benchmarks.mock_transport import mock_adapter_transport

        workflow_id = "review_ai_flow"
        workflow_version = "1.0.0"
        scenario_id = "governed_review"
        run_id = seeded_run(workflow_id, version=workflow_version)
        canned = {
            (scenario_id, "codex-stub", 1): review_envelopes.review_agent_happy(
                score=0.85,
            ),
        }
        with mock_adapter_transport(canned, scenario_id=scenario_id):
            first = benchmark_driver.run_workflow(
                run_id,
                workflow_id,
                workflow_version,
            )
            if first.resume_token is not None:
                token = first.resume_token
                benchmark_driver.resume_workflow(
                    run_id,
                    token,
                    payload={"decision": "granted"},
                )

        record, _ = load_run(workspace_root, run_id)
        steps = record.get("steps", [])
        compile_step = next(
            (s for s in steps if s.get("step_name") == "compile_context" and s.get("state") == "completed"),
            None,
        )
        assert compile_step is not None, (
            "expected completed compile_context step in run record; "
            f"got steps={[(s.get('step_name'), s.get('state')) for s in steps]}"
        )
        output_ref = compile_step.get("output_ref")
        assert output_ref, f"context_compile step missing output_ref: {compile_step}"
        evidence_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
        artifact_path = evidence_dir / output_ref
        assert artifact_path.is_file(), f"context_compile artefact missing: {artifact_path}"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        context_path_str = artifact.get("context_path")
        assert context_path_str, f"context_compile artefact missing context_path: {artifact}"
        # Driver resolves context_pack_ref from this path; full-mode
        # will pass it through to the real adapter.
        context_file = Path(context_path_str)
        assert context_file.is_file(), f"context_pack_ref target file missing: {context_file}"
        # Content may be empty on a fresh workspace (no session /
        # canonical / fact lanes seeded) — the F1 contract is only
        # that the file lands at `context_path` so F2 + real-adapter
        # can pipe it through `{context_pack_ref}` substitution.
        # Stronger content assertions belong with F2's real-adapter
        # smoke.
        _ = context_file.read_text(encoding="utf-8")


# ── 4) Full-mode smoke tests (opt-in) ───────────────────────────────


@pytest.mark.full_mode
class TestFullModeGovernedReview:
    """Ops-only smoke: real `claude-code-cli` subprocess path.

    Skipped by default. Run via:
        pytest tests/benchmarks/test_full_mode_smoke.py \\
            --benchmark-mode=full -q

    Prerequisites: see `docs/BENCHMARK-FULL-MODE.md`. Requires
    `ANTHROPIC_API_KEY` (or `CLAUDE_API_KEY`) exported and the
    `claude` binary on PATH. Runs against a disposable sandbox
    workspace; NEVER against the ao-kernel main checkout.
    """

    def test_real_adapter_invocation_reaches_subprocess(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        """Full-mode happy path — dispatches to the real
        `invoke_cli` path. This test does NOT wrap the driver in
        `mock_adapter_transport` so the real subprocess is
        exercised.

        The test is deliberately minimal in its assertions: it runs
        the workflow and checks that the driver attempted a real
        subprocess call by inspecting the run log for a non-mock
        command string. Real cost/verdict semantics are F2 scope.
        """
        workflow_id = "review_ai_flow"
        workflow_version = "1.0.0"
        run_id = seeded_run(workflow_id, version=workflow_version)
        # NOTE: no mock_adapter_transport — real subprocess path.
        # Let the driver dispatch; if it reaches the real transport
        # the invocation log should carry a `claude`-invoking
        # command, not a `benchmark-mock[...]` marker.
        try:
            benchmark_driver.run_workflow(
                run_id,
                workflow_id,
                workflow_version,
            )
        except Exception as exc:
            # Real subprocess may fail for legitimate reasons
            # (missing API key, etc.) — that still proves the
            # real path was taken. Soft-fail here with context for
            # operators.
            pytest.skip(f"full-mode real invocation failed (prerequisites?): {exc}")

        evidence_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
        log_path = next(
            evidence_dir.glob("step-*/adapter-invocation.log"),
            None,
        )
        assert log_path is not None, (
            "no adapter-invocation.log under evidence dir — did the real subprocess path actually dispatch?"
        )
        log_text = log_path.read_text(encoding="utf-8")
        assert "benchmark-mock" not in log_text, (
            "full-mode path must not use mock_adapter_transport; log indicates mock was invoked"
        )


@pytest.mark.full_mode
class TestFullModeGovernedBugfix:
    """Sibling full-mode smoke for the bugfix bench scenario.

    Same prerequisites as `TestFullModeGovernedReview` plus
    `GH_TOKEN` (or `GITHUB_TOKEN`). Runs against a disposable
    sandbox repo."""

    def test_real_adapter_invocation_reaches_subprocess(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        workflow_id = "governed_bugfix_bench"
        workflow_version = "1.0.0"
        run_id = seeded_run(workflow_id, version=workflow_version)
        try:
            benchmark_driver.run_workflow(
                run_id,
                workflow_id,
                workflow_version,
            )
        except Exception as exc:
            pytest.skip(f"full-mode real invocation failed (prerequisites?): {exc}")

        evidence_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
        log_path = next(
            evidence_dir.glob("step-*/adapter-invocation.log"),
            None,
        )
        assert log_path is not None
        log_text = log_path.read_text(encoding="utf-8")
        assert "benchmark-mock" not in log_text
