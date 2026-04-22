from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from ao_kernel.coordination import ClaimRegistry
from ao_kernel.coordination.claim import claim_path
from ao_kernel.coordination.path_ownership import acquire_path_write_claims
from ao_kernel.coordination.status import (
    build_coordination_status,
    coordination_status_schema,
    render_coordination_status,
)

FIXED_NOW = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)


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


def _validate_snapshot(snapshot: dict) -> None:
    schema = coordination_status_schema()
    errors = list(Draft202012Validator(schema).iter_errors(snapshot))
    assert errors == []


class TestCoordinationStatus:
    def test_disabled_policy_returns_idle_snapshot(self, tmp_path: Path) -> None:
        snapshot = build_coordination_status(tmp_path, now=FIXED_NOW)

        _validate_snapshot(snapshot)
        assert snapshot["status"] == "IDLE"
        assert snapshot["coordination_enabled"] is False
        assert snapshot["generated_at"] == FIXED_NOW.isoformat()
        assert snapshot["claims"] == []
        assert snapshot["summary"]["total_active"] == 0
        assert snapshot["summary"]["total_reported"] == 0

    def test_enabled_empty_workspace_returns_idle_enabled_snapshot(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())

        snapshot = build_coordination_status(tmp_path, now=FIXED_NOW)

        _validate_snapshot(snapshot)
        assert snapshot["status"] == "IDLE"
        assert snapshot["coordination_enabled"] is True
        assert snapshot["generated_at"] == FIXED_NOW.isoformat()
        assert snapshot["summary"]["coordination_enabled"] is True

    def test_path_area_claims_surface_resource_kind_and_label(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        acquire_path_write_claims(
            registry,
            tmp_path,
            owner_agent_id="agent-alpha",
            paths=["pkg/a.py", "tests/test_demo.py"],
        )

        snapshot = build_coordination_status(tmp_path, now=FIXED_NOW)

        _validate_snapshot(snapshot)
        assert snapshot["status"] == "OK"
        assert snapshot["summary"]["total_active"] == 2
        assert snapshot["summary"]["by_agent"] == {"agent-alpha": 2}
        assert snapshot["summary"]["by_claim_state"]["ACTIVE"] == 2
        labels = {(item["resource_kind"], item["resource_label"]) for item in snapshot["claims"]}
        assert ("path-area", "pkg") in labels
        assert ("path-area", "tests") in labels

    def test_grace_and_takeover_ready_states_are_reported(
        self, tmp_path: Path,
    ) -> None:
        _write_workspace_policy(
            tmp_path,
            _enabled_policy(expiry_seconds=10, takeover_grace_period_seconds=5),
        )
        registry = ClaimRegistry(tmp_path)
        grace_claim = registry.acquire_claim("worktree-grace", "agent-alpha")
        ready_claim = registry.acquire_claim("worktree-ready", "agent-beta")

        grace_doc = json.loads(
            claim_path(tmp_path, grace_claim.resource_id).read_text(encoding="utf-8")
        )
        ready_doc = json.loads(
            claim_path(tmp_path, ready_claim.resource_id).read_text(encoding="utf-8")
        )
        grace_doc["heartbeat_at"] = (FIXED_NOW - timedelta(seconds=12)).isoformat()
        grace_doc["expires_at"] = (FIXED_NOW - timedelta(seconds=2)).isoformat()
        ready_doc["heartbeat_at"] = (FIXED_NOW - timedelta(seconds=20)).isoformat()
        ready_doc["expires_at"] = (FIXED_NOW - timedelta(seconds=10)).isoformat()
        from ao_kernel.coordination.claim import claim_revision

        grace_doc["revision"] = claim_revision(grace_doc)
        ready_doc["revision"] = claim_revision(ready_doc)
        claim_path(tmp_path, grace_claim.resource_id).write_text(
            json.dumps(grace_doc, sort_keys=True),
            encoding="utf-8",
        )
        claim_path(tmp_path, ready_claim.resource_id).write_text(
            json.dumps(ready_doc, sort_keys=True),
            encoding="utf-8",
        )

        snapshot = build_coordination_status(tmp_path, now=FIXED_NOW)

        _validate_snapshot(snapshot)
        by_id = {item["work_item_id"]: item for item in snapshot["claims"]}
        assert by_id["worktree-grace"]["claim_state"] == "GRACE"
        assert by_id["worktree-ready"]["claim_state"] == "TAKEOVER_READY"
        assert snapshot["summary"]["total_active"] == 1
        assert snapshot["summary"]["total_reported"] == 2
        assert snapshot["summary"]["by_claim_state"]["GRACE"] == 1
        assert snapshot["summary"]["by_claim_state"]["TAKEOVER_READY"] == 1

    def test_rendered_status_mentions_state_and_owner(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")

        rendered = render_coordination_status(
            build_coordination_status(tmp_path, now=FIXED_NOW)
        )

        assert "== coordination status ==" in rendered
        assert "owner=agent-alpha" in rendered
        assert "state=ACTIVE" in rendered
        assert "worktree-a" in rendered
