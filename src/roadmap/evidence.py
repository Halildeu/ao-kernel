from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from src.shared.utils import write_json_atomic, write_text_atomic

MANIFEST_NAME = "integrity.manifest.v1.json"


def _now_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, obj)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, text)


@dataclass(frozen=True)
class RoadmapEvidencePaths:
    run_dir: Path
    roadmap_path: Path
    plan_path: Path
    summary_path: Path
    dlq_path: Path
    steps_dir: Path


def init_evidence_dir(evidence_root: Path, run_id: str) -> RoadmapEvidencePaths:
    run_dir = (evidence_root / run_id).resolve()
    steps_dir = run_dir / "steps"
    run_dir.mkdir(parents=True, exist_ok=True)
    steps_dir.mkdir(parents=True, exist_ok=True)
    return RoadmapEvidencePaths(
        run_dir=run_dir,
        roadmap_path=run_dir / "roadmap.json",
        plan_path=run_dir / "plan.json",
        summary_path=run_dir / "summary.json",
        dlq_path=run_dir / "dlq.json",
        steps_dir=steps_dir,
    )


def write_step_evidence(paths: RoadmapEvidencePaths, step_id: str, *, step_input: Any, step_output: Any, logs: str) -> None:
    step_dir = paths.steps_dir / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    write_json(step_dir / "input.json", step_input)
    write_json(step_dir / "output.json", step_output)
    write_text(step_dir / "logs.txt", logs)


def write_integrity_manifest(run_dir: Path) -> None:
    run_dir = run_dir.resolve()
    entries: list[dict[str, str]] = []
    for p in sorted([p for p in run_dir.rglob("*") if p.is_file()], key=lambda x: x.as_posix()):
        if p.name == MANIFEST_NAME:
            continue
        rel = p.relative_to(run_dir).as_posix()
        entries.append({"path": rel, "sha256": _sha256_file(p)})

    manifest = {
        "version": "v1",
        "run_id": run_dir.name,
        "created_at": _now_iso8601(),
        "files": sorted(entries, key=lambda e: e["path"]),
    }
    write_json(run_dir / MANIFEST_NAME, manifest)

