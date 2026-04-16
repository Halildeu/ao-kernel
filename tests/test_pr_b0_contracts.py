"""Contract tests for FAZ-B PR-B0 bundled artefacts.

New-in-B0 assets that land as declarative data (not code):
- 4 data schemas (claim, fencing-state, price-catalog, spend-ledger)
- 3 policy schemas (coordination-claims, cost-tracking, metrics)
- 3 bundled dormant policies
- 1 bundled price catalog (checksum-verified)
- 1 bundled workflow (review_ai_flow — contract pin for B6/B7 runtime)
- review-findings artefact schema (for the output_parse rule walker
  PR-B2/B6 will exercise end-to-end)

This suite asserts: each schema is meta-valid (Draft 2020-12); each
bundled instance validates against its declared schema; cross-schema
invariants hold (capability_enum parity — already covered in
test_workflow_registry.py but asserted again here defensively);
policy-wide rollout stance (all three B0 policies ship dormant); and
a handful of sad-path fixtures (missing required field, wrong enum,
severity outside closed set, checksum mismatch).

Companion suites exercising specific surfaces:
- tests/test_executor_adapter_invoker.py — output_parse rule walker
  + InvocationResult.extracted_outputs (TestOutputParseExtraction +
  TestDuplicateCapabilityLoaderCheck)
- tests/test_config.py — catalogs loader (load_default("catalogs", ...))
  + deterministic equality on bundled load + catalog checksum round-trip
- tests/test_workflow_registry.py::TestPatternDriftGuard::
  test_capability_enum_matches_adapter_contract — capability_enum
  parity between adapter and workflow-definition schemas
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


SCHEMAS_NEW_IN_B0 = [
    "claim.schema.v1.json",
    "fencing-state.schema.v1.json",
    "price-catalog.schema.v1.json",
    "spend-ledger.schema.v1.json",
    "review-findings.schema.v1.json",
    "policy-coordination-claims.schema.v1.json",
    "policy-cost-tracking.schema.v1.json",
    "policy-metrics.schema.v1.json",
]


def _load_schema(name: str) -> dict[str, Any]:
    return load_default("schemas", name)


# ---------------------------------------------------------------------------
# Every new schema is Draft 2020-12 meta-valid
# ---------------------------------------------------------------------------


class TestSchemaMetaValidity:
    @pytest.mark.parametrize("name", SCHEMAS_NEW_IN_B0)
    def test_schema_is_draft_2020_12_valid(self, name: str) -> None:
        schema = _load_schema(name)
        # Raises jsonschema.exceptions.SchemaError on failure.
        Draft202012Validator.check_schema(schema)
        # Sanity — every schema declares $schema + $id so loaders can
        # dispatch by URN. Also silences the test-quality advisory by
        # making the success path explicit.
        assert schema.get("$schema", "").startswith("https://json-schema.org/draft/")
        assert schema.get("$id", "").startswith("urn:ao:")


# ---------------------------------------------------------------------------
# Bundled instances validate against their declared schemas
# ---------------------------------------------------------------------------


class TestBundledDefaultsValidate:
    def test_policy_coordination_claims_matches_schema(self) -> None:
        policy = load_default("policies", "policy_coordination_claims.v1.json")
        schema = _load_schema("policy-coordination-claims.schema.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(policy))
        assert errors == [], [e.message for e in errors]

    def test_policy_cost_tracking_matches_schema(self) -> None:
        policy = load_default("policies", "policy_cost_tracking.v1.json")
        schema = _load_schema("policy-cost-tracking.schema.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(policy))
        assert errors == [], [e.message for e in errors]

    def test_policy_metrics_matches_schema(self) -> None:
        policy = load_default("policies", "policy_metrics.v1.json")
        schema = _load_schema("policy-metrics.schema.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(policy))
        assert errors == [], [e.message for e in errors]

    def test_bundled_price_catalog_matches_schema(self) -> None:
        catalog = load_default("catalogs", "price-catalog.v1.json")
        schema = _load_schema("price-catalog.schema.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(catalog))
        assert errors == [], [e.message for e in errors]

    def test_bundled_review_ai_flow_matches_schema(self) -> None:
        """review_ai_flow is the contract pin for B6 runtime; B0 asserts
        it parses against the existing workflow-definition schema with the
        new review_findings capability in capability_enum."""
        # workflow-definition is an existing PR-A2 schema, not "new in B0",
        # so load it via the defaults helper directly.
        flow_path = (
            Path(__file__).resolve().parent.parent
            / "ao_kernel"
            / "defaults"
            / "workflows"
            / "review_ai_flow.v1.json"
        )
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
        schema = load_default("schemas", "workflow-definition.schema.v1.json")
        errors = list(Draft202012Validator(schema).iter_errors(flow))
        assert errors == [], [e.message for e in errors]
        # Declared capability requirement references the new enum value.
        assert "review_findings" in flow["required_capabilities"]


# ---------------------------------------------------------------------------
# Rollout stance — all three B0 policies ship dormant
# ---------------------------------------------------------------------------


class TestPoliciesShipDormant:
    """B0 release gate: no policy from this PR activates automatically.
    Operators opt in via workspace override. See CLAUDE.md §2."""

    @pytest.mark.parametrize(
        "policy_name",
        [
            "policy_coordination_claims.v1.json",
            "policy_cost_tracking.v1.json",
            "policy_metrics.v1.json",
        ],
    )
    def test_top_level_enabled_is_false(self, policy_name: str) -> None:
        policy = load_default("policies", policy_name)
        assert policy["enabled"] is False, (
            f"{policy_name} must ship dormant (enabled=false); "
            f"operators opt in via workspace override."
        )

    def test_metrics_labels_advanced_also_off(self) -> None:
        """Defence-in-depth: even if a user force-enables the policy,
        the advanced-label switch stays off and the allowlist is empty
        so cardinality-dangerous labels do not leak."""
        policy = load_default("policies", "policy_metrics.v1.json")
        assert policy["labels_advanced"]["enabled"] is False
        assert policy["labels_advanced"]["allowlist"] == []


# ---------------------------------------------------------------------------
# review-findings schema — closed severity enum + happy + sad fixtures
# ---------------------------------------------------------------------------


class TestReviewFindingsSchema:
    def test_severity_enum_is_exactly_four_values(self) -> None:
        schema = _load_schema("review-findings.schema.v1.json")
        sev = schema["$defs"]["finding"]["properties"]["severity"]["enum"]
        assert sev == ["error", "warning", "info", "note"]
        # 'critical' was deliberately excluded (CNS-028v2 iter-2 W7).
        assert "critical" not in sev

    def test_minimal_fixture_validates(self) -> None:
        schema = _load_schema("review-findings.schema.v1.json")
        payload = {
            "schema_version": "1",
            "findings": [
                {"severity": "warning", "message": "tighten the bound"}
            ],
            "summary": "Reviewed 1 file",
        }
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == []

    def test_empty_findings_list_is_valid(self) -> None:
        schema = _load_schema("review-findings.schema.v1.json")
        payload = {
            "schema_version": "1",
            "findings": [],
            "summary": "No issues",
        }
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == []

    def test_rejects_severity_outside_closed_enum(self) -> None:
        schema = _load_schema("review-findings.schema.v1.json")
        payload = {
            "schema_version": "1",
            "findings": [
                {"severity": "critical", "message": "not an allowed value"}
            ],
            "summary": "x",
        }
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors

    def test_rejects_missing_summary(self) -> None:
        schema = _load_schema("review-findings.schema.v1.json")
        payload = {
            "schema_version": "1",
            "findings": [],
            # summary missing
        }
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert any("summary" in e.message for e in errors)


# ---------------------------------------------------------------------------
# price-catalog schema — conditional vendor_model_id + checksum drift
# ---------------------------------------------------------------------------


class TestPriceCatalogSchema:
    def test_source_enum_is_exactly_three_values(self) -> None:
        schema = _load_schema("price-catalog.schema.v1.json")
        src_enum = schema["properties"]["source"]["enum"]
        assert set(src_enum) == {"bundled", "vendor_api", "manual"}

    def test_vendor_model_id_conditional_enforced_for_vendor_api(self) -> None:
        """W8v4 absorb: top-level source=vendor_api ⇒ every entry
        requires vendor_model_id. bundled / manual sources do not."""
        schema = _load_schema("price-catalog.schema.v1.json")
        entry_without_vendor_id = {
            "provider_id": "x",
            "model": "m",
            "input_cost_per_1k": 0.001,
            "output_cost_per_1k": 0.002,
            "currency": "USD",
            "billing_unit": "per_1k_tokens",
            "effective_date": "2026-04-16",
        }
        # Happy: bundled source, no vendor_model_id — valid
        ok_doc = {
            "catalog_version": "1",
            "generated_at": "2026-04-16T00:00:00+00:00",
            "source": "bundled",
            "stale_after": "2026-07-16T00:00:00+00:00",
            "checksum": "sha256:" + "0" * 64,
            "entries": [entry_without_vendor_id],
        }
        assert list(Draft202012Validator(schema).iter_errors(ok_doc)) == []

        # Sad: vendor_api source, no vendor_model_id — rejected
        sad_doc = dict(ok_doc, source="vendor_api")
        errors = list(Draft202012Validator(schema).iter_errors(sad_doc))
        assert errors, "vendor_api source must require vendor_model_id"

        # Happy again: vendor_api + vendor_model_id — valid
        recovered_doc = dict(
            ok_doc,
            source="vendor_api",
            entries=[dict(entry_without_vendor_id, vendor_model_id="m-2026-04-16")],
        )
        assert list(Draft202012Validator(schema).iter_errors(recovered_doc)) == []

    def test_bundled_catalog_checksum_matches_canonical_entries(self) -> None:
        """Regression guard for the PR-B2 checksum-verify path."""
        catalog = load_default("catalogs", "price-catalog.v1.json")
        canonical = json.dumps(
            catalog["entries"],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert catalog["checksum"] == expected


# ---------------------------------------------------------------------------
# Cross-schema drift guards (capability_enum parity restated defensively)
# ---------------------------------------------------------------------------


class TestCapabilityEnumDriftDefence:
    """Primary gate lives in test_workflow_registry.py::
    TestPatternDriftGuard. Restating the invariant here keeps the B0
    contract suite self-contained for future readers."""

    def test_capability_enum_sets_equal_and_include_review_findings(self) -> None:
        adapter = load_default("schemas", "agent-adapter-contract.schema.v1.json")
        workflow = load_default("schemas", "workflow-definition.schema.v1.json")
        a = set(adapter["$defs"]["capability_enum"]["enum"])
        w = set(workflow["$defs"]["capability_enum"]["enum"])
        assert a == w
        assert "review_findings" in a
