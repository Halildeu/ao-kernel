"""PR-C5: simulate_policy_change proposed_policy_patches integration +
CLI parser mutex behaviour.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

import pytest

from ao_kernel.policy_sim.loader import BaselineSource
from ao_kernel.policy_sim.simulator import simulate_policy_change


class TestMutexSemantics:
    def test_both_non_none_raises_value_error(
        self, tmp_path: Path,
    ) -> None:
        """v3 explicit semantic: both kwargs `is not None` → ValueError.
        ``None`` means "not provided"; ``{}`` means "provided, empty"."""
        with pytest.raises(
            ValueError, match="mutually exclusive",
        ):
            simulate_policy_change(
                project_root=tmp_path,
                scenarios=[],
                proposed_policies={},  # explicit empty
                proposed_policy_patches={"foo.v1.json": {}},  # explicit
            )

    def test_both_none_allowed(self, tmp_path: Path) -> None:
        """Neither kwarg provided → baseline-only run (existing
        behaviour contract preserved). Returns a DiffReport with
        zero scenarios evaluated."""
        report = simulate_policy_change(
            project_root=tmp_path,
            scenarios=[],
            # both kwargs omitted → baseline-only
        )
        assert report.scenarios_evaluated == 0
        assert report.baseline_policy_hashes == {}
        assert report.proposed_policy_hashes == {}


class TestProposedPolicyPatches:
    def test_patches_apply_against_baseline(
        self, tmp_path: Path,
    ) -> None:
        """Plumbing test: verify the simulator routes patches through
        ``resolve_target_policy`` + ``apply_merge_patch`` before the
        scenario loop. We provide a baseline_override for a fake
        policy name so the resolver finds it without touching
        bundled shape-validated policies."""
        from unittest.mock import patch as _mock

        patches: Mapping[str, Mapping[str, Any]] = {
            "fake_policy.v1.json": {"flag": True, "remove_me": None},
        }
        baseline_overrides: Mapping[str, Mapping[str, Any]] = {
            "fake_policy.v1.json": {
                "flag": False,
                "remove_me": "goodbye",
                "preserved": "yes",
            },
        }

        captured: dict[str, Any] = {}

        def _capture_validate(name: str, policy: Mapping[str, Any]) -> None:
            captured[name] = dict(policy)

        # Bypass shape validation (we're testing the merge plumbing,
        # not the shape registry).
        with _mock(
            "ao_kernel.policy_sim.simulator.validate_proposed_policy",
            _capture_validate,
        ):
            simulate_policy_change(
                project_root=tmp_path,
                scenarios=[],
                proposed_policy_patches=patches,
                baseline_source=BaselineSource.EXPLICIT,
                baseline_overrides=baseline_overrides,
            )

        # Effective proposed dict reflects merged result:
        # - flag flipped False → True (patch wins)
        # - remove_me deleted (patch None)
        # - preserved kept (not in patch)
        assert captured == {
            "fake_policy.v1.json": {
                "flag": True,
                "preserved": "yes",
            },
        }

    def test_unknown_policy_patch_fails_fast(
        self, tmp_path: Path,
    ) -> None:
        """PR-C5 v3: fail-fast on unknown policy filename (typo
        protection). resolve_target_policy raises
        TargetPolicyNotFoundError when no bundled default nor
        workspace override exists."""
        from ao_kernel.policy_sim.errors import TargetPolicyNotFoundError

        patches: Mapping[str, Mapping[str, Any]] = {
            "nonexistent_policy.v1.json": {"anything": 1},
        }
        with pytest.raises(TargetPolicyNotFoundError):
            simulate_policy_change(
                project_root=tmp_path,
                scenarios=[],
                proposed_policy_patches=patches,
                baseline_source=BaselineSource.BUNDLED,
            )


class TestCliParserMutex:
    """Parser-level tests: argparse's mutually_exclusive_group
    rejects conflicting / missing flag combinations before the
    handler runs."""

    def _build_parser(self) -> argparse.ArgumentParser:
        from ao_kernel.cli import _build_parser

        return _build_parser()

    def test_both_flags_triggers_system_exit(
        self, tmp_path: Path,
    ) -> None:
        parser = self._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "policy-sim", "run",
                "--proposed-policies", str(tmp_path),
                "--proposed-patches", str(tmp_path),
            ])

    def test_neither_flag_triggers_system_exit(self) -> None:
        parser = self._build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["policy-sim", "run"])

    def test_only_policies_flag_accepted(self, tmp_path: Path) -> None:
        parser = self._build_parser()
        args = parser.parse_args([
            "policy-sim", "run",
            "--proposed-policies", str(tmp_path),
        ])
        assert args.proposed_policies == str(tmp_path)
        assert args.proposed_patches is None

    def test_only_patches_flag_accepted(self, tmp_path: Path) -> None:
        parser = self._build_parser()
        args = parser.parse_args([
            "policy-sim", "run",
            "--proposed-patches", str(tmp_path),
        ])
        assert args.proposed_patches == str(tmp_path)
        assert args.proposed_policies is None
