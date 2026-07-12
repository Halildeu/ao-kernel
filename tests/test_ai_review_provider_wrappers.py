from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import ao_kernel.ai_review_provider_wrappers as wrappers
from ao_kernel.ai_review_provider_wrappers import extract_json_object, normalize_provider_output


ROOT = Path(__file__).resolve().parents[1]


def _review_request() -> str:
    return json.dumps(
        {
            "task": "review_high_risk_pr_change",
            "context": {
                "repository": "Halildeu/ao-kernel",
                "work_package": "AO-MA-10X",
                "changed_files": ["ao_kernel/ao_release_gate.py"],
                "round_index": 1,
            },
            "diff": "diff --git a/ao_kernel/ao_release_gate.py b/ao_kernel/ao_release_gate.py\n",
        }
    )


def _review_json(agent: str = "fake-reviewer") -> str:
    return json.dumps(
        {
            "agent": agent,
            "verdict": "AGREE",
            "checks_considered": [
                {"name": "tests", "status": "pass"},
                {"name": "secret_scan", "status": "pass"},
            ],
            "findings": ["review clean"],
        },
        sort_keys=True,
    )


def _write_executable(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)
    return path


def _run_wrapper(provider: str, *, env: dict[str, str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "ao_kernel.ai_review_provider_wrappers", provider],
        cwd=ROOT,
        input=stdin if stdin is not None else _review_request(),
        capture_output=True,
        text=True,
        check=False,
        env=merged_env,
        timeout=30,
    )


