"""Tests for ``ao_kernel.metrics.policy`` — PR-B5 C1 policy loader.

Mirrors the shape of ``test_coordination_policy.py``: dormant default,
workspace override precedence, schema validation, runtime defence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from ao_kernel.metrics.errors import InvalidLabelAllowlistError
from ao_kernel.metrics.policy import (
    LabelsAdvanced,
    MetricsPolicy,
    load_metrics_policy,
)


def _valid_policy_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version": "v1",
        "enabled": False,
        "labels_advanced": {
            "enabled": False,
            "allowlist": [],
        },
    }
    base.update(overrides)
    return base


class TestLoadBundledDefault:
    def test_bundled_ships_dormant(self, tmp_path: Path) -> None:
        """PR-B5 invariant: bundled policy_metrics.v1.json ships with
        enabled=false. The export CLI relies on this for dormant-mode
        banner semantics."""
        policy = load_metrics_policy(tmp_path)
        assert policy.enabled is False

    def test_bundled_labels_advanced_disabled(self, tmp_path: Path) -> None:
        """Bundled ships labels_advanced.enabled=false + empty allowlist
        so the low-cardinality default label set is emitted even after
        an operator flips policy.enabled=true without further tuning."""
        policy = load_metrics_policy(tmp_path)
        assert policy.labels_advanced.enabled is False
        assert policy.labels_advanced.allowlist == ()


class TestWorkspaceOverride:
    @staticmethod
    def _write_override(
        workspace_root: Path, doc: dict[str, Any]
    ) -> None:
        path = (
            workspace_root
            / ".ao"
            / "policies"
            / "policy_metrics.v1.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))

    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        self._write_override(
            tmp_path,
            _valid_policy_dict(enabled=True),
        )
        policy = load_metrics_policy(tmp_path)
        assert policy.enabled is True

    def test_override_enables_advanced_labels(
        self, tmp_path: Path
    ) -> None:
        self._write_override(
            tmp_path,
            _valid_policy_dict(
                enabled=True,
                labels_advanced={
                    "enabled": True,
                    "allowlist": ["model"],
                },
            ),
        )
        policy = load_metrics_policy(tmp_path)
        assert policy.labels_advanced.enabled is True
        assert policy.labels_advanced.allowlist == ("model",)

    def test_override_missing_falls_back_to_bundled(
        self, tmp_path: Path
    ) -> None:
        """No override file → bundled default. No raise, dormant."""
        assert not (tmp_path / ".ao").exists()
        policy = load_metrics_policy(tmp_path)
        assert policy.enabled is False

    def test_override_corrupt_json_raises(self, tmp_path: Path) -> None:
        """Fail-closed: malformed JSON in override file → JSONDecodeError.
        Operators must fix the override; silent fallback to bundled is
        forbidden by CLAUDE.md §2."""
        path = (
            tmp_path
            / ".ao"
            / "policies"
            / "policy_metrics.v1.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_metrics_policy(tmp_path)


class TestSchemaValidation:
    def test_override_invalid_allowlist_enum(
        self, tmp_path: Path
    ) -> None:
        """Schema's closed enum ``{"model", "agent_id"}`` rejects typos
        at load time. Covers the canonical B0 contract the runtime
        relies on."""
        with pytest.raises(ValidationError):
            load_metrics_policy(
                tmp_path,
                override=_valid_policy_dict(
                    labels_advanced={
                        "enabled": True,
                        "allowlist": ["run_id"],  # not in enum
                    },
                ),
            )

    def test_override_missing_required_fields(
        self, tmp_path: Path
    ) -> None:
        """Missing ``enabled`` field → ValidationError (schema requires
        version + enabled + labels_advanced)."""
        bad = {"version": "v1", "labels_advanced": {"enabled": False, "allowlist": []}}
        with pytest.raises(ValidationError):
            load_metrics_policy(tmp_path, override=bad)

    def test_override_extra_top_level_key_rejected(
        self, tmp_path: Path
    ) -> None:
        """additionalProperties=false → extra key rejected."""
        with pytest.raises(ValidationError):
            load_metrics_policy(
                tmp_path,
                override=_valid_policy_dict(unknown_knob=True),
            )


class TestRuntimeDefenceInDepth:
    def test_programmatic_bypass_caught_in_from_dict(self) -> None:
        """Runtime guard: if a caller constructs a policy dict with an
        allowlist value outside the closed enum and passes it directly
        to ``_from_dict`` (bypassing schema), the loader raises
        :class:`InvalidLabelAllowlistError`. Defence in depth for
        programmatic construction paths."""
        from ao_kernel.metrics.policy import _from_dict

        bad = {
            "version": "v1",
            "enabled": True,
            "labels_advanced": {
                "enabled": True,
                "allowlist": ["provider"],  # plausible typo; not legal
            },
        }
        with pytest.raises(InvalidLabelAllowlistError):
            _from_dict(bad)

    def test_advanced_allowlist_respects_enabled_flag(self) -> None:
        """Defence-in-depth accessor: even when allowlist is non-empty,
        ``advanced_allowlist()`` returns () if labels_advanced.enabled
        is false. Callers rely on this for the "both switches must
        align" invariant."""
        policy = MetricsPolicy(
            enabled=True,
            labels_advanced=LabelsAdvanced(
                enabled=False,
                allowlist=("model",),
            ),
        )
        assert policy.advanced_allowlist() == ()

    def test_advanced_allowlist_returns_values_when_enabled(self) -> None:
        policy = MetricsPolicy(
            enabled=True,
            labels_advanced=LabelsAdvanced(
                enabled=True,
                allowlist=("model", "agent_id"),
            ),
        )
        assert policy.advanced_allowlist() == ("model", "agent_id")


class TestLoadedPolicyIsHashable:
    def test_policy_is_hashable_for_caching(
        self, tmp_path: Path
    ) -> None:
        """Registry adapter (C2) caches built metric families keyed by
        policy; the dataclass being frozen+hashable is load-bearing."""
        policy = load_metrics_policy(tmp_path)
        # Hashable objects can serve as dict keys:
        cache = {policy: "cached"}
        assert cache[policy] == "cached"
        # And hash() is stable for frozen dataclasses:
        assert hash(policy) == hash(load_metrics_policy(tmp_path))
