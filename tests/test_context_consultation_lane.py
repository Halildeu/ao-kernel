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
from ao_kernel.context.profile_router import PROFILES


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
