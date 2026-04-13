"""Edge case tests for memory distiller — cross-session fact promotion."""

from __future__ import annotations

from pathlib import Path


def _write_session(tmp_path: Path, session_id: str, decisions: list[dict]) -> None:
    """Helper: create a valid session_context.v1.json with schema + SHA256."""
    from ao_kernel.session import new_context
    from ao_kernel._internal.session.context_store import save_context_atomic, SessionPaths

    ctx = new_context(session_id=session_id, workspace_root=tmp_path)
    ctx["ephemeral_decisions"] = decisions

    sp = SessionPaths(workspace_root=tmp_path, session_id=session_id)
    sp.context_path.parent.mkdir(parents=True, exist_ok=True)
    save_context_atomic(sp.context_path, ctx)


def _decision(key: str, value: str, created_at: str) -> dict:
    """Build a schema-valid ephemeral decision."""
    return {
        "key": key,
        "value": value,
        "source": "agent",
        "created_at": created_at,
    }


class TestDistillEdgeCases:
    def test_empty_sessions_dir(self, tmp_path: Path):
        """Empty sessions directory returns no distilled facts."""
        from ao_kernel._internal.session.memory_distiller import distill_decisions_from_sessions

        sessions_dir = tmp_path / ".cache" / "sessions"
        sessions_dir.mkdir(parents=True)
        result = distill_decisions_from_sessions(workspace_root=tmp_path)
        assert result == []

    def test_threshold_boundary_min_occurrences(self, tmp_path: Path):
        """Key in exactly min_occurrences sessions → promoted; fewer → excluded."""
        from ao_kernel._internal.session.memory_distiller import distill_decisions_from_sessions

        d = _decision("lang", "python", "2026-01-01T00:00:00Z")
        _write_session(tmp_path, "s1", [d])
        _write_session(tmp_path, "s2", [d])

        # 2 sessions, min_occurrences=2 → should be promoted
        result = distill_decisions_from_sessions(workspace_root=tmp_path, min_occurrences=2, min_stability=1)
        keys = [r["key"] for r in result]
        assert "lang" in keys

        # 1 session below threshold
        tmp2 = tmp_path / "workspace2"
        tmp2.mkdir()
        _write_session(tmp2, "s1", [d])
        result2 = distill_decisions_from_sessions(workspace_root=tmp2, min_occurrences=2, min_stability=1)
        assert result2 == []

    def test_stability_exact_min_stability(self, tmp_path: Path):
        """Exactly min_stability consecutive same values → promoted; fewer → excluded."""
        from ao_kernel._internal.session.memory_distiller import distill_decisions_from_sessions

        d1 = _decision("db", "postgres", "2026-01-01T00:00:00Z")
        d2 = _decision("db", "postgres", "2026-01-02T00:00:00Z")
        _write_session(tmp_path, "s1", [d1])
        _write_session(tmp_path, "s2", [d2])

        result = distill_decisions_from_sessions(workspace_root=tmp_path, min_occurrences=2, min_stability=2)
        keys = [r["key"] for r in result]
        assert "db" in keys

        # Break stability: last value different → stability=1
        tmp2 = tmp_path / "workspace2"
        tmp2.mkdir()
        d3 = _decision("db", "mysql", "2026-01-03T00:00:00Z")
        _write_session(tmp2, "s1", [d1])
        _write_session(tmp2, "s2", [d3])

        result2 = distill_decisions_from_sessions(workspace_root=tmp2, min_occurrences=2, min_stability=2)
        db_entries = [r for r in result2 if r["key"] == "db"]
        assert db_entries == []

    def test_alternating_values_excluded(self, tmp_path: Path):
        """Alternating pattern [A, B, A] has stability=1 → excluded with min_stability=2."""
        from ao_kernel._internal.session.memory_distiller import distill_decisions_from_sessions

        _write_session(tmp_path, "s1", [_decision("fw", "flask", "2026-01-01T00:00:00Z")])
        _write_session(tmp_path, "s2", [_decision("fw", "django", "2026-01-02T00:00:00Z")])
        _write_session(tmp_path, "s3", [_decision("fw", "flask", "2026-01-03T00:00:00Z")])

        result = distill_decisions_from_sessions(
            workspace_root=tmp_path, min_occurrences=2, min_stability=2,
        )
        fw_entries = [r for r in result if r["key"] == "fw"]
        assert fw_entries == []
