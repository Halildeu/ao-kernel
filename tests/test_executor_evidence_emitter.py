"""Tests for ``ao_kernel.executor.evidence_emitter``.

Covers plan v2 CNS-20260415-022 decisions:
- B3: per-run lock + monotonic ``seq`` field.
- B5: opaque ``event_id`` (not monotonic); ordering via seq.
- 17-kind taxonomy whitelist.
- Redaction at emission (env key regex + stdout patterns).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ao_kernel.executor import RedactionConfig, emit_adapter_log, emit_event


def _redaction() -> RedactionConfig:
    # Test-only synthetic pattern; avoids tripping repo secret-scan hooks
    # on a real-looking OpenAI/GitHub token literal. Production patterns
    # live in policy_worktree_profile.v1.json and are validated separately.
    return RedactionConfig(
        env_keys_matching=(re.compile(r"(?i).*(token|secret|key).*"),),
        stdout_patterns=(
            re.compile(r"FAKESEC-[A-Za-z0-9]{10,}"),
        ),
        file_content_patterns=(),
    )


class TestSeqMonotonic:
    def test_seq_starts_at_one(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000001"
        e = emit_event(
            tmp_path,
            run_id=rid,
            kind="workflow_started",
            actor="ao-kernel",
            payload={},
        )
        assert e.seq == 1

    def test_seq_increments_sequentially(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000002"
        seqs = [
            emit_event(
                tmp_path,
                run_id=rid,
                kind="workflow_started" if i == 0 else "step_started",
                actor="ao-kernel",
                payload={"i": i},
            ).seq
            for i in range(5)
        ]
        assert seqs == [1, 2, 3, 4, 5]


class TestEventIdOpaque:
    def test_event_id_unique_but_not_monotonic(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000003"
        ids = [
            emit_event(
                tmp_path,
                run_id=rid,
                kind="step_started",
                actor="ao-kernel",
                payload={"i": i},
            ).event_id
            for i in range(20)
        ]
        # All unique.
        assert len(set(ids)) == 20
        # Length at least 48 chars (token_urlsafe(48) ~ 64).
        assert all(len(i) >= 48 for i in ids)


class TestKindWhitelist:
    @pytest.mark.parametrize(
        "kind",
        [
            "workflow_started",
            "step_completed",
            "adapter_invoked",
            "approval_granted",
            "policy_denied",
        ],
    )
    def test_known_kinds_accepted(self, tmp_path: Path, kind: str) -> None:
        rid = "00000000-0000-4000-8000-000000000004"
        e = emit_event(
            tmp_path,
            run_id=rid,
            kind=kind,
            actor="ao-kernel",
            payload={},
        )
        assert e.kind == kind

    def test_unknown_kind_rejected(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000005"
        with pytest.raises(ValueError, match="Unknown evidence event kind"):
            emit_event(
                tmp_path,
                run_id=rid,
                kind="not_a_kind",
                actor="ao-kernel",
                payload={},
            )


class TestRedaction:
    def test_openai_style_secret_redacted_in_stdout(
        self, tmp_path: Path
    ) -> None:
        rid = "00000000-0000-4000-8000-000000000006"
        payload = {"msg": "leaked FAKESEC-abcdefghij token"}
        e = emit_event(
            tmp_path,
            run_id=rid,
            kind="step_started",
            actor="ao-kernel",
            payload=payload,
            redaction=_redaction(),
        )
        assert "***REDACTED***" in str(e.payload["msg"])
        assert "FAKESEC-abc" not in str(e.payload["msg"])

    def test_env_key_value_redacted(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000007"
        payload = {
            "env": {"TOKEN_KEY": "some-value", "PATH": "/bin"},
        }
        e = emit_event(
            tmp_path,
            run_id=rid,
            kind="step_started",
            actor="ao-kernel",
            payload=payload,
            redaction=_redaction(),
        )
        env_out = e.payload["env"]
        assert env_out["TOKEN_KEY"] == "***REDACTED***"
        assert env_out["PATH"] == "/bin"

    def test_adapter_log_stdout_redacted(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000008"
        log_path = emit_adapter_log(
            tmp_path,
            run_id=rid,
            adapter_id="codex-stub",
            captured_stdout="output FAKESEC-ghpabcdefij end",
            captured_stderr="",
            redaction=_redaction(),
        )
        text = log_path.read_text(encoding="utf-8")
        assert "***REDACTED***" in text
        assert "FAKESEC-ghp" not in text


class TestJSONLLayout:
    def test_events_file_is_appendable(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-000000000009"
        for i in range(3):
            emit_event(
                tmp_path,
                run_id=rid,
                kind="step_started",
                actor="ao-kernel",
                payload={"i": i},
            )
        events_path = (
            tmp_path / ".ao" / "evidence" / "workflows" / rid / "events.jsonl"
        )
        lines = events_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        records = [json.loads(line) for line in lines]
        assert [r["seq"] for r in records] == [1, 2, 3]

    def test_payload_hash_deterministic(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000000a"
        e1 = emit_event(
            tmp_path,
            run_id=rid,
            kind="step_started",
            actor="ao-kernel",
            payload={"a": 1, "b": 2},
        )
        # Same payload -> same hash.
        rid2 = "00000000-0000-4000-8000-00000000000b"
        e2 = emit_event(
            tmp_path,
            run_id=rid2,
            kind="step_started",
            actor="ao-kernel",
            payload={"b": 2, "a": 1},  # key order differs
        )
        assert e1.payload_hash == e2.payload_hash


class TestActorValidation:
    def test_unknown_actor_rejected(self, tmp_path: Path) -> None:
        rid = "00000000-0000-4000-8000-00000000000c"
        with pytest.raises(ValueError, match="Unknown evidence actor"):
            emit_event(
                tmp_path,
                run_id=rid,
                kind="step_started",
                actor="robot",
                payload={},
            )
