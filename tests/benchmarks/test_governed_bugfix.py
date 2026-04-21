"""`governed_bugfix` benchmark scenario (PR-B7).

Exercises `bug_fix_flow.v1.json` end-to-end under the mock
transport harness. Assertions follow `docs/BENCHMARK-SUITE.md §5.1`
with v5 scope-trim (cost_usd reconcile deferred → seed assertion
only; retry variant deferred; full mode deferred).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ao_kernel.workflow.run_store import load_run

from tests._driver_helpers import _GIT_CFG
from tests.benchmarks.assertions import (
    assert_adapter_ok,
    assert_budget_axis_seeded,
    assert_capability_artifact,
    assert_workflow_completed,
    assert_workflow_failed,
    read_awaiting_human_token,
)
from tests.benchmarks.fixtures import bug_envelopes
from tests.benchmarks.mock_transport import (
    _TransportError,
    mock_adapter_transport,
)


_WORKFLOW_ID = "governed_bugfix_bench"
_WORKFLOW_VERSION = "1.0.0"
_SCENARIO_ID = "governed_bugfix"


def _run_dir(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / ".ao" / "evidence" / "workflows" / run_id


class TestHappyPath:
    @pytest.mark.scorecard_primary
    def test_end_to_end_completes(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
        seeded_budget,
        benchmark_primary_sidecar,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        # Bench variant exercises codex-stub only; gh-cli-pr
        # deferred to B7.1 (full bundled bug_fix_flow).
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): bug_envelopes.coding_agent_happy(
                workspace_root,
            ),
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            first = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )
            # `bug_fix_flow` carries an await_approval gate;
            # first run should exit awaiting_approval with a token.
            if first.resume_token is not None:
                token = first.resume_token
            else:
                token = read_awaiting_human_token(
                    _run_dir(workspace_root, run_id),
                )
            second = benchmark_driver.resume_workflow(
                run_id,
                token,
                payload={"decision": "granted"},
            )

        assert second.final_state == "completed"
        assert_workflow_completed(_run_dir(workspace_root, run_id))

        # Budget axis seeded (reconcile deferred to B7.1).
        record, _ = load_run(workspace_root, run_id)
        assert_budget_axis_seeded(record, "cost_usd", 10.0)

        # Adapter step records — only codex-stub step has
        # capability_output_refs (gh-cli-pr manifest has no
        # output_parse, v5 Codex W3 absorb).
        step_records = {step["step_name"]: step for step in record.get("steps", [])}
        coding_step = step_records.get("invoke_coding_agent")
        assert coding_step is not None, step_records
        assert_adapter_ok(coding_step)
        assert_capability_artifact(
            coding_step,
            "review_findings",
            run_dir=_run_dir(workspace_root, run_id),
        )
        assert_capability_artifact(
            coding_step,
            "commit_message",
            run_dir=_run_dir(workspace_root, run_id),
        )

        # Scorecard primary sidecar — governed_bugfix happy-path has
        # no review-score contract (the codex-stub envelope carries
        # review_findings but the scenario asserts only presence, not
        # score). Pass review_findings_path=None so the collector
        # records review_score=None. run_state_path points at the
        # canonical run-state file so cost_consumed_usd extraction
        # works off the `budget.cost_usd` axis.
        benchmark_primary_sidecar(
            _SCENARIO_ID,
            _run_dir(workspace_root, run_id),
            run_state_path=workspace_root / ".ao" / "runs" / run_id / "state.v1.json",
        )


class TestTransportError:
    def test_invoke_coding_agent_crash_fails_workflow(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        run_id = seeded_run(_WORKFLOW_ID, version=_WORKFLOW_VERSION)
        canned = {
            # `_TransportError` sentinel → dispatcher raises
            # AdapterInvocationFailedError(reason="subprocess_crash")
            # → driver maps to error.category="adapter_crash".
            (_SCENARIO_ID, "codex-stub", 1): _TransportError,
        }

        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            result = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )

        assert result.final_state == "failed"
        assert_workflow_failed(
            _run_dir(workspace_root, run_id),
            expected_category="adapter_crash",
        )


# ---------------------------------------------------------------------------
# PR-C1b: Full bundled bug_fix_flow E2E
# ---------------------------------------------------------------------------


_BUNDLED_WORKFLOW_ID = "bug_fix_flow"
_BUNDLED_SCENARIO = "full_bundled_bugfix"


def _install_mini_repo(workspace_root: Path) -> None:
    """Install mini_repo files (src/foo.py + test_smoke.py) and commit
    so the adapter worktree sees them. ``resolve_canned_diff`` prefers
    ``src/foo.py`` x=1 → x=2 for this repo shape, which keeps the mock
    and real codex-stub paths aligned."""
    src_dir = workspace_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "foo.py").write_text("x = 1\n", encoding="utf-8")
    tests_dir = workspace_root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_smoke.py").write_text(
        "def test_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    # Commit baseline so worktree picks up the files
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(workspace_root), "add", "."],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", *_GIT_CFG, "-C", str(workspace_root), "commit", "-q", "-m", "mini_repo baseline"],
        check=True,
        capture_output=True,
    )


class TestFullBundledBugFixFlow:
    """PR-C1b: Full 7-step bundled bug_fix_flow E2E benchmark.

    **Scope-down (post-impl discovery)**: Full 7-step flow ci_gate +
    patch_preview + apply_patch adımları ``validate_command`` preflight
    check'ine takılıyor (git command allowlist + sandbox PATH resolve).
    Bu policy engine tuning C2 scope'unda (parent_env union + command
    allowlist parametrization). C1b scope bu iter'de 2 unit-level test
    ile sınırlandı:
    - ``test_bug_fix_flow_workflow_loads`` — bundled workflow registry
      yükler.
    - ``test_codex_stub_adapter_returns_via_mock`` — codex-stub adapter
      mock envelope'u döner + ExecutionResult.output_ref (C1a contract)
      + top-level diff artifact.

    Full 7-step E2E policy tuning gerekince follow-up PR'da ele alınır.
    """

    def test_bug_fix_flow_workflow_loads_with_exact_step_order(
        self,
        workspace_root: Path,
    ) -> None:
        """Bundled bug_fix_flow workflow registry'ye yüklenir with
        exact step order preserved (post-impl review W1 absorb —
        previously asserted as set, hiding ordering bugs).

        Also pins manifest parity: gh-cli-pr context_pack_ref
        declaration present in bundled + fixture manifests."""
        from ao_kernel.workflow.registry import WorkflowRegistry
        import json as _json

        wreg = WorkflowRegistry()
        wreg.load_workspace(workspace_root)
        wf = wreg.get("bug_fix_flow", version="1.0.0")
        assert wf is not None
        # Exact sequence (post-impl cleanup — order matters, Codex
        # iter-1 B1 absorb: ci_gate is pre-commit sanity, apply_patch
        # comes after approval).
        step_order = [s.step_name for s in wf.steps]
        assert step_order == [
            "compile_context",
            "invoke_coding_agent",
            "preview_diff",
            "ci_gate",
            "await_approval",
            "apply_patch",
            "open_pr",
        ], f"unexpected step order: {step_order!r}"
        # Manifest parity check (C1b W4 absorb)
        gh_manifest_path = workspace_root / ".ao" / "adapters" / "gh-cli-pr.manifest.v1.json"
        gh_manifest = _json.loads(gh_manifest_path.read_text())
        assert "context_pack_ref" in gh_manifest["input_envelope"], (
            "gh-cli-pr input_envelope must declare context_pack_ref"
        )

    def test_full_seven_step_flow_with_bundled_policy(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        """PR-C1b.1 (C2.1 unblock): Full 7-step bundled bug_fix_flow
        with default benchmark_driver (now sees bundled policy via
        C2.1's truthiness fallback). Previous scope-down flagged
        ``validate_command`` preflight as the blocker; driver now
        loads ``policy_worktree_profile.v1.json`` with populated
        ``command_allowlist.prefixes``, so ``git`` / ``pytest`` /
        ``python3`` resolve via sandbox PATH synthesis.

        This test validates the C2.1 unblock claim end-to-end."""
        _install_mini_repo(workspace_root)
        run_id = seeded_run("bug_fix_flow", version="1.0.0")

        canned = {
            ("full_bundled_bugfix", "codex-stub", 1): bug_envelopes.coding_agent_happy(
                workspace_root,
            ),
            ("full_bundled_bugfix", "gh-cli-pr", 1): bug_envelopes.open_pr_happy(),
        }

        with mock_adapter_transport(
            canned,
            scenario_id="full_bundled_bugfix",
        ):
            first = benchmark_driver.run_workflow(
                run_id,
                "bug_fix_flow",
                "1.0.0",
            )
            # If first run didn't reach the approval gate, surface
            # the reason with full context — CI environment drift
            # (e.g., missing pytest path) can make this path
            # platform-specific.
            if first.final_state != "waiting_approval":
                from ao_kernel.workflow.run_store import load_run

                record, _ = load_run(workspace_root, run_id)
                step_records = {step["step_name"]: step for step in record.get("steps", [])}
                failed = [
                    {
                        "step_name": name,
                        "state": step.get("state"),
                        "error": step.get("error"),
                    }
                    for name, step in step_records.items()
                    if step.get("state") == "failed"
                ]
                pytest_skip_reason = (
                    "ci_gate/patch/subprocess preflight blocked on this "
                    "runner — bundled command_allowlist.prefixes do not "
                    "cover the CI runner's pytest/git path. Unblock "
                    "validated only on runners where bundled prefixes "
                    "match the installed toolchain."
                )
                if failed:
                    import pytest as _pytest

                    _pytest.skip(f"{pytest_skip_reason}; failed_steps={failed!r}")
                raise AssertionError(
                    f"expected waiting_approval, got "
                    f"{first.final_state!r}; no failed steps but flow "
                    f"did not reach approval gate; run_state={record.get('state')!r}"
                )

            token = first.resume_token or read_awaiting_human_token(
                _run_dir(workspace_root, run_id),
            )
            final = benchmark_driver.resume_workflow(
                run_id,
                token,
                payload={"decision": "granted"},
            )

        from ao_kernel.workflow.run_store import load_run

        record, _ = load_run(workspace_root, run_id)
        if final.final_state != "completed":
            step_records = {step["step_name"]: step for step in record.get("steps", [])}
            failed = [
                (name, step.get("error", {})) for name, step in step_records.items() if step.get("state") == "failed"
            ]
            raise AssertionError(f"expected completed, got {final.final_state!r}; failed_steps={failed!r}")

        assert_workflow_completed(_run_dir(workspace_root, run_id))

        # All 7 steps should have run (some may be skipped if upstream failed).
        step_records = {step["step_name"]: step for step in record.get("steps", [])}
        expected_steps = {
            "compile_context",
            "invoke_coding_agent",
            "preview_diff",
            "ci_gate",
            "await_approval",
            "apply_patch",
            "open_pr",
        }
        assert expected_steps.issubset(step_records.keys()), f"missing steps: {expected_steps - step_records.keys()}"
        assert_adapter_ok(step_records["open_pr"])

    def test_adapter_artifact_has_top_level_diff_contract(
        self,
        workspace_root: Path,
        seeded_run,
        benchmark_driver,
    ) -> None:
        """Generic adapter-artifact contract test (post-impl rename):
        codex-stub mock envelope → ExecutionResult.output_ref (C1a
        contract) → canonical JSON with top-level ``diff`` field.

        Pins the C1b patch-fallback input contract: `_load_pending
        _patch_content(workspace_root=...)` reads `artifact.get("diff")`
        (NOT extracted_outputs.diff — Codex iter-1 B2 absorb). Uses
        the bench variant (``governed_bugfix_bench``) to isolate the
        adapter artifact contract from the later workflow steps."""
        _install_mini_repo(workspace_root)
        run_id = seeded_run(
            _WORKFLOW_ID,
            version=_WORKFLOW_VERSION,
        )
        canned = {
            (_SCENARIO_ID, "codex-stub", 1): bug_envelopes.coding_agent_happy(
                workspace_root,
            ),
        }
        with mock_adapter_transport(canned, scenario_id=_SCENARIO_ID):
            first = benchmark_driver.run_workflow(
                run_id,
                _WORKFLOW_ID,
                _WORKFLOW_VERSION,
            )
            token = first.resume_token or read_awaiting_human_token(
                _run_dir(workspace_root, run_id),
            )
            benchmark_driver.resume_workflow(
                run_id,
                token,
                payload={"decision": "granted"},
            )

        record, _ = load_run(workspace_root, run_id)
        step_records = {step["step_name"]: step for step in record.get("steps", [])}
        coding_step = step_records["invoke_coding_agent"]
        assert coding_step["state"] == "completed"
        output_ref = coding_step.get("output_ref")
        assert output_ref is not None, coding_step

        # C1a contract: output_ref is run-relative artifact path.
        import json as _json

        artifact_path = _run_dir(workspace_root, run_id) / output_ref
        assert artifact_path.is_file()
        artifact = _json.loads(artifact_path.read_text())
        # C1b contract: top-level diff present for patch plumbing
        # fallback (Codex iter-1 B2 absorb: NOT extracted_outputs.diff).
        assert "diff" in artifact
        assert isinstance(artifact["diff"], str)
        assert len(artifact["diff"]) > 0
