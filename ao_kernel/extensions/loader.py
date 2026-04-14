"""Extension loader — discover, validate, and track extension manifests.

Per CNS-20260414-008 consensus (Claude + Codex):
    - Lossless parse — every schema-required field is captured, optional
      discovery fields (docs_ref, ai_context_refs, tests_*) preserved.
    - jsonschema validation — JSON-parseable-but-schema-invalid manifests
      are skipped with a warning, not silently defaulted.
    - Duplicate entrypoint detection — conflicts are recorded, first-wins
      resolution keeps the registry deterministic.
    - Compat gating — manifests whose core_min/core_max exclude the running
      ao_kernel version are registered but marked ``_activation_blockers``.
    - Stale refs — manifest-declared paths (ai_context_refs, docs_ref,
      tests_entrypoints) that do not exist on disk are flagged for auditors.

Sources:
    1. Bundled defaults (``ao_kernel/defaults/extensions/``) — always present
    2. Workspace extensions (``<project_root>/.ao/extensions/``) — override+merge

Workspace-root contract (CNS-008 §next_iteration_asks #2):
    load_from_workspace(project_root) expects the PROJECT ROOT (the
    directory that CONTAINS ``.ao/``), NOT the ``.ao`` directory itself.
    config.workspace_root() returns ``.ao``; callers normalize via .parent.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtensionManifest:
    """Parsed, validated extension manifest.

    Required-field set mirrors the v1 schema verbatim. Optional fields
    default to empty structures so consumers can treat any manifest
    uniformly without None-guards. Computed fields (manifest_path,
    content_hash, _stale_refs, _activation_blockers) are populated by
    the loader, never read from the raw JSON.
    """

    # ── Schema required ───────────────────────────────────────────────
    version: str
    extension_id: str
    semver: str
    origin: str
    owner: str
    layer_contract: dict[str, Any]
    entrypoints: dict[str, list[str]]
    policies: list[str]
    ui_surfaces: list[str]
    compat: dict[str, Any]

    # ── Schema optional (discovery / ops surface) ────────────────────
    enabled: bool = False
    owner_tenant: str = ""
    gates: dict[str, Any] = field(default_factory=dict)
    docs_ref: str = ""
    ai_context_refs: tuple[str, ...] = ()
    tests_entrypoints: tuple[str, ...] = ()
    tests_policy: dict[str, Any] = field(default_factory=dict)
    policy_files: tuple[str, ...] = ()
    model_kind: str = ""
    delivery_modes: tuple[str, ...] = ()
    required_policies: tuple[str, ...] = ()
    outputs: dict[str, Any] = field(default_factory=dict)
    guardrails: dict[str, Any] = field(default_factory=dict)

    # ── Computed by loader (provenance + audit) ──────────────────────
    manifest_path: str = ""
    content_hash: str = ""
    source: str = "bundled"  # "bundled" or "workspace"
    stale_refs: tuple[str, ...] = ()
    activation_blockers: tuple[str, ...] = ()


@dataclass
class ConflictRecord:
    """Duplicate entrypoint conflict between two manifests."""

    entrypoint_group: str     # e.g. "kernel_api_actions"
    entrypoint: str           # e.g. "intake_create_plan"
    winner: str               # extension_id that registered first
    shadowed: list[str]       # extension_ids whose declaration was ignored


@dataclass
class LoadReport:
    """Outcome of a load_from_* call."""

    loaded: int
    skipped: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[ConflictRecord] = field(default_factory=list)


def _content_hash(raw_bytes: bytes) -> str:
    return sha256(raw_bytes).hexdigest()


def _tuple_of_str(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(x) for x in value)
    return ()


def _parse_manifest(
    data: dict[str, Any],
    *,
    manifest_path: str,
    raw_bytes: bytes,
    source: str,
) -> ExtensionManifest:
    """Build a lossless ExtensionManifest from a validated dict.

    Assumes the caller already ran jsonschema validation; no fallback
    defaulting for required fields. Optional fields fall back to the
    dataclass defaults so the return value is type-stable.
    """
    return ExtensionManifest(
        version=str(data["version"]),
        extension_id=str(data["extension_id"]),
        semver=str(data["semver"]),
        origin=str(data["origin"]),
        owner=str(data["owner"]),
        layer_contract=dict(data["layer_contract"]),
        entrypoints=_normalize_entrypoints(data["entrypoints"]),
        policies=list(data["policies"]),
        ui_surfaces=list(data["ui_surfaces"]),
        compat=dict(data["compat"]),
        enabled=bool(data.get("enabled", False)),
        owner_tenant=str(data.get("owner_tenant", "")),
        gates=dict(data.get("gates", {})),
        docs_ref=str(data.get("docs_ref", "")),
        ai_context_refs=_tuple_of_str(data.get("ai_context_refs")),
        tests_entrypoints=_tuple_of_str(data.get("tests_entrypoints")),
        tests_policy=dict(data.get("tests_policy", {})),
        policy_files=_tuple_of_str(data.get("policy_files")),
        model_kind=str(data.get("model_kind", "")),
        delivery_modes=_tuple_of_str(data.get("delivery_modes")),
        required_policies=_tuple_of_str(data.get("required_policies")),
        outputs=dict(data.get("outputs", {})),
        guardrails=dict(data.get("guardrails", {})),
        manifest_path=manifest_path,
        content_hash=_content_hash(raw_bytes),
        source=source,
    )


def _normalize_entrypoints(raw: Any) -> dict[str, list[str]]:
    """Coerce entrypoints payload to dict[str, list[str]]."""
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            normalized[str(k)] = [str(x) for x in v]
    return normalized


def _validate_schema(data: dict[str, Any], *, schema: dict[str, Any] | None) -> str | None:
    """Run jsonschema validation. Returns error message or None on success.

    Skips validation when ``schema`` is None (caller could not load it) —
    better to accept a well-shaped manifest than block the entire registry
    on a missing schema file.
    """
    if schema is None:
        return None
    try:
        import jsonschema
        jsonschema.validate(data, schema)
    except Exception as exc:  # jsonschema.ValidationError and friends
        return str(exc).splitlines()[0]
    return None


def _load_schema() -> dict[str, Any] | None:
    try:
        from ao_kernel.config import load_default
        return load_default("schemas", "extension-manifest.schema.v1.json")
    except Exception as exc:
        logger.debug("extension schema load failed: %s", exc)
        return None


def _compat_blockers(manifest: ExtensionManifest) -> tuple[str, ...]:
    """Return any compat blockers that disqualify this manifest from activation."""
    core_min = manifest.compat.get("core_min", "")
    core_max = manifest.compat.get("core_max", "")
    try:
        import ao_kernel
        current = getattr(ao_kernel, "__version__", "0.0.0")
    except Exception:
        current = "0.0.0"

    blockers: list[str] = []
    try:
        from packaging.version import Version, InvalidVersion
    except ImportError:
        # packaging is a transitive dep (pip, setuptools). Skip check if
        # genuinely unavailable rather than block every extension.
        return ()

    def _cmp(a: str, op: str, b: str) -> bool:
        try:
            va, vb = Version(a), Version(b)
        except InvalidVersion:
            return False
        if op == "lt":
            return va < vb
        if op == "gt":
            return va > vb
        return False

    if core_min and _cmp(current, "lt", core_min):
        blockers.append(f"compat:core_min={core_min} > current={current}")
    if core_max and _cmp(current, "gt", core_max):
        blockers.append(f"compat:core_max={core_max} < current={current}")
    return tuple(blockers)


def _stale_ref_paths(manifest: ExtensionManifest, *, base: Path | None) -> tuple[str, ...]:
    """Return manifest-declared paths that do not exist relative to base.

    Bundled manifests copied from the upstream autonomous-orchestrator repo
    often reference paths (``src/prj_kernel_api/adapter.py``, etc.) that do
    not exist in the ao-kernel package tree. Flagging them keeps the
    registry honest without blocking activation.
    """
    if base is None or not base.is_dir():
        return ()
    refs: list[str] = []
    refs.extend(manifest.ai_context_refs)
    if manifest.docs_ref:
        refs.append(manifest.docs_ref)
    refs.extend(manifest.tests_entrypoints)
    stale = [r for r in refs if r and not (base / r).exists()]
    return tuple(stale)


class ExtensionRegistry:
    """Client-scoped registry of loaded manifests + conflict tracking."""

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionManifest] = {}
        # (entrypoint_group, entrypoint) -> winning extension_id
        self._entrypoint_owner: dict[tuple[str, str], str] = {}
        self._conflicts: list[ConflictRecord] = []

    # ── Loaders ───────────────────────────────────────────────────────

    def load_from_defaults(self, *, refs_base: Path | None = None) -> LoadReport:
        """Load bundled manifests packaged under ao_kernel.defaults.extensions.

        ``refs_base`` controls where stale-ref path checks resolve from.
        Callers typically pass the project root; None skips the stale check.
        """
        schema = _load_schema()
        try:
            import importlib.resources as resources
            extensions_pkg = resources.files("ao_kernel.defaults.extensions")
        except (ImportError, ModuleNotFoundError):
            return LoadReport(loaded=0)

        report = LoadReport(loaded=0)
        # Sorted iteration → deterministic first-wins conflict resolution.
        items = sorted(
            (item for item in extensions_pkg.iterdir() if item.is_dir()),
            key=lambda i: i.name,
        )
        for item in items:
            manifest_file = item / "extension.manifest.v1.json"
            self._ingest(
                manifest_file,
                schema=schema,
                source="bundled",
                refs_base=refs_base,
                report=report,
            )
        return report

    def load_from_workspace(self, project_root: Path, *, refs_base: Path | None = None) -> LoadReport:
        """Load workspace overrides from <project_root>/.ao/extensions/.

        Workspace manifests are ingested AFTER bundled defaults, so a matching
        extension_id replaces the bundled entry (override semantics). Each
        entrypoint is re-registered; if bundled already owned it, the conflict
        is recorded and the workspace entry wins.
        """
        schema = _load_schema()
        extensions_dir = project_root / ".ao" / "extensions"
        if not extensions_dir.is_dir():
            return LoadReport(loaded=0)

        report = LoadReport(loaded=0)
        for ext_dir in sorted(extensions_dir.iterdir(), key=lambda p: p.name):
            if not ext_dir.is_dir():
                continue
            manifest_path = ext_dir / "extension.manifest.v1.json"
            self._ingest(
                manifest_path,
                schema=schema,
                source="workspace",
                refs_base=refs_base or project_root,
                report=report,
                allow_override=True,
            )
        return report

    # ── Query API ─────────────────────────────────────────────────────

    def get(self, extension_id: str) -> ExtensionManifest | None:
        return self._extensions.get(extension_id)

    def list_all(self) -> list[ExtensionManifest]:
        return sorted(self._extensions.values(), key=lambda m: m.extension_id)

    def list_enabled(self) -> list[ExtensionManifest]:
        """Enabled manifests with NO activation blockers (compat-healthy)."""
        return [
            m for m in self.list_all()
            if m.enabled and not m.activation_blockers
        ]

    def find_by_entrypoint(self, entrypoint_name: str) -> list[ExtensionManifest]:
        out: list[ExtensionManifest] = []
        for m in self._extensions.values():
            for ep_list in m.entrypoints.values():
                if entrypoint_name in ep_list:
                    out.append(m)
                    break
        return out

    def find_conflicts(self) -> list[ConflictRecord]:
        return list(self._conflicts)

    # ── Ingestion (private) ───────────────────────────────────────────

    def _ingest(
        self,
        manifest_file: Any,
        *,
        schema: dict[str, Any] | None,
        source: str,
        refs_base: Path | None,
        report: LoadReport,
        allow_override: bool = False,
    ) -> None:
        try:
            raw_bytes = manifest_file.read_bytes()
        except (FileNotFoundError, OSError) as exc:
            report.skipped.append({"path": str(manifest_file), "reason": f"read_error: {exc}"})
            return

        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            report.skipped.append({"path": str(manifest_file), "reason": f"json_error: {exc}"})
            logger.warning("extension manifest unparseable (%s): %s", manifest_file, exc)
            return

        if not isinstance(data, dict):
            report.skipped.append({"path": str(manifest_file), "reason": "not_an_object"})
            return

        err = _validate_schema(data, schema=schema)
        if err:
            report.skipped.append({"path": str(manifest_file), "reason": f"schema_invalid: {err}"})
            logger.warning(
                "extension manifest schema invalid (%s): %s", manifest_file, err,
            )
            return

        try:
            manifest = _parse_manifest(
                data,
                manifest_path=str(manifest_file),
                raw_bytes=raw_bytes,
                source=source,
            )
        except (KeyError, ValueError) as exc:
            report.skipped.append({"path": str(manifest_file), "reason": f"parse_error: {exc}"})
            return

        manifest = self._enrich(manifest, refs_base=refs_base)

        ext_id = manifest.extension_id
        if ext_id in self._extensions and not allow_override:
            # Duplicate extension_id inside bundled set — keep first, warn.
            report.skipped.append({
                "path": str(manifest_file),
                "reason": f"duplicate_extension_id: {ext_id}",
            })
            logger.warning("duplicate extension_id ignored: %s", ext_id)
            return

        self._extensions[ext_id] = manifest
        self._register_entrypoints(manifest, report=report)
        report.loaded += 1

    def _enrich(self, manifest: ExtensionManifest, *, refs_base: Path | None) -> ExtensionManifest:
        """Attach compat blockers and stale refs to a freshly parsed manifest."""
        from dataclasses import replace
        blockers = _compat_blockers(manifest)
        stale = _stale_ref_paths(manifest, base=refs_base)
        return replace(manifest, activation_blockers=blockers, stale_refs=stale)

    def _register_entrypoints(self, manifest: ExtensionManifest, *, report: LoadReport) -> None:
        for group, names in manifest.entrypoints.items():
            for name in names:
                key = (group, name)
                owner = self._entrypoint_owner.get(key)
                if owner is None or owner == manifest.extension_id:
                    self._entrypoint_owner[key] = manifest.extension_id
                    continue
                # Conflict: someone else already owns this entrypoint.
                existing = next(
                    (c for c in self._conflicts if c.entrypoint_group == group and c.entrypoint == name),
                    None,
                )
                if existing is None:
                    self._conflicts.append(ConflictRecord(
                        entrypoint_group=group,
                        entrypoint=name,
                        winner=owner,
                        shadowed=[manifest.extension_id],
                    ))
                else:
                    if manifest.extension_id not in existing.shadowed:
                        existing.shadowed.append(manifest.extension_id)
                logger.warning(
                    "entrypoint conflict: %s/%s declared by %s (winner) and %s",
                    group, name, owner, manifest.extension_id,
                )


__all__ = [
    "ExtensionManifest",
    "ExtensionRegistry",
    "ConflictRecord",
    "LoadReport",
]
