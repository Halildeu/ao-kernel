"""v3.6 E2: context pipeline consultation lane tests (8 pins).

Compiler stays pure (plan §3.E2 + Codex iter-1 revision #1): it
accepts a pre-loaded ``consultations`` tuple and renders a
``## Consultations`` section. I/O happens in
``compile_context_sdk`` (agent_coordination).

Coverage:
- Empty consultations → no header emitted
- Populated consultations → header + rendered lines, caller-supplied order preserved
- `ProfileConfig.max_consultations` SSOT — per-profile cap applied
- EMERGENCY profile → 0 consultations regardless of input
- PLANNING profile → up to 10 consultations
- Oversized input → capped (last-added-first-dropped)
- Null-tolerant render (None topic/from_agent/to_agent → graceful)
- `compile_context_sdk` wiring: AGREE first, PARTIAL second, then capped
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.consultation.promotion import PromotedConsultation
from ao_kernel.context.context_compiler import compile_context
from ao_kernel.context.profile_router import PROFILES, ProfileConfig


def _mk_consultation(
    cns_id: str,
    *,
    verdict: str = "AGREE",
    topic: str | None = "architecture",
    from_agent: str | None = "claude",
    to_agent: str | None = "codex",
    resolved_at: str | None = "2026-04-18T10:00:00+00:00",
    promoted_at: str = "2026-04-19T10:00:00+00:00",
    confidence: float | None = None,
) -> PromotedConsultation:
    from ao_kernel.consultation.promotion import verdict_confidence

    return PromotedConsultation(
        cns_id=cns_id,
        topic=topic,
        from_agent=from_agent,
        to_agent=to_agent,
        final_verdict=verdict,
        resolved_at=resolved_at,
        record_digest="sha256:deadbeef",
        evidence_path=".ao/evidence/consultations/x",
        confidence=confidence if confidence is not None else verdict_confidence(verdict),
        promoted_at=promoted_at,
    )


class TestEmpty:
    def test_no_consultations_omits_header(self) -> None:
        """Empty tuple → no ## Consultations section (no empty header artefact)."""
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=(),
            profile="TASK_EXECUTION",
        )
        assert "## Consultations" not in result.preamble


class TestPopulated:
    def test_header_and_rendered_entries(self) -> None:
        """Populated tuple → ## Consultations header + compact render."""
        consultations = (
            _mk_consultation("CNS-001", verdict="AGREE"),
            _mk_consultation("CNS-002", verdict="PARTIAL", topic="cost"),
        )
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=consultations,
            profile="PLANNING",
        )
        assert "## Consultations" in result.preamble
        assert "[CNS-001] architecture AGREE" in result.preamble
        assert "[CNS-002] cost PARTIAL" in result.preamble
        # Arrow between agents
        assert "claude\u2192codex" in result.preamble

    def test_caller_supplied_order_preserved(self) -> None:
        """Compiler renders in the order supplied by the caller —
        no internal re-sort by promoted_at etc."""
        consultations = (
            _mk_consultation("CNS-AAA"),
            _mk_consultation("CNS-BBB"),
            _mk_consultation("CNS-CCC"),
        )
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=consultations,
            profile="PLANNING",
        )
        idx_a = result.preamble.index("[CNS-AAA]")
        idx_b = result.preamble.index("[CNS-BBB]")
        idx_c = result.preamble.index("[CNS-CCC]")
        assert idx_a < idx_b < idx_c


class TestProfileCaps:
    def test_profile_config_max_consultations_ssot(self) -> None:
        """ProfileConfig exposes `max_consultations` per profile (SSOT
        per plan §3.E2, Codex iter-1 revision #6)."""
        assert PROFILES["PLANNING"].max_consultations == 10
        assert PROFILES["REVIEW"].max_consultations == 10
        assert PROFILES["EMERGENCY"].max_consultations == 0
        assert PROFILES["TASK_EXECUTION"].max_consultations == 3
        assert PROFILES["STARTUP"].max_consultations == 3
        assert PROFILES["ASSESSMENT"].max_consultations == 3

    def test_emergency_profile_suppresses_consultations(self) -> None:
        """EMERGENCY profile → 0 consultations rendered even when
        caller supplies a populated tuple (lean context invariant)."""
        consultations = (_mk_consultation("CNS-EMERGENCY"),)
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=consultations,
            profile="EMERGENCY",
        )
        assert "## Consultations" not in result.preamble
        assert "CNS-EMERGENCY" not in result.preamble

    def test_oversized_input_capped_per_profile(self) -> None:
        """TASK_EXECUTION has max_consultations=3; a 5-entry tuple
        must be trimmed to 3, keeping caller-supplied order from the
        top (last-added-first-dropped)."""
        consultations = tuple(_mk_consultation(f"CNS-{i:03d}") for i in range(5))
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=consultations,
            profile="TASK_EXECUTION",
        )
        assert result.preamble.count("[CNS-") == 3
        assert "CNS-000" in result.preamble
        assert "CNS-001" in result.preamble
        assert "CNS-002" in result.preamble
        assert "CNS-003" not in result.preamble
        assert "CNS-004" not in result.preamble


