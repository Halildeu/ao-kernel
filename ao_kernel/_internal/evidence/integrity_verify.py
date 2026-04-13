from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any


MANIFEST_NAME = "integrity.manifest.v1.json"


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_shape_invalid() -> dict[str, Any]:
    return {"status": "MISMATCH", "missing_files": [], "mismatched_files": [MANIFEST_NAME]}


def verify_run_dir(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return {"status": "MISSING", "missing_files": [MANIFEST_NAME], "mismatched_files": []}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return _manifest_shape_invalid()

    if not isinstance(manifest, dict):
        return _manifest_shape_invalid()

    file_entries = manifest.get("files")
    if not isinstance(file_entries, list):
        return _manifest_shape_invalid()

    missing_files: list[str] = []
    mismatched_files: list[str] = []

    normalized: list[tuple[str, str]] = []
    for entry in file_entries:
        if not isinstance(entry, dict):
            return _manifest_shape_invalid()
        rel_path = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(rel_path, str) or not rel_path:
            return _manifest_shape_invalid()
        if not isinstance(expected, str) or len(expected) != 64:
            return _manifest_shape_invalid()
        normalized.append((rel_path, expected))

    for rel_path, expected in sorted(normalized, key=lambda x: x[0]):
        p = run_dir / rel_path
        if not p.exists():
            missing_files.append(rel_path)
            continue
        if not p.is_file():
            missing_files.append(rel_path)
            continue
        actual = _sha256_file(p)
        if actual != expected:
            mismatched_files.append(rel_path)

    if missing_files:
        return {
            "status": "MISSING",
            "missing_files": sorted(missing_files),
            "mismatched_files": sorted(mismatched_files),
        }
    if mismatched_files:
        return {
            "status": "MISMATCH",
            "missing_files": [],
            "mismatched_files": sorted(mismatched_files),
        }
    return {"status": "OK", "missing_files": [], "mismatched_files": []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.evidence.integrity_verify")
    ap.add_argument("--run", required=True, help="Path to evidence/<run_id> directory.")
    args = ap.parse_args(argv)

    payload = verify_run_dir(Path(args.run))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

    status = payload.get("status")
    if status == "OK":
        return 0
    if status == "MISSING":
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
