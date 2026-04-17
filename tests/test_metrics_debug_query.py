"""Tests for ``ao-kernel metrics debug-query`` — PR-B5 C3b.

Covers the timezone-strict ``--since`` contract (plan v4 iter-2 fix),
the --run filter, corrupt-JSONL fail-closed, and the JSON output
shape (summary + events).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from ao_kernel._internal.metrics.debug_query import (
    cmd_metrics_debug_query,
    parse_iso8601_strict,
)


def _args(workspace: Path, **kwargs) -> SimpleNamespace:
    return SimpleNamespace(
        workspace_root=str(workspace),
        since=kwargs.get("since"),
        run=kwargs.get("run"),
        output=kwargs.get("output"),
        format=kwargs.get("format", "json"),
    )


def _write_events(
    ws: Path, run_id: str, events: list[dict]
) -> None:
    path = ws / ".ao" / "evidence" / "workflows" / run_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n",
        encoding="utf-8",
    )


class TestParseIso8601Strict:
    def test_accepts_z_shorthand(self) -> None:
        parsed = parse_iso8601_strict("2026-04-17T18:00:00Z")
        # ``Z`` must become UTC (offset zero) — the strict wrapper
        # preserves whatever parse_iso8601 produces.
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0

    def test_accepts_explicit_offset(self) -> None:
        parsed = parse_iso8601_strict("2026-04-17T21:00:00+03:00")
        assert parsed.tzinfo is not None
        assert parsed.isoformat() == "2026-04-17T21:00:00+03:00"

    def test_rejects_naive_iso(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            parse_iso8601_strict("2026-04-17T18:00:00")
        assert "timezone required" in str(excinfo.value)

    def test_rejects_epoch_int(self) -> None:
        # Epoch ints aren't ISO-8601 strings — parse fails at the
        # underlying helper, strict wrapper surfaces the message.
        with pytest.raises(ValueError) as excinfo:
            parse_iso8601_strict("1713376200")
        assert "ISO-8601" in str(excinfo.value) or "timezone" in str(
            excinfo.value
        )

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError):
            parse_iso8601_strict("")


class TestHappyPath:
    def test_empty_workspace_returns_empty_events(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = cmd_metrics_debug_query(_args(tmp_path))
        assert rc == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["summary"] == {"total": 0, "by_kind": {}}
        assert payload["events"] == []

    def test_summary_counts_by_kind(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_events(
            tmp_path,
            "run-alpha",
            [
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {"violations_count": 0},
                },
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T10:01:00+00:00",
                    "payload": {"violations_count": 2},
                },
                {
                    "kind": "claim_takeover",
                    "ts": "2026-04-17T10:02:00+00:00",
                    "payload": {},
                },
            ],
        )
        rc = cmd_metrics_debug_query(_args(tmp_path))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["total"] == 3
        assert payload["summary"]["by_kind"] == {
            "claim_takeover": 1,
            "policy_checked": 2,
        }


class TestSinceFilter:
    def test_since_filters_out_earlier_events(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_events(
            tmp_path,
            "run-beta",
            [
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T09:00:00+00:00",
                    "payload": {"violations_count": 0},
                },
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T11:00:00+00:00",
                    "payload": {"violations_count": 0},
                },
            ],
        )
        since = datetime(2026, 4, 17, 10, 0, 0, tzinfo=timezone.utc)
        rc = cmd_metrics_debug_query(_args(tmp_path, since=since))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["total"] == 1


class TestRunFilter:
    def test_run_filter_scopes_events(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_events(
            tmp_path,
            "run-c1",
            [
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {},
                }
            ],
        )
        _write_events(
            tmp_path,
            "run-c2",
            [
                {
                    "kind": "policy_checked",
                    "ts": "2026-04-17T10:00:00+00:00",
                    "payload": {},
                }
            ],
        )
        rc = cmd_metrics_debug_query(_args(tmp_path, run="run-c1"))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["summary"]["total"] == 1
        assert payload["filter"]["run_id"] == "run-c1"

    def test_run_filter_unknown_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # No evidence dir at all → run filter cannot resolve → exit 1.
        rc = cmd_metrics_debug_query(_args(tmp_path, run="run-missing"))
        assert rc == 1


class TestCorruptJSONL:
    def test_corrupt_events_returns_exit_two(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        evidence_dir = (
            tmp_path / ".ao" / "evidence" / "workflows" / "run-x"
        )
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "events.jsonl").write_text(
            '{"kind": "policy_checked"}\n{ not valid\n',
            encoding="utf-8",
        )
        rc = cmd_metrics_debug_query(_args(tmp_path))
        assert rc == 2
        err = capsys.readouterr().err
        assert "corrupt evidence" in err.lower()


class TestOutputFlag:
    def test_atomic_output_writes_json(self, tmp_path: Path) -> None:
        output_path = tmp_path / "debug.json"
        rc = cmd_metrics_debug_query(
            _args(tmp_path, output=str(output_path))
        )
        assert rc == 0
        content = json.loads(output_path.read_text(encoding="utf-8"))
        assert set(content.keys()) == {"filter", "summary", "events"}
