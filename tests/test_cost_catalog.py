"""Tests for ``ao_kernel.cost.catalog`` — price catalog loader."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from ao_kernel.cost.catalog import (
    PriceCatalogEntry,
    _canonical_entries_json,
    clear_catalog_cache,
    find_entry,
    load_price_catalog,
)
from ao_kernel.cost.errors import (
    PriceCatalogChecksumError,
    PriceCatalogStaleError,
)
from ao_kernel.cost.policy import (
    CostTrackingPolicy,
    RoutingByCost,
)


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    """Each test gets a fresh LRU cache — otherwise bundled hit in test A
    bleeds into test B's override scenario."""
    clear_catalog_cache()
    yield
    clear_catalog_cache()


def _entry_doc(**overrides: Any) -> dict[str, Any]:
    base = {
        "provider_id": "anthropic",
        "model": "claude-3-5-sonnet",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "cached_input_cost_per_1k": 0.0003,
        "currency": "USD",
        "billing_unit": "per_1k_tokens",
        "effective_date": "2024-10-22",
    }
    base.update(overrides)
    return base


def _catalog_doc(
    *,
    entries: list[dict[str, Any]] | None = None,
    source: str = "manual",
    stale_after: str = "2099-01-01T00:00:00+00:00",
    generated_at: str = "2026-04-16T00:00:00+00:00",
    override_checksum: str | None = None,
) -> dict[str, Any]:
    if entries is None:
        entries = [_entry_doc()]
    canonical = json.dumps(
        entries,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    checksum = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    doc = {
        "catalog_version": "1",
        "generated_at": generated_at,
        "source": source,
        "stale_after": stale_after,
        "checksum": override_checksum if override_checksum is not None else checksum,
        "entries": entries,
    }
    return doc


def _policy(**overrides: Any) -> CostTrackingPolicy:
    return CostTrackingPolicy(
        enabled=True,
        price_catalog_path=".ao/cost/catalog.v1.json",
        spend_ledger_path=".ao/cost/spend.jsonl",
        fail_closed_on_exhaust=True,
        strict_freshness=overrides.get("strict_freshness", False),
        fail_closed_on_missing_usage=True,
        idempotency_window_lines=1000,
        routing_by_cost=RoutingByCost(enabled=False),
    )


class TestBundledLoad:
    def test_bundled_loads_without_override(self, tmp_path: Path) -> None:
        """No workspace override → bundled starter catalog returned."""
        catalog = load_price_catalog(tmp_path)
        assert catalog.catalog_version == "1"
        assert catalog.source == "bundled"
        assert len(catalog.entries) >= 6  # 6 entries in bundled starter

    def test_bundled_has_anthropic_sonnet(self, tmp_path: Path) -> None:
        catalog = load_price_catalog(tmp_path)
        sonnet = find_entry(catalog, "anthropic", "claude-3-5-sonnet")
        assert sonnet is not None
        assert sonnet.input_cost_per_1k == pytest.approx(0.003)
        assert sonnet.output_cost_per_1k == pytest.approx(0.015)


class TestWorkspaceOverride:
    def _write_override(
        self,
        workspace_root: Path,
        doc: dict[str, Any],
        *,
        subpath: str = ".ao/cost/catalog.v1.json",
    ) -> None:
        path = workspace_root / subpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))

    def test_workspace_override_preempts_bundled(self, tmp_path: Path) -> None:
        override_doc = _catalog_doc(
            entries=[
                _entry_doc(
                    provider_id="acme",
                    model="acme-large",
                    input_cost_per_1k=0.5,
                    output_cost_per_1k=1.0,
                    cached_input_cost_per_1k=0.1,
                )
            ],
        )
        self._write_override(tmp_path, override_doc)
        catalog = load_price_catalog(tmp_path, policy=_policy())
        acme = find_entry(catalog, "acme", "acme-large")
        assert acme is not None
        # Bundled anthropic entry now absent (override replaces)
        assert find_entry(catalog, "anthropic", "claude-3-5-sonnet") is None

    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / ".ao" / "cost" / "catalog.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_price_catalog(tmp_path, policy=_policy())

    def test_schema_invalid_raises(self, tmp_path: Path) -> None:
        """Fail-closed: invalid catalog must not silently fall back."""
        doc = _catalog_doc()
        del doc["generated_at"]  # violate required
        self._write_override(tmp_path, doc)
        with pytest.raises(ValidationError):
            load_price_catalog(tmp_path, policy=_policy())


