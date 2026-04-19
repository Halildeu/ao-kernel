"""v3.6 E1: PromotedConsultation reader facade tests (7 pins).

Strict core, lenient edges (plan §3.E1 + Codex iter-1 revision #1):
- Missing cns_id/final_verdict/promoted_at → row silently SKIPPED
- Missing topic/from_agent/to_agent → None-tolerant
- Missing confidence → derived from verdict via verdict_confidence()
- Missing provenance fields → None
- Two rows with same cns_id → dedup by most recent promoted_at
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.consultation.promotion import (
    PromotedConsultation,
    query_promoted_consultations,
    verdict_confidence,
)


def _write_store(
    workspace_root: Path,
    decisions: dict[str, dict],
) -> None:
    ao = workspace_root / ".ao"
    ao.mkdir(parents=True, exist_ok=True)
    (ao / "canonical_decisions.v1.json").write_text(
        json.dumps(
            {
                "version": "v1",
                "decisions": decisions,
                "facts": {},
                "updated_at": "2026-04-19T00:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _canonical_entry(
    cns_id: str,
    *,
    verdict: str = "AGREE",
    topic: str = "architecture",
    from_agent: str | None = "claude",
    to_agent: str | None = "codex",
    resolved_at: str | None = "2026-04-18T10:00:00+00:00",
    promoted_at: str = "2026-04-19T10:00:00+00:00",
    confidence: float | None = None,
    record_digest: str | None = "sha256:deadbeef",
    evidence_path: str | None = ".ao/evidence/consultations/xyz",
    category: str = "consultation",
    expires_at: str = "",
) -> dict:
    value: dict = {
        "cns_id": cns_id,
        "topic": topic,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "final_verdict": verdict,
        "resolved_at": resolved_at,
    }
    provenance: dict = {
        "method": "consultation_promotion",
        "cns_id": cns_id,
    }
    if record_digest is not None:
        provenance["record_digest"] = record_digest
    if evidence_path is not None:
        provenance["evidence_path"] = evidence_path
    entry: dict = {
        "key": f"consultation.{cns_id}",
        "value": value,
        "category": category,
        "source": "consultation_archive",
        "confidence": confidence if confidence is not None else verdict_confidence(verdict),
        "provenance": provenance,
        "promoted_at": promoted_at,
        "expires_at": expires_at,
    }
    return entry


class TestEmptyStore:
    def test_empty_store_returns_empty_tuple(self, tmp_path: Path) -> None:
        result = query_promoted_consultations(tmp_path)
        assert result == ()
        assert isinstance(result, tuple)


class TestHappyPath:
    def test_single_agree_hydrates(self, tmp_path: Path) -> None:
        _write_store(
            tmp_path,
            {"consultation.CNS-001": _canonical_entry("CNS-001")},
        )
        result = query_promoted_consultations(tmp_path)
        assert len(result) == 1
        rec = result[0]
        assert isinstance(rec, PromotedConsultation)
        assert rec.cns_id == "CNS-001"
        assert rec.final_verdict == "AGREE"
        assert rec.confidence == 1.0
        assert rec.topic == "architecture"
        assert rec.from_agent == "claude"
        assert rec.to_agent == "codex"
        assert rec.record_digest == "sha256:deadbeef"
        assert rec.evidence_path == ".ao/evidence/consultations/xyz"

    def test_mixed_verdicts_and_verdict_filter(
        self,
        tmp_path: Path,
    ) -> None:
        _write_store(
            tmp_path,
            {
                "consultation.CNS-001": _canonical_entry(
                    "CNS-001",
                    verdict="AGREE",
                    promoted_at="2026-04-19T10:00:00+00:00",
                ),
                "consultation.CNS-002": _canonical_entry(
                    "CNS-002",
                    verdict="PARTIAL",
                    promoted_at="2026-04-19T09:00:00+00:00",
                ),
            },
        )
        all_records = query_promoted_consultations(tmp_path)
        assert len(all_records) == 2
        # Sorted by promoted_at desc
        assert all_records[0].cns_id == "CNS-001"
        assert all_records[1].cns_id == "CNS-002"

        only_agree = query_promoted_consultations(tmp_path, verdict="AGREE")
        assert [rec.cns_id for rec in only_agree] == ["CNS-001"]

        only_partial = query_promoted_consultations(
            tmp_path,
            verdict="PARTIAL",
        )
        assert [rec.cns_id for rec in only_partial] == ["CNS-002"]
        assert only_partial[0].confidence == pytest.approx(0.7)


class TestTopicFilter:
    def test_topic_filter_case_insensitive_substring(
        self,
        tmp_path: Path,
    ) -> None:
        _write_store(
            tmp_path,
            {
                "consultation.CNS-001": _canonical_entry(
                    "CNS-001",
                    topic="Runtime Architecture",
                ),
                "consultation.CNS-002": _canonical_entry(
                    "CNS-002",
                    topic="policy engine",
                ),
            },
        )
        arch_only = query_promoted_consultations(tmp_path, topic="architecture")
        assert [rec.cns_id for rec in arch_only] == ["CNS-001"]
        # Case-insensitive substring match
        upper = query_promoted_consultations(tmp_path, topic="RUNTIME")
        assert [rec.cns_id for rec in upper] == ["CNS-001"]


class TestExpiryLifecycle:
    def test_expired_excluded_by_default(self, tmp_path: Path) -> None:
        _write_store(
            tmp_path,
            {
                "consultation.CNS-001": _canonical_entry(
                    "CNS-001",
                    expires_at="2020-01-01T00:00:00Z",  # past
                ),
                "consultation.CNS-002": _canonical_entry("CNS-002"),
            },
        )
        default = query_promoted_consultations(tmp_path)
        assert [rec.cns_id for rec in default] == ["CNS-002"]

    def test_expired_included_when_requested(self, tmp_path: Path) -> None:
        _write_store(
            tmp_path,
            {
                "consultation.CNS-001": _canonical_entry(
                    "CNS-001",
                    expires_at="2020-01-01T00:00:00Z",
                    promoted_at="2026-04-19T10:00:00+00:00",
                ),
                "consultation.CNS-002": _canonical_entry(
                    "CNS-002",
                    promoted_at="2026-04-19T09:00:00+00:00",
                ),
            },
        )
        result = query_promoted_consultations(
            tmp_path,
            include_expired=True,
        )
        assert {rec.cns_id for rec in result} == {"CNS-001", "CNS-002"}


class TestMalformedRowSkip:
    def test_row_missing_cns_id_silently_skipped(
        self,
        tmp_path: Path,
    ) -> None:
        """Strict-core hydration: missing cns_id → row SKIP, reader
        never raises."""
        bad = _canonical_entry("CNS-IGNORED")
        bad["value"].pop("cns_id")
        _write_store(
            tmp_path,
            {
                "consultation.CNS-MALFORMED": bad,
                "consultation.CNS-GOOD": _canonical_entry("CNS-GOOD"),
            },
        )
        result = query_promoted_consultations(tmp_path)
        assert [rec.cns_id for rec in result] == ["CNS-GOOD"]


class TestDuplicateDedup:
    def test_two_rows_same_cns_id_dedup_by_promoted_at(
        self,
        tmp_path: Path,
    ) -> None:
        """Malformed-store defence (plan §3.E2 tests + Codex iter-2
        rewording): two distinct canonical rows whose hydrated
        cns_id values collide → reader dedupes, keeping the more
        recent promoted_at. Canonical key uniqueness is enforced
        upstream on the happy path; this guards future store-format
        drift."""
        older = _canonical_entry(
            "CNS-DUP",
            verdict="PARTIAL",
            promoted_at="2026-04-18T09:00:00+00:00",
        )
        newer = _canonical_entry(
            "CNS-DUP",
            verdict="AGREE",
            promoted_at="2026-04-19T10:00:00+00:00",
        )
        _write_store(
            tmp_path,
            {
                "consultation.CNS-DUP-a": older,
                "consultation.CNS-DUP-b": newer,
            },
        )
        result = query_promoted_consultations(tmp_path)
        assert len(result) == 1
        assert result[0].cns_id == "CNS-DUP"
        assert result[0].final_verdict == "AGREE"
        assert result[0].promoted_at == "2026-04-19T10:00:00+00:00"
