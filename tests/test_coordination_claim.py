"""Tests for ``ao_kernel.coordination.claim`` — Claim dataclass + CAS helper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.coordination.claim import (
    claim_from_dict,
    claim_path,
    claim_revision,
    claim_to_dict,
    save_claim_cas,
)
from ao_kernel.coordination.errors import (
    ClaimCorruptedError,
    ClaimRevisionConflictError,
)


def _valid_claim_dict(**overrides: Any) -> dict[str, Any]:
    base = {
        "claim_id": "11111111-1111-4111-8111-111111111111",
        "owner_agent_id": "agent-alpha",
        "resource_id": "worktree-abc",
        "fencing_token": 0,
        "acquired_at": "2026-04-17T10:00:00+00:00",
        "heartbeat_at": "2026-04-17T10:00:00+00:00",
    }
    base.update(overrides)
    base["revision"] = claim_revision(base)
    return base


class TestClaimRevision:
    def test_hash_is_deterministic(self) -> None:
        doc = _valid_claim_dict()
        doc_no_rev = {k: v for k, v in doc.items() if k != "revision"}
        first = claim_revision(doc_no_rev)
        second = claim_revision(doc_no_rev)
        assert first == second

    def test_hash_ignores_revision_field(self) -> None:
        """Rehashing a claim dict with revision already set must match
        the hash computed WITHOUT the revision field."""
        doc = _valid_claim_dict()
        doc_no_rev = {k: v for k, v in doc.items() if k != "revision"}
        assert claim_revision(doc) == claim_revision(doc_no_rev)

    def test_different_fields_yield_different_hashes(self) -> None:
        d1 = _valid_claim_dict(fencing_token=0)
        d2 = _valid_claim_dict(fencing_token=1)
        # strip revision to compare content hashes directly
        d1.pop("revision")
        d2.pop("revision")
        assert claim_revision(d1) != claim_revision(d2)

    def test_hash_is_prefixed_sha256(self) -> None:
        doc = _valid_claim_dict()
        rev = claim_revision(doc)
        assert rev.startswith("sha256:")
        assert len(rev) == len("sha256:") + 64


class TestClaimSerialisation:
    def test_roundtrip_preserves_fields(self) -> None:
        doc = _valid_claim_dict(expires_at="2026-04-17T10:01:30+00:00")
        claim = claim_from_dict(doc)
        roundtripped = claim_to_dict(claim)
        assert claim_from_dict(roundtripped) == claim

    def test_roundtrip_without_expires_at(self) -> None:
        """``expires_at`` is optional; absence must round-trip cleanly."""
        doc = _valid_claim_dict()
        assert "expires_at" not in doc
        claim = claim_from_dict(doc)
        assert claim.expires_at is None
        roundtripped = claim_to_dict(claim)
        assert "expires_at" not in roundtripped

    def test_from_dict_accepts_minimal_valid(self) -> None:
        doc = _valid_claim_dict()
        claim = claim_from_dict(doc)
        assert claim.claim_id == doc["claim_id"]
        assert claim.fencing_token == 0
        assert claim.revision.startswith("sha256:")

    def test_from_dict_rejects_missing_required(self) -> None:
        doc = _valid_claim_dict()
        del doc["owner_agent_id"]
        # stamp revision after mutation so schema error, not hash mismatch, fires
        doc["revision"] = claim_revision(doc)
        with pytest.raises(ClaimCorruptedError) as excinfo:
            claim_from_dict(doc)
        assert "schema" in str(excinfo.value).lower()

    def test_from_dict_rejects_negative_fencing_token(self) -> None:
        doc = _valid_claim_dict()
        doc["fencing_token"] = -1
        doc["revision"] = claim_revision(doc)
        with pytest.raises(ClaimCorruptedError):
            claim_from_dict(doc)

    def test_from_dict_rejects_revision_mismatch(self) -> None:
        """Silent edits to on-disk claim JSON must be detected."""
        doc = _valid_claim_dict()
        # Mutate a field but LEAVE the stored revision untouched.
        doc["fencing_token"] = 99
        with pytest.raises(ClaimCorruptedError) as excinfo:
            claim_from_dict(doc, source_path=Path("/tmp/fake.json"))
        assert "revision hash mismatch" in str(excinfo.value)
        assert "fake.json" in str(excinfo.value)


class TestSaveClaimCas:
    def _write_existing(self, workspace_root: Path, doc: dict[str, Any]) -> None:
        path = claim_path(workspace_root, doc["resource_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True, ensure_ascii=False))

    def test_happy_path_updates_record(self, tmp_path: Path) -> None:
        original = _valid_claim_dict(heartbeat_at="2026-04-17T10:00:00+00:00")
        self._write_existing(tmp_path, original)
        updated = {**original, "heartbeat_at": "2026-04-17T10:00:30+00:00"}
        updated["revision"] = claim_revision(updated)
        save_claim_cas(
            tmp_path, original["resource_id"], updated,
            expected_revision=original["revision"],
        )
        on_disk = json.loads(claim_path(tmp_path, original["resource_id"]).read_text())
        assert on_disk["heartbeat_at"] == "2026-04-17T10:00:30+00:00"
        assert on_disk["revision"] == updated["revision"]

    def test_cas_conflict_raises(self, tmp_path: Path) -> None:
        original = _valid_claim_dict()
        self._write_existing(tmp_path, original)
        updated = {**original, "heartbeat_at": "2026-04-17T10:00:30+00:00"}
        updated["revision"] = claim_revision(updated)
        with pytest.raises(ClaimRevisionConflictError) as excinfo:
            save_claim_cas(
                tmp_path, original["resource_id"], updated,
                expected_revision="sha256:" + "0" * 64,  # wrong revision
            )
        assert excinfo.value.expected_revision.startswith("sha256:0")
        assert excinfo.value.actual_revision == original["revision"]

    def test_absent_file_raises_revision_conflict(self, tmp_path: Path) -> None:
        """save_claim_cas is the update path; absent file means the claim
        was released under us, which should surface as revision conflict."""
        doc = _valid_claim_dict()
        with pytest.raises(ClaimRevisionConflictError) as excinfo:
            save_claim_cas(
                tmp_path, doc["resource_id"], doc,
                expected_revision="sha256:" + "0" * 64,
            )
        assert excinfo.value.actual_revision == "<absent>"

    def test_stamped_revision_mismatch_rejected(self, tmp_path: Path) -> None:
        """Caller must stamp revision correctly before calling save_claim_cas."""
        original = _valid_claim_dict()
        self._write_existing(tmp_path, original)
        bad_update = {**original, "heartbeat_at": "2026-04-17T10:00:30+00:00"}
        # Deliberately do NOT restamp revision.
        with pytest.raises(ClaimCorruptedError) as excinfo:
            save_claim_cas(
                tmp_path, original["resource_id"], bad_update,
                expected_revision=original["revision"],
            )
        assert "stamped revision" in str(excinfo.value)

    def test_corrupt_on_disk_raises(self, tmp_path: Path) -> None:
        path = claim_path(tmp_path, "corrupt-resource")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {{{")
        doc = _valid_claim_dict(resource_id="corrupt-resource")
        with pytest.raises(ClaimCorruptedError) as excinfo:
            save_claim_cas(
                tmp_path, "corrupt-resource", doc,
                expected_revision="sha256:" + "0" * 64,
            )
        assert "JSON decode failed" in str(excinfo.value)
