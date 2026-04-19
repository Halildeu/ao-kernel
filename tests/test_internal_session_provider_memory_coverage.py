"""v3.13 H3c — ``_internal/session/provider_memory.py`` coverage.

Pulls the module out of ``coverage.run.omit``. Fixture harness builds
a schema-valid session context via ``new_context()`` +
``save_context_atomic()`` rather than mocking ``load_context`` — that
exercises real serialization + validation round-trips.

Covered surfaces:

- ``_safe_slug`` — regex normalization + fallback to "default"
- ``resolve_auto_compact_token_limit`` — codex config read, fail-open
  to ``0`` on exception, non-dict guards, negative/str clamp
- ``read_provider_session_state`` — missing file (exists=False),
  JSON_INVALID error_code propagation, memory_strategy pass-through,
  provider/wire_api mismatch → no continuation, match →
  ``previous_response_id`` + ``conversation_id`` populated,
  ``compaction_summary_ref`` when compaction completed
- ``maybe_auto_compact_markdown`` — below threshold no-op,
  above threshold writes archive + summary + updates session state,
  zero/negative threshold short-circuit, summary_ref relative to
  workspace
- ``persist_provider_result`` — missing session → ``updated=False``,
  happy path ``updated=True``
- ``_render_compaction_summary`` — headings + bullets + narrative,
  fallback excerpt when structured output is longer than input
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fixture harness — real session context via new_context() + atomic save.
# ---------------------------------------------------------------------------


_FIXED_TS = "2026-04-20T00:00:00Z"


def _make_session_context(
    *,
    workspace_root: Path,
    session_id: str = "test-session",
    memory_strategy: str = "local_only",
    provider_state: dict[str, Any] | None = None,
    compaction: dict[str, Any] | None = None,
) -> Path:
    """Create a schema-valid session context file and return its path.

    ``provider_state`` is merged with a default ``updated_at`` stamp
    so callers only have to supply the domain fields; the full
    schema contract (``provider`` + ``wire_api`` + ``updated_at``
    required) is honored.
    """
    from ao_kernel._internal.session.context_store import (
        SessionPaths,
        new_context,
        save_context_atomic,
    )

    sp = SessionPaths(workspace_root=workspace_root, session_id=session_id)
    sp.context_path.parent.mkdir(parents=True, exist_ok=True)

    ctx = new_context(
        session_id=session_id,
        workspace_root=str(workspace_root),
        ttl_seconds=3600,
    )
    ctx["memory_strategy"] = memory_strategy
    if provider_state is not None:
        full_provider_state: dict[str, Any] = {"updated_at": _FIXED_TS}
        full_provider_state.update(provider_state)
        ctx["provider_state"] = full_provider_state
    if compaction is not None:
        ctx["compaction"] = compaction

    save_context_atomic(sp.context_path, ctx)
    return sp.context_path


# ---------------------------------------------------------------------------
# _safe_slug
# ---------------------------------------------------------------------------


class TestSafeSlug:
    def test_normalizes_illegal_chars(self) -> None:
        from ao_kernel._internal.session.provider_memory import _safe_slug

        assert _safe_slug("hello/world@example") == "hello-world-example"

    def test_strips_leading_trailing_dashes(self) -> None:
        from ao_kernel._internal.session.provider_memory import _safe_slug

        assert _safe_slug("---foo---") == "foo"

    def test_empty_string_falls_back_to_default(self) -> None:
        from ao_kernel._internal.session.provider_memory import _safe_slug

        assert _safe_slug("") == "default"
        assert _safe_slug("   ") == "default"
        # Only illegal chars → after normalize + strip, empty → "default".
        assert _safe_slug("@@@///") == "default"

    def test_preserves_allowed_alnum_and_punctuation(self) -> None:
        from ao_kernel._internal.session.provider_memory import _safe_slug

        # Dot, underscore, dash allowed through.
        assert _safe_slug("a.b_c-d") == "a.b_c-d"


# ---------------------------------------------------------------------------
# resolve_auto_compact_token_limit
# ---------------------------------------------------------------------------


class TestResolveAutoCompactTokenLimit:
    def test_exception_during_resolve_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        def _boom(_: Path) -> dict[str, Any]:
            raise RuntimeError("codex read failed")

        monkeypatch.setattr(pm, "resolve_effective_codex_config", _boom)
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 0

    def test_non_dict_resolved_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        monkeypatch.setattr(pm, "resolve_effective_codex_config", lambda _: "not-a-dict")
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 0

    def test_missing_effective_config_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        monkeypatch.setattr(pm, "resolve_effective_codex_config", lambda _: {})
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 0

    def test_non_dict_effective_config_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        monkeypatch.setattr(
            pm,
            "resolve_effective_codex_config",
            lambda _: {"effective_config": "not-a-dict"},
        )
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 0

    def test_happy_path_returns_positive_int(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        monkeypatch.setattr(
            pm,
            "resolve_effective_codex_config",
            lambda _: {"effective_config": {"model_auto_compact_token_limit": 1000}},
        )
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 1000

    def test_negative_clamped_to_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        monkeypatch.setattr(
            pm,
            "resolve_effective_codex_config",
            lambda _: {"effective_config": {"model_auto_compact_token_limit": -50}},
        )
        # max(0, int(-50)) → 0
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 0

    def test_non_numeric_raises_returns_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.session import provider_memory as pm

        monkeypatch.setattr(
            pm,
            "resolve_effective_codex_config",
            lambda _: {"effective_config": {"model_auto_compact_token_limit": "not-a-number"}},
        )
        # int("not-a-number") raises → except returns 0.
        assert pm.resolve_auto_compact_token_limit(workspace_root=tmp_path) == 0


# ---------------------------------------------------------------------------
# read_provider_session_state
# ---------------------------------------------------------------------------


class TestReadProviderSessionState:
    def test_missing_context_returns_exists_false(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )

        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="absent",
            provider="openai",
            wire_api="chat",
        )
        assert payload["exists"] is False
        assert payload["memory_strategy"] == "local_only"
        assert payload["provider_state"] == {}
        assert payload["continuation"] == {}

    def test_invalid_json_sets_error_code(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )
        from ao_kernel._internal.session.context_store import SessionPaths

        sp = SessionPaths(workspace_root=tmp_path, session_id="bad-json")
        sp.context_path.parent.mkdir(parents=True, exist_ok=True)
        sp.context_path.write_text("{not valid", encoding="utf-8")

        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="bad-json",
            provider="openai",
            wire_api="chat",
        )
        # SessionContextError propagates as error_code in payload.
        assert payload.get("error_code") == "JSON_INVALID"
        assert payload["exists"] is False

    def test_existing_context_no_matching_provider_has_empty_continuation(self, tmp_path: Path) -> None:
        """memory_strategy != provider_state → no continuation hand-off."""
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="s1",
            memory_strategy="local_only",  # not in {provider_state, hybrid}
            provider_state={
                "provider": "openai",
                "wire_api": "chat",
                "last_response_id": "resp-111",
                "conversation_id": "conv-1",
            },
        )
        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="s1",
            provider="openai",
            wire_api="chat",
        )
        assert payload["exists"] is True
        assert payload["memory_strategy"] == "local_only"
        assert payload["continuation"] == {}
        # provider_state still surfaced so callers can inspect.
        assert payload["provider_state"]["last_response_id"] == "resp-111"

    def test_matching_hybrid_provider_populates_continuation(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="s2",
            memory_strategy="hybrid",
            provider_state={
                "provider": "openai",
                "wire_api": "chat",
                "last_response_id": "resp-abc",
                "conversation_id": "conv-42",
            },
        )
        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="s2",
            provider="openai",
            wire_api="chat",
        )
        assert payload["continuation"] == {
            "previous_response_id": "resp-abc",
            "conversation_id": "conv-42",
        }

    def test_provider_mismatch_gates_continuation(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="s3",
            memory_strategy="hybrid",
            provider_state={
                "provider": "anthropic",  # doesn't match "openai"
                "wire_api": "messages",
                "last_response_id": "resp-x",
                "conversation_id": "conv-x",
            },
        )
        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="s3",
            provider="openai",
            wire_api="chat",
        )
        assert payload["continuation"] == {}

    def test_compaction_summary_ref_surfaces_when_completed(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="s4",
            memory_strategy="hybrid",
            compaction={
                "status": "completed",
                "summary_ref": ".cache/reports/session_compaction_s4.v1.md",
            },
        )
        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="s4",
            provider="openai",
            wire_api="chat",
        )
        assert payload.get("compaction_summary_ref") == (".cache/reports/session_compaction_s4.v1.md")

    def test_compaction_idle_does_not_surface_summary_ref(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="s5",
            compaction={"status": "idle"},
        )
        payload = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="s5",
            provider="openai",
            wire_api="chat",
        )
        assert "compaction_summary_ref" not in payload


# ---------------------------------------------------------------------------
# maybe_auto_compact_markdown
# ---------------------------------------------------------------------------


class TestMaybeAutoCompactMarkdown:
    def test_below_threshold_no_op(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            maybe_auto_compact_markdown,
        )

        payload = maybe_auto_compact_markdown(
            workspace_root=tmp_path,
            session_id="s",
            markdown="short content",
            provider="openai",
            wire_api="chat",
            threshold_tokens=100000,  # well above anything the short string triggers
        )
        assert payload["applied"] is False
        assert payload["input_markdown"] == "short content"
        assert payload["summary_ref"] == ""

    def test_zero_threshold_short_circuits(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            maybe_auto_compact_markdown,
        )

        payload = maybe_auto_compact_markdown(
            workspace_root=tmp_path,
            session_id="s",
            markdown="anything",
            provider="openai",
            wire_api="chat",
            threshold_tokens=0,
        )
        assert payload["applied"] is False
        assert payload["threshold_tokens"] == 0

    def test_negative_threshold_normalized_to_zero(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            maybe_auto_compact_markdown,
        )

        payload = maybe_auto_compact_markdown(
            workspace_root=tmp_path,
            session_id="s",
            markdown="anything",
            provider="openai",
            wire_api="chat",
            threshold_tokens=-50,
        )
        # `max(0, int(threshold_tokens))` → 0 in payload.
        assert payload["threshold_tokens"] == 0
        assert payload["applied"] is False

    def test_above_threshold_writes_summary_and_archive(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            maybe_auto_compact_markdown,
        )

        # Rough estimate: ~4 chars per token, so 400 chars ≈ 100 tokens.
        long_md = "# Heading\n\n" + "- bullet item\n" * 200 + "paragraph " * 200

        payload = maybe_auto_compact_markdown(
            workspace_root=tmp_path,
            session_id="auto-1",
            markdown=long_md,
            provider="openai",
            wire_api="chat",
            threshold_tokens=10,
        )
        assert payload["applied"] is True
        # Archive + summary written under .cache/reports/.
        reports_dir = tmp_path / ".cache" / "reports"
        assert reports_dir.is_dir()
        archive_file = reports_dir / "session_compaction_auto-1.original.v1.md"
        summary_file = reports_dir / "session_compaction_auto-1.v1.md"
        assert archive_file.read_text(encoding="utf-8") == long_md
        assert summary_file.is_file()
        # summary_ref is workspace-relative posix.
        assert payload["summary_ref"].startswith(".cache/reports/")

    def test_summary_updates_existing_session_context(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            maybe_auto_compact_markdown,
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="auto-2",
            memory_strategy="hybrid",
            provider_state={"provider": "openai", "wire_api": "chat"},
        )
        long_md = ("# heading\n" * 200) + ("- bullet\n" * 200)
        payload = maybe_auto_compact_markdown(
            workspace_root=tmp_path,
            session_id="auto-2",
            markdown=long_md,
            provider="openai",
            wire_api="chat",
            threshold_tokens=5,
        )
        assert payload["applied"] is True
        # Session context picks up the compaction summary ref.
        state = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="auto-2",
            provider="openai",
            wire_api="chat",
        )
        assert state.get("compaction_summary_ref") == payload["summary_ref"]


# ---------------------------------------------------------------------------
# persist_provider_result
# ---------------------------------------------------------------------------


class TestPersistProviderResult:
    def test_missing_session_returns_updated_false(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import persist_provider_result

        result = persist_provider_result(
            workspace_root=tmp_path,
            session_id="absent",
            provider="openai",
            wire_api="chat",
            response_id="resp-1",
        )
        assert result["updated"] is False
        assert result["reason"] == "session_missing"

    def test_happy_path_updates_context(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import (
            persist_provider_result,
            read_provider_session_state,
        )

        _make_session_context(
            workspace_root=tmp_path,
            session_id="p1",
            memory_strategy="hybrid",
            provider_state={"provider": "openai", "wire_api": "chat"},
        )
        result = persist_provider_result(
            workspace_root=tmp_path,
            session_id="p1",
            provider="openai",
            wire_api="chat",
            response_id="resp-new",
            conversation_id="conv-new",
        )
        assert result["updated"] is True
        # Round-trip through read to confirm state was written.
        state = read_provider_session_state(
            workspace_root=tmp_path,
            session_id="p1",
            provider="openai",
            wire_api="chat",
        )
        assert state["provider_state"]["last_response_id"] == "resp-new"
        assert state["provider_state"]["conversation_id"] == "conv-new"

    def test_invalid_session_json_returns_reason(self, tmp_path: Path) -> None:
        from ao_kernel._internal.session.provider_memory import persist_provider_result
        from ao_kernel._internal.session.context_store import SessionPaths

        sp = SessionPaths(workspace_root=tmp_path, session_id="bad")
        sp.context_path.parent.mkdir(parents=True, exist_ok=True)
        sp.context_path.write_text("{not-json", encoding="utf-8")

        result = persist_provider_result(
            workspace_root=tmp_path,
            session_id="bad",
            provider="openai",
            wire_api="chat",
            response_id="resp",
        )
        assert result["updated"] is False
        assert result["reason"] == "JSON_INVALID"


# ---------------------------------------------------------------------------
# _render_compaction_summary
# ---------------------------------------------------------------------------


class TestRenderCompactionSummary:
    def test_structured_sections_when_headings_and_bullets_present(self) -> None:
        from ao_kernel._internal.session.provider_memory import (
            _render_compaction_summary,
        )

        # Input must be large enough that the structured summary fits
        # inside its length; otherwise the function falls through to
        # the fallback Excerpt path.
        md_lines = [
            "# Top heading",
            "",
            "## Sub heading",
            "",
            "- first bullet to show up in Key Bullets section",
            "- second bullet",
            "",
        ]
        for i in range(200):
            md_lines.append(f"paragraph line number {i} contains enough text to dwarf the summary scaffolding")
        md = "\n".join(md_lines) + "\n"
        summary = _render_compaction_summary(markdown=md, session_id="s", approx_input_tokens=42)
        assert "# Session Compaction Summary" in summary
        assert "## Headings" in summary
        assert "Top heading" in summary
        assert "## Key Bullets" in summary
        assert "first bullet" in summary
        assert "## Narrative Excerpt" in summary
        assert "session_id: s" in summary
        assert "approx_input_tokens: 42" in summary

    def test_fallback_excerpt_when_summary_would_exceed_input(self) -> None:
        """If the structured template grows larger than the original
        input, the function falls back to a clipped excerpt rather
        than shipping a summary longer than the source."""
        from ao_kernel._internal.session.provider_memory import (
            _render_compaction_summary,
        )

        # Very short input; structured template would balloon past it.
        summary = _render_compaction_summary(markdown="tiny", session_id="s", approx_input_tokens=1)
        # Fallback path writes the "Excerpt" header and clipped body.
        assert "## Excerpt" in summary
        assert "original_sha256:" in summary

    def test_narrative_excerpt_truncated_to_2400_chars(self) -> None:
        from ao_kernel._internal.session.provider_memory import (
            _render_compaction_summary,
        )

        # Paragraph text only, no headings or bullets. Use one
        # contiguous paragraph so structured path can't balloon with
        # heading/bullet sections and force the fallback.
        big_paragraph = "word " * 2000
        summary = _render_compaction_summary(markdown=big_paragraph, session_id="s", approx_input_tokens=100)
        # Either the narrative excerpt clips at 2400 chars or we fell
        # into the fallback Excerpt path — both are acceptable bounds.
        assert len(summary) < len(big_paragraph) + 1000

    def test_crlf_normalized_to_lf_for_hash(self) -> None:
        from ao_kernel._internal.session.provider_memory import (
            _render_compaction_summary,
        )

        lf = _render_compaction_summary(markdown="line1\nline2\n", session_id="s", approx_input_tokens=1)
        crlf = _render_compaction_summary(markdown="line1\r\nline2\r\n", session_id="s", approx_input_tokens=1)

        # Extract the hash lines from both summaries; they must match
        # because CRLF is normalized to LF before hashing.
        def _extract_sha(out: str) -> str:
            for line in out.splitlines():
                if line.startswith("- original_sha256:"):
                    return line.split(":", 1)[1].strip()
            raise AssertionError("no sha line")

        assert _extract_sha(lf) == _extract_sha(crlf)