def _set_stdin(monkeypatch: pytest.MonkeyPatch, stdin: str | None = None) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin if stdin is not None else _review_request()))


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _repo_with_high_risk_change(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    target = repo / "ao_kernel" / "ao_release_gate.py"
    target.parent.mkdir(parents=True)
    target.write_text("# base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature")
    target.write_text("# base\n# high-risk provider wrapper change\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    return repo


def test_extract_json_object_accepts_fenced_provider_output() -> None:
    payload = extract_json_object("prefix\n```json\n" + _review_json() + "\n```\n", label="provider stdout")
    assert payload["agent"] == "fake-reviewer"
    assert payload["verdict"] == "AGREE"


def test_extract_json_object_rejects_output_without_json() -> None:
    with pytest.raises(ValueError, match="provider stdout did not contain a JSON object"):
        extract_json_object("plain prose only", label="provider stdout")


def test_timeout_seconds_validates_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AO_MA10_PROVIDER_TIMEOUT_SECONDS", raising=False)
    assert wrappers._timeout_seconds() == wrappers.DEFAULT_TIMEOUT_SECONDS

    monkeypatch.setenv("AO_MA10_PROVIDER_TIMEOUT_SECONDS", "7")
    assert wrappers._timeout_seconds() == 7

    monkeypatch.setenv("AO_MA10_PROVIDER_TIMEOUT_SECONDS", "not-an-int")
    with pytest.raises(ValueError, match="must be an integer"):
        wrappers._timeout_seconds()

    monkeypatch.setenv("AO_MA10_PROVIDER_TIMEOUT_SECONDS", "4")
    with pytest.raises(ValueError, match="between 5 and 900"):
        wrappers._timeout_seconds()


def test_wrapper_rejects_empty_invalid_and_non_object_stdin(tmp_path: Path) -> None:
    fake = _write_executable(tmp_path / "claude", "#!/usr/bin/env python3\nraise SystemExit(99)\n")

    empty = _run_wrapper("claude", env={"AO_MA10_CLAUDE_BIN": str(fake)}, stdin="")
    assert empty.returncode == 2
    assert "requires review request JSON" in empty.stderr

    invalid = _run_wrapper("claude", env={"AO_MA10_CLAUDE_BIN": str(fake)}, stdin="{")
    assert invalid.returncode == 2
    assert "stdin is not valid JSON" in invalid.stderr

    non_object = _run_wrapper("claude", env={"AO_MA10_CLAUDE_BIN": str(fake)}, stdin='["not", "object"]')
    assert non_object.returncode == 2
    assert "stdin must be a JSON object" in non_object.stderr


def test_normalize_provider_output_accepts_nested_reviewer_shape() -> None:
    normalized = normalize_provider_output(
        {
            "reviewer": {"agent": "nested", "verdict": "AGREE"},
            "checks_considered": [{"name": "tests", "status": "pass"}],
            "findings": ["clean"],
        },
        provider="openai",
    )
    assert normalized == {
        "agent": "nested",
        "verdict": "AGREE",
        "checks_considered": [{"name": "tests", "status": "pass"}],
        "findings": ["clean"],
    }


def test_claude_wrapper_normalizes_fenced_json(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "claude",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "assert sys.argv[1] == '-p'",
                "assert 'review_request' in sys.argv[2]",
                "print('```json')",
                f"print({json.dumps(_review_json('claude-fake'))})",
                "print('```')",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper("claude", env={"AO_MA10_CLAUDE_BIN": str(fake)})
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "claude-fake"


def test_claude_wrapper_uses_configured_cwd_and_validates_stderr(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "claude",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, os, sys",
                f"assert os.getcwd() == {json.dumps(str(tmp_path))}",
                "print('diagnostic only', file=sys.stderr)",
                f"print({json.dumps(_review_json('claude-cwd-fake'))})",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "claude",
        env={"AO_MA10_CLAUDE_BIN": str(fake), "AO_MA10_CLAUDE_CWD": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "claude-cwd-fake"


def test_claude_wrapper_reports_nonzero_provider_exit(tmp_path: Path) -> None:
    fake = _write_executable(tmp_path / "claude", "#!/usr/bin/env python3\nraise SystemExit(7)\n")
    proc = _run_wrapper("claude", env={"AO_MA10_CLAUDE_BIN": str(fake)})
    assert proc.returncode == 2
    assert "claude provider command failed with exit 7" in proc.stderr


def test_run_claude_provider_direct_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    _set_stdin(monkeypatch)
    monkeypatch.setenv("AO_MA10_CLAUDE_BIN", "fake-claude")
    monkeypatch.setenv("AO_MA10_CLAUDE_CWD", str(tmp_path))
    monkeypatch.setenv("AO_MA10_PROVIDER_TIMEOUT_SECONDS", "9")
    calls: list[tuple[list[str], str]] = []

    def fake_run(
        args: list[str],
        *,
        cwd: str,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((args, cwd))
        assert capture_output is True
        assert text is True
        assert timeout == 9
        assert check is False
        assert args[0] == "fake-claude"
        assert args[1] == "-p"
        assert "review_request" in args[2]
        return subprocess.CompletedProcess(args, 0, stdout=_review_json("claude-direct"), stderr="diagnostic only")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    assert wrappers.run_claude_provider() == 0
    assert calls == [(["fake-claude", "-p", calls[0][0][2]], str(tmp_path))]
    assert json.loads(capsys.readouterr().out)["agent"] == "claude-direct"


def test_run_claude_provider_direct_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["claude"], 7, stdout="", stderr="")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="claude provider command failed with exit 7"):
        wrappers.run_claude_provider()


def test_codex_wrapper_reads_output_last_message(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "codex",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import pathlib, sys",
                "assert sys.argv[1] == 'exec'",
                "assert '--sandbox' in sys.argv and 'read-only' in sys.argv",
                "output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])",
                f"output.write_text({json.dumps(_review_json('codex-fake'))})",
                "print('ignored noisy stdout')",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "codex",
        env={"AO_MA10_CODEX_BIN": str(fake), "AO_MA10_CODEX_REPO_ROOT": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "codex-fake"


def test_codex_wrapper_falls_back_to_stdout_and_validates_stderr(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "codex",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "assert '--output-last-message' in sys.argv",
                "print('diagnostic only', file=sys.stderr)",
                f"print({json.dumps(_review_json('codex-stdout-fake'))})",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "codex",
        env={"AO_MA10_CODEX_BIN": str(fake), "AO_MA10_CODEX_REPO_ROOT": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "codex-stdout-fake"


def test_codex_wrapper_reports_nonzero_provider_exit(tmp_path: Path) -> None:
    fake = _write_executable(tmp_path / "codex", "#!/usr/bin/env python3\nraise SystemExit(9)\n")
    proc = _run_wrapper(
        "codex",
        env={"AO_MA10_CODEX_BIN": str(fake), "AO_MA10_CODEX_REPO_ROOT": str(tmp_path)},
    )
    assert proc.returncode == 2
    assert "codex provider command failed with exit 9" in proc.stderr


def test_run_codex_provider_direct_writes_last_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _set_stdin(monkeypatch)
    monkeypatch.setenv("AO_MA10_CODEX_BIN", "fake-codex")
    monkeypatch.setenv("AO_MA10_CODEX_REPO_ROOT", str(tmp_path))

    def fake_run(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert args[:2] == ["fake-codex", "exec"]
        assert "--sandbox" in args and "read-only" in args
        assert args[args.index("--cd") + 1] == str(tmp_path)
        output = Path(args[args.index("--output-last-message") + 1])
        output.write_text(_review_json("codex-direct"), encoding="utf-8")
        assert capture_output is True
        assert text is True
        assert timeout == wrappers.DEFAULT_TIMEOUT_SECONDS
        assert check is False
        return subprocess.CompletedProcess(args, 0, stdout="ignored", stderr="diagnostic only")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    assert wrappers.run_codex_provider() == 0
    assert json.loads(capsys.readouterr().out)["agent"] == "codex-direct"


def test_run_codex_provider_direct_stdout_fallback(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _set_stdin(monkeypatch)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["codex"], 0, stdout=_review_json("codex-direct-stdout"), stderr="")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    assert wrappers.run_codex_provider() == 0
    assert json.loads(capsys.readouterr().out)["agent"] == "codex-direct-stdout"


def test_run_codex_provider_direct_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["codex"], 9, stdout="", stderr="")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="codex provider command failed with exit 9"):
        wrappers.run_codex_provider()


def test_mavis_payload_helpers_accept_supported_shapes() -> None:
    assert wrappers._messages_from_payload({"data": [{"content": "a"}]}) == [{"content": "a"}]
    assert wrappers._messages_from_payload({"items": [{"content": "b"}]}) == [{"content": "b"}]
    assert wrappers._messages_from_payload({"from_session": "mvs_a", "to_session": "mvs_b", "content": "c"}) == [
        {"from_session": "mvs_a", "to_session": "mvs_b", "content": "c"}
    ]
    assert wrappers._messages_from_payload({"messages": "not-list"}) == []
    assert wrappers._message_content({"content": {"nested": True}}) == '{"nested": true}'
    assert wrappers._message_content({"unknown": "value"}) == ""
    assert wrappers._message_created_ms({"timeCreated": "123"}) == 123
    assert wrappers._message_created_ms({"createdAtMs": "not-digits"}) == 0
    assert wrappers._message_session_value({"fromSession": "mvs_from"}, "from_session", "fromSession") == "mvs_from"
    assert wrappers._message_session_value({}, "from_session") == ""


def test_mavis_wrapper_reports_nonzero_command(tmp_path: Path) -> None:
    fake = _write_executable(tmp_path / "mavis", "#!/usr/bin/env python3\nraise SystemExit(4)\n")
    proc = _run_wrapper(
        "mavis",
        env={
            "AO_MA10_MAVIS_BIN": str(fake),
            "AO_MA10_MAVIS_POLL_SECONDS": "0.01",
        },
    )
    assert proc.returncode == 2
    assert "mavis command failed with exit 4" in proc.stderr


def test_mavis_communication_mode_requires_session_ids(tmp_path: Path) -> None:
    fake = _write_executable(tmp_path / "mavis", "#!/usr/bin/env python3\nraise SystemExit(99)\n")
    proc = _run_wrapper(
        "mavis",
        env={
            "AO_MA10_MAVIS_BIN": str(fake),
            "AO_MA10_MAVIS_MODE": "communication",
        },
    )
    assert proc.returncode == 2
    assert "FROM_SESSION_ID and AO_MA10_MAVIS_TO_SESSION_ID are required" in proc.stderr


def test_run_mavis_low_level_command_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AO_MA10_MAVIS_BIN", "fake-mavis")

    def fake_run(
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert args == ["fake-mavis", "status", "--json"]
        assert capture_output is True
        assert text is True
        assert timeout == 5
        assert check is False
        return subprocess.CompletedProcess(args, 0, stdout='{"status":"running"}', stderr="diagnostic only")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    assert wrappers._run_mavis(["status", "--json"], timeout=5) == {"status": "running"}


def test_run_mavis_low_level_command_direct_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["mavis"], 4, stdout="", stderr="")

    monkeypatch.setattr(wrappers.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="mavis command failed with exit 4"):
        wrappers._run_mavis(["status"], timeout=5)


def test_run_mavis_provider_direct_communication_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_stdin(monkeypatch)
    monkeypatch.setenv("AO_MA10_MAVIS_MODE", "communication")
    monkeypatch.setenv("AO_MA10_MAVIS_FROM_SESSION_ID", "agent-session")
    monkeypatch.setenv("AO_MA10_MAVIS_TO_SESSION_ID", "mavis-session")
    monkeypatch.setenv("AO_MA10_MAVIS_POLL_SECONDS", "0.01")
    calls: list[list[str]] = []

    def fake_run_mavis(args: list[str], *, timeout: int) -> dict[str, object]:
        calls.append(args)
        if args[:2] == ["communication", "send"]:
            return {"messageId": 1, "status": "delivered"}
        assert args[:2] == ["communication", "messages"]
        now = int(wrappers.time.time() * 1000) + 1
        return {
            "messages": [
                {
                    "from_session": "other-session",
                    "to_session": "agent-session",
                    "time_created": now,
                    "content": _review_json("wrong-session"),
                },
                {
                    "from_session": "mavis-session",
                    "to_session": "agent-session",
                    "time_created": now,
                    "content": "not json",
                },
                {
                    "from_session": "mavis-session",
                    "to_session": "agent-session",
                    "time_created": now,
                    "content": _review_json("mavis-direct-communication"),
                },
            ]
        }

    monkeypatch.setattr(wrappers, "_run_mavis", fake_run_mavis)
    assert wrappers.run_mavis_provider() == 0
    assert calls[0][:2] == ["communication", "send"]
    assert json.loads(capsys.readouterr().out)["agent"] == "mavis-direct-communication"


def test_mavis_communication_ignores_tool_call_envelopes_before_final_review(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_stdin(monkeypatch)
    monkeypatch.setenv("AO_MA10_MAVIS_MODE", "communication")
    monkeypatch.setenv("AO_MA10_MAVIS_FROM_SESSION_ID", "agent-session")
    monkeypatch.setenv("AO_MA10_MAVIS_TO_SESSION_ID", "mavis-session")
    monkeypatch.setenv("AO_MA10_MAVIS_POLL_SECONDS", "0.01")
    poll_count = 0

    def fake_run_mavis(args: list[str], *, timeout: int) -> dict[str, object]:
        nonlocal poll_count
        if args[:2] == ["communication", "send"]:
            return {"messageId": 1, "status": "delivered"}
        poll_count += 1
        now = int(wrappers.time.time() * 1000) + 1
        messages: list[dict[str, object]] = [
            {
                "from_session": "mavis-session",
                "to_session": "agent-session",
                "time_created": now,
                "tool_calls": [{"tool_name": "bash", "arguments": {"verdict": "AGREE"}}],
            },
            {
                "from_session": "mavis-session",
                "to_session": "agent-session",
                "time_created": now,
                "content": '{"event":"tool-call-complete"}',
            },
        ]
        if poll_count > 1:
            messages.append(
                {
                    "from_session": "mavis-session",
                    "to_session": "agent-session",
                    "time_created": now,
                    "content": _review_json("mavis-communication-final-review"),
                }
            )
        return {"messages": messages}

    monkeypatch.setattr(wrappers, "_run_mavis", fake_run_mavis)
    assert wrappers.run_mavis_provider() == 0
    assert poll_count == 2
    assert json.loads(capsys.readouterr().out)["agent"] == "mavis-communication-final-review"


def test_mavis_wrapper_sends_prompt_and_polls_response(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "mavis",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys, time",
                "args = sys.argv[1:]",
                "if args[:2] == ['communication', 'send']:",
                "    assert '--content' in args",
                "    print(json.dumps({'messageId': 1, 'status': 'delivered'}))",
                "elif args[:2] == ['communication', 'messages']:",
                "    print(json.dumps({'messages': [{",
                "      'from_session': 'mavis-session',",
                "      'to_session': 'agent-session',",
                "      'time_created': 1,",
                "      'content': '{\"agent\":\"stale\",\"verdict\":\"AGREE\",\"checks_considered\":[{\"name\":\"tests\",\"status\":\"pass\"},{\"name\":\"secret_scan\",\"status\":\"pass\"}],\"findings\":[\"stale\"]}'",
                "    }, {",
                "      'from_session': 'mavis-session',",
                "      'to_session': 'agent-session',",
                "      'time_created': int(time.time() * 1000) + 1,",
                f"      'content': '```json\\\\n{_review_json('mavis-fake')}\\\\n```'",
                "    }]}))",
                "else:",
                "    raise SystemExit(3)",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "mavis",
        env={
            "AO_MA10_MAVIS_BIN": str(fake),
            "AO_MA10_MAVIS_FROM_SESSION_ID": "agent-session",
            "AO_MA10_MAVIS_TO_SESSION_ID": "mavis-session",
            "AO_MA10_MAVIS_POLL_SECONDS": "0.01",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "mavis-fake"


def test_mavis_communication_filters_wrong_and_unparseable_messages(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "mavis",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys, time",
                "args = sys.argv[1:]",
                "if args[:2] == ['communication', 'send']:",
                "    print(json.dumps({'messageId': 1, 'status': 'delivered'}))",
                "elif args[:2] == ['communication', 'messages']:",
                "    now = int(time.time() * 1000) + 1",
                "    print(json.dumps({'messages': [{",
                "      'from_session': 'other-session',",
                "      'to_session': 'agent-session',",
                "      'time_created': now,",
                "      'content': '{\"agent\":\"wrong\",\"verdict\":\"AGREE\",\"checks_considered\":[{\"name\":\"tests\",\"status\":\"pass\"}],\"findings\":[\"wrong\"]}'",
                "    }, {",
                "      'from_session': 'mavis-session',",
                "      'to_session': 'agent-session',",
                "      'time_created': now,",
                "      'content': 'not json'",
                "    }, {",
                "      'from_session': 'mavis-session',",
                "      'to_session': 'agent-session',",
                "      'time_created': now,",
                f"      'content': {json.dumps(_review_json('mavis-filtered-fake'))}",
                "    }]}))",
                "else:",
                "    raise SystemExit(3)",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "mavis",
        env={
            "AO_MA10_MAVIS_BIN": str(fake),
            "AO_MA10_MAVIS_FROM_SESSION_ID": "agent-session",
            "AO_MA10_MAVIS_TO_SESSION_ID": "mavis-session",
            "AO_MA10_MAVIS_POLL_SECONDS": "0.01",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "mavis-filtered-fake"


def test_mavis_wrapper_defaults_to_new_session_mode(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "mavis",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "args = sys.argv[1:]",
                "if args[:2] == ['session', 'new']:",
                "    assert '--prompt' in args",
                "    assert '--workspace' in args",
                "    print(json.dumps({'sessionId': 'mvs_new_session_1234567890abcdef123456'}))",
                "elif args[:2] == ['session', 'messages']:",
                "    print(json.dumps({'messages': [{",
                "      'role': 'assistant',",
                "      'msg_content': " + json.dumps(_review_json("mavis-new-session-fake")),
                "    }]}))",
                "else:",
                "    raise SystemExit(3)",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "mavis",
        env={
            "AO_MA10_MAVIS_BIN": str(fake),
            "AO_MA10_MAVIS_WORKSPACE": str(tmp_path),
            "AO_MA10_MAVIS_POLL_SECONDS": "0.01",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "mavis-new-session-fake"


def test_mavis_new_session_rejects_missing_session_id(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "mavis",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "if sys.argv[1:3] == ['session', 'new']:",
                "    print(json.dumps({'sessionId': 'not-a-mavis-session'}))",
                "else:",
                "    raise SystemExit(3)",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "mavis",
        env={"AO_MA10_MAVIS_BIN": str(fake), "AO_MA10_MAVIS_POLL_SECONDS": "0.01"},
    )
    assert proc.returncode == 2
    assert "mavis session new did not return a sessionId" in proc.stderr


def test_mavis_new_session_skips_non_assistant_and_unparseable_messages(tmp_path: Path) -> None:
    fake = _write_executable(
        tmp_path / "mavis",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "args = sys.argv[1:]",
                "if args[:2] == ['session', 'new']:",
                "    print(json.dumps({'sessionId': 'mvs_new_session_abcdef1234567890abcdef'}))",
                "elif args[:2] == ['session', 'messages']:",
                "    print(json.dumps({'messages': [{",
                "      'role': 'user',",
                "      'msg_content': " + json.dumps(_review_json("mavis-user-ignored")),
                "    }, {",
                "      'role': 'assistant',",
                "      'msg_content': 'not json'",
                "    }, {",
                "      'role': 'model',",
                "      'msg_content': " + json.dumps(_review_json("mavis-model-fake")),
                "    }]}))",
                "else:",
                "    raise SystemExit(3)",
            ]
        )
        + "\n",
    )
    proc = _run_wrapper(
        "mavis",
        env={
            "AO_MA10_MAVIS_BIN": str(fake),
            "AO_MA10_MAVIS_WORKSPACE": str(tmp_path),
            "AO_MA10_MAVIS_POLL_SECONDS": "0.01",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["agent"] == "mavis-model-fake"


def test_run_mavis_provider_direct_new_session_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _set_stdin(monkeypatch)
    monkeypatch.setenv("AO_MA10_MAVIS_AGENT", "")
    monkeypatch.setenv("AO_MA10_MAVIS_TITLE", "direct-title")
    monkeypatch.setenv("AO_MA10_MAVIS_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("AO_MA10_MAVIS_POLL_SECONDS", "0.01")

    def fake_run_mavis(args: list[str], *, timeout: int) -> dict[str, object]:
        if args[:2] == ["session", "new"]:
            assert args[2] == "mavis"
            assert args[args.index("--title") + 1] == "direct-title"
            assert args[args.index("--workspace") + 1] == str(tmp_path)
            return {"sessionId": "mvs_direct_session_abcdef1234567890abcdef"}
        assert args[:2] == ["session", "messages"]
        return {
            "messages": [
                {"role": "user", "msg_content": _review_json("ignored-user")},
                {"role": "assistant", "msg_content": "not json"},
                {"role": "model", "msg_content": _review_json("mavis-direct-new-session")},
            ]
        }

    monkeypatch.setattr(wrappers, "_run_mavis", fake_run_mavis)
    assert wrappers.run_mavis_provider() == 0
    assert json.loads(capsys.readouterr().out)["agent"] == "mavis-direct-new-session"


def test_mavis_new_session_ignores_tool_call_envelopes_before_final_review(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _set_stdin(monkeypatch)
    monkeypatch.setenv("AO_MA10_MAVIS_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("AO_MA10_MAVIS_POLL_SECONDS", "0.01")
    poll_count = 0

    def fake_run_mavis(args: list[str], *, timeout: int) -> dict[str, object]:
        nonlocal poll_count
        if args[:2] == ["session", "new"]:
            return {"sessionId": "mvs_tool_call_then_final_abcdef1234567890"}
        assert args[:2] == ["session", "messages"]
        poll_count += 1
        messages: list[dict[str, object]] = [
            {
                "role": "assistant",
                "tool_calls": [{"tool_name": "bash", "arguments": {"verdict": "AGREE"}}],
            },
            {"role": "assistant", "msg_content": '{"event":"tool-call-complete"}'},
        ]
        if poll_count > 1:
            messages.append({"role": "assistant", "msg_content": _review_json("mavis-final-review")})
        return {"messages": messages}

    monkeypatch.setattr(wrappers, "_run_mavis", fake_run_mavis)
    assert wrappers.run_mavis_provider() == 0
    assert poll_count == 2
    assert json.loads(capsys.readouterr().out)["agent"] == "mavis-final-review"


def test_run_mavis_provider_direct_rejects_missing_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_stdin(monkeypatch)

    def fake_run_mavis(args: list[str], *, timeout: int) -> dict[str, object]:
        assert args[:2] == ["session", "new"]
        return {"sessionId": "not-mavis"}

    monkeypatch.setattr(wrappers, "_run_mavis", fake_run_mavis)
    with pytest.raises(ValueError, match="mavis session new did not return a sessionId"):
        wrappers.run_mavis_provider()


def test_main_returns_provider_error_direct(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert wrappers.main(["claude"]) == 2
    assert "provider-wrapper-error: provider wrapper requires review request JSON" in capsys.readouterr().err


def test_ai_review_collect_uses_productized_provider_wrapper_envs(tmp_path: Path) -> None:
    repo = _repo_with_high_risk_change(tmp_path)
    claude = _write_executable(
        tmp_path / "claude",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                f"print({json.dumps(_review_json('claude-env-wrapper'))})",
            ]
        )
        + "\n",
    )
    codex = _write_executable(
        tmp_path / "codex",
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import pathlib, sys",
                "output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])",
                f"output.write_text({json.dumps(_review_json('codex-env-wrapper'))})",
            ]
        )
        + "\n",
    )
    env = os.environ.copy()
    env.update(
        {
            "AO_MA10_CLAUDE_BIN": str(claude),
            "AO_MA10_CODEX_BIN": str(codex),
            "AO_MA10_CODEX_REPO_ROOT": str(repo),
            "AO_MA10_OPENAI_REVIEW_CMD": f"{sys.executable} -m ao_kernel.ai_review_provider_wrappers codex",
            "AO_MA10_ANTHROPIC_REVIEW_CMD": f"{sys.executable} -m ao_kernel.ai_review_provider_wrappers claude",
        }
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ao_kernel.cli",
            "ai-review",
            "collect",
            "--repository",
            "Halildeu/ao-kernel",
            "--work-package",
            "AO-MA-10X",
            "--base-ref",
            "main",
            "--head-ref",
            "feature",
            "--repo-root",
            str(repo),
            "--output-dir",
            str(tmp_path / "reviews"),
            "--implementer-provider",
            "minimax",
            "--test-command",
            "true",
            "--format",
            "json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    summary = json.loads(proc.stdout)
    assert summary["raw_review_providers"] == ["openai", "anthropic"]
