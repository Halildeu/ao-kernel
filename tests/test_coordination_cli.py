"""Tests for ``ao-kernel coordination status`` CLI handler."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from ao_kernel._internal.coordination.cli_handlers import (
    cmd_coordination_status,
    cmd_coordination_takeover,
)
from ao_kernel.cli import main
from ao_kernel.coordination import ClaimRegistry
from ao_kernel.coordination.claim import claim_path, claim_revision


def _args(workspace: Path | None, **kwargs) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_root=(str(workspace) if workspace is not None else None),
        format=kwargs.get("format", "text"),
        output=kwargs.get("output"),
        resource_id=kwargs.get("resource_id"),
        owner_tag=kwargs.get("owner_tag"),
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


def _rewind_claim_heartbeat(
    workspace_root: Path,
    resource_id: str,
    *,
    seconds_ago: int,
) -> None:
    path = claim_path(workspace_root, resource_id)
    doc = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    doc["heartbeat_at"] = (now - timedelta(seconds=seconds_ago)).isoformat()
    doc["expires_at"] = (now - timedelta(seconds=max(seconds_ago - 90, 0))).isoformat()
    doc["revision"] = claim_revision(doc)
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")


class TestCoordinationStatusCli:
    def test_text_output_reports_disabled_workspace(
        self, tmp_path: Path, capsys
    ) -> None:
        rc = cmd_coordination_status(_args(tmp_path, format="text"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "coordination disabled" in out

    def test_json_output_writes_snapshot_file(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        output_path = tmp_path / "coordination-status.json"

        rc = cmd_coordination_status(
            _args(tmp_path, format="json", output=str(output_path))
        )

        assert rc == 0
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["status"] == "OK"
        assert payload["summary"]["by_agent"] == {"agent-alpha": 1}
        assert payload["claims"][0]["work_item_id"] == "worktree-a"


class TestCoordinationTakeoverCli:
    def test_text_output_reports_successful_takeover(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)

        rc = cmd_coordination_takeover(
            _args(
                tmp_path,
                format="text",
                resource_id="worktree-a",
                owner_tag="agent-beta",
            )
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "== coordination takeover ==" in out
        assert "Resource: worktree-a" in out
        assert "New owner: agent-beta" in out
        assert "Status: TAKEN_OVER" in out

    def test_json_output_writes_claim_payload(self, tmp_path: Path) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)
        output_path = tmp_path / "coordination-takeover.json"

        rc = cmd_coordination_takeover(
            _args(
                tmp_path,
                format="json",
                output=str(output_path),
                resource_id="worktree-a",
                owner_tag="agent-beta",
            )
        )

        assert rc == 0
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["status"] == "TAKEN_OVER"
        assert payload["resource_id"] == "worktree-a"
        assert payload["owner_tag"] == "agent-beta"
        assert payload["fencing_token"] == 1

    def test_live_claim_conflict_is_nonzero(self, tmp_path: Path, capsys) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")

        rc = cmd_coordination_takeover(
            _args(
                tmp_path,
                resource_id="worktree-a",
                owner_tag="agent-beta",
            )
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert "held by agent" in err
        assert "agent-alpha" in err

    def test_grace_claim_conflict_is_nonzero(self, tmp_path: Path, capsys) -> None:
        _write_workspace_policy(
            tmp_path,
            _enabled_policy(expiry_seconds=60, takeover_grace_period_seconds=10),
        )
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=65)

        rc = cmd_coordination_takeover(
            _args(
                tmp_path,
                resource_id="worktree-a",
                owner_tag="agent-beta",
            )
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert "takeover grace" in err

    def test_absent_claim_returns_nonzero(self, tmp_path: Path, capsys) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())

        rc = cmd_coordination_takeover(
            _args(
                tmp_path,
                resource_id="never-existed",
                owner_tag="agent-beta",
            )
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert "no claim exists" in err

    def test_main_dispatch_executes_takeover_command(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_workspace_policy(tmp_path, _enabled_policy())
        registry = ClaimRegistry(tmp_path)
        registry.acquire_claim("worktree-a", "agent-alpha")
        _rewind_claim_heartbeat(tmp_path, "worktree-a", seconds_ago=120)

        rc = main(
            [
                "--workspace-root",
                str(tmp_path),
                "coordination",
                "takeover",
                "--resource-id",
                "worktree-a",
                "--owner-tag",
                "agent-beta",
            ]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "Status: TAKEN_OVER" in out