class TestInlineOverride:
    def test_inline_override_bypasses_filesystem(self, tmp_path: Path) -> None:
        doc = _catalog_doc(
            entries=[_entry_doc(provider_id="acme", model="acme-tiny")]
        )
        catalog = load_price_catalog(tmp_path, override=doc)
        entry = find_entry(catalog, "acme", "acme-tiny")
        assert entry is not None
        assert entry.provider_id == "acme"
        assert entry.model == "acme-tiny"
        assert catalog.source == "manual"


class TestChecksumVerify:
    def test_checksum_mismatch_raises(self, tmp_path: Path) -> None:
        bad = _catalog_doc(
            override_checksum="sha256:" + "0" * 64,  # wrong sha
        )
        with pytest.raises(PriceCatalogChecksumError) as excinfo:
            load_price_catalog(tmp_path, override=bad)
        assert excinfo.value.expected_checksum.startswith("sha256:")
        assert excinfo.value.actual_checksum.startswith("sha256:")

    def test_checksum_ignores_doc_level_fields(self, tmp_path: Path) -> None:
        """Checksum only over entries[] — generated_at/source churn does
        not break verification."""
        entries = [_entry_doc()]
        doc1 = _catalog_doc(entries=entries, generated_at="2026-04-16T00:00:00+00:00")
        doc2 = _catalog_doc(entries=entries, generated_at="2026-05-01T00:00:00+00:00")
        # Both doc1 and doc2 should load cleanly — same entries → same checksum
        assert doc1["checksum"] == doc2["checksum"]

    def test_canonical_form_stable(self) -> None:
        """Canonical form is deterministic across dict key orderings."""
        entries_a = [{"provider_id": "p", "model": "m", "input_cost_per_1k": 1.0}]
        entries_b = [{"model": "m", "input_cost_per_1k": 1.0, "provider_id": "p"}]
        assert _canonical_entries_json(entries_a) == _canonical_entries_json(entries_b)


class TestStaleGate:
    def test_strict_stale_raises(self, tmp_path: Path) -> None:
        past_ts = (
            _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(days=1)
        ).isoformat()
        doc = _catalog_doc(stale_after=past_ts)
        with pytest.raises(PriceCatalogStaleError):
            load_price_catalog(
                tmp_path,
                override=doc,
                policy=_policy(strict_freshness=True),
            )

    def test_lenient_stale_warns(self, tmp_path: Path, caplog) -> None:
        past_ts = (
            _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(days=1)
        ).isoformat()
        doc = _catalog_doc(stale_after=past_ts)
        with caplog.at_level("WARNING"):
            catalog = load_price_catalog(
                tmp_path,
                override=doc,
                policy=_policy(strict_freshness=False),
            )
        assert catalog.catalog_version == "1"  # served despite stale
        assert any(
            "stale" in rec.getMessage() for rec in caplog.records
        )

    def test_fresh_catalog_passes(self, tmp_path: Path) -> None:
        future_ts = (
            _dt.datetime.now(tz=_dt.timezone.utc) + _dt.timedelta(days=30)
        ).isoformat()
        doc = _catalog_doc(stale_after=future_ts)
        catalog = load_price_catalog(
            tmp_path,
            override=doc,
            policy=_policy(strict_freshness=True),
        )
        assert catalog.catalog_version == "1"


