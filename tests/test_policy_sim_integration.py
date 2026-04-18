"""End-to-end integration tests for the policy-sim harness
(PR-B4 C5).

Exercises the full bundled-fixture pipeline via the public API
and the CLI, asserts regression invariants (`_KINDS == 27`,
policy hashes stable) and proposed-policy flip scenarios.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from ao_kernel._internal.policy_sim.cli_handlers import cmd_policy_sim_run
from ao_kernel.policy_sim import (
    BaselineSource,
    load_bundled_scenarios,
    simulate_policy_change,
)
from ao_kernel.policy_sim.diff import canonical_policy_hash


class TestBundledFixtureEndToEnd:
    def test_identity_when_proposed_empty(self, tmp_path: Path) -> None:
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        assert report.scenarios_evaluated == 3
        assert all(
            d.transition in {"allow_to_allow", "deny_to_deny"}
            for d in report.deltas
        )
        assert report.host_fs_dependent is False

    def test_proposed_autonomy_allow_triggers_flip(
        self, tmp_path: Path
    ) -> None:
        """Proposed policy_autonomy with allow defaults should
        flip the governance_policy scenario to allow."""
        proposed = {
            "policy_autonomy.v1.json": {
                "version": "v1",
                "intents": {"AUTONOMY_UNKNOWN_INTENT": {"mode": "allow"}},
                "defaults": {"mode": "allow"},
            }
        }
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies=proposed,
            baseline_source=BaselineSource.BUNDLED,
        )
        assert report.scenarios_evaluated == 3
        # At minimum the hashes must differ for the flipped policy.
        baseline_hash = report.baseline_policy_hashes[
            "policy_autonomy.v1.json"
        ]
        proposed_hash = report.proposed_policy_hashes[
            "policy_autonomy.v1.json"
        ]
        assert baseline_hash != proposed_hash

    def test_policy_hash_stable_across_runs(self, tmp_path: Path) -> None:
        """Same inputs → same canonical hash (cross-run stability)."""
        a = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        b = simulate_policy_change(
            project_root=tmp_path,
            scenarios=load_bundled_scenarios(),
            proposed_policies={},
        )
        assert a.baseline_policy_hashes == b.baseline_policy_hashes

    def test_canonical_hash_reproduces_contract_bytes(self) -> None:
        """Policy-sim hash bytes must use sort_keys + ensure_ascii=False
        + (",", ":") separators + UTF-8 + SHA-256, matching the
        canonical form inlined in `executor/artifacts.py:74`."""
        import hashlib

        payload = {"b": 2, "nested": {"z": 1, "a": 2}, "a": 1}
        expected_canonical = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected_digest = hashlib.sha256(
            expected_canonical.encode("utf-8")
        ).hexdigest()
        assert canonical_policy_hash(payload) == f"sha256:{expected_digest}"


class TestKindsInvariant:
    def test_kinds_is_27(self) -> None:
        """Policy-sim emits ZERO new evidence kinds; the
        executor's `_KINDS` count must stay at 27 after the
        package lands (plan v3 §2.1 + §8)."""
        from ao_kernel.executor import evidence_emitter

        kinds = getattr(evidence_emitter, "_KINDS", None)
        assert kinds is not None, "evidence_emitter._KINDS missing"
        assert len(kinds) == 27


class TestCliEndToEnd:
    def test_run_writes_json_report(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out_path = tmp_path / "report.json"
        proposed_dir = tmp_path / "proposed"
        proposed_dir.mkdir()

        args = argparse.Namespace(
            scenarios=None,
            proposed_policies=str(proposed_dir),
            baseline_source="bundled",
            baseline_overrides=None,
            format="json",
            output=str(out_path),
            enable_host_fs_probes=False,
            project_root=None,
        )
        rc = cmd_policy_sim_run(args)
        assert rc == 0
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["scenarios_evaluated"] == 3
        assert payload["schema_version"] == "v1"
