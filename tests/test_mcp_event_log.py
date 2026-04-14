"""Tests for ao_kernel._internal.evidence.mcp_event_log (B4).

Covers:
  - Library mode no-op
  - Daily-rotated path layout
  - Redaction of sensitive fields + secret-shaped substrings
  - Params shape projection (types only, no values)
  - Append semantics (new file, existing file, JSON parse)
  - Fail-open on disk errors
"""

from __future__ import annotations

import json
from pathlib import Path

from ao_kernel._internal.evidence.mcp_event_log import record_mcp_event


class TestLibraryModeNoop:
    def test_none_workspace_returns_false(self):
        ok = record_mcp_event(None, "ao_policy_check", {"allowed": True})
        assert ok is False

    def test_missing_workspace_dir_returns_false(self, tmp_path):
        ghost = tmp_path / "does-not-exist"
        ok = record_mcp_event(ghost, "ao_policy_check", {"allowed": True})
        assert ok is False


class TestPathLayout:
    def test_creates_daily_rotated_jsonl(self, tmp_path):
        ok = record_mcp_event(
            tmp_path,
            "ao_workspace_status",
            {"allowed": True, "decision": "allow", "api_version": "0.1.0"},
        )
        assert ok is True
        mcp_dir = tmp_path / ".ao" / "evidence" / "mcp"
        assert mcp_dir.is_dir()
        files = list(mcp_dir.glob("*.jsonl"))
        assert len(files) == 1
        # Name format YYYY-MM-DD.jsonl
        stem = files[0].stem
        assert len(stem) == 10 and stem[4] == "-" and stem[7] == "-"


class TestEventShape:
    def test_event_is_valid_json(self, tmp_path):
        envelope = {
            "allowed": True,
            "decision": "allow",
            "reason_codes": ["OK"],
            "policy_ref": "policy_x.v1.json",
            "api_version": "0.1.0",
            "data": {"nested": 1},
            "error": None,
        }
        record_mcp_event(tmp_path, "ao_policy_check", envelope, duration_ms=42)
        log_file = next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))
        lines = log_file.read_text().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["tool"] == "ao_policy_check"
        assert event["allowed"] is True
        assert event["decision"] == "allow"
        assert event["reason_codes"] == ["OK"]
        assert event["policy_ref"] == "policy_x.v1.json"
        assert event["api_version"] == "0.1.0"
        assert event["duration_ms"] == 42
        assert "ts" in event and event["ts"].endswith("Z")

    def test_data_shape_projection_is_type_only(self, tmp_path):
        envelope = {
            "allowed": True,
            "decision": "allow",
            "data": {"count": 3, "items": [1, 2, 3], "flag": True},
        }
        record_mcp_event(tmp_path, "t", envelope)
        log_file = next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))
        event = json.loads(log_file.read_text())
        # Projection: keys preserved, values replaced with type names.
        assert event["data_shape"] == {"count": "int", "items": "list", "flag": "bool"}

    def test_params_shape_is_type_only(self, tmp_path):
        # Build fake at runtime (see test_extra_redacts_sensitive_keys).
        fake_key = "sk-" + ("d" * 20)
        params = {"provider_id": "openai", "api_key": fake_key}
        record_mcp_event(tmp_path, "t", {"allowed": True}, params=params)
        log_file = next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))
        event = json.loads(log_file.read_text())
        assert event["params_shape"] == {"provider_id": "str", "api_key": "str"}
        # Raw content must not appear anywhere in the serialised event.
        assert fake_key not in log_file.read_text()


class TestRedaction:
    def test_extra_redacts_sensitive_keys(self, tmp_path):
        # Construct fake secret at runtime so the source file itself does not
        # contain a pattern the pre-commit guard would flag.
        fake_key = "sk-" + ("a" * 20)
        record_mcp_event(
            tmp_path, "t", {"allowed": True},
            extra={"api_key": fake_key, "normal_key": "visible"},
        )
        text = (next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))).read_text()
        assert fake_key not in text
        assert "***REDACTED***" in text
        assert "visible" in text  # non-sensitive keys preserved

    def test_extra_redacts_secret_shaped_substrings(self, tmp_path):
        fake_key = "sk-" + ("b" * 20)
        record_mcp_event(
            tmp_path, "t", {"allowed": True},
            extra={"note": f"leaked {fake_key} during test"},
        )
        text = (next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))).read_text()
        assert fake_key not in text
        assert "***REDACTED***" in text

    def test_nested_mapping_redacted(self, tmp_path):
        fake_token = "ghp_" + ("c" * 20)
        record_mcp_event(
            tmp_path, "t", {"allowed": True},
            extra={"auth": {"token": fake_token, "scheme": "bearer"}},
        )
        event = json.loads((next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))).read_text())
        assert event["auth"]["token"] == "***REDACTED***"
        assert event["auth"]["scheme"] == "bearer"

    def test_messages_key_redacted(self, tmp_path):
        record_mcp_event(
            tmp_path, "t", {"allowed": True},
            extra={"messages": [{"role": "user", "content": "private user text"}]},
        )
        text = (next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))).read_text()
        assert "private user text" not in text


class TestAppendSemantics:
    def test_multiple_events_append_to_same_file(self, tmp_path):
        for i in range(3):
            record_mcp_event(tmp_path, "t", {"allowed": True, "data": {"i": i}})
        log_file = next((tmp_path / ".ao" / "evidence" / "mcp").glob("*.jsonl"))
        lines = log_file.read_text().splitlines()
        assert len(lines) == 3
        # Every line is a complete JSON object (integrity check).
        for line in lines:
            json.loads(line)


class TestFailOpen:
    def test_write_failure_returns_false_and_does_not_raise(self, tmp_path, monkeypatch):
        # Force the Path.open call to blow up — simulating a readonly FS.
        original_open = Path.open

        def boom(self, *a, **k):
            if self.suffix == ".jsonl":
                raise OSError("simulated readonly")
            return original_open(self, *a, **k)

        monkeypatch.setattr(Path, "open", boom)
        ok = record_mcp_event(tmp_path, "t", {"allowed": True})
        assert ok is False