class TestLenientRender:
    def test_none_topic_and_agents_render_gracefully(self) -> None:
        """Reader facade may emit None for lenient edges — render
        must not crash or print literal ``None``."""
        consultations = (
            _mk_consultation(
                "CNS-NONE",
                topic=None,
                from_agent=None,
                to_agent=None,
                resolved_at=None,
            ),
        )
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=consultations,
            profile="PLANNING",
        )
        assert "None" not in result.preamble
        assert "[CNS-NONE]" in result.preamble
        assert "(topic unknown)" in result.preamble
        assert "unresolved" in result.preamble


class TestBlockAbsorb:
    """Codex post-impl BLOCK iter-2 absorb.

    BLOCK #1 — duplicate render: canonical lane + consultation lane
    both contained consultation-category entries before the fix. SDK
    layer now excludes `category=="consultation"` from canonical dict
    so consultations appear exactly once under the typed section.

    BLOCK #2 — budget bypass: consultation lines did not count toward
    the `max_tokens` cap and were not reflected in `total_tokens`.
    Compiler now reserves char-budget for each accepted consultation
    line before rendering; anything that would push the preamble over
    the cap is dropped tail-first.
    """

    def test_consultation_not_duplicated_in_canonical_lane(
        self,
        tmp_path: Path,
    ) -> None:
        from ao_kernel.context.agent_coordination import compile_context_sdk

        ao = tmp_path / ".ao"
        ao.mkdir()
        store = {
            "version": "v1",
            "decisions": {
                "consultation.CNS-DEDUP": {
                    "key": "consultation.CNS-DEDUP",
                    "value": {
                        "cns_id": "CNS-DEDUP",
                        "topic": "dedup",
                        "from_agent": "claude",
                        "to_agent": "codex",
                        "final_verdict": "AGREE",
                        "resolved_at": "2026-04-18T10:00:00+00:00",
                    },
                    "category": "consultation",
                    "source": "consultation_archive",
                    "confidence": 1.0,
                    "provenance": {
                        "method": "consultation_promotion",
                        "cns_id": "CNS-DEDUP",
                    },
                    "promoted_at": "2026-04-19T10:00:00+00:00",
                    "expires_at": "",
                },
            },
            "facts": {},
            "updated_at": "2026-04-19T00:00:00Z",
        }
        (ao / "canonical_decisions.v1.json").write_text(
            json.dumps(store, indent=2),
            encoding="utf-8",
        )

        result = compile_context_sdk(
            tmp_path,
            session_context={"ephemeral_decisions": []},
            messages=None,
            profile="PLANNING",
        )
        preamble = result["preamble"]
        # Consultation row must be rendered in the typed section only,
        # not in the ## Canonical Decisions blob.
        assert "## Canonical Decisions" not in preamble
        assert "## Consultations" in preamble
        # Concretely ensure the CNS-DEDUP row appears exactly once.
        assert preamble.count("CNS-DEDUP") == 1

    def test_consultation_lines_respect_token_budget(self) -> None:
        """Budget fit: a long consultation list tail-truncates before
        the preamble exceeds the char budget (`max_tokens * 4`).
        Also verifies `total_tokens` reflects consultation chars."""
        # Moderate budget — each ~160-char long line fits 1-2 times
        # in a 200-char budget (max_tokens=50). 5 lines cannot all
        # fit, so the tail must drop.
        custom = ProfileConfig(
            profile_id="TIGHT",
            description="tight budget",
            priority_prefixes=(),
            max_decisions=5,
            max_tokens=50,  # 200-char budget
            max_consultations=10,
        )
        PROFILES["TIGHT"] = custom
        try:
            consultations = tuple(
                _mk_consultation(
                    f"CNS-{i:03d}",
                    topic="x" * 80,  # ~160-char line each
                )
                for i in range(5)
            )
            result = compile_context(
                {"ephemeral_decisions": []},
                consultations=consultations,
                profile="TIGHT",
            )
            rendered_count = result.preamble.count("[CNS-")
            assert rendered_count < 5, f"expected some consultations dropped, got {rendered_count}/5"
            assert rendered_count >= 1, f"expected at least one consultation accepted, got {rendered_count}"
            # total_tokens must reflect consultation chars, not 0.
            assert result.total_tokens > 0
            # Preamble length within budget (allow ~80 char slack for
            # the `[Context Profile: TIGHT]` prefix + section header).
            budget_chars = custom.max_tokens * 4
            assert len(result.preamble) <= budget_chars + 80, (
                f"preamble={len(result.preamble)} over budget={budget_chars}"
            )
        finally:
            PROFILES.pop("TIGHT", None)


