"""Tests for evidence integrity verification — all verify_run_dir() branches."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from ao_kernel._internal.evidence.integrity_verify import MANIFEST_NAME, verify_run_dir


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


class TestVerifyRunDir:
    def test_ok_matching_manifest(self, tmp_path: Path):
        """All files present and hashes match → OK."""
        content = b'{"key": "value"}'
        (tmp_path / "request.json").write_bytes(content)
        manifest = {
            "files": [
                {"path": "request.json", "sha256": _sha256_bytes(content)},
            ]
        }
        (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "OK"
        assert result["missing_files"] == []
        assert result["mismatched_files"] == []

    def test_missing_manifest(self, tmp_path: Path):
        """No manifest file → MISSING with manifest in missing_files."""
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISSING"
        assert MANIFEST_NAME in result["missing_files"]

    def test_missing_referenced_file(self, tmp_path: Path):
        """Manifest references a file that doesn't exist → MISSING."""
        manifest = {
            "files": [
                {"path": "nonexistent.json", "sha256": "a" * 64},
            ]
        }
        (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISSING"
        assert "nonexistent.json" in result["missing_files"]

    def test_hash_mismatch(self, tmp_path: Path):
        """File exists but hash doesn't match → MISMATCH."""
        (tmp_path / "data.json").write_bytes(b'{"real": "content"}')
        manifest = {
            "files": [
                {"path": "data.json", "sha256": "0" * 64},
            ]
        }
        (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISMATCH"
        assert "data.json" in result["mismatched_files"]

    def test_manifest_invalid_json(self, tmp_path: Path):
        """Manifest is not valid JSON → MISMATCH (shape invalid)."""
        (tmp_path / MANIFEST_NAME).write_text("not json {{{")
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISMATCH"
        assert MANIFEST_NAME in result["mismatched_files"]

    def test_manifest_not_dict(self, tmp_path: Path):
        """Manifest is valid JSON but not a dict → MISMATCH."""
        (tmp_path / MANIFEST_NAME).write_text(json.dumps([1, 2, 3]))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISMATCH"

    def test_manifest_files_not_list(self, tmp_path: Path):
        """Manifest has 'files' but it's not a list → MISMATCH."""
        (tmp_path / MANIFEST_NAME).write_text(json.dumps({"files": "not_a_list"}))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISMATCH"

    def test_manifest_entry_bad_sha_length(self, tmp_path: Path):
        """Manifest entry has sha256 with wrong length → MISMATCH."""
        (tmp_path / "file.json").write_bytes(b"{}")
        manifest = {"files": [{"path": "file.json", "sha256": "tooshort"}]}
        (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISMATCH"

    def test_multiple_files_mixed_status(self, tmp_path: Path):
        """One file OK, one missing → MISSING takes precedence."""
        good_content = b'{"ok": true}'
        (tmp_path / "good.json").write_bytes(good_content)
        manifest = {
            "files": [
                {"path": "good.json", "sha256": _sha256_bytes(good_content)},
                {"path": "gone.json", "sha256": "a" * 64},
            ]
        }
        (tmp_path / MANIFEST_NAME).write_text(json.dumps(manifest))
        result = verify_run_dir(tmp_path)
        assert result["status"] == "MISSING"
        assert "gone.json" in result["missing_files"]
        assert "good.json" not in result["mismatched_files"]
