"""ao_kernel.prompts — Prompt variant registry + loader (v3.12 E1).

Contract-only surface for operator-driven prompt experiments. ao-kernel
does NOT orchestrate A/B dispatch at runtime — that is deferred until
operator-validated real-adapter smokes exist (see
``docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md`` prereq + ``docs/PROMPT-EXPERIMENTS-RUNBOOK.md``).

This module ships three things:

1. :class:`PromptVariant` dataclass — the typed shape operators write
   into ``.ao/registry/prompt_variant_registry.v1.json``.
2. :func:`load_prompt_variants` — workspace override + bundled fallback
   registry loader with schema validation and duplicate-id guard.
3. The ``intent.metadata.variant_id`` contract (documented below).

Contract — operator flow:

- Operator authors one or more ``PromptVariant`` entries in the
  workspace registry (default: empty).
- When starting a workflow run, operator stamps the chosen variant id
  via ``create_run(... intent={"metadata": {"variant_id": "my.variant.v1"}})``.
- Adapter dispatch is operator-driven: the variant's ``prompt_template``
  is passed into the adapter's input (typically via the
  ``{context_pack_ref}`` file for ``claude-code-cli``).
- Post-run, :func:`ao_kernel.experiments.compare_variants` (v3.12 E2)
  reads the run record and pairs ``intent.metadata.variant_id`` with
  ``step_record.capability_output_refs['review_findings']`` to produce
  a side-by-side comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ao_kernel._internal.shared.resource_loader import load_resource


# Bundled registry path pieces (for importlib.resources / direct file).
_REGISTRY_FILENAME = "prompt_variant_registry.v1.json"
_SCHEMA_FILENAME = "prompt-variant.schema.v1.json"

# Workspace override path (relative to workspace root).
_WORKSPACE_REL = Path(".ao") / "registry" / _REGISTRY_FILENAME


class PromptVariantError(ValueError):
    """Raised when the prompt variant registry violates its schema or
    invariants (duplicate variant_id, unknown expected_capability,
    missing required fields)."""


@dataclass(frozen=True)
class PromptVariant:
    """Typed prompt variant record.

    See ``prompt-variant.schema.v1.json`` for the full JSON contract.
    Fields are held immutable (frozen=True) so callers can hash or
    cache the variant safely.
    """

    variant_id: str
    version: str
    prompt_template: str
    expected_capability: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> PromptVariant:
        """Build a :class:`PromptVariant` from a registry entry dict.

        Raises :class:`PromptVariantError` on missing required fields
        or unknown ``expected_capability`` values. Extra metadata keys
        pass through without validation (schema allows
        ``additionalProperties`` on ``metadata``).
        """
        missing = [k for k in ("variant_id", "version", "prompt_template") if k not in raw]
        if missing:
            raise PromptVariantError(f"PromptVariant missing required field(s): {missing!r}")

        expected = raw.get("expected_capability")
        if expected is not None and expected not in (
            "review_findings",
            "commit_message",
            "write_diff",
        ):
            raise PromptVariantError(
                f"PromptVariant expected_capability must be one of "
                f"('review_findings', 'commit_message', 'write_diff'); "
                f"got {expected!r}"
            )

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise PromptVariantError(f"PromptVariant metadata must be a mapping; got {type(metadata).__name__}")

        return cls(
            variant_id=str(raw["variant_id"]),
            version=str(raw["version"]),
            prompt_template=str(raw["prompt_template"]),
            expected_capability=expected,
            metadata=dict(metadata),
        )


def load_prompt_variants(workspace_root: Path | None = None) -> list[PromptVariant]:
    """Load the prompt variant registry with workspace override.

    Resolution order (same pattern as other bundled registries):

    1. ``<workspace_root>/.ao/registry/prompt_variant_registry.v1.json``
       (workspace override), when ``workspace_root`` is given and the
       file exists.
    2. Bundled default: ``ao_kernel/defaults/registry/prompt_variant_registry.v1.json``
       (empty variants list in the bundled ship).

    Raises :class:`PromptVariantError` on:

    - Missing ``variants`` key (registry file must declare an array).
    - Duplicate ``variant_id`` across entries.
    - Any per-variant validation failure (see
      :meth:`PromptVariant.from_dict`).

    Returns an empty list when the bundled fallback is used and no
    operator override is present.
    """
    import json

    raw_registry: Mapping[str, Any] | None = None

    if workspace_root is not None:
        override_path = Path(workspace_root) / _WORKSPACE_REL
        if override_path.is_file():
            raw_registry = json.loads(override_path.read_text(encoding="utf-8"))

    if raw_registry is None:
        raw_registry = load_resource("registry", _REGISTRY_FILENAME)

    if not isinstance(raw_registry, Mapping):
        raise PromptVariantError(f"prompt_variant_registry must be a JSON object; got {type(raw_registry).__name__}")

    variants_raw = raw_registry.get("variants")
    if not isinstance(variants_raw, list):
        raise PromptVariantError("prompt_variant_registry.variants must be an array")

    variants: list[PromptVariant] = []
    seen_ids: set[str] = set()
    for entry in variants_raw:
        if not isinstance(entry, Mapping):
            raise PromptVariantError(f"prompt_variant_registry entries must be objects; got {type(entry).__name__}")
        variant = PromptVariant.from_dict(entry)
        if variant.variant_id in seen_ids:
            raise PromptVariantError(f"Duplicate variant_id in registry: {variant.variant_id!r}")
        seen_ids.add(variant.variant_id)
        variants.append(variant)

    return variants


__all__ = [
    "PromptVariant",
    "PromptVariantError",
    "load_prompt_variants",
]
