"""Truth tests for the bundled-extension retirement ledger (RETIRED.v1.json).

The ledger is a machine-readable audit index of bundled extensions removed from
ao_kernel/defaults/extensions/. These tests enforce that the ledger stays
schema-valid, internally consistent, and — critically — that every id it claims
to have retired is genuinely absent from the live bundled inventory (no
"retired on paper but still shipped" drift).
"""

from __future__ import annotations

import copy

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default
from ao_kernel.extensions.loader import ExtensionRegistry

SCHEMA_NAME = "retired-extension-ledger.schema.v1.json"
EXPECTED_RETIRED = {"PRJ-EXECUTORPORT", "PRJ-MEMORYPORT", "PRJ-OBSERVABILITY-OTEL"}


def _schema() -> dict:
    return load_default("schemas", SCHEMA_NAME)


def _ledger() -> dict:
    return load_default("extensions", "RETIRED.v1.json")


def test_schema_is_itself_valid() -> None:
    Draft202012Validator.check_schema(_schema())


def test_ledger_validates_against_schema() -> None:
    errors = list(Draft202012Validator(_schema()).iter_errors(_ledger()))
    assert not errors, [e.message for e in errors]


def test_ledger_records_exactly_the_expected_retired_ids() -> None:
    ledger = _ledger()
    ids = [entry["extension_id"] for entry in ledger["retired_extensions"]]
    assert sorted(ids) == sorted(EXPECTED_RETIRED)
    # uniqueItems is enforced by the schema; assert it here too for clarity.
    assert len(ids) == len(set(ids))


def test_every_retired_entry_is_fully_specified() -> None:
    for entry in _ledger()["retired_extensions"]:
        assert entry["ratchet_bucket"] == "retire_candidate"
        assert entry["restorable_from_git_history"] is True
        assert len(entry["reason"]) >= 10
        assert entry["superseded_by"].strip()


def test_retired_ids_are_absent_from_live_bundled_inventory() -> None:
    # The core invariant: a retired id must NOT still ship as a loadable manifest.
    reg = ExtensionRegistry()
    reg.load_from_defaults()
    live_ids = {manifest.extension_id for manifest in reg.list_all()}
    retired_ids = {entry["extension_id"] for entry in _ledger()["retired_extensions"]}
    assert retired_ids.isdisjoint(live_ids), f"retired-on-paper but still shipped: {sorted(retired_ids & live_ids)}"


def test_ledger_file_is_not_loaded_as_an_extension() -> None:
    # RETIRED.v1.json lives under defaults/extensions/ but is a file, not a
    # manifest directory; the loader (dir-walk only) must ignore it.
    reg = ExtensionRegistry()
    reg.load_from_defaults()
    live_ids = {manifest.extension_id for manifest in reg.list_all()}
    assert "RETIRED" not in live_ids
    assert "RETIRED.v1" not in live_ids


def test_schema_rejects_unknown_top_level_field() -> None:
    bad = copy.deepcopy(_ledger())
    bad["unexpected_field"] = "nope"
    errors = list(Draft202012Validator(_schema()).iter_errors(bad))
    assert errors, "additionalProperties:false must reject unknown top-level fields"


def test_schema_rejects_unknown_entry_field() -> None:
    bad = copy.deepcopy(_ledger())
    bad["retired_extensions"][0]["unexpected_field"] = "nope"
    errors = list(Draft202012Validator(_schema()).iter_errors(bad))
    assert errors, "additionalProperties:false must reject unknown per-entry fields"
