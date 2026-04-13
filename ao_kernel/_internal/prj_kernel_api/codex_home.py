"""Program-led Codex home bootstrap (workspace-scoped, deterministic)."""

from __future__ import annotations
from ao_kernel._internal.shared.utils import write_text_atomic

import json
try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any, Dict


def _find_repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_toml(path: Path) -> Dict[str, Any]:
    return tomllib.loads(_read_text(path))


def _load_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(_read_text(path))
    return obj if isinstance(obj, dict) else {}


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(base)
    for key, value in overlay.items():
        existing = out.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            out[key] = _deep_merge(existing, value)
        else:
            out[key] = value
    return out


def _policy_candidates(*, repo_root: Path, workspace_root: Path) -> list[Path]:
    return [
        repo_root / "policies" / "policy_codex_runtime.v1.json",
        workspace_root / "policies" / "policy_codex_runtime.v1.json",
        workspace_root / ".cache" / "policy_overrides" / "policy_codex_runtime.override.v1.json",
    ]


def _runtime_overlay(*, repo_root: Path, workspace_root: Path) -> tuple[Dict[str, Any], list[str]]:
    overlay: Dict[str, Any] = {}
    sources: list[str] = []
    for path in _policy_candidates(repo_root=repo_root, workspace_root=workspace_root):
        if not path.exists():
            continue
        try:
            loaded = _load_json(path)
        except Exception:
            continue
        candidate = loaded.get("runtime_overlay") if isinstance(loaded.get("runtime_overlay"), dict) else None
        if not isinstance(candidate, dict):
            continue
        overlay = _deep_merge(overlay, candidate)
        sources.append(str(path))
    return overlay, sources


def _toml_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("\"", "\\\"")


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return f"\"{_toml_escape(value)}\""
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {type(value).__name__}")


def _render_table(lines: list[str], table: Dict[str, Any], prefix: str = "") -> None:
    scalar_items = []
    child_tables = []
    for key in sorted(table.keys()):
        value = table[key]
        if isinstance(value, dict):
            child_tables.append((key, value))
        else:
            scalar_items.append((key, value))

    if prefix:
        lines.append(f"[{prefix}]")
    for key, value in scalar_items:
        lines.append(f"{key} = {_toml_value(value)}")

    if scalar_items and child_tables:
        lines.append("")
    for index, (key, child) in enumerate(child_tables):
        next_prefix = f"{prefix}.{key}" if prefix else key
        _render_table(lines, child, next_prefix)
        if index != len(child_tables) - 1:
            lines.append("")


def _dump_toml(cfg: Dict[str, Any]) -> str:
    lines: list[str] = []
    _render_table(lines, cfg, "")
    return "\n".join(lines).rstrip() + "\n"


def resolve_effective_codex_config(workspace_root: str | Path) -> Dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    repo_root = _find_repo_root(Path(__file__).resolve())
    template_path = repo_root / ".codex" / "config.toml"
    if not template_path.exists():
        raise SystemExit("CODEX_HOME bootstrap failed: missing template .codex/config.toml.")

    template_cfg = _load_toml(template_path)
    overlay_cfg, overlay_sources = _runtime_overlay(repo_root=repo_root, workspace_root=workspace)
    effective_cfg = _deep_merge(template_cfg, overlay_cfg)
    return {
        "repo_root": str(repo_root),
        "workspace_root": str(workspace),
        "template_path": str(template_path),
        "overlay_sources": overlay_sources,
        "template_config": template_cfg,
        "overlay_config": overlay_cfg,
        "effective_config": effective_cfg,
        "rendered_toml": _dump_toml(effective_cfg),
    }


def ensure_codex_home(workspace_root: str) -> Dict[str, str]:
    ws = Path(workspace_root).resolve()
    target = ws / ".cache" / "codex_home"
    target.mkdir(parents=True, exist_ok=True)

    resolved = resolve_effective_codex_config(ws)
    config_path = target / "config.toml"
    rendered = str(resolved.get("rendered_toml") or "")
    current = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if current != rendered:
        write_text_atomic(config_path, rendered)

    env_overrides = {"CODEX_HOME": str(target)}
    overlay_sources = resolved.get("overlay_sources")
    if isinstance(overlay_sources, list) and overlay_sources:
        env_overrides["CODEX_RUNTIME_POLICY_SOURCE"] = ",".join(str(item) for item in overlay_sources if isinstance(item, str))
    return env_overrides
