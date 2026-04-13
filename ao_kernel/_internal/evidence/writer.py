from __future__ import annotations
from ao_kernel._internal.shared.utils import write_text_atomic

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from ao_kernel._internal.utils.jsonio import save_json


def _sha256_file(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_concat_files(paths: list[Path]) -> str:
    h = sha256()
    for p in paths:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _append_text(path: Path, text: str) -> None:
    normalized = text if text.endswith("\n") else (text + "\n")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(normalized)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _git_commit_and_dirty(workspace: Path) -> tuple[str, bool]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=workspace,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return ("unknown", False)

    if proc.returncode != 0 or proc.stdout.strip() != "true":
        return ("unknown", False)

    commit = "unknown"
    dirty = False

    commit_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, text=True, capture_output=True)
    if commit_proc.returncode == 0:
        c = (commit_proc.stdout or "").strip()
        if c:
            commit = c

    status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=workspace, text=True, capture_output=True)
    if status_proc.returncode == 0:
        dirty = bool((status_proc.stdout or "").strip())

    return (commit, dirty)


def _hash_json_dir(workspace: Path, rel_dir: str) -> str:
    d = workspace / rel_dir
    paths: list[Path] = []
    if d.exists():
        paths = [p for p in d.glob("*.json") if p.is_file()]
    paths = sorted(paths, key=lambda p: p.relative_to(workspace).as_posix())
    return _sha256_concat_files(paths)


@dataclass(frozen=True)
class EvidenceWriter:
    out_dir: Path
    run_id: str

    @property
    def run_dir(self) -> Path:
        return self.out_dir / self.run_id

    def write_request(self, envelope: dict) -> None:
        save_json(self.run_dir / "request.json", envelope)

    def write_summary(self, summary: dict) -> None:
        save_json(self.run_dir / "summary.json", summary)

    def write_closeout(self, closeout: dict[str, Any]) -> None:
        save_json(self.run_dir / "closeout.v1.json", closeout)

    def write_suspend(self, suspend: dict) -> None:
        save_json(self.run_dir / "suspend.json", suspend)

    def write_resume_log(self, text: str) -> None:
        p = self.run_dir / "resume.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(p, text if text.endswith("\n") else (text + "\n"))

    def write_node_input(self, node_id: str, data: Any) -> None:
        save_json(self.run_dir / "nodes" / node_id / "input.json", data)

    def write_node_output(self, node_id: str, data: Any) -> None:
        save_json(self.run_dir / "nodes" / node_id / "output.json", data)

    def write_node_log(self, node_id: str, text: str) -> None:
        node_dir = self.run_dir / "nodes" / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        _append_text(node_dir / "logs.txt", text)
        _append_jsonl(
            node_dir / "events.v1.jsonl",
            {
                "version": "v1",
                "event_type": "NODE_LOG",
                "ts": _now_iso(),
                "run_id": self.run_id,
                "node_id": node_id,
                "message": str(text).rstrip("\n"),
            },
        )

    def write_provenance(self, *, workspace: Path, summary: dict[str, Any]) -> None:
        commit, dirty = _git_commit_and_dirty(workspace)

        governor_dir = workspace / "governor"
        governor_hash = "none" if not governor_dir.exists() else _hash_json_dir(workspace, "governor")

        workflow_fingerprint = (
            summary.get("workflow_fingerprint") if isinstance(summary.get("workflow_fingerprint"), str) else None
        )
        provider_used = summary.get("provider_used") if isinstance(summary.get("provider_used"), str) else "unknown"
        model_used = summary.get("model_used") if isinstance(summary.get("model_used"), str) else None

        provenance = {
            "version": "v1",
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git": {"commit": commit, "dirty": bool(dirty)},
            "fingerprints": {
                "workflow_fingerprint": workflow_fingerprint,
                "policies_hash": _hash_json_dir(workspace, "policies"),
                "registry_hash": _hash_json_dir(workspace, "registry"),
                "orchestrator_hash": _hash_json_dir(workspace, "orchestrator"),
                "governor_hash": governor_hash,
            },
            "provider": {"provider_used": provider_used, "model_used": model_used},
        }
        execution_target = summary.get("execution_target") if isinstance(summary.get("execution_target"), dict) else {}
        if execution_target:
            provenance["execution_target"] = execution_target
        save_json(self.run_dir / "provenance.v1.json", provenance)

    def write_integrity_manifest(self) -> None:
        run_dir = self.run_dir
        run_dir.mkdir(parents=True, exist_ok=True)

        manifest_name = "integrity.manifest.v1.json"
        manifest_path = run_dir / manifest_name

        files: list[dict[str, str]] = []
        for p in run_dir.rglob("*"):
            if not p.is_file():
                continue

            rel = p.relative_to(run_dir).as_posix()
            if rel == manifest_name:
                continue
            files.append({"path": rel, "sha256": _sha256_file(p)})

        files.sort(key=lambda x: x["path"])
        manifest = {
            "version": "v1",
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }
        save_json(manifest_path, manifest)
