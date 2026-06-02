"""Tests for ao_kernel.project_sync.manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ao_kernel.project_sync import ProjectionManifest, ProjectSyncError


def _sample_payload() -> dict[str, object]:
    return {
        "schema_version": "v5-issue-projection.v1",
        "runtime_created_state": {
            "project_board": {
                "number": 3,
                "node_id": "PVT_kwHOCx7tY84BZW65",
                "title": "Roadmap v5.0.0",
            },
            "milestone": {"title": "v5.0.0 — Full Production Promotion"},
            "issues_created": {"E-1": 774, "E-2": 775},
        },
    }


def test_manifest_load_round_trip(tmp_path: Path) -> None:
    """Loaded payload matches the on-disk JSON exactly."""
    path = tmp_path / "manifest.json"
    payload = _sample_payload()
    path.write_text(json.dumps(payload), encoding="utf-8")
    manifest = ProjectionManifest.load(path)
    assert manifest.payload == payload


def test_manifest_load_missing_file_fails_closed(tmp_path: Path) -> None:
    """Missing manifest file raises ProjectSyncError per fail-closed contract."""
    missing = tmp_path / "nope.json"
    with pytest.raises(ProjectSyncError) as exc_info:
        ProjectionManifest.load(missing)
    assert "not found" in str(exc_info.value)


def test_manifest_load_invalid_json_fails_closed(tmp_path: Path) -> None:
    """Non-JSON text in the manifest is rejected, not silently empty."""
    path = tmp_path / "bad.json"
    path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(ProjectSyncError) as exc_info:
        ProjectionManifest.load(path)
    assert "valid JSON" in str(exc_info.value)


def test_manifest_digest_is_deterministic(tmp_path: Path) -> None:
    """Same payload -> same digest, even with shuffled top-level keys."""
    payload_a = _sample_payload()
    payload_b = {key: payload_a[key] for key in reversed(list(payload_a))}
    manifest_a = ProjectionManifest(path=tmp_path / "a.json", payload=payload_a)
    manifest_b = ProjectionManifest(path=tmp_path / "b.json", payload=payload_b)
    assert manifest_a.digest() == manifest_b.digest()
    assert manifest_a.digest().startswith("sha256:")


def test_manifest_save_serialises_sorted_keys(tmp_path: Path) -> None:
    """Save produces canonical sorted-key JSON for stable diffs."""
    path = tmp_path / "manifest.json"
    payload = {"z": 1, "a": 2, "m": 3}
    manifest = ProjectionManifest(path=path, payload=payload)
    manifest.save()
    text = path.read_text(encoding="utf-8")
    assert text.index('"a"') < text.index('"m"') < text.index('"z"')


def test_manifest_helpers_extract_runtime_state(tmp_path: Path) -> None:
    """project_node_id / project_number / issues_created accessors work."""
    manifest = ProjectionManifest(path=tmp_path / "m.json", payload=_sample_payload())
    assert manifest.project_node_id() == "PVT_kwHOCx7tY84BZW65"
    assert manifest.project_number() == 3
    assert manifest.issues_created() == {"E-1": 774, "E-2": 775}


def test_manifest_helpers_handle_missing_runtime(tmp_path: Path) -> None:
    """Helpers return None / empty when the runtime block is absent."""
    manifest = ProjectionManifest(path=tmp_path / "m.json", payload={"schema_version": "v1"})
    assert manifest.project_node_id() is None
    assert manifest.project_number() is None
    assert manifest.issues_created() == {}
