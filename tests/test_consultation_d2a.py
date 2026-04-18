"""v3.5 D2a: consultation archive + normalize + integrity tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.config import load_default
from ao_kernel.consultation.archive import archive_all
from ao_kernel.consultation.evidence import (
    ConsultationEventKind,
    _identity_for_event,
)
from ao_kernel.consultation.integrity import (
    compute_consultation_manifest,
    verify_consultation_manifest,
)
from ao_kernel.consultation.normalize import (
    NormalizedVerdict,
    ResolutionStatus,
    iteration_from_filename,
    normalize_verdict,
)


@pytest.fixture
def policy() -> dict:
    return load_default("policies", "policy_agent_consultation.v1.json")


def _seed_cns(
    workspace_root: Path,
    cns_id: str,
    *,
    request_payload: dict,
    responses: list[tuple[str, dict]],  # (agent, payload)
    request_iter2: dict | None = None,
) -> None:
    """Drop request + response JSONs into `.ao/consultations/`."""
    req_dir = workspace_root / ".ao" / "consultations" / "requests"
    resp_dir = workspace_root / ".ao" / "consultations" / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    (req_dir / f"{cns_id}.request.v1.json").write_text(
        json.dumps(request_payload), encoding="utf-8",
    )
    if request_iter2 is not None:
        (req_dir / f"{cns_id}.iter2.request.v1.json").write_text(
            json.dumps(request_iter2), encoding="utf-8",
        )
    for i, (agent, payload) in enumerate(responses, start=1):
        suffix = "" if i == 1 else f".iter{i}"
        (resp_dir / f"{cns_id}{suffix}.{agent}.response.v1.json").write_text(
            json.dumps(payload), encoding="utf-8",
        )


# ─── Verdict normalization ─────────────────────────────────────────────


class TestVerdictNormalization:
    def test_agree_variants(self) -> None:
        for raw in ("AGREE", "agree", "Merge", "GREEN", "approve"):
            assert normalize_verdict(raw) == NormalizedVerdict.AGREE

    def test_partial_variants(self) -> None:
        for raw in ("PARTIAL", "partial", "AMBER", "mostly_agree", "phased-core"):
            assert normalize_verdict(raw) == NormalizedVerdict.PARTIAL

    def test_revise_variants(self) -> None:
        for raw in ("REVISE", "REVISE-AGAIN", "scope_cut", "needs_changes", "B", "C", "D"):
            assert normalize_verdict(raw) == NormalizedVerdict.REVISE

    def test_reject_variants(self) -> None:
        for raw in ("REJECT", "RED", "BLOCK", "block", "DISAGREE", "rejected"):
            assert normalize_verdict(raw) == NormalizedVerdict.REJECT

    def test_unclassified_fallback(self) -> None:
        for raw in ("WEIRD", "", "random_string", None, 42):
            assert normalize_verdict(raw) == NormalizedVerdict.UNCLASSIFIED

    def test_whitespace_trimmed(self) -> None:
        assert normalize_verdict("  AGREE  ") == NormalizedVerdict.AGREE

    def test_case_insensitive(self) -> None:
        assert normalize_verdict("aGrEe") == NormalizedVerdict.AGREE

    def test_object_verdict_option_id(self) -> None:
        obj = {"option_id": "AGREE", "body": "looks good"}
        assert normalize_verdict(obj) == NormalizedVerdict.AGREE

    def test_object_verdict_unknown_option(self) -> None:
        obj = {"option_id": "UNKNOWN", "body": "..."}
        assert normalize_verdict(obj) == NormalizedVerdict.UNCLASSIFIED

    def test_object_without_option_id(self) -> None:
        obj = {"body": "unclear"}
        assert normalize_verdict(obj) == NormalizedVerdict.UNCLASSIFIED

    def test_multi_answer_verdict_numeric_question_prefix(self) -> None:
        """Historical corpus: verdict='1:C,3:B,7:C' → first token 'C' → REVISE.

        Codex D2a iter-5 BLOCK absorb — multi-answer fallback parses
        leading answer token and maps it via the regular matrix.
        """
        assert normalize_verdict("1:C,3:B,7:C") == NormalizedVerdict.REVISE

    def test_multi_answer_verdict_section_prefix(self) -> None:
        """Historical corpus: verdict='S1:C,S2:A,S3:C,S4:B' → 'C' → REVISE."""
        assert normalize_verdict("S1:C,S2:A,S3:C,S4:B") == NormalizedVerdict.REVISE

    def test_multi_answer_verdict_agree_first(self) -> None:
        """First answer wins — 'AGREE,...' maps to AGREE regardless of rest."""
        assert normalize_verdict("1:AGREE,2:REVISE") == NormalizedVerdict.AGREE


# ─── Resolution record source stability ────────────────────────────────


class TestResolutionRecordSourceStable:
    def test_config_digest_not_in_record(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        _seed_cns(
            tmp_path,
            "CNS-20260418-001",
            request_payload={"consultation_id": "CNS-20260418-001", "topic": "test"},
            responses=[("codex", {
                "consultation_id": "CNS-20260418-001",
                "overall_verdict": "AGREE",
            })],
        )
        archive_all(policy, workspace_root=tmp_path)
        record_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-001" / "resolution.record.v1.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assert "config_digest" not in record
        assert "archived_at" not in record  # archive-time metadata separate

    def test_resolved_at_from_last_response(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        _seed_cns(
            tmp_path,
            "CNS-20260418-002",
            request_payload={"consultation_id": "CNS-20260418-002"},
            responses=[("codex", {
                "consultation_id": "CNS-20260418-002",
                "overall_verdict": "AGREE",
                "responded_at": "2026-04-15T10:00:00+00:00",
            })],
        )
        archive_all(policy, workspace_root=tmp_path)
        record_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-002" / "resolution.record.v1.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assert record["resolved_at"] == "2026-04-15T10:00:00+00:00"

    def test_archive_meta_separate_file(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        _seed_cns(
            tmp_path,
            "CNS-20260418-003",
            request_payload={"consultation_id": "CNS-20260418-003"},
            responses=[("codex", {"consultation_id": "CNS-20260418-003", "overall_verdict": "AGREE"})],
        )
        archive_all(policy, workspace_root=tmp_path)
        meta_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-003" / "archive-meta.json"
        )
        assert meta_path.is_file()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "archived_at" in meta
        assert meta["archiver_version"] == "v1"

    def test_request_revisions_first_class(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        _seed_cns(
            tmp_path,
            "CNS-20260418-004",
            request_payload={"consultation_id": "CNS-20260418-004"},
            request_iter2={"consultation_id": "CNS-20260418-004", "iter": 2},
            responses=[("codex", {"consultation_id": "CNS-20260418-004", "overall_verdict": "AGREE"})],
        )
        archive_all(policy, workspace_root=tmp_path)
        record_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-004" / "resolution.record.v1.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        iters = sorted(r["iteration"] for r in record["requests"])
        assert iters == [1, 2]

    def test_status_pending_when_all_unclassified(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        _seed_cns(
            tmp_path,
            "CNS-20260418-005",
            request_payload={"consultation_id": "CNS-20260418-005"},
            responses=[("codex", {
                "consultation_id": "CNS-20260418-005",
                "overall_verdict": "WEIRD_VERDICT",
            })],
        )
        archive_all(policy, workspace_root=tmp_path)
        record_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-005" / "resolution.record.v1.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assert record["status"] == ResolutionStatus.PENDING.value
        assert record["resolved_at"] is None


# ─── Per-kind event identity dedupe ────────────────────────────────────


class TestPerKindDedupe:
    def test_normalized_event_identity_uses_record_digest(self) -> None:
        evt_a = {
            "kind": ConsultationEventKind.NORMALIZED.value,
            "cns_id": "CNS-X",
            "resolution_record_digest": "sha256:aaa",
            "normalizer_version": "v1",
        }
        evt_b = {
            "kind": ConsultationEventKind.NORMALIZED.value,
            "cns_id": "CNS-X",
            "resolution_record_digest": "sha256:bbb",
            "normalizer_version": "v1",
        }
        assert _identity_for_event(evt_a) != _identity_for_event(evt_b)
        assert _identity_for_event(evt_a) == _identity_for_event({**evt_a})

    def test_source_event_identity_uses_source_sha(self) -> None:
        evt_a = {
            "kind": ConsultationEventKind.OPENED.value,
            "source_path": "requests/x.json",
            "source_sha256": "sha256:aaa",
            "normalizer_version": "v1",
        }
        evt_b = {**evt_a, "source_sha256": "sha256:bbb"}
        assert _identity_for_event(evt_a) != _identity_for_event(evt_b)

    def test_idempotent_archive_no_duplicate_events(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        _seed_cns(
            tmp_path,
            "CNS-20260418-006",
            request_payload={"consultation_id": "CNS-20260418-006"},
            responses=[("codex", {"consultation_id": "CNS-20260418-006", "overall_verdict": "AGREE"})],
        )
        archive_all(policy, workspace_root=tmp_path)
        events_path = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-006" / "events.jsonl"
        )
        first_len = len(events_path.read_text(encoding="utf-8").splitlines())
        archive_all(policy, workspace_root=tmp_path)
        second_len = len(events_path.read_text(encoding="utf-8").splitlines())
        assert first_len == second_len  # no duplicate events


# ─── Integrity manifest ────────────────────────────────────────────────


class TestIntegrityManifest:
    def _base_setup(self, tmp_path: Path, policy: dict) -> Path:
        _seed_cns(
            tmp_path,
            "CNS-20260418-007",
            request_payload={"consultation_id": "CNS-20260418-007"},
            responses=[("codex", {"consultation_id": "CNS-20260418-007", "overall_verdict": "AGREE"})],
        )
        archive_all(policy, workspace_root=tmp_path)
        return (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-007"
        )

    def test_manifest_covers_snapshots_events_record(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_dir = self._base_setup(tmp_path, policy)
        manifest = compute_consultation_manifest(cns_dir)
        keys = set(manifest["entries"].keys())
        assert any(k.startswith("requests/") for k in keys)
        assert any(k.startswith("responses/") for k in keys)
        assert "events.jsonl" in keys
        assert "resolution.record.v1.json" in keys

    def test_manifest_excludes_archive_meta(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_dir = self._base_setup(tmp_path, policy)
        manifest = compute_consultation_manifest(cns_dir)
        assert "archive-meta.json" not in manifest["entries"]
        assert "integrity.manifest.v1.json" not in manifest["entries"]

    def test_verify_detects_tampering(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_dir = self._base_setup(tmp_path, policy)
        # Tamper with the record
        record_path = cns_dir / "resolution.record.v1.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["final_verdict"] = "TAMPERED"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        ok, errors = verify_consultation_manifest(cns_dir)
        assert ok is False
        assert any("digest mismatch" in e for e in errors)

    def test_verify_detects_missing_file(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_dir = self._base_setup(tmp_path, policy)
        (cns_dir / "resolution.record.v1.json").unlink()
        ok, errors = verify_consultation_manifest(cns_dir)
        assert ok is False
        assert any("missing file" in e for e in errors)


# ─── iteration_from_filename ───────────────────────────────────────────


class TestSuffixedCnsIdPreservation:
    """Codex D2a iter-6 BLOCK absorb: historical corpus has suffixed
    CNS ids like ``CNS-20260416-028v2`` that a naive regex
    ``CNS-\\d{8}-\\d+`` would truncate to ``CNS-20260416-028``. The
    extractor now reads ``consultation_id`` from the JSON (SSOT);
    filename first-segment is the INVALID_JSON fallback."""

    def test_suffixed_cns_id_preserved_from_json(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_id = "CNS-20260416-028v2"
        _seed_cns(
            tmp_path,
            cns_id,
            request_payload={"consultation_id": cns_id, "topic": "test"},
            responses=[("codex", {
                "consultation_id": cns_id,
                "overall_verdict": "AGREE",
            })],
        )
        archive_all(policy, workspace_root=tmp_path)

        # Evidence dir must use the full suffixed id
        evidence_dir = (
            tmp_path / ".ao" / "evidence" / "consultations" / cns_id
        )
        assert evidence_dir.is_dir(), (
            f"evidence dir missing for suffixed id: {evidence_dir}"
        )
        # Resolution record round-trips the full id
        record = json.loads(
            (evidence_dir / "resolution.record.v1.json").read_text(
                encoding="utf-8",
            )
        )
        assert record["cns_id"] == cns_id

        # Naively-truncated id must NOT exist as a parallel bucket
        wrong_dir = (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260416-028"
        )
        assert not wrong_dir.exists()


class TestDualSourceDedupe:
    """Codex D2a iter-7 BLOCK absorb: during D1 migration window the
    same CNS filename can live in canonical + legacy simultaneously.
    Archive must dedupe (canonical wins) so snapshots + record stay
    single-entry."""

    def _seed_canonical_and_legacy(
        self, workspace_root: Path, cns_id: str,
    ) -> None:
        canonical_req = (
            workspace_root / ".ao" / "consultations" / "requests"
        )
        legacy_req = (
            workspace_root / ".cache" / "index" / "consultations" / "requests"
        )
        canonical_res = (
            workspace_root / ".ao" / "consultations" / "responses"
        )
        legacy_res = (
            workspace_root / ".cache" / "reports" / "consultations"
        )
        for d in (canonical_req, legacy_req, canonical_res, legacy_res):
            d.mkdir(parents=True, exist_ok=True)

        filename_req = f"{cns_id}.request.v1.json"
        filename_res = f"{cns_id}.codex.response.v1.json"

        canonical_payload = {
            "consultation_id": cns_id,
            "topic": "test",
            "from_agent": "claude",
            "to_agent": "codex",
        }
        legacy_payload = {
            **canonical_payload,
            "body": "STALE LEGACY CONTENT",
        }

        (canonical_req / filename_req).write_text(
            json.dumps(canonical_payload), encoding="utf-8",
        )
        (legacy_req / filename_req).write_text(
            json.dumps(legacy_payload), encoding="utf-8",
        )

        response_canonical = {
            "consultation_id": cns_id,
            "overall_verdict": "AGREE",
        }
        response_legacy = {
            "consultation_id": cns_id,
            "overall_verdict": "STALE_LEGACY",
        }
        (canonical_res / filename_res).write_text(
            json.dumps(response_canonical), encoding="utf-8",
        )
        (legacy_res / filename_res).write_text(
            json.dumps(response_legacy), encoding="utf-8",
        )

    def test_dual_source_dedupe_canonical_wins(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_id = "CNS-20260418-099"
        self._seed_canonical_and_legacy(tmp_path, cns_id)

        archive_all(policy, workspace_root=tmp_path)

        evidence_dir = (
            tmp_path / ".ao" / "evidence" / "consultations" / cns_id
        )
        # Single snapshot per artefact (no duplicates from dual source)
        req_snaps = list(
            (evidence_dir / "requests").iterdir()
        )
        assert len(req_snaps) == 1
        res_snaps = list(
            (evidence_dir / "responses").iterdir()
        )
        assert len(res_snaps) == 1

        # Canonical content wins (legacy STALE not picked up)
        req_body = json.loads(
            req_snaps[0].read_text(encoding="utf-8")
        )
        assert "STALE LEGACY CONTENT" not in req_body.get("body", "")

        res_body = json.loads(
            res_snaps[0].read_text(encoding="utf-8")
        )
        assert res_body["overall_verdict"] == "AGREE"

        # Record has single request + single response entry
        record = json.loads(
            (evidence_dir / "resolution.record.v1.json").read_text(
                encoding="utf-8",
            )
        )
        assert len(record["requests"]) == 1
        assert len(record["responses"]) == 1
        assert record["final_verdict"] == "AGREE"


class TestVerifyCli:
    """Codex D2a iter-8 BLOCK absorb: `--verify` CLI surface pinned."""

    def _archive_fixture(self, tmp_path: Path, policy: dict) -> Path:
        _seed_cns(
            tmp_path,
            "CNS-20260418-501",
            request_payload={"consultation_id": "CNS-20260418-501"},
            responses=[("codex", {
                "consultation_id": "CNS-20260418-501",
                "overall_verdict": "AGREE",
            })],
        )
        archive_all(policy, workspace_root=tmp_path)
        return (
            tmp_path / ".ao" / "evidence" / "consultations"
            / "CNS-20260418-501"
        )

    def test_cli_verify_success(
        self, tmp_path: Path, policy: dict, capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._archive_fixture(tmp_path, policy)

        import argparse

        from ao_kernel.cli import _cmd_consultation_archive

        args = argparse.Namespace(
            verify=True,
            dry_run=False,
            renormalize=False,
            output="json",
            project_root=str(tmp_path),
        )
        rc = _cmd_consultation_archive(args)
        assert rc == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["ok"] is True
        assert payload["scanned"] >= 1

    def test_cli_verify_detects_tampering_nonzero(
        self, tmp_path: Path, policy: dict,
    ) -> None:
        cns_dir = self._archive_fixture(tmp_path, policy)
        record = cns_dir / "resolution.record.v1.json"
        doc = json.loads(record.read_text(encoding="utf-8"))
        doc["final_verdict"] = "TAMPERED"
        record.write_text(json.dumps(doc), encoding="utf-8")

        import argparse

        from ao_kernel.cli import _cmd_consultation_archive

        args = argparse.Namespace(
            verify=True,
            dry_run=False,
            renormalize=False,
            output="human",
            project_root=str(tmp_path),
        )
        rc = _cmd_consultation_archive(args)
        assert rc == 1  # non-zero on tamper


class TestIterationParse:
    def test_initial_request(self) -> None:
        assert iteration_from_filename("CNS-20260418-001.request.v1.json") == 1

    def test_iter2_request(self) -> None:
        assert iteration_from_filename("CNS-20260418-001.iter2.request.v1.json") == 2

    def test_iter5_response(self) -> None:
        assert iteration_from_filename("CNS-20260418-001.iter5.codex.response.v1.json") == 5
