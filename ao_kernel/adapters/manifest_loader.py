"""Adapter manifest loader.

Scans ``<workspace_root>/.ao/adapters/*.manifest.v1.json``, validates
each against PR-A0's ``agent-adapter-contract.schema.v1.json`` at load
boundary, and exposes an ``AdapterRegistry`` for lookup +
capability queries.

Filename convention (plan v2 B6 fix): the stem of the filename up to
(but excluding) the ``.manifest.v1.json`` suffix must equal
``raw["adapter_id"]``. No dash/underscore normalization — mismatches
are rejected to prevent typosquatting.

All failure modes land in ``LoadReport.skipped`` with a typed
``reason`` so audit trails distinguish read/decode/schema/mismatch/
duplicate.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from jsonschema.validators import Draft202012Validator

from ao_kernel.adapters.errors import AdapterManifestNotFoundError

_SCHEMA_PACKAGE = "ao_kernel.defaults.schemas"
_SCHEMA_FILENAME = "agent-adapter-contract.schema.v1.json"
_MANIFEST_SUFFIX = ".manifest.v1.json"


@functools.lru_cache(maxsize=1)
def _load_schema() -> Mapping[str, Any]:
    text = (
        resources.files(_SCHEMA_PACKAGE)
        .joinpath(_SCHEMA_FILENAME)
        .read_text(encoding="utf-8")
    )
    schema: Mapping[str, Any] = json.loads(text)
    return schema


@functools.lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema())


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterManifest:
    """Parsed adapter manifest. Immutable.

    Invocation / envelope shapes are carried as ``Mapping[str, Any]``
    so PR-A3 executor can consume them without this module duplicating
    the CLI/HTTP branch semantics. PR-A0 schema already constrains the
    structure.
    """

    adapter_id: str
    adapter_kind: str
    version: str
    capabilities: frozenset[str]
    invocation: Mapping[str, Any]
    input_envelope_shape: Mapping[str, Any]
    output_envelope_shape: Mapping[str, Any]
    interrupt_contract: Mapping[str, Any] | None
    policy_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_path: Path
    output_parse: Mapping[str, Any] | None = None
    """Optional capability-aware extraction surface (PR-B0 net-new).

    Shape: ``{"rules": [{"json_path": str, "capability"?: str,
    "schema_ref"?: str}, ...]}``. When present, ``adapter_invoker.
    _invocation_from_envelope`` walks ``rules`` to populate
    ``InvocationResult.extracted_outputs``. ``None`` means no typed
    extraction (backwards-compatible default for adapters that predate
    FAZ-B).
    """


@dataclass(frozen=True)
class SkippedManifest:
    """One manifest file that failed to load cleanly."""

    source_path: Path
    reason: Literal[
        "json_decode",
        "schema_invalid",
        "adapter_id_mismatch",
        "read_error",
        "not_an_object",
        "duplicate_adapter_id",
    ]
    details: str


@dataclass(frozen=True)
class LoadReport:
    """Outcome of a load pass."""

    loaded: tuple[AdapterManifest, ...]
    skipped: tuple[SkippedManifest, ...]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class AdapterRegistry:
    """In-memory index of adapter manifests keyed by ``adapter_id``."""

    def __init__(self) -> None:
        self._by_id: dict[str, AdapterManifest] = {}

    def load_bundled(self) -> LoadReport:
        """Load bundled adapter manifests from package defaults (PR-A6).

        Uses ``importlib.resources`` so manifests are wheel-safe.
        Workspace manifests override bundled ones for the same
        ``adapter_id`` — call ``load_bundled()`` BEFORE
        ``load_workspace()`` to get the correct precedence.
        """
        loaded: list[AdapterManifest] = []
        skipped: list[SkippedManifest] = []
        try:
            pkg = resources.files("ao_kernel.defaults.adapters")
        except (ModuleNotFoundError, TypeError):
            return LoadReport(loaded=(), skipped=())
        for item in sorted(pkg.iterdir(), key=lambda i: i.name):
            if not item.name.endswith(_MANIFEST_SUFFIX):
                continue
            with resources.as_file(item) as path:
                self._ingest(source_path=path, loaded=loaded, skipped=skipped)
        return LoadReport(loaded=tuple(loaded), skipped=tuple(skipped))

    def load_workspace(self, workspace_root: Path) -> LoadReport:
        """Scan ``<workspace_root>/.ao/adapters/*.manifest.v1.json``.

        Deterministic load order (sorted by filename). Workspace
        manifests override bundled ones for the same ``adapter_id``
        (PR-A6 B3 absorb — workspace > bundled precedence).
        """
        loaded: list[AdapterManifest] = []
        skipped: list[SkippedManifest] = []
        dir_path = workspace_root / ".ao" / "adapters"
        if not dir_path.is_dir():
            return LoadReport(loaded=(), skipped=())
        for source_path in sorted(dir_path.glob(f"*{_MANIFEST_SUFFIX}")):
            self._ingest(
                source_path=source_path, loaded=loaded, skipped=skipped,
                allow_override=True,
            )
        return LoadReport(loaded=tuple(loaded), skipped=tuple(skipped))

    def _ingest(
        self,
        *,
        source_path: Path,
        loaded: list[AdapterManifest],
        skipped: list[SkippedManifest],
        allow_override: bool = False,
    ) -> None:
        expected_id = _expected_id_from_filename(source_path)

        try:
            text = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append(SkippedManifest(
                source_path=source_path,
                reason="read_error",
                details=str(exc),
            ))
            return

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            skipped.append(SkippedManifest(
                source_path=source_path,
                reason="json_decode",
                details=str(exc),
            ))
            return

        if not isinstance(raw, dict):
            skipped.append(SkippedManifest(
                source_path=source_path,
                reason="not_an_object",
                details="top-level JSON value is not an object",
            ))
            return

        errors = list(_validator().iter_errors(raw))
        if errors:
            summary = "; ".join(
                f"{e.json_path}: {e.message}" for e in errors[:3]
            )
            if len(errors) > 3:
                summary += f" (+{len(errors) - 3} more)"
            skipped.append(SkippedManifest(
                source_path=source_path,
                reason="schema_invalid",
                details=summary,
            ))
            return

        # Edge case contract (CNS-028v2 Q6v7, docs/BENCHMARK-SUITE.md §3.2):
        # multiple ``output_parse.rules`` targeting the same capability are
        # fail-closed at load time. The rule walker stores results keyed by
        # ``capability`` in ``InvocationResult.extracted_outputs``, so two
        # rules with the same capability would have order-dependent ambiguity.
        # JSON Schema ``uniqueItems`` cannot express "same key within sibling
        # objects"; this check is a complement, not a replacement.
        #
        # Second check (CNS-028v2 iter-6 W2 post-impl fix): every rule's
        # ``capability`` value — when present — must also appear in the
        # adapter's top-level ``capabilities[]`` declaration. The adapter
        # advertises what it supports; extraction rules reference that
        # advertised surface. A rule referencing an un-advertised capability
        # would silently expand the adapter's effective surface via the
        # extraction side channel, which defeats the point of
        # ``capabilities[]`` as the source of truth. Fail-closed at load
        # time; matches the rationale in the output_parse schema description.
        op = raw.get("output_parse")
        if isinstance(op, Mapping):
            advertised_caps = frozenset(raw.get("capabilities", ()))
            seen_caps: set[str] = set()
            for rule in op.get("rules", ()):
                if not isinstance(rule, Mapping):
                    continue
                cap = rule.get("capability")
                if isinstance(cap, str):
                    if cap in seen_caps:
                        skipped.append(SkippedManifest(
                            source_path=source_path,
                            reason="schema_invalid",
                            details=(
                                f"output_parse.rules has multiple entries "
                                f"for capability={cap!r}; duplicate "
                                f"capability is invalid (see "
                                f"docs/BENCHMARK-SUITE.md §3.2 edge-case "
                                f"contract)."
                            ),
                        ))
                        return
                    seen_caps.add(cap)
                    if cap not in advertised_caps:
                        skipped.append(SkippedManifest(
                            source_path=source_path,
                            reason="schema_invalid",
                            details=(
                                f"output_parse.rules references capability="
                                f"{cap!r} that is not listed in top-level "
                                f"capabilities={sorted(advertised_caps)!r}; "
                                f"extraction rules may only reference "
                                f"advertised capabilities (CNS-028v2 iter-6 "
                                f"W2)."
                            ),
                        ))
                        return

        raw_id = raw.get("adapter_id")
        if raw_id != expected_id:
            skipped.append(SkippedManifest(
                source_path=source_path,
                reason="adapter_id_mismatch",
                details=(
                    f"filename implies adapter_id={expected_id!r} but "
                    f"manifest declares {raw_id!r}"
                ),
            ))
            return

        if raw_id in self._by_id:
            if allow_override:
                # Workspace > bundled precedence (PR-A6 B3)
                pass  # fall through to overwrite
            else:
                skipped.append(SkippedManifest(
                    source_path=source_path,
                    reason="duplicate_adapter_id",
                    details=(
                        f"adapter_id={raw_id!r} already registered from "
                        f"{self._by_id[raw_id].source_path}"
                    ),
                ))
                return

        manifest = _parse_manifest(raw, source_path=source_path)
        self._by_id[manifest.adapter_id] = manifest
        loaded.append(manifest)

    # -- lookup -------------------------------------------------------------

    def get(self, adapter_id: str) -> AdapterManifest:
        manifest = self._by_id.get(adapter_id)
        if manifest is None:
            raise AdapterManifestNotFoundError(adapter_id=adapter_id)
        return manifest

    def list_adapters(self) -> list[AdapterManifest]:
        return sorted(self._by_id.values(), key=lambda m: m.adapter_id)

    def missing_capabilities(
        self,
        adapter_id: str,
        required: Iterable[str],
    ) -> frozenset[str]:
        """Return the set of required capabilities not provided by the adapter.

        Raises ``AdapterManifestNotFoundError`` when ``adapter_id`` is
        not registered (caller must guard or accept the raise).
        """
        manifest = self.get(adapter_id)
        required_set = frozenset(required)
        return required_set - manifest.capabilities

    def supports_capabilities(
        self,
        adapter_id: str,
        required: Iterable[str],
    ) -> bool:
        """Convenience boolean helper on top of ``missing_capabilities``.

        ``True`` iff the adapter supplies every required capability;
        ``False`` if anything is missing. Raises
        ``AdapterManifestNotFoundError`` for unknown ``adapter_id``.
        """
        return not self.missing_capabilities(adapter_id, required)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expected_id_from_filename(source_path: Path) -> str:
    """Derive the expected adapter_id from the manifest filename.

    Strips the ``.manifest.v1.json`` suffix; no underscore↔dash
    normalization. Filename ``codex-stub.manifest.v1.json`` yields
    ``codex-stub``.
    """
    name = source_path.name
    if name.endswith(_MANIFEST_SUFFIX):
        return name[: -len(_MANIFEST_SUFFIX)]
    # Fallback: full stem (callers should not reach this path because
    # the glob pattern restricts filenames, but defensive handling keeps
    # the function total).
    return source_path.stem


def _parse_manifest(
    raw: Mapping[str, Any],
    *,
    source_path: Path,
) -> AdapterManifest:
    return AdapterManifest(
        adapter_id=raw["adapter_id"],
        adapter_kind=raw["adapter_kind"],
        version=raw["version"],
        capabilities=frozenset(raw.get("capabilities", ())),
        invocation=dict(raw.get("invocation", {})),
        input_envelope_shape=dict(raw.get("input_envelope", {})),
        output_envelope_shape=dict(raw.get("output_envelope", {})),
        interrupt_contract=(
            dict(raw["interrupt_contract"])
            if "interrupt_contract" in raw
            else None
        ),
        policy_refs=tuple(raw.get("policy_refs", ())),
        evidence_refs=tuple(raw.get("evidence_refs", ())),
        source_path=source_path,
        output_parse=(
            # Deep-copy the rule list so mutation of the original raw
            # dict cannot retroactively affect the loaded manifest.
            {"rules": [dict(r) for r in raw["output_parse"].get("rules", ())]}
            if "output_parse" in raw
            else None
        ),
    )


__all__ = [
    "AdapterManifest",
    "SkippedManifest",
    "LoadReport",
    "AdapterRegistry",
]
