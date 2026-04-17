"""Tests for ``ao_kernel.coordination.policy`` — policy loader + matcher."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from ao_kernel.coordination.policy import (
    CoordinationPolicy,
    EvidenceRedaction,
    load_coordination_policy,
    match_resource_pattern,
)


def _valid_policy_dict(**overrides: Any) -> dict[str, Any]:
    base = {
        "version": "v1",
        "enabled": False,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 5,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    base.update(overrides)
    return base


class TestLoadBundledDefault:
    def test_bundled_ships_dormant(self, tmp_path: Path) -> None:
        """The bundled policy_coordination_claims.v1.json ships with
        enabled=false. Registry callers rely on this to enforce
        opt-in semantics (ClaimCoordinationDisabledError)."""
        policy = load_coordination_policy(tmp_path)
        assert policy.enabled is False

    def test_bundled_default_knobs(self, tmp_path: Path) -> None:
        policy = load_coordination_policy(tmp_path)
        assert policy.heartbeat_interval_seconds == 30
        assert policy.expiry_seconds == 90
        assert policy.takeover_grace_period_seconds == 15
        assert policy.max_claims_per_agent == 5
        assert policy.claim_resource_patterns == ("*",)


class TestWorkspaceOverride:
    def _write_override(self, workspace_root: Path, doc: dict[str, Any]) -> None:
        path = workspace_root / ".ao" / "policies" / "policy_coordination_claims.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))

    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        self._write_override(
            tmp_path,
            _valid_policy_dict(enabled=True, max_claims_per_agent=3),
        )
        policy = load_coordination_policy(tmp_path)
        assert policy.enabled is True
        assert policy.max_claims_per_agent == 3

    def test_override_malformed_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / ".ao" / "policies" / "policy_coordination_claims.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_coordination_policy(tmp_path)

    def test_override_schema_invalid_raises(self, tmp_path: Path) -> None:
        """Fail-closed: operator error surfaces, not silently fall back
        to the bundled dormant default."""
        doc = _valid_policy_dict()
        del doc["expiry_seconds"]  # violate required
        self._write_override(tmp_path, doc)
        with pytest.raises(ValidationError):
            load_coordination_policy(tmp_path)


class TestInlineOverride:
    def test_inline_override_bypasses_filesystem(self, tmp_path: Path) -> None:
        """Callers (tests, runtime evaluations) can pass a dict directly
        without touching .ao/policies/."""
        policy = load_coordination_policy(
            tmp_path,
            override=_valid_policy_dict(enabled=True, expiry_seconds=120),
        )
        assert policy.enabled is True
        assert policy.expiry_seconds == 120

    def test_inline_override_schema_invalid_raises(self, tmp_path: Path) -> None:
        bad = _valid_policy_dict()
        bad["max_claims_per_agent"] = -1  # schema violation (minimum: 0)
        with pytest.raises(ValidationError):
            load_coordination_policy(tmp_path, override=bad)


class TestUnlimitedQuotaSemantic:
    """B1v3: max_claims_per_agent=0 ⇒ unlimited (quota disabled).

    The registry's check is ``if limit > 0 and count >= limit: raise``.
    A policy with ``max_claims_per_agent=0`` must load successfully
    (schema minimum is 0) and the registry's own semantic layer
    interprets it as unlimited. The policy loader itself does not
    enforce that semantic; it only validates the schema."""

    def test_zero_limit_loads(self, tmp_path: Path) -> None:
        policy = load_coordination_policy(
            tmp_path,
            override=_valid_policy_dict(max_claims_per_agent=0),
        )
        assert policy.max_claims_per_agent == 0


class TestPositiveQuotaSemantic:
    def test_positive_limit_preserved(self, tmp_path: Path) -> None:
        policy = load_coordination_policy(
            tmp_path,
            override=_valid_policy_dict(max_claims_per_agent=7),
        )
        assert policy.max_claims_per_agent == 7


class TestEvidenceRedactionDataclass:
    def test_empty_redaction_defaults(self, tmp_path: Path) -> None:
        policy = load_coordination_policy(tmp_path)  # bundled dormant
        assert policy.evidence_redaction == EvidenceRedaction()

    def test_populated_redaction_roundtrip(self, tmp_path: Path) -> None:
        doc = _valid_policy_dict(evidence_redaction={
            "env_keys_matching": ["(?i).*secret.*"],
            "stdout_patterns": ["sk-[A-Za-z0-9]{20,}"],
            "file_content_patterns": [],
            "patterns": ["Bearer\\s+.+"],
        })
        policy = load_coordination_policy(tmp_path, override=doc)
        assert policy.evidence_redaction.env_keys_matching == ("(?i).*secret.*",)
        assert policy.evidence_redaction.stdout_patterns == ("sk-[A-Za-z0-9]{20,}",)
        assert policy.evidence_redaction.patterns == ("Bearer\\s+.+",)


class TestMatchResourcePattern:
    def _policy_with_patterns(self, patterns: list[str]) -> CoordinationPolicy:
        return CoordinationPolicy(
            enabled=True,
            heartbeat_interval_seconds=30,
            expiry_seconds=90,
            takeover_grace_period_seconds=15,
            max_claims_per_agent=5,
            claim_resource_patterns=tuple(patterns),
        )

    def test_wildcard_allows_all(self) -> None:
        policy = self._policy_with_patterns(["*"])
        assert match_resource_pattern(policy, "worktree-abc") is True
        assert match_resource_pattern(policy, "anything-goes") is True

    def test_prefix_match(self) -> None:
        policy = self._policy_with_patterns(["worktree-*"])
        assert match_resource_pattern(policy, "worktree-abc") is True
        assert match_resource_pattern(policy, "run-xyz") is False

    def test_multi_pattern_or_semantics(self) -> None:
        policy = self._policy_with_patterns(["worktree-*", "run-*"])
        assert match_resource_pattern(policy, "worktree-abc") is True
        assert match_resource_pattern(policy, "run-xyz") is True
        assert match_resource_pattern(policy, "evidence-1") is False

    def test_empty_pattern_list_denies_all(self) -> None:
        policy = self._policy_with_patterns([])
        assert match_resource_pattern(policy, "anything") is False

    def test_exact_match(self) -> None:
        policy = self._policy_with_patterns(["worktree-exact"])
        assert match_resource_pattern(policy, "worktree-exact") is True
        assert match_resource_pattern(policy, "worktree-exact-x") is False

    def test_case_sensitive(self) -> None:
        """fnmatch.fnmatchcase is used so patterns are case-sensitive.
        Callers who need case-insensitive matching encode the resource
        id consistently (e.g. lowercase) in the first place."""
        policy = self._policy_with_patterns(["Worktree-*"])
        assert match_resource_pattern(policy, "Worktree-A") is True
        assert match_resource_pattern(policy, "worktree-a") is False
