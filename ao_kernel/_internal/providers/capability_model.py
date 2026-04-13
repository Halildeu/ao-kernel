"""Unified provider capability model — single SSOT from provider_capability_registry.v1.json.

Replaces scattered capability flags (provider-local frozensets, router class registry)
with a single canonical source: registry/provider_capability_registry.v1.json.
Probe state overlays at runtime for dynamic capability discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, Set

from ao_kernel._internal.shared.utils import load_json


class ProviderCapability(Enum):
    """All known LLM provider capabilities — aligned with registry."""
    CHAT = "chat"
    STREAMING = "streaming"
    TOOL_USE = "tool_use"
    VISION = "vision"
    BATCH = "batch"
    CONTINUATION = "continuation"
    EXTENDED_THINKING = "extended_thinking"
    CODE_AGENTIC = "code_agentic"
    EMBEDDING = "embedding"
    STRUCTURED_OUTPUT = "structured_output"
    MODERATION = "moderation"
    AUDIO = "audio"
    IMAGE_GEN = "image_gen"


# Reverse map for string → enum
_CAPABILITY_MAP: Dict[str, ProviderCapability] = {c.value: c for c in ProviderCapability}

# Capability levels from registry
LEVEL_SUPPORTED = "supported"
LEVEL_EXPERIMENTAL = "experimental"
LEVEL_UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class CapabilityManifest:
    """Resolved capability manifest for a provider+model combination."""
    provider_id: str
    model: str
    capabilities: FrozenSet[ProviderCapability]
    experimental: FrozenSet[ProviderCapability]
    wire_api: str
    auth_header: str
    default_model: str

    def supports(self, capability: ProviderCapability) -> bool:
        """Check if capability is supported (includes experimental)."""
        return capability in self.capabilities or capability in self.experimental

    def supports_str(self, capability_str: str) -> bool:
        """Check by string name (for backward compat with provider.supports_capability)."""
        cap = _CAPABILITY_MAP.get(capability_str)
        if cap is None:
            return False
        return self.supports(cap)


def load_capability_registry(repo_root: Path | str | None = None) -> Dict[str, Any]:
    """Load the canonical provider capability registry.

    Searches: repo_root/registry/provider_capability_registry.v1.json
    Falls back to: registry/provider_capability_registry.v1.json
    """
    candidates = []
    if repo_root:
        candidates.append(Path(repo_root) / "registry" / "provider_capability_registry.v1.json")
    candidates.append(Path("registry") / "provider_capability_registry.v1.json")

    for path in candidates:
        if path.exists():
            return load_json(path)
    return {"version": "v1", "capabilities": [], "providers": {}}


def resolve_manifest(
    provider_id: str,
    model: str = "",
    *,
    registry: Dict[str, Any] | None = None,
    repo_root: Path | str | None = None,
    probe_state: Dict[str, Any] | None = None,
) -> CapabilityManifest:
    """Resolve capability manifest for a provider.

    Uses canonical registry as base. Optionally overlays probe state for
    runtime-discovered capabilities.

    Args:
        provider_id: Provider identifier (claude, openai, google, etc.)
        model: Model identifier (used for model-specific overrides in future)
        registry: Pre-loaded registry dict (avoids re-reading file)
        repo_root: Repo root for loading registry if not pre-loaded
        probe_state: Runtime probe state for dynamic capability overlay
    """
    if registry is None:
        registry = load_capability_registry(repo_root)

    providers = registry.get("providers", {})
    provider_data = providers.get(provider_id, {})

    if not isinstance(provider_data, dict):
        return CapabilityManifest(
            provider_id=provider_id,
            model=model,
            capabilities=frozenset(),
            experimental=frozenset(),
            wire_api="unknown",
            auth_header="Authorization",
            default_model=model,
        )

    # Parse capabilities from registry
    caps_data = provider_data.get("capabilities", {})
    supported: set[ProviderCapability] = set()
    experimental: set[ProviderCapability] = set()

    for cap_str, level in caps_data.items():
        cap = _CAPABILITY_MAP.get(cap_str)
        if cap is None:
            continue
        if level == LEVEL_SUPPORTED:
            supported.add(cap)
        elif level == LEVEL_EXPERIMENTAL:
            experimental.add(cap)

    # Overlay probe state if available
    if probe_state and isinstance(probe_state, dict):
        probe_providers = probe_state.get("providers", {})
        probe_provider = probe_providers.get(provider_id, {})
        if isinstance(probe_provider, dict):
            for cap_str, probe_info in probe_provider.items():
                cap = _CAPABILITY_MAP.get(cap_str)
                if cap is None:
                    continue
                if isinstance(probe_info, dict) and probe_info.get("probe_status") == "ok":
                    if cap not in supported:
                        experimental.add(cap)

    return CapabilityManifest(
        provider_id=provider_id,
        model=model or provider_data.get("default_model", ""),
        capabilities=frozenset(supported),
        experimental=frozenset(experimental),
        wire_api=provider_data.get("wire_api", "unknown"),
        auth_header=provider_data.get("auth_header", "Authorization"),
        default_model=provider_data.get("default_model", ""),
    )


def negotiate(
    required: Set[ProviderCapability],
    manifest: CapabilityManifest,
) -> tuple[bool, Set[ProviderCapability]]:
    """Check if manifest satisfies required capabilities.

    Returns (all_satisfied, missing_capabilities).
    """
    missing = set()
    for cap in required:
        if not manifest.supports(cap):
            missing.add(cap)
    return len(missing) == 0, missing


def get_provider_capabilities(
    provider_id: str,
    *,
    repo_root: Path | str | None = None,
) -> FrozenSet[str]:
    """Get supported capability strings for a provider.

    Convenience wrapper for backward compat with provider.supports_capability().
    Returns frozenset of capability string names.
    """
    manifest = resolve_manifest(provider_id, repo_root=repo_root)
    return frozenset(
        cap.value for cap in manifest.capabilities | manifest.experimental
    )
