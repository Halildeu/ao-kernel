"""Provider command wrappers for ``ao-kernel ai-review``.

The ai-review collector intentionally treats provider commands as an external
trust boundary: commands receive a no-secret JSON review request on stdin and
must return a small review JSON object on stdout. This module provides
repo-owned wrappers for local Claude, Codex, and Mavis/MiniMax runtimes so
operators do not have to hand-roll shell snippets for each environment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence, cast

from ao_kernel.ai_review import (
    _agent_from_output,
    _checks_from_output,
    _findings_from_output,
    _verdict_from_output,
    assert_no_secret_like_text,
)

ALLOWED_VERDICTS = {"AGREE", "REVISE", "BLOCK", "PARTIAL", "RED"}
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MAVIS_BIN = "mavis"


def _timeout_seconds() -> int:
    raw = os.environ.get("AO_MA10_PROVIDER_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("AO_MA10_PROVIDER_TIMEOUT_SECONDS must be an integer") from exc
    if value < 5 or value > 900:
        raise ValueError("AO_MA10_PROVIDER_TIMEOUT_SECONDS must be between 5 and 900")
    return value


def _json_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["agent", "verdict", "checks_considered", "findings"],
        "properties": {
            "agent": {"type": "string", "minLength": 1},
            "verdict": {"type": "string", "enum": sorted(ALLOWED_VERDICTS)},
            "checks_considered": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "status"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "status": {"type": "string", "enum": ["pass", "fail"]},
                    },
                },
            },
            "findings": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        },
    }


def _load_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("provider wrapper requires review request JSON on stdin")
    assert_no_secret_like_text(raw, label="provider wrapper stdin")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("provider wrapper stdin is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("provider wrapper stdin must be a JSON object")
    return cast(dict[str, Any], payload)


def _prompt_for_provider(request: dict[str, Any], *, provider_name: str) -> str:
    prompt = {
        "role": f"{provider_name} independent high-risk PR reviewer",
        "instructions": [
            "Review the request JSON as an independent reviewer.",
            "Treat review_request as the authority; do not rely on ambient working-directory state.",
            "Return exactly one JSON object and no prose.",
            "Use AGREE only when the context-bound preflight evidence records tests and secret_scan as pass, and scope, drift, and forbidden-action checks are clean.",
            "When preflight evidence passes, include checks named exactly tests and secret_scan with status pass.",
            "Use REVISE or BLOCK when any issue remains.",
            "Do not include secret values in findings.",
            "AI output is evidence only; release authority remains ao-release-gate plus GitHub ruleset.",
        ],
        "required_output": _json_output_schema(),
        "review_request": request,
    }
    rendered = json.dumps(prompt, indent=2, sort_keys=True)
    assert_no_secret_like_text(rendered, label=f"{provider_name} provider prompt")
    return rendered


def _candidate_texts(text: str) -> list[str]:
    candidates = [text.strip()]
    for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE):
        candidates.insert(0, match.group(1).strip())
    return [candidate for candidate in candidates if candidate]


def extract_json_object(text: str, *, label: str) -> dict[str, Any]:
    assert_no_secret_like_text(text, label=label)
    decoder = json.JSONDecoder()
    for candidate in _candidate_texts(text):
        stripped = candidate.strip()
        if not stripped:
            continue
        if stripped.startswith("{"):
            try:
                payload, index = decoder.raw_decode(stripped)
            except json.JSONDecodeError:
                payload = None
            else:
                if isinstance(payload, dict) and not stripped[index:].strip():
                    return cast(dict[str, Any], payload)
        for start, char in enumerate(stripped):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(stripped[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload)
    raise ValueError(f"{label} did not contain a JSON object")


def normalize_provider_output(payload: dict[str, Any], *, provider: str) -> dict[str, Any]:
    normalized = {
        "agent": _agent_from_output(payload, provider),
        "verdict": _verdict_from_output(payload, provider),
        "checks_considered": _checks_from_output(payload, provider),
        "findings": _findings_from_output(payload, provider),
    }
    rendered = json.dumps(normalized, sort_keys=True)
    assert_no_secret_like_text(rendered, label=f"{provider} normalized provider output")
    return normalized


def _emit(payload: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    return 0


def _provider_error(message: str) -> int:
    sys.stderr.write(f"provider-wrapper-error: {message}\n")
    return 2


def run_claude_provider() -> int:
    request = _load_request()
    prompt = _prompt_for_provider(request, provider_name="Claude")
    claude_bin = os.environ.get("AO_MA10_CLAUDE_BIN", "claude")
    timeout = _timeout_seconds()
    configured_cwd = os.environ.get("AO_MA10_CLAUDE_CWD", "").strip()
    if configured_cwd:
        cwd_context: tempfile.TemporaryDirectory[str] | None = None
        cwd = configured_cwd
    else:
        cwd_context = tempfile.TemporaryDirectory(prefix="ao-kernel-claude-review-")
        cwd = cwd_context.name
    try:
        proc = subprocess.run(
            [claude_bin, "-p", prompt],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    finally:
        if cwd_context is not None:
            cwd_context.cleanup()
    if proc.stderr.strip():
        assert_no_secret_like_text(proc.stderr, label="claude provider stderr")
    if proc.returncode != 0:
        raise RuntimeError(f"claude provider command failed with exit {proc.returncode}")
    payload = extract_json_object(proc.stdout, label="claude provider stdout")
    return _emit(normalize_provider_output(payload, provider="anthropic"))


def run_codex_provider() -> int:
    request = _load_request()
    prompt = _prompt_for_provider(request, provider_name="Codex")
    codex_bin = os.environ.get("AO_MA10_CODEX_BIN", "codex")
    repo_root = os.environ.get("AO_MA10_CODEX_REPO_ROOT", os.getcwd())
    timeout = _timeout_seconds()
    with tempfile.TemporaryDirectory(prefix="ao-kernel-codex-review-") as tmp:
        tmp_path = Path(tmp)
        schema_path = tmp_path / "review-output.schema.json"
        output_path = tmp_path / "last-message.json"
        schema_path.write_text(json.dumps(_json_output_schema(), indent=2, sort_keys=True), encoding="utf-8")
        proc = subprocess.run(
            [
                codex_bin,
                "exec",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--cd",
                repo_root,
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.stderr.strip():
            assert_no_secret_like_text(proc.stderr, label="codex provider stderr")
        if proc.returncode != 0:
            raise RuntimeError(f"codex provider command failed with exit {proc.returncode}")
        output_text = output_path.read_text(encoding="utf-8") if output_path.exists() else proc.stdout
    payload = extract_json_object(output_text, label="codex provider output")
    return _emit(normalize_provider_output(payload, provider="openai"))


def _mavis_bin() -> str:
    return os.environ.get("AO_MA10_MAVIS_BIN", DEFAULT_MAVIS_BIN)


def _run_mavis(args: Sequence[str], *, timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        [_mavis_bin(), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.stderr.strip():
        assert_no_secret_like_text(proc.stderr, label="mavis stderr")
    if proc.returncode != 0:
        raise RuntimeError(f"mavis command failed with exit {proc.returncode}")
    payload = extract_json_object(proc.stdout, label="mavis stdout")
    return payload


def _message_session_value(message: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _message_content(message: dict[str, Any]) -> str:
    for key in ("content", "msg_content", "message", "body", "text"):
        value = message.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return json.dumps(value, sort_keys=True)
    return ""


def _normalized_review_from_message(message: dict[str, Any], *, label: str) -> dict[str, Any] | None:
    content = _message_content(message)
    if not content:
        return None
    try:
        review = extract_json_object(content, label=label)
        return normalize_provider_output(review, provider="minimax")
    except ValueError:
        return None


def _message_created_ms(message: dict[str, Any]) -> int:
    for key in ("time_created", "timeCreated", "created_at_ms", "createdAtMs"):
        value = message.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _messages_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("messages")
    if raw is None and isinstance(payload.get("data"), list):
        raw = payload["data"]
    if raw is None and isinstance(payload.get("items"), list):
        raw = payload["items"]
    if raw is None and all(key in payload for key in ("from_session", "to_session")):
        raw = [payload]
    if not isinstance(raw, list):
        return []
    return [cast(dict[str, Any], item) for item in raw if isinstance(item, dict)]


def _run_mavis_communication_provider(prompt: str, *, timeout: int) -> int:
    from_session = os.environ.get("AO_MA10_MAVIS_FROM_SESSION_ID", "").strip()
    to_session = os.environ.get("AO_MA10_MAVIS_TO_SESSION_ID", "").strip()
    if not from_session or not to_session:
        raise ValueError("AO_MA10_MAVIS_FROM_SESSION_ID and AO_MA10_MAVIS_TO_SESSION_ID are required")
    deadline = time.monotonic() + timeout
    sent_after_ms = int(time.time() * 1000)
    _run_mavis(
        [
            "communication",
            "send",
            "--from",
            from_session,
            "--to",
            to_session,
            "--command",
            "prompt",
            "--content",
            prompt,
        ],
        timeout=min(timeout, 30),
    )
    poll_interval = float(os.environ.get("AO_MA10_MAVIS_POLL_SECONDS", "5"))
    while time.monotonic() < deadline:
        payload = _run_mavis(
            ["communication", "messages", "--to", from_session, "--status", "all"],
            timeout=min(timeout, 30),
        )
        for message in reversed(_messages_from_payload(payload)):
            if _message_created_ms(message) < sent_after_ms:
                continue
            message_from = _message_session_value(message, "from_session", "fromSession", "from")
            message_to = _message_session_value(message, "to_session", "toSession", "to")
            if message_from != to_session or message_to != from_session:
                continue
            review = _normalized_review_from_message(message, label="mavis response content")
            if review is None:
                continue
            return _emit(review)
        time.sleep(poll_interval)
    raise TimeoutError("mavis provider did not return valid review JSON before timeout")


def _messages_for_session(session_id: str, *, timeout: int) -> list[dict[str, Any]]:
    payload = _run_mavis(["session", "messages", session_id], timeout=min(timeout, 30))
    return _messages_from_payload(payload)


def _run_mavis_new_session_provider(prompt: str, *, timeout: int) -> int:
    agent = os.environ.get("AO_MA10_MAVIS_AGENT", "mavis").strip() or "mavis"
    title = os.environ.get("AO_MA10_MAVIS_TITLE", "ao-kernel-ai-review-provider").strip()
    workspace = os.environ.get("AO_MA10_MAVIS_WORKSPACE", os.getcwd()).strip()
    create_payload = _run_mavis(
        [
            "session",
            "new",
            agent,
            "--from",
            "root",
            "--title",
            title,
            "--workspace",
            workspace,
            "--prompt",
            prompt,
        ],
        timeout=min(timeout, 30),
    )
    session_id = create_payload.get("sessionId")
    if not isinstance(session_id, str) or not session_id.startswith("mvs_"):
        raise ValueError("mavis session new did not return a sessionId")
    deadline = time.monotonic() + timeout
    poll_interval = float(os.environ.get("AO_MA10_MAVIS_POLL_SECONDS", "5"))
    while time.monotonic() < deadline:
        for message in reversed(_messages_for_session(session_id, timeout=timeout)):
            role = message.get("role")
            if role not in {"assistant", "model"}:
                continue
            review = _normalized_review_from_message(message, label="mavis session assistant content")
            if review is None:
                continue
            return _emit(review)
        time.sleep(poll_interval)
    raise TimeoutError(f"mavis session {session_id} did not return valid review JSON before timeout")


def run_mavis_provider() -> int:
    request = _load_request()
    prompt = _prompt_for_provider(request, provider_name="Mavis/MiniMax")
    timeout = _timeout_seconds()
    mode = os.environ.get("AO_MA10_MAVIS_MODE", "").strip().lower()
    if mode == "communication" or (
        os.environ.get("AO_MA10_MAVIS_FROM_SESSION_ID") and os.environ.get("AO_MA10_MAVIS_TO_SESSION_ID")
    ):
        return _run_mavis_communication_provider(prompt, timeout=timeout)
    return _run_mavis_new_session_provider(prompt, timeout=timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provider wrappers for ao-kernel ai-review.")
    subparsers = parser.add_subparsers(dest="provider", required=True)
    subparsers.add_parser("claude", help="Call local Claude CLI and normalize review JSON.")
    subparsers.add_parser("codex", help="Call local Codex CLI and normalize review JSON.")
    subparsers.add_parser("mavis", help="Call local Mavis/MiniMax orchestrator and normalize review JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.provider == "claude":
            return run_claude_provider()
        if args.provider == "codex":
            return run_codex_provider()
        if args.provider == "mavis":
            return run_mavis_provider()
        parser.error(f"unsupported provider {args.provider}")
        return 2
    except (RuntimeError, TimeoutError, ValueError, subprocess.SubprocessError) as exc:
        return _provider_error(str(exc))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