class TestSdkWiringAgreePreferred:
    def test_compile_context_sdk_prefers_agree_then_partial(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Codex iter-1 revision #1 absorb — compile_context_sdk
        is the I/O-layer that queries the store; it must prefer
        AGREE over PARTIAL before feeding the pure compiler."""
        from ao_kernel.context.agent_coordination import compile_context_sdk

        # Seed canonical store directly.
        ao = tmp_path / ".ao"
        ao.mkdir()
        store = {
            "version": "v1",
            "decisions": {
                "consultation.CNS-PART": {
                    "key": "consultation.CNS-PART",
                    "value": {
                        "cns_id": "CNS-PART",
                        "topic": "partial-case",
                        "from_agent": "claude",
                        "to_agent": "codex",
                        "final_verdict": "PARTIAL",
                        "resolved_at": "2026-04-18T09:00:00+00:00",
                    },
                    "category": "consultation",
                    "source": "consultation_archive",
                    "confidence": 0.7,
                    "provenance": {
                        "method": "consultation_promotion",
                        "cns_id": "CNS-PART",
                    },
                    "promoted_at": "2026-04-19T10:00:00+00:00",
                    "expires_at": "",
                },
                "consultation.CNS-AGREE": {
                    "key": "consultation.CNS-AGREE",
                    "value": {
                        "cns_id": "CNS-AGREE",
                        "topic": "agreed-case",
                        "from_agent": "claude",
                        "to_agent": "codex",
                        "final_verdict": "AGREE",
                        "resolved_at": "2026-04-18T08:00:00+00:00",
                    },
                    "category": "consultation",
                    "source": "consultation_archive",
                    "confidence": 1.0,
                    "provenance": {
                        "method": "consultation_promotion",
                        "cns_id": "CNS-AGREE",
                    },
                    "promoted_at": "2026-04-19T09:00:00+00:00",
                    "expires_at": "",
                },
            },
            "facts": {},
            "updated_at": "2026-04-19T00:00:00Z",
        }
        (ao / "canonical_decisions.v1.json").write_text(
            json.dumps(store, indent=2),
            encoding="utf-8",
        )

        result = compile_context_sdk(
            tmp_path,
            session_context={"ephemeral_decisions": []},
            messages=None,
            profile="PLANNING",
        )
        # Both should be present; AGREE must appear before PARTIAL
        preamble = result["preamble"]
        idx_agree = preamble.index("[CNS-AGREE]")
        idx_part = preamble.index("[CNS-PART]")
        assert idx_agree < idx_part, "AGREE must render before PARTIAL"


class TestObservabilityAccounting:
    """v3.8 H5: consultation lane contributes to
    `items_included/items_excluded/selection_log` telemetry surface.
    Closes Codex v3.6 E2 residual follow-up — consultation lines
    were budget-aware but invisible to the counters."""

    def test_accepted_consultation_counted_in_items_included(self) -> None:
        consultations = (
            _mk_consultation("CNS-OBS-1"),
            _mk_consultation("CNS-OBS-2"),
        )
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=consultations,
            profile="PLANNING",
        )
        # Two consultations accepted; PLANNING profile has no
        # session / canonical / fact items in this fixture.
        assert result.items_included == 2
        assert result.items_excluded == 0

    def test_dropped_consultation_counted_in_items_excluded(self) -> None:
        """Tight budget drops trailing consultations; they must show
        up under `items_excluded` and in `selection_log` with
        lane='consultation'."""
        custom = ProfileConfig(
            profile_id="H5_TIGHT",
            description="tight budget — consultation drop test",
            priority_prefixes=(),
            max_decisions=5,
            max_tokens=50,  # 200-char budget
            max_consultations=10,
        )
        PROFILES["H5_TIGHT"] = custom
        try:
            consultations = tuple(
                _mk_consultation(f"CNS-DROP-{i:03d}", topic="x" * 80)
                for i in range(5)
            )
            result = compile_context(
                {"ephemeral_decisions": []},
                consultations=consultations,
                profile="H5_TIGHT",
            )
            # Some accepted, some dropped; total must equal input count.
            assert result.items_included >= 1
            assert result.items_excluded >= 1
            assert (
                result.items_included + result.items_excluded == len(consultations)
            ), (
                f"counter drift: included={result.items_included} + "
                f"excluded={result.items_excluded} != {len(consultations)}"
            )
            # selection_log has a consultation-lane entry for each
            # capped consultation (accepted or excluded).
            consultation_log = [
                row
                for row in result.selection_log
                if row.get("lane") == "consultation"
            ]
            assert len(consultation_log) == len(consultations)
            excluded_rows = [
                row for row in consultation_log if row["included"] is False
            ]
            assert excluded_rows
            assert all(
                "budget" in row["reason"] for row in excluded_rows
            ), f"unexpected exclusion reasons: {[r['reason'] for r in excluded_rows]}"
        finally:
            PROFILES.pop("H5_TIGHT", None)

    def test_empty_consultations_leaves_counters_untouched(self) -> None:
        """No consultations passed → counters reflect only other lanes."""
        result = compile_context(
            {"ephemeral_decisions": []},
            consultations=(),
            profile="TASK_EXECUTION",
        )
        # Fresh workspace with no other lanes either.
        assert result.items_included == 0
        assert result.items_excluded == 0
        assert not [
            r for r in result.selection_log if r.get("lane") == "consultation"
        ]
