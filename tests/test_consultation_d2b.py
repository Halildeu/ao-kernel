"""v3.5 D2b: canonical promotion tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.config import load_default
from ao_kernel.consultation.archive import archive_all
from ao_kernel.consultation.promotion import (
    PromotionSummary,
    promote_resolved_consultations,
    verdict_confidence,
)
from ao_kernel.context.canonical_store import load_store


@pytest.fixture
def policy_enabled() -> dict:
    policy = load_default("policies", "policy_agent_consultation.v1.json")
    policy["promotion"] = {"enabled": True}
    return policy


@pytest.fixture
def policy_disabled() -> dict:
    policy = load_default("policies", "policy_agent_consultation.v1.json")
    policy.setdefault("promotion", {"enabled": False})
    return policy


def _seed_cns(
    workspace_root: Path,
    cns_id: str,
    *,
    verdict: str = "AGREE",
    request_iter2: bool = False,
) -> None:
    req_dir = workspace_root / ".ao" / "consultations" / "requests"
    resp_dir = workspace_root / ".ao" / "consultations" / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)
    (req_dir / f"{cns_id}.request.v1.json").write_text(
        json.dumps({
            "consultation_id": cns_id,
            "topic": "architecture",
            "from_agent": "claude",
            "to_agent": "codex",
        }), encoding="utf-8",
    )
    if request_iter2:
        (req_dir / f"{cns_id}.iter2.request.v1.json").write_text(
            json.dumps({"consultation_id": cns_id, "iter": 2}),
            encoding="utf-8",
        )
    (resp_dir / f"{cns_id}.codex.response.v1.json").write_text(
        json.dumps({
            "consultation_id": cns_id,
            "overall_verdict": verdict,
            "responded_at": "2026-04-18T10:00:00+00:00",
        }), encoding="utf-8",
    )


def _archive_and_promote(
    tmp_path: Path, policy: dict, cns_id: str, verdict: str = "AGREE",
) -> PromotionSummary:
    _seed_cns(tmp_path, cns_id, verdict=verdict)
    # D2a archive needs a consultation policy too — reuse default
    archive_policy = load_default(
        "policies", "policy_agent_consultation.v1.json",
    )
    archive_all(archive_policy, workspace_root=tmp_path)
    return promote_resolved_consultations(tmp_path, policy)


# ─── Confidence mapping ────────────────────────────────────────────────


class TestVerdictConfidence:
    def test_agree_confidence_1(self) -> None:
        assert verdict_confidence("AGREE") == 1.0

    def test_partial_confidence_0_7(self) -> None:
        assert verdict_confidence("PARTIAL") == 0.7

    def test_unknown_defaults_to_zero(self) -> None:
        # D2b eligibility gate prevents REVISE/REJECT reaching this fn,
        # but defensive default must not crash.
        assert verdict_confidence("REVISE") == 0.0


# ─── Eligibility filter ────────────────────────────────────────────────


class TestEligibility:
    def test_agree_resolved_promoted(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        summary = _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-601", verdict="AGREE",
        )
        assert summary.eligible == 1
        assert summary.promoted == 1

    def test_partial_resolved_promoted(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        summary = _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-602", verdict="PARTIAL",
        )
        assert summary.eligible == 1
        assert summary.promoted == 1

    def test_revise_skipped_ineligible(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        summary = _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-603", verdict="REVISE",
        )
        assert summary.eligible == 0
        assert summary.skipped_ineligible == 1
        assert summary.promoted == 0

    def test_reject_skipped_ineligible(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        summary = _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-604", verdict="REJECT",
        )
        assert summary.skipped_ineligible == 1
        assert summary.promoted == 0

    def test_unclassified_skipped_ineligible(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        summary = _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-605",
            verdict="WEIRD_VERDICT_XYZ",
        )
        # Status becomes pending when UNCLASSIFIED
        assert summary.skipped_ineligible == 1


# ─── Idempotency ───────────────────────────────────────────────────────


class TestIdempotency:
    def test_same_digest_skipped_on_rerun(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        first = _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-611", verdict="AGREE",
        )
        assert first.promoted == 1

        second = promote_resolved_consultations(
            tmp_path, policy_enabled,
        )
        assert second.skipped_same_digest == 1
        assert second.promoted == 0
        assert second.updated == 0

    def test_provenance_record_digest_prefixed(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-612",
        )
        store = load_store(tmp_path)
        key = "consultation.CNS-20260418-612"
        entry = store["decisions"][key]
        digest = entry["provenance"]["record_digest"]
        assert digest.startswith("sha256:")


# ─── Key/value contract ────────────────────────────────────────────────


class TestKeyValueContract:
    def test_key_namespaced(self, tmp_path: Path, policy_enabled: dict) -> None:
        _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-621",
        )
        store = load_store(tmp_path)
        assert "consultation.CNS-20260418-621" in store["decisions"]
        assert "CNS-20260418-621" not in store["decisions"]  # bare key forbidden

    def test_value_compact_no_full_corpus(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        _archive_and_promote(
            tmp_path, policy_enabled, "CNS-20260418-622",
        )
        store = load_store(tmp_path)
        entry = store["decisions"]["consultation.CNS-20260418-622"]
        value = entry["value"]
        # Compact set only — no `requests` / `responses` arrays
        assert "requests" not in value
        assert "responses" not in value
        # Index-shaped metadata present
        assert value["cns_id"] == "CNS-20260418-622"
        assert value["final_verdict"] == "AGREE"


# ─── Policy flag + --force ─────────────────────────────────────────────


class TestPolicyFlag:
    def test_disabled_default_skips_everything(
        self, tmp_path: Path, policy_disabled: dict,
    ) -> None:
        _seed_cns(tmp_path, "CNS-20260418-631", verdict="AGREE")
        archive_all(
            load_default("policies", "policy_agent_consultation.v1.json"),
            workspace_root=tmp_path,
        )
        summary = promote_resolved_consultations(
            tmp_path, policy_disabled,
        )
        assert summary.skipped_disabled == 1
        assert summary.promoted == 0
        assert summary.scanned == 0  # short-circuit before walking

    def test_force_bypasses_disabled(
        self, tmp_path: Path, policy_disabled: dict,
    ) -> None:
        _seed_cns(tmp_path, "CNS-20260418-632", verdict="AGREE")
        archive_all(
            load_default("policies", "policy_agent_consultation.v1.json"),
            workspace_root=tmp_path,
        )
        summary = promote_resolved_consultations(
            tmp_path, policy_disabled, force=True,
        )
        assert summary.skipped_disabled == 0
        assert summary.promoted == 1


# ─── Integrity gate + empty workspace ──────────────────────────────────


class TestIntegrityAndEmpty:
    def test_empty_workspace_clean_summary(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        summary = promote_resolved_consultations(
            tmp_path, policy_enabled,
        )
        assert summary.scanned == 0
        assert summary.promoted == 0
        assert summary.errors == ()

    def test_integrity_failure_skips_cns(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        _seed_cns(tmp_path, "CNS-20260418-641", verdict="AGREE")
        archive_all(
            load_default("policies", "policy_agent_consultation.v1.json"),
            workspace_root=tmp_path,
        )
        # Tamper with resolution record
        record_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-641" / "resolution.record.v1.json"
        )
        doc = json.loads(record_path.read_text(encoding="utf-8"))
        doc["final_verdict"] = "TAMPERED"
        record_path.write_text(json.dumps(doc), encoding="utf-8")

        summary = promote_resolved_consultations(
            tmp_path, policy_enabled,
        )
        assert summary.skipped_integrity == 1
        assert summary.promoted == 0


# ─── Dry-run mode ──────────────────────────────────────────────────────


class TestDryRun:
    def test_dry_run_counts_without_store_write(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        _seed_cns(tmp_path, "CNS-20260418-651", verdict="AGREE")
        archive_all(
            load_default("policies", "policy_agent_consultation.v1.json"),
            workspace_root=tmp_path,
        )
        summary = promote_resolved_consultations(
            tmp_path, policy_enabled, dry_run=True,
        )
        assert summary.promoted == 1  # would-promote counter
        # But store not written
        store = load_store(tmp_path)
        assert "consultation.CNS-20260418-651" not in store.get(
            "decisions", {},
        )


# ─── Request revisions propagate to promoted value ─────────────────────


class TestRequestRevisions:
    def test_promote_preserves_topic_and_agents(
        self, tmp_path: Path, policy_enabled: dict,
    ) -> None:
        _seed_cns(
            tmp_path, "CNS-20260418-661",
            verdict="AGREE", request_iter2=True,
        )
        archive_all(
            load_default("policies", "policy_agent_consultation.v1.json"),
            workspace_root=tmp_path,
        )
        promote_resolved_consultations(tmp_path, policy_enabled)
        store = load_store(tmp_path)
        entry = store["decisions"]["consultation.CNS-20260418-661"]
        assert entry["value"]["topic"] == "architecture"
        assert entry["value"]["from_agent"] == "claude"
        assert entry["value"]["to_agent"] == "codex"
