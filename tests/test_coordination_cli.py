"""Tests for ``ao-kernel coordination status`` CLI handler."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ao_kernel._internal.coordination.cli_handlers import cmd_coordination_status
from ao_kernel.coordination import ClaimRegistry


def _args(workspace: Path | None, **kwargs) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_root=(str(workspace) if workspace is not None else None),
        format=kwargs.get("format", "text"),
        output=kwargs.get("output"),
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
