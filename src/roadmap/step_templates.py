from __future__ import annotations
from src.shared.utils import write_text_atomic

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

class RoadmapStepError(RuntimeError):
    def __init__(self, error_code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}


def _ensure_inside_workspace(workspace: Path, target: Path) -> None:
    workspace = workspace.resolve()
    target = target.resolve()
    try:
        target.relative_to(workspace)
    except Exception as e:
        raise RoadmapStepError("WORKSPACE_ROOT_VIOLATION", f"Path escapes workspace_root: {target}") from e


@dataclass
class VirtualFS:
    # Dry-run virtual filesystem overlay.
    files: dict[str, str]

    def get_text(self, rel_path: str, workspace: Path) -> str | None:
        if rel_path in self.files:
            return self.files[rel_path]
        p = (workspace / rel_path).resolve()
        if not p.exists() or not p.is_file():
            return None
        return p.read_text(encoding="utf-8")

    def set_text(self, rel_path: str, text: str) -> None:
        self.files[rel_path] = text

    def would_exist(self, rel_path: str, workspace: Path) -> bool:
        if rel_path in self.files:
            return True
        p = (workspace / rel_path).resolve()
        return p.exists()


def step_create_file(*, workspace: Path, virtual_fs: VirtualFS, path: str, content: str, overwrite: bool, dry_run: bool) -> dict[str, Any]:
    rel = Path(path).as_posix()
    p = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, p)

    exists = p.exists() or (rel in virtual_fs.files)
    if exists and not overwrite:
        existing = virtual_fs.get_text(rel, workspace)
        if existing == content:
            return {"status": "OK", "side_effects": {"noop": {"path": rel}}}
        raise RoadmapStepError("CONTENT_MISMATCH", f"File exists with different content (overwrite=false): {rel}")

    if dry_run:
        virtual_fs.set_text(rel, content)
        return {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_write": {"path": rel, "bytes_estimate": len(content.encode('utf-8'))}}}

    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(p, content)
    return {"status": "OK", "side_effects": {"wrote": {"path": rel, "bytes": len(content.encode('utf-8'))}}}


def step_ensure_dir(*, workspace: Path, path: str, dry_run: bool) -> dict[str, Any]:
    rel = Path(path).as_posix()
    p = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, p)
    if dry_run:
        return {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_create_dir": {"path": rel}}}
    p.mkdir(parents=True, exist_ok=True)
    return {"status": "OK", "side_effects": {"created_dir": {"path": rel}}}


def _json_text(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def step_create_json_from_template(
    *,
    workspace: Path,
    virtual_fs: VirtualFS,
    path: str,
    json_obj: Any,
    overwrite: bool,
    dry_run: bool,
) -> tuple[dict[str, Any], str, str]:
    rel = Path(path).as_posix()
    p = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, p)

    content = _json_text(json_obj)
    exists = p.exists() or (rel in virtual_fs.files)
    old = virtual_fs.get_text(rel, workspace) or ""
    if exists and not overwrite:
        if old == content:
            return ({"status": "OK", "side_effects": {"noop": {"path": rel}}}, old, content)
        try:
            existing_obj = json.loads(old)
        except json.JSONDecodeError:
            existing_obj = None
        if existing_obj is not None and existing_obj == json_obj:
            return ({"status": "OK", "side_effects": {"noop": {"path": rel}}}, old, content)
        raise RoadmapStepError("CONTENT_MISMATCH", f"File exists with different content (overwrite=false): {rel}")
    if dry_run:
        virtual_fs.set_text(rel, content)
        return (
            {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_write": {"path": rel, "bytes_estimate": len(content.encode('utf-8'))}}},
            old,
            content,
        )

    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(p, content)
    return ({"status": "OK", "side_effects": {"wrote": {"path": rel, "bytes": len(content.encode('utf-8'))}}}, old, content)


def step_add_schema_file(
    *,
    workspace: Path,
    virtual_fs: VirtualFS,
    path: str,
    schema_json: Any,
    dry_run: bool,
) -> tuple[dict[str, Any], str, str]:
    if not isinstance(schema_json, dict):
        raise RoadmapStepError("SCHEMA_INVALID", "add_schema_file schema_json must be an object")
    try:
        Draft202012Validator.check_schema(schema_json)
    except Exception as e:
        raise RoadmapStepError("SCHEMA_INVALID", "add_schema_file schema_json must be Draft 2020-12 valid") from e
    return step_create_json_from_template(
        workspace=workspace,
        virtual_fs=virtual_fs,
        path=path,
        json_obj=schema_json,
        overwrite=False,
        dry_run=dry_run,
    )


def step_add_ci_gate_script(
    *,
    workspace: Path,
    virtual_fs: VirtualFS,
    path: str,
    content: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[dict[str, Any], str, str]:
    rel = Path(path).as_posix()
    p = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, p)

    exists = p.exists() or (rel in virtual_fs.files)
    old = virtual_fs.get_text(rel, workspace) or ""
    if exists and not overwrite:
        if old == content:
            return ({"status": "OK", "side_effects": {"noop": {"path": rel}}}, old, content)
        raise RoadmapStepError("CONTENT_MISMATCH", f"File exists with different content (overwrite=false): {rel}")
    if dry_run:
        virtual_fs.set_text(rel, content)
        return (
            {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_write": {"path": rel, "bytes_estimate": len(content.encode('utf-8'))}}},
            old,
            content,
        )

    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(p, content)
    return ({"status": "OK", "side_effects": {"wrote": {"path": rel, "bytes": len(content.encode('utf-8'))}}}, old, content)


def step_patch_policy_report_inject(
    *,
    workspace: Path,
    virtual_fs: VirtualFS,
    target: str,
    marker: str,
    insert_text: str,
    dry_run: bool,
) -> tuple[dict[str, Any], str, str]:
    rel = Path(target).as_posix()
    p = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, p)
    old = virtual_fs.get_text(rel, workspace)
    if old is None:
        raise RoadmapStepError("FILE_NOT_FOUND", f"Target file not found: {rel}")

    if marker not in old:
        raise RoadmapStepError("MARKER_NOT_FOUND", f"Marker not found in {rel}: {marker!r}")

    new = old.replace(marker, marker + insert_text)
    if dry_run:
        virtual_fs.set_text(rel, new)
        return (
            {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_patch": {"path": rel, "marker": marker}}},
            old,
            new,
        )
    write_text_atomic(p, new)
    return (
        {"status": "OK", "side_effects": {"patched": {"path": rel, "marker": marker}}},
        old,
        new,
    )


def step_patch_file(*, workspace: Path, virtual_fs: VirtualFS, path: str, patches: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    rel = Path(path).as_posix()
    p = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, p)

    current = virtual_fs.get_text(rel, workspace)
    if current is None:
        raise RoadmapStepError("FILE_NOT_FOUND", f"File not found for patch_file: {rel}")

    new_text = current
    applied = 0
    for patch in patches:
        pat = patch.get("pattern")
        rep = patch.get("replacement")
        if not isinstance(pat, str) or not pat:
            raise RoadmapStepError("PATCH_INVALID", "patch_file patch.pattern must be a non-empty string")
        if not isinstance(rep, str):
            raise RoadmapStepError("PATCH_INVALID", "patch_file patch.replacement must be a string")
        if pat not in new_text:
            raise RoadmapStepError("PATTERN_NOT_FOUND", f"Pattern not found in {rel}: {pat!r}")
        new_text = new_text.replace(pat, rep)
        applied += 1

    if dry_run:
        virtual_fs.set_text(rel, new_text)
        return {"status": "SKIPPED_DRY_RUN", "side_effects": {"would_patch": {"path": rel, "patches_applied": applied}}}

    write_text_atomic(p, new_text)
    return {"status": "OK", "side_effects": {"patched": {"path": rel, "patches_applied": applied}}}


def step_run_cmd(
    *,
    workspace: Path,
    cmd: str,
    must_succeed: bool,
    dry_run: bool,
    env_overrides: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    if dry_run:
        return ({"status": "SKIPPED_DRY_RUN", "side_effects": {"would_run": {"cmd": cmd}}}, "")

    argv = shlex.split(cmd)
    if not argv:
        raise RoadmapStepError("CMD_INVALID", "run_cmd cmd is empty")

    env = os.environ.copy()
    # Prevent recursive roadmap-runner smoke loops when run_cmd calls smoke_test.py.
    env["ORCH_ROADMAP_RUNNER"] = "1"
    if env_overrides:
        for k, v in env_overrides.items():
            env[str(k)] = str(v)

    try:
        proc = subprocess.run(
            argv,
            cwd=str(workspace),
            text=True,
            capture_output=True,
            env=env,
        )
    except FileNotFoundError:
        if argv[0] in {"python", "python3"}:
            argv = [sys.executable, *argv[1:]]
            proc = subprocess.run(
                argv,
                cwd=str(workspace),
                text=True,
                capture_output=True,
                env=env,
            )
        else:
            raise

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    logs = stdout + ("\n" if stdout and stderr else "") + stderr

    if must_succeed and proc.returncode != 0:
        def _tail(text: str, max_lines: int = 8) -> str:
            lines = [ln for ln in (text or "").splitlines() if ln.strip()]
            if not lines:
                return ""
            return "\n".join(lines[-max_lines:])

        raise RoadmapStepError(
            "CMD_FAILED",
            f"run_cmd failed rc={proc.returncode}",
            details={
                "cmd": cmd,
                "argv": [str(x) for x in argv],
                "cwd": str(workspace),
                "return_code": int(proc.returncode),
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
            },
        )

    return (
        {
            "status": "OK" if proc.returncode == 0 else "FAIL",
            "side_effects": {"ran": {"cmd": cmd, "return_code": proc.returncode}},
            "return_code": proc.returncode,
        },
        logs,
    )


def step_assert_paths_exist(*, workspace: Path, virtual_fs: VirtualFS, paths: list[str]) -> dict[str, Any]:
    missing: list[str] = []
    for raw in paths:
        rel = Path(str(raw)).as_posix()
        p = (workspace / rel).resolve()
        _ensure_inside_workspace(workspace, p)
        if not virtual_fs.would_exist(rel, workspace):
            missing.append(rel)

    if missing:
        raise RoadmapStepError("PATHS_MISSING", "Missing required paths: " + ", ".join(sorted(missing)))
    return {"status": "OK", "side_effects": {"asserted": {"paths": [Path(p).as_posix() for p in paths]}}}

def step_assert_pointer_target_exists(*, workspace: Path, pointer_path: str) -> dict[str, Any]:
    rel = Path(pointer_path).as_posix()
    pointer_file = (workspace / rel).resolve()
    _ensure_inside_workspace(workspace, pointer_file)
    if not pointer_file.exists():
        raise RoadmapStepError("POINTER_MISSING", f"Pointer file missing: {rel}")
    try:
        obj = json.loads(pointer_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise RoadmapStepError("POINTER_INVALID", f"Pointer file invalid JSON: {rel}") from e
    if not isinstance(obj, dict):
        raise RoadmapStepError("POINTER_INVALID", f"Pointer file must be object: {rel}")
    stored = obj.get("stored_path")
    if not isinstance(stored, str) or not stored.strip():
        raise RoadmapStepError("POINTER_INVALID", f"Pointer missing stored_path: {rel}")
    stored_rel = Path(stored).as_posix()
    stored_path = (workspace / stored_rel).resolve()
    _ensure_inside_workspace(workspace, stored_path)
    if not stored_path.exists():
        raise RoadmapStepError("POINTER_TARGET_MISSING", f"Pointer target missing: {stored_rel}")
    return {"status": "OK", "side_effects": {"asserted_pointer": {"pointer_path": rel, "stored_path": stored_rel}}}

def step_assert_core_paths_exist(*, core_root: Path, paths: list[str]) -> dict[str, Any]:
    core_root = core_root.resolve()

    missing: list[str] = []
    for raw in paths:
        rel = Path(str(raw)).as_posix()
        p = (core_root / rel).resolve()
        try:
            p.relative_to(core_root)
        except Exception as e:
            raise RoadmapStepError("CORE_PATH_INVALID", f"Core path escapes core_root: {rel}") from e
        if not p.exists():
            missing.append(rel)

    if missing:
        raise RoadmapStepError("CORE_PATH_MISSING", "Missing required core paths: " + ", ".join(sorted(missing)))
    return {"status": "OK", "side_effects": {"asserted_core_paths": {"paths": [Path(p).as_posix() for p in paths]}}}


def step_iso_core_check(*, workspace: Path, tenant: str, required_files: list[str]) -> dict[str, Any]:
    tenant_id = str(tenant).strip()
    if not tenant_id:
        raise RoadmapStepError("ISO_CORE_INVALID", "iso_core_check tenant must be non-empty")

    base = (workspace / "tenant" / tenant_id).resolve()
    _ensure_inside_workspace(workspace, base)

    missing: list[str] = []
    for rf in required_files:
        rel = Path(str(rf)).as_posix()
        p = (base / rel).resolve()
        _ensure_inside_workspace(workspace, p)
        if not p.exists() or not p.is_file():
            missing.append(str(Path("tenant") / tenant_id / rel))

    if missing:
        raise RoadmapStepError("ISO_CORE_MISSING", "Missing ISO core files: " + ", ".join(sorted(missing)))

    return {"status": "OK", "side_effects": {"iso_core_ok": {"tenant": tenant_id, "files": [Path(f).as_posix() for f in required_files]}}}
