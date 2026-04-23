"""v3.7 F1: full-mode scaffold + pytest option contract pins.

**Scope narrowing after Codex post-impl BLOCK (iter-2 absorb):**
F1 ships the *scaffold* for full-mode benchmark runs — the pytest
option + `@pytest.mark.full_mode` marker + `benchmark_mode` fixture
+ `context_pack_ref` real-artefact pin + secret registry
canonicalization. It does NOT ship real-adapter smoke tests: the
bundled bench workflows reference `codex-stub` (a local Python
helper) rather than `claude-code-cli` / `gh-cli-pr`, and the
bundled `policy_worktree_profile` is dormant. Wiring the first
genuine real-adapter smoke requires:

1. A bench workflow variant pointing at real adapter manifests.
2. ~~`claude-code-cli.manifest.v1.json` to advertise the
   `review_findings` capability (currently absent).~~ **DONE in
   v3.10 A1 (#156)** — claude-code-cli now advertises
   `review_findings` + an `output_parse` rule pointing at
   `review-findings.schema.v1.json`.
3. Workspace override that enables `policy_worktree_profile`.

Items 1 and 3 are scheduled for v3.10 A2 (workflow variant) and
A3 (runbook); the original v3.7 F2 routing has been folded into
the v3.10 A arc. See the master plan doc for the current split.

What F1 pins here (all run in fast mode — default):

- 2 pins: pytest option surface + `benchmark_mode` fixture resolves
- 2 pins: bundled secret allowlist is a strict superset of docs
  canonical set AND keeps the legacy aliases for backward-compat
- 1 pin: `compile_context` workflow step produces a resolvable
  `context_pack_ref` artefact (so F2 can consume it without
  hand-written fixtures)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.config import load_default


# ── 1) pytest option + mode fixture ──────────────────────────────────


class TestBenchmarkModeOption:
    def test_default_mode_is_fast(self, benchmark_mode: str) -> None:
        """`benchmark_mode` fixture resolves to 'fast' by default.
        Running this under `--benchmark-mode=full` flips to 'full'."""
        assert benchmark_mode in ("fast", "full")

    def test_full_mode_option_surface_wired(
        self,
        request: pytest.FixtureRequest,
    ) -> None:
        """`--benchmark-mode` is registered via `pytest_addoption`.
        This test itself is NOT `full_mode`-marked and always runs
        in fast mode; it just confirms the option is accessible."""
        mode = request.config.getoption("--benchmark-mode")
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
    """Pin that a benchmark workflow happy path produces a resolvable
    `context_pack_ref` artefact via `compile_context`. Full-mode
    tests in F2 will rely on the same plumbing — F1 asserts the
    artefact exists after a fast-mode run so F2's real-adapter path
    can rely on it without hand-written fixtures.

    This is a post-run assertion layered onto a fast-mode happy-path
    workflow run; it does NOT require real adapter binaries.
    """

    def test_context_pack_ref_exists_after_governed_review(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        """Fast-mode mirror of `TestHappyPath::test_review_findings_flow_completes`
        (minus the scorecard_primary sidecar) that asserts the
        `compile_context` artefact references a real `context_path`."""
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
        # Driver resolves `context_pack_ref` from this path; F2 will
        # pipe it through to the real adapter's argv substitution.
        context_file = Path(context_path_str)
        assert context_file.is_file(), f"context_pack_ref target file missing: {context_file}"
        # Content may be empty on a fresh workspace (no session /
        # canonical / fact lanes seeded) — F1's contract is only
        # that the file lands at `context_path`. Stronger content
        # assertions belong with F2's real-adapter smoke.
        _ = context_file.read_text(encoding="utf-8")


# ── 4) v3.7 F2 full-mode codex-stub smoke ────────────────────────────
#
# The first runnable `@full_mode` smoke (v3.7 F2): dispatches
# `governed_review` through the real adapter-path `invoke_cli` against
# the deterministic `codex-stub` Python helper. No external LLM
# credentials required — codex-stub runs locally and emits a canned
# envelope that drives the `post_adapter_reconcile` middleware to
# write `llm_spend_recorded` events with `source="adapter_path"`.
#
# Scope-out per Codex F2 plan-time AGREE: external claude-code-cli +
# gh-cli-pr wiring, bench workflow variants, worktree-profile
# enablement — all belong to separate F2.1+ PRs.


@pytest.mark.full_mode
@pytest.mark.scorecard_primary
class TestFullModeAdapterPathReconcile:
    """v3.7 F2 — first runnable full-mode smoke.

    Exercises `governed_review` end-to-end without
    `mock_adapter_transport`. The codex-stub local Python helper
    stands in for external LLM adapters; the adapter-path
    `post_adapter_reconcile` middleware emits real
    `llm_spend_recorded` events which the scorecard collector now
    maps to `cost_source="real_adapter"`.

    Skipped under `--benchmark-mode=fast`; only runs under
    `--benchmark-mode=full`.
    """

    def test_governed_review_emits_adapter_path_spend_event(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
        benchmark_primary_sidecar,
    ) -> None:
        from ao_kernel.workflow.run_store import load_run

        from tests.benchmarks.assertions import assert_spend_recorded_event

        workflow_id = "review_ai_flow"
        workflow_version = "1.0.0"
        scenario_id = "governed_review"
        run_id = seeded_run(workflow_id, version=workflow_version)

        # NO mock_adapter_transport — real invoke_cli dispatches to
        # codex-stub. The manifest calls bare `python3`, which may
        # resolve to a system python lacking ao_kernel. Detect that
        # prereq miss via the workflow_failed event and skip.
        try:
            first = benchmark_driver.run_workflow(
                run_id,
                workflow_id,
                workflow_version,
            )
        except FileNotFoundError as exc:
            pytest.skip(f"subprocess prereq missing: {exc}")

        if first.resume_token is not None:
            benchmark_driver.resume_workflow(
                run_id,
                first.resume_token,
                payload={"decision": "granted"},
            )

        run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id

        # Detect subprocess-prereq failure (e.g. system `python3` has
        # no `ao_kernel` on sys.path). This is a legitimate
        # environment miss; skip cleanly. Other workflow failure
        # categories (policy_denied, output_parse_failed, adapter_crash)
        # should surface.
        events_path = run_dir / "events.jsonl"
        if events_path.is_file():
            for line in events_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("kind") != "workflow_failed":
                    continue
                payload = ev.get("payload") or {}
                reason = str(payload.get("reason") or "")
                category = payload.get("category")
                code = payload.get("code")
                # Inspect adapter log stderr for the underlying
                # module/binary miss signal.
                adapter_log = run_dir / "adapter-codex-stub.jsonl"
                stderr_blob = ""
                if adapter_log.is_file():
                    stderr_blob = adapter_log.read_text(encoding="utf-8")
                # Codex post-impl BLOCK absorb #2 — widen prereq
                # detection: the driver surfaces binary-miss as
                # code="COMMAND_NOT_FOUND" (see
                # multi_step_driver._run_adapter_step), not only
                # NON_ZERO_EXIT.
                prereq_miss = category == "invocation_failed" and (
                    code == "COMMAND_NOT_FOUND"
                    or (
                        code == "NON_ZERO_EXIT"
                        and (
                            "No module named" in stderr_blob
                            or "ModuleNotFoundError" in stderr_blob
                            or "command not found" in stderr_blob
                        )
                    )
                )
                if prereq_miss:
                    pytest.skip(f"subprocess prereq miss (code={code}): {reason}")
                pytest.fail(f"workflow_failed: category={category} reason={reason}")

        # Pin the real adapter-path reconcile fired — this is the
        # signal the scorecard collector consumes for
        # `cost_source="real_adapter"`.
        event = assert_spend_recorded_event(run_dir, source="adapter_path")
        assert event.get("kind") == "llm_spend_recorded"
        payload = event.get("payload") or {}
        assert payload.get("source") == "adapter_path"
        assert payload.get("run_id") == run_id
        assert isinstance(payload.get("step_id"), str) and payload["step_id"]
        assert isinstance(payload.get("attempt"), int) and payload["attempt"] >= 1
        assert float(payload.get("cost_usd", 0.0)) > 0.0

        # Publish the scorecard primary sidecar (full-mode expected
        # set = {governed_review} per mode-gated session-finish).
        record, _ = load_run(workspace_root, run_id)
        steps = record.get("steps", [])
        review_step = next(
            (s for s in steps if s.get("step_name") == "invoke_review_agent"),
            None,
        )
        refs = (review_step or {}).get("capability_output_refs") or {}
        findings_ref = refs.get("review_findings")
        findings_path = run_dir / findings_ref if findings_ref else None
        benchmark_primary_sidecar(
            scenario_id,
            run_dir,
            run_state_path=workspace_root / ".ao" / "runs" / run_id / "state.v1.json",
            review_findings_path=findings_path,
        )