class TestVendorApiSourceConditional:
    def test_vendor_api_requires_vendor_model_id(self, tmp_path: Path) -> None:
        """Schema if/then: source=vendor_api → entries[].vendor_model_id required."""
        entries_missing_vendor = [_entry_doc()]  # no vendor_model_id
        doc = _catalog_doc(entries=entries_missing_vendor, source="vendor_api")
        with pytest.raises(ValidationError):
            load_price_catalog(tmp_path, override=doc)

    def test_vendor_api_with_vendor_model_id_ok(self, tmp_path: Path) -> None:
        entries = [
            _entry_doc(vendor_model_id="claude-3-5-sonnet-20241022"),
        ]
        doc = _catalog_doc(entries=entries, source="vendor_api")
        catalog = load_price_catalog(tmp_path, override=doc)
        assert catalog.source == "vendor_api"
        assert catalog.entries[0].vendor_model_id == "claude-3-5-sonnet-20241022"

    def test_manual_source_without_vendor_model_id_ok(self, tmp_path: Path) -> None:
        """source=manual → vendor_model_id optional."""
        doc = _catalog_doc(entries=[_entry_doc()], source="manual")
        catalog = load_price_catalog(tmp_path, override=doc)
        assert catalog.entries[0].vendor_model_id is None


class TestFindEntry:
    def test_match(self, tmp_path: Path) -> None:
        catalog = load_price_catalog(tmp_path)  # bundled
        entry = find_entry(catalog, "anthropic", "claude-3-5-sonnet")
        assert entry is not None
        assert entry.provider_id == "anthropic"

    def test_no_match_returns_none(self, tmp_path: Path) -> None:
        catalog = load_price_catalog(tmp_path)
        assert find_entry(catalog, "nonexistent", "ghost-model") is None

    def test_case_sensitive(self, tmp_path: Path) -> None:
        catalog = load_price_catalog(tmp_path)
        assert find_entry(catalog, "Anthropic", "claude-3-5-sonnet") is None


class TestLruCache:
    def test_same_workspace_two_calls_hits_cache(self, tmp_path: Path) -> None:
        """Second call returns the same instance — filesystem read once.

        We can't easily count disk reads without mocking; instead we
        assert object identity: cache returns the same PriceCatalog
        instance across calls within TTL.
        """
        cat1 = load_price_catalog(tmp_path)
        cat2 = load_price_catalog(tmp_path)
        assert cat1 is cat2

    def test_clear_cache_forces_reload(self, tmp_path: Path) -> None:
        cat1 = load_price_catalog(tmp_path)
        clear_catalog_cache()
        cat2 = load_price_catalog(tmp_path)
        # New instance after cache clear
        assert cat1 is not cat2

    def test_inline_override_bypasses_cache(self, tmp_path: Path) -> None:
        """override= kwarg skips cache — always validates + parses fresh."""
        doc = _catalog_doc(entries=[_entry_doc(model="alt-1")])
        cat1 = load_price_catalog(tmp_path, override=doc)
        cat2 = load_price_catalog(tmp_path, override=doc)
        # Fresh instances each call (no cache entry for override path)
        assert cat1 is not cat2


class TestEmptyEntries:
    def test_empty_entries_array_rejected(self, tmp_path: Path) -> None:
        """Schema minItems: 1 — empty catalog indistinguishable from absent."""
        doc = _catalog_doc(entries=[])
        # Checksum recomputed for empty list
        doc["checksum"] = "sha256:" + hashlib.sha256(b"[]").hexdigest()
        with pytest.raises(ValidationError):
            load_price_catalog(tmp_path, override=doc)


class TestEntryDataclass:
    def test_entry_frozen(self) -> None:
        entry = PriceCatalogEntry(
            provider_id="p",
            model="m",
            input_cost_per_1k=1.0,
            output_cost_per_1k=2.0,
            currency="USD",
            billing_unit="per_1k_tokens",
            effective_date="2026-01-01",
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.provider_id = "other"  # type: ignore[misc]
