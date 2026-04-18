"""PR-C5: RFC 7396 JSON Merge Patch unit tests (edge-case suite).

Covers all rules documented in ``ao_kernel/policy_sim/merge_patch.py``
including the v2 type-contract narrowing (policy-doc object patch
only) and immutability invariants.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.policy_sim.merge_patch import (
    apply_merge_patch,
    load_policy_patches_from_dir,
)


class TestApplyMergePatchRules:
    def test_null_value_deletes_key(self) -> None:
        baseline = {"keep": "v", "remove": "v"}
        patch = {"remove": None}
        assert apply_merge_patch(baseline, patch) == {"keep": "v"}

    def test_nested_merge_recurses(self) -> None:
        baseline = {
            "outer": {"inner": "old", "keep": "v"},
            "sibling": "s",
        }
        patch = {"outer": {"inner": "new"}}
        assert apply_merge_patch(baseline, patch) == {
            "outer": {"inner": "new", "keep": "v"},
            "sibling": "s",
        }

    def test_absent_key_preserves_baseline(self) -> None:
        baseline = {"a": 1, "b": 2}
        patch: dict = {}
        assert apply_merge_patch(baseline, patch) == {"a": 1, "b": 2}

    def test_array_replace_not_merge(self) -> None:
        """RFC 7396: arrays are replaced, not merged."""
        baseline = {"arr": [2, 3]}
        patch = {"arr": [1]}
        assert apply_merge_patch(baseline, patch) == {"arr": [1]}

    def test_scalar_replacing_object(self) -> None:
        """Type mismatch → straight replace."""
        baseline = {"k": {"nested": "v"}}
        patch = {"k": "scalar"}
        assert apply_merge_patch(baseline, patch) == {"k": "scalar"}

    def test_object_replacing_scalar(self) -> None:
        """Mapping patch over scalar baseline → replace (baseline side
        not Mapping, so no recursion)."""
        baseline = {"k": "scalar"}
        patch = {"k": {"n": "v"}}
        assert apply_merge_patch(baseline, patch) == {"k": {"n": "v"}}

    def test_top_level_non_mapping_patch_rejected(self) -> None:
        """PR-C5 type contract: policy-doc object patch only."""
        with pytest.raises(TypeError, match="must be a Mapping"):
            apply_merge_patch({"k": "v"}, [1, 2, 3])  # type: ignore[arg-type]


class TestImmutabilityInvariants:
    def test_baseline_not_mutated(self) -> None:
        baseline = {"a": 1, "nested": {"x": "y"}}
        patch = {"a": 2, "nested": {"x": "z"}}
        baseline_snapshot = json.dumps(baseline, sort_keys=True)
        apply_merge_patch(baseline, patch)
        assert json.dumps(baseline, sort_keys=True) == baseline_snapshot

    def test_patch_not_mutated(self) -> None:
        baseline = {"a": 1}
        patch = {"a": 2, "nested": {"x": "y"}}
        patch_snapshot = json.dumps(patch, sort_keys=True)
        apply_merge_patch(baseline, patch)
        assert json.dumps(patch, sort_keys=True) == patch_snapshot


class TestLoadPoliciesPatchesFromDir:
    def test_versioned_filename_convention(
        self, tmp_path: Path,
    ) -> None:
        """PR-C5 reversible filename: <name>.v1.patch.json → <name>.v1.json."""
        patches_dir = tmp_path / "patches"
        patches_dir.mkdir()
        (patches_dir / "policy_worktree_profile.v1.patch.json").write_text(
            json.dumps({"enabled": True}),
            encoding="utf-8",
        )
        (patches_dir / "policy_secrets.v1.patch.json").write_text(
            json.dumps({"deny_by_default": False}),
            encoding="utf-8",
        )
        result = load_policy_patches_from_dir(patches_dir)
        assert result == {
            "policy_worktree_profile.v1.json": {"enabled": True},
            "policy_secrets.v1.json": {"deny_by_default": False},
        }

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_policy_patches_from_dir(tmp_path / "nonexistent")

    def test_non_object_patch_rejected(self, tmp_path: Path) -> None:
        patches_dir = tmp_path / "patches"
        patches_dir.mkdir()
        (patches_dir / "broken.v1.patch.json").write_text(
            json.dumps([1, 2, 3]),
            encoding="utf-8",
        )
        with pytest.raises(TypeError, match="must contain a JSON object"):
            load_policy_patches_from_dir(patches_dir)
