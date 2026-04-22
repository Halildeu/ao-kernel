from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.coordination import ClaimConflictError, ClaimRegistry
from ao_kernel.coordination.path_ownership import (
    acquire_path_write_claims,
    build_path_write_resource_id,
    build_path_write_scopes,
    normalize_workspace_relative_path,
    release_path_write_claims,
)


def _enabled_policy(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": "v1",
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "expiry_seconds": 90,
        "takeover_grace_period_seconds": 15,
        "max_claims_per_agent": 5,
        "claim_resource_patterns": ["*"],
        "evidence_redaction": {"patterns": []},
    }
    base.update(overrides)
    return base


def _write_workspace_policy(workspace_root: Path, doc: dict[str, object]) -> None:
    policy_dir = workspace_root / ".ao" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy_coordination_claims.v1.json").write_text(
        json.dumps(doc, sort_keys=True),
        encoding="utf-8",
    )


class TestPathNormalization:
    def test_normalize_relative_path(self, tmp_path: Path) -> None:
        assert (
            normalize_workspace_relative_path(tmp_path, Path("pkg/demo.py"))
            == "pkg/demo.py"
        )

    def test_normalize_absolute_path_under_workspace(self, tmp_path: Path) -> None:
        target = tmp_path / "pkg" / "demo.py"
        target.parent.mkdir(parents=True)
        target.write_text("print('x')\n", encoding="utf-8")

        assert normalize_workspace_relative_path(tmp_path, target) == "pkg/demo.py"

    def test_rejects_path_outside_workspace(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("x\n", encoding="utf-8")

        with pytest.raises(ValueError, match="outside project root"):
            normalize_workspace_relative_path(tmp_path, outside)


class TestScopeBuilding:
    def test_same_area_collapses_to_single_scope(self, tmp_path: Path) -> None:
        scopes = build_path_write_scopes(
            tmp_path,
            [
                "pkg/a.py",
                "pkg/sub/b.py",
                tmp_path / "pkg" / "c.py",
            ],
        )

        assert len(scopes) == 1
        assert scopes[0].area == "pkg"
        assert scopes[0].paths == ("pkg/a.py", "pkg/c.py", "pkg/sub/b.py")
        assert scopes[0].resource_id.startswith("write-area.pkg.")

    def test_multiple_areas_sorted_deterministically(self, tmp_path: Path) -> None:
        scopes = build_path_write_scopes(
            tmp_path,
            [
                "tests/test_demo.py",
                "pkg/core.py",
                "README.md",
            ],
        )

        assert [scope.area for scope in scopes] == ["README.md", "pkg", "tests"]
        assert scopes[0].paths == ("README.md",)
        assert scopes[1].paths == ("pkg/core.py",)
        assert scopes[2].paths == ("tests/test_demo.py",)

    def test_resource_id_is_deterministic_for_weird_area_names(self) -> None:
        rid_a = build_path_write_resource_id(".github")
        rid_b = build_path_write_resource_id(".github")
        rid_c = build_path_write_resource_id("docs v2")
        rid_d = build_path_write_resource_id("çalışma")

        assert rid_a == rid_b
        assert rid_a.startswith("write-area.github.")
        assert rid_c.startswith("write-area.docs_v2.")
        assert rid_d.startswith("write-area.")
        assert rid_d.isascii()
        assert rid_a != rid_c


class TestAcquireReleaseHelpers:
    def test_acquire_same_area_produces_single_claim(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)

        lease_set = acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-alpha",
            paths=["pkg/a.py", "pkg/b.py"],
        )

        assert len(lease_set.leases) == 1
        lease = lease_set.leases[0]
        assert lease.scope.area == "pkg"
        assert lease.claim.resource_id == lease.scope.resource_id

    def test_acquire_multiple_areas_claims_each_area(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)

        lease_set = acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-alpha",
            paths=["pkg/a.py", "tests/test_demo.py"],
        )

        assert [lease.scope.area for lease in lease_set.leases] == ["pkg", "tests"]
        live_claims = registry.list_agent_claims("agent-alpha")
        assert {claim.resource_id for claim in live_claims} == {
            lease.scope.resource_id for lease in lease_set.leases
        }

    def test_conflict_on_same_area_blocks_second_writer(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)

        first = acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-alpha",
            paths=["pkg/a.py"],
        )

        with pytest.raises(ClaimConflictError):
            acquire_path_write_claims(
                registry,
                tmp_path,
                owner_agent_id="agent-beta",
                paths=["pkg/other.py"],
            )

        release_path_write_claims(registry, first)

    def test_partial_conflict_rolls_back_earlier_acquired_scopes(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)

        blocked = acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-beta",
            paths=["tests/existing.py"],
        )

        with pytest.raises(ClaimConflictError):
            acquire_path_write_claims(
                registry,
                tmp_path,
                owner_agent_id="agent-alpha",
                paths=["pkg/a.py", "tests/blocked.py"],
            )

        assert registry.list_agent_claims("agent-alpha") == []
        remaining = registry.list_agent_claims("agent-beta")
        assert [claim.resource_id for claim in remaining] == [
            blocked.leases[0].scope.resource_id
        ]

    def test_release_reverses_claims_and_clears_registry(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)

        lease_set = acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-alpha",
            paths=["pkg/a.py", "tests/test_demo.py"],
        )

        release_path_write_claims(registry, lease_set)

        assert registry.list_agent_claims("agent-alpha") == []

    def test_acquire_rejects_workspace_registry_root_mismatch(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        other_root = tmp_path / "other"
        other_root.mkdir()

        with pytest.raises(ValueError, match="does not match ClaimRegistry"):
            acquire_path_write_claims(
                registry,
                other_root,
                owner_agent_id="agent-alpha",
                paths=["pkg/a.py"],
            )
