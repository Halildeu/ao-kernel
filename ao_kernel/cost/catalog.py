"""Price catalog loader (PR-B2 commit 2).

Loads ``price-catalog.v1.json`` from a workspace override (set via
``policy_cost_tracking.price_catalog_path``) or falls back to the
bundled starter catalog. Verifies ``checksum`` (SHA-256 over
canonical ``entries[]`` JSON) and applies the ``stale_after`` gate
per the policy's ``strict_freshness`` knob.

Loader is UNCONDITIONAL — dormant-gate is the caller's responsibility
(CNS-031 iter-1 Q6 absorb). The middleware short-circuits before
calling ``load_price_catalog`` when ``policy.enabled=false``.

LRU cache: 300-second TTL per workspace_root (CNS-031 iter-1 Q8
absorb). Cache key is the resolved source path; misses re-read disk.

See ``docs/COST-MODEL.md`` §2 for object shape + field semantics.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ao_kernel.config import load_default
from ao_kernel.cost.errors import (
    PriceCatalogChecksumError,
    PriceCatalogStaleError,
)
from ao_kernel.cost.policy import CostTrackingPolicy


logger = logging.getLogger(__name__)


_CATALOG_SCHEMA_CACHE: dict[str, Any] | None = None
_BUNDLED_CATALOG_CACHE: dict[str, Any] | None = None

# LRU cache: { workspace_root_str: (PriceCatalog, loaded_at_monotonic_seconds) }
_CATALOG_INSTANCE_CACHE: dict[str, tuple["PriceCatalog", float]] = {}
_CACHE_TTL_SECONDS: float = 300.0


def _catalog_schema() -> dict[str, Any]:
    """Load and cache ``price-catalog.schema.v1.json``."""
    global _CATALOG_SCHEMA_CACHE
    if _CATALOG_SCHEMA_CACHE is None:
        _CATALOG_SCHEMA_CACHE = load_default(
            "schemas", "price-catalog.schema.v1.json",
        )
    return _CATALOG_SCHEMA_CACHE


def _bundled_catalog() -> dict[str, Any]:
    """Load and cache the bundled starter catalog."""
    global _BUNDLED_CATALOG_CACHE
    if _BUNDLED_CATALOG_CACHE is None:
        _BUNDLED_CATALOG_CACHE = load_default(
            "catalogs", "price-catalog.v1.json",
        )
    return _BUNDLED_CATALOG_CACHE


@dataclass(frozen=True)
class PriceCatalogEntry:
    """One catalog entry — a ``(provider_id, model)`` price record.

    Fields mirror ``price-catalog.schema.v1.json::$defs/entry`` one-to-
    one. ``vendor_model_id`` is optional (required only when the
    catalog-level ``source=vendor_api`` — enforced at schema load, not
    here). ``cached_input_cost_per_1k`` is optional (None means "no
    caching discount on record" — full-rate fallback in
    :func:`compute_cost`).
    """

    provider_id: str
    model: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    currency: str
    billing_unit: str
    effective_date: str
    vendor_model_id: str | None = None
    cached_input_cost_per_1k: float | None = None


@dataclass(frozen=True)
class PriceCatalog:
    """Versioned, checksum-verified snapshot of price records.

    Immutable by construction. :func:`find_entry` walks ``entries``
    linearly — O(N) acceptable for MVP scope (bundled ~6, operator
    catalogs typically < 100). Indexed lookup deferred to FAZ-D if
    workloads warrant.
    """

    catalog_version: str
    generated_at: str
    source: str  # "bundled" | "vendor_api" | "manual"
    stale_after: str
    checksum: str
    entries: tuple[PriceCatalogEntry, ...]


def _canonical_entries_json(entries: list[Mapping[str, Any]]) -> str:
    """Canonical JSON form for checksum.

    Mirrors the bundled tooling contract: ``json.dumps(entries,
    sort_keys=True, ensure_ascii=False, separators=(",",":"))``.
    """
    return json.dumps(
        entries,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _compute_checksum(entries: list[Mapping[str, Any]]) -> str:
    """Recompute ``sha256:<hex>`` over canonical ``entries[]`` JSON."""
    canonical = _canonical_entries_json(entries)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_checksum(
    doc: Mapping[str, Any],
    source_path: str,
) -> None:
    """Raise :class:`PriceCatalogChecksumError` on mismatch."""
    expected = str(doc.get("checksum", ""))
    entries = list(doc.get("entries", []))
    actual = _compute_checksum(entries)
    if expected != actual:
        raise PriceCatalogChecksumError(
            catalog_path=source_path,
            expected_checksum=expected,
            actual_checksum=actual,
        )


def _check_staleness(
    doc: Mapping[str, Any],
    source_path: str,
    *,
    strict: bool,
) -> None:
    """Apply the stale-after policy gate.

    ``strict=False`` (default policy.strict_freshness): emit a WARN
    log and return — catalog still served.

    ``strict=True``: raise :class:`PriceCatalogStaleError` — fail-closed.
    """
    stale_after_raw = str(doc.get("stale_after", ""))
    try:
        stale_after = _dt.datetime.fromisoformat(
            stale_after_raw.replace("Z", "+00:00")
        )
    except ValueError:
        # Schema validation already constrains format: date-time, so a
        # malformed value here would mean the schema was bypassed. Treat
        # unparseable as "not stale" — defensive; the schema guard is
        # the real anchor.
        return

    now = _dt.datetime.now(tz=_dt.timezone.utc)
    if now <= stale_after:
        return

    now_iso = now.isoformat()
    if strict:
        raise PriceCatalogStaleError(
            catalog_path=source_path,
            stale_after=stale_after_raw,
            now=now_iso,
        )
    logger.warning(
        "price catalog at %s is stale (stale_after=%s, now=%s); "
        "strict_freshness=false — serving anyway",
        source_path,
        stale_after_raw,
        now_iso,
    )


def _validate(doc: Mapping[str, Any]) -> None:
    """Validate ``doc`` against ``price-catalog.schema.v1.json``.

    Fail-closed per CLAUDE.md §2: a malformed catalog must not be
    silently ignored.
    """
    from jsonschema import Draft202012Validator

    Draft202012Validator(_catalog_schema()).validate(doc)


def _from_dict(doc: Mapping[str, Any]) -> PriceCatalog:
    """Parse a schema-valid catalog dict into :class:`PriceCatalog`."""
    entries = tuple(
        PriceCatalogEntry(
            provider_id=str(e["provider_id"]),
            model=str(e["model"]),
            input_cost_per_1k=float(e["input_cost_per_1k"]),
            output_cost_per_1k=float(e["output_cost_per_1k"]),
            currency=str(e["currency"]),
            billing_unit=str(e["billing_unit"]),
            effective_date=str(e["effective_date"]),
            vendor_model_id=(
                str(e["vendor_model_id"]) if "vendor_model_id" in e else None
            ),
            cached_input_cost_per_1k=(
                float(e["cached_input_cost_per_1k"])
                if "cached_input_cost_per_1k" in e
                else None
            ),
        )
        for e in doc["entries"]
    )
    return PriceCatalog(
        catalog_version=str(doc["catalog_version"]),
        generated_at=str(doc["generated_at"]),
        source=str(doc["source"]),
        stale_after=str(doc["stale_after"]),
        checksum=str(doc["checksum"]),
        entries=entries,
    )


def _resolve_source(
    workspace_root: Path,
    policy: CostTrackingPolicy | None,
) -> tuple[Mapping[str, Any], str]:
    """Return ``(doc, source_path_str)`` — workspace override preferred,
    bundled fallback."""
    if policy is not None:
        override_path = workspace_root / policy.price_catalog_path
    else:
        override_path = (
            workspace_root / ".ao" / "cost" / "catalog.v1.json"
        )
    if override_path.is_file():
        with override_path.open("r", encoding="utf-8") as fh:
            loaded: Mapping[str, Any] = json.load(fh)
        return loaded, str(override_path)
    # Bundled fallback
    return _bundled_catalog(), "<bundled>"


def _cache_key(workspace_root: Path) -> str:
    return str(workspace_root.resolve())


def _cache_get(key: str) -> PriceCatalog | None:
    entry = _CATALOG_INSTANCE_CACHE.get(key)
    if entry is None:
        return None
    catalog, loaded_at = entry
    if time.monotonic() - loaded_at > _CACHE_TTL_SECONDS:
        # Expired; evict and miss.
        _CATALOG_INSTANCE_CACHE.pop(key, None)
        return None
    return catalog


def _cache_set(key: str, catalog: PriceCatalog) -> None:
    _CATALOG_INSTANCE_CACHE[key] = (catalog, time.monotonic())


def clear_catalog_cache() -> None:
    """Drop the LRU cache (tests + operator tooling)."""
    _CATALOG_INSTANCE_CACHE.clear()


def load_price_catalog(
    workspace_root: Path,
    *,
    override: Mapping[str, Any] | None = None,
    policy: CostTrackingPolicy | None = None,
) -> PriceCatalog:
    """Load the price catalog.

    Resolution order:

    1. If ``override`` dict is supplied (tests), validate + parse it
       directly (no filesystem, no cache).
    2. Workspace override at ``{workspace_root}/{policy.price_catalog_path}``
       (defaults to ``.ao/cost/catalog.v1.json`` when policy omitted).
    3. Bundled starter catalog at
       ``ao_kernel/defaults/catalogs/price-catalog.v1.json``.

    Validation chain (both override + filesystem paths):

    - JSON schema validation (fail-closed on malformed doc).
    - Checksum verification (SHA-256 over canonical ``entries[]``)
      → :class:`PriceCatalogChecksumError` on mismatch.
    - Staleness gate (``policy.strict_freshness``) →
      :class:`PriceCatalogStaleError` in strict mode, WARN log otherwise.

    Caching: filesystem + bundled paths cached 300 seconds per
    resolved ``workspace_root``. Inline ``override=`` bypasses cache.
    """
    if override is not None:
        _validate(override)
        _verify_checksum(override, "<inline-override>")
        strict = policy.strict_freshness if policy is not None else False
        _check_staleness(override, "<inline-override>", strict=strict)
        return _from_dict(override)

    cache_key = _cache_key(workspace_root)
    cached = _cache_get(cache_key)
    if cached is not None:
        # Staleness re-check on cache hit — the stale-after timestamp is
        # content-bound, but wall-clock may have crossed it since last
        # load. Re-evaluate the gate so strict mode surfaces the stale
        # error promptly rather than serving a cached value past TTL.
        if policy is not None:
            _check_staleness(
                {"stale_after": cached.stale_after},
                f"<cached:{cache_key}>",
                strict=policy.strict_freshness,
            )
        return cached

    doc, source_path = _resolve_source(workspace_root, policy)
    _validate(doc)
    _verify_checksum(doc, source_path)
    strict = policy.strict_freshness if policy is not None else False
    _check_staleness(doc, source_path, strict=strict)
    catalog = _from_dict(doc)
    _cache_set(cache_key, catalog)
    return catalog


def find_entry(
    catalog: PriceCatalog,
    provider_id: str,
    model: str,
) -> PriceCatalogEntry | None:
    """Return the entry matching ``(provider_id, model)`` or ``None``.

    Linear scan. Callers handle the ``None`` case themselves — raising
    :class:`PriceCatalogNotFoundError` is the cost middleware's job
    (it has the extra context: catalog_version, etc.).
    """
    for entry in catalog.entries:
        if entry.provider_id == provider_id and entry.model == model:
            return entry
    return None


__all__ = [
    "PriceCatalog",
    "PriceCatalogEntry",
    "clear_catalog_cache",
    "find_entry",
    "load_price_catalog",
]
