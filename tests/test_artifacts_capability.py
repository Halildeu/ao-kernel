"""Tests for ``ao_kernel.executor.artifacts.write_capability_artifact``
(PR-B6 v4 commit 1).

Mirrors the existing ``write_artifact`` unit test coverage: atomic
write semantics + canonical JSON + SHA-256 digest + error paths. The
new helper adds a ``capability`` key to the filename template and
validates the capability against the schema pattern.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ao_kernel.executor.artifacts import write_capability_artifact


class TestHappyPath:
    def test_writes_file_and_returns_ref_and_digest(
        self, tmp_path: Path
    ) -> None:
        payload = {
            "schema_version": "1",
            "findings": [{"severity": "info", "message": "ok"}],
        }
        ref, digest = write_capability_artifact(
            run_dir=tmp_path,
            step_id="step-alpha",
            attempt=1,
            capability="review_findings",
            payload=payload,
        )

        assert ref == "artifacts/step-alpha-review_findings-attempt1.json"
        written = tmp_path / ref
        assert written.is_file()

        # Content is canonical JSON; digest matches.
        expected_body = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        assert written.read_bytes() == expected_body
        assert digest == hashlib.sha256(expected_body).hexdigest()

    def test_distinct_capabilities_write_distinct_files(
        self, tmp_path: Path
    ) -> None:
        ref_a, _ = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"a": 1},
        )
        ref_b, _ = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="commit_message",
            payload={"b": 2},
        )
        assert ref_a != ref_b
        assert (tmp_path / ref_a).is_file()
        assert (tmp_path / ref_b).is_file()

    def test_retry_attempts_write_distinct_files(self, tmp_path: Path) -> None:
        ref_a, _ = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"a": 1},
        )
        ref_b, _ = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=2,
            capability="review_findings",
            payload={"a": 2},
        )
        assert ref_a != ref_b
        assert "attempt1" in ref_a
        assert "attempt2" in ref_b

    def test_canonical_json_order_independent(self, tmp_path: Path) -> None:
        """Key ordering of input dict does not affect the canonical
        bytes — digest is stable across dict iteration orders."""
        _, d1 = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"b": 2, "a": 1},
        )
        # Reuse the same file (os.replace overwrites); same canonical
        # output must come out.
        _, d2 = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"a": 1, "b": 2},
        )
        assert d1 == d2


class TestParentDirAutoCreate:
    def test_creates_artifacts_dir_with_restricted_perms(
        self, tmp_path: Path
    ) -> None:
        """Parent ``artifacts/`` directory auto-created with mode 0o700
        (mirrors write_artifact contract)."""
        write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={},
        )
        artifacts_dir = tmp_path / "artifacts"
        assert artifacts_dir.is_dir()
        mode = artifacts_dir.stat().st_mode & 0o777
        # No world-access. Parent dir mode 0o700 on creation; umask may
        # relax it but world bits must remain zero.
        assert mode & 0o007 == 0


class TestValidation:
    def test_attempt_zero_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            write_capability_artifact(
                run_dir=tmp_path,
                step_id="s1",
                attempt=0,
                capability="review_findings",
                payload={},
            )

    def test_attempt_negative_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            write_capability_artifact(
                run_dir=tmp_path,
                step_id="s1",
                attempt=-1,
                capability="review_findings",
                payload={},
            )

    def test_capability_uppercase_rejected(self, tmp_path: Path) -> None:
        """Schema pattern ``^[a-z][a-z0-9_]{0,63}$`` rejects uppercase."""
        with pytest.raises(ValueError, match="capability must match"):
            write_capability_artifact(
                run_dir=tmp_path,
                step_id="s1",
                attempt=1,
                capability="ReviewFindings",
                payload={},
            )

    def test_capability_hyphen_rejected(self, tmp_path: Path) -> None:
        """Hyphen not in pattern (underscores only)."""
        with pytest.raises(ValueError, match="capability must match"):
            write_capability_artifact(
                run_dir=tmp_path,
                step_id="s1",
                attempt=1,
                capability="review-findings",
                payload={},
            )

    def test_capability_empty_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="capability must match"):
            write_capability_artifact(
                run_dir=tmp_path,
                step_id="s1",
                attempt=1,
                capability="",
                payload={},
            )


class TestAtomicWrite:
    def test_no_tempfile_left_after_success(self, tmp_path: Path) -> None:
        """Successful write leaves no ``*.tmp`` tempfiles."""
        write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"ok": True},
        )
        artifacts_dir = tmp_path / "artifacts"
        tempfiles = list(artifacts_dir.glob("*.tmp"))
        assert tempfiles == []

    def test_overwrite_same_target(self, tmp_path: Path) -> None:
        """Writing the same (step_id, capability, attempt) overwrites
        atomically (os.replace)."""
        ref_a, _ = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"v": 1},
        )
        ref_b, _ = write_capability_artifact(
            run_dir=tmp_path,
            step_id="s1",
            attempt=1,
            capability="review_findings",
            payload={"v": 2},
        )
        assert ref_a == ref_b
        # Second write content wins
        content = json.loads((tmp_path / ref_a).read_text(encoding="utf-8"))
        assert content == {"v": 2}
