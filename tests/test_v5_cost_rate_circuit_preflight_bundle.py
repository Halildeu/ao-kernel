"""V5 cost / rate / circuit-breaker preflight bundle invariants.

Current-state evidence for production-readiness matrix dimension 3
(cost_rate_circuit_breaker_evidence). Records the already-present cost-control
runtime modules (cost ceiling enforcement, per-provider circuit breaker, per
provider rate limiter, per-call audit, dry-run cost evidence harness) without
flipping any guard flag or claiming the dimension complete. The matrix
dimension stays ``partial``; live cost evidence, breach/rollback evidence from
a protected run, and a fresh pricing snapshot remain bound to PR-Xfinal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "v5-cost-rate-circuit-preflight-bundle.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-cost-rate-circuit-preflight.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
DOC_PATH = ROOT / ".claude" / "plans" / "V5-COST-RATE-CIRCUIT-PREFLIGHT-BUNDLE.md"


EXPECTED_CONTROLS = {
    "cost_ceiling_enforcement_module",
    "circuit_breaker_per_provider",
    "rate_limiter_per_provider",
    "per_call_audit_schema",
    "dry_run_cost_evidence_harness",
}


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _matrix() -> dict[str, Any]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def test_schema_present_valid_and_strict() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:v5-cost-rate-circuit-preflight-bundle:v1"

    def object_nodes(node: Any) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if node.get("type") == "object":
                nodes.append(node)
            for value in node.values():
                nodes.extend(object_nodes(value))
        elif isinstance(node, list):
            for value in node:
                nodes.extend(object_nodes(value))
        return nodes

    for node in object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_current_fixture_validates_and_pins_non_authority_state() -> None:
    payload = _fixture()
    assert _valid(payload)
    assert payload["dimension"] == "cost_rate_circuit_breaker_evidence"
    assert payload["evidence_class"] == "preflight_current_state"
    assert payload["final_release_bound"] is False
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    boundary = payload["current_boundary"]
    assert boundary["cost_ceiling_module_present"] is True
    assert boundary["soft_and_hard_breach_modeled"] is True
    assert boundary["circuit_breaker_per_provider_present"] is True
    assert boundary["rate_limiter_per_provider_present"] is True
    assert boundary["live_cost_evidence_bound_to_pr_xfinal"] is False


def test_schema_rejects_guard_flip_or_live_cost_claims() -> None:
    for field, value in (
        ("final_release_bound", True),
        ("support_widening", True),
        ("production_platform_claim", True),
        ("live_adapter_execution", True),
    ):
        payload = _fixture()
        payload[field] = value
        assert not _valid(payload), f"{field}={value!r} must fail closed"

    payload = _fixture()
    payload["current_boundary"]["live_cost_evidence_bound_to_pr_xfinal"] = True
    assert not _valid(payload), "premature live-cost PR-Xfinal binding must fail closed"


def test_schema_pins_exactly_five_canonical_controls() -> None:
    payload = _fixture()
    payload["cost_controls"][0]["control"] = "circuit_breaker_per_provider"
    assert not _valid(payload), "duplicate control must fail closed"

    payload = _fixture()
    payload["cost_controls"] = payload["cost_controls"][:4]
    assert not _valid(payload), "missing a canonical control must fail closed"


def test_schema_pins_three_distinct_residual_concepts() -> None:
    # Each of the three concepts must be present exactly once as a distinct object.
    for missing in ("live_cost", "breach_rollback", "pricing_snapshot"):
        payload = _fixture()
        kept = [item for item in payload["residual_missing_evidence"] if item["concept"] != missing]
        # Keep length 3 by duplicating a *different* concept, so `missing` is genuinely absent.
        payload["residual_missing_evidence"] = kept + [
            {"concept": kept[0]["concept"], "description": "duplicate filler"}
        ]
        assert not _valid(payload), f"missing '{missing}' residual concept must fail closed"

    # Concept-collapse attack (object form makes this impossible): a duplicate
    # concept with two fillers cannot satisfy three distinct concepts.
    payload = _fixture()
    payload["residual_missing_evidence"] = [
        {"concept": "live_cost", "description": "all three jammed in one"},
        {"concept": "live_cost", "description": "filler one"},
        {"concept": "live_cost", "description": "filler two"},
    ]
    assert not _valid(payload), "collapsing concepts into one must fail closed"


def test_cost_controls_match_expected_active_set() -> None:
    payload = _fixture()
    controls = payload["cost_controls"]
    assert {item["control"] for item in controls} == EXPECTED_CONTROLS
    for item in controls:
        assert item["current_state"] == "active_in_current_repo_runtime"
        assert item["future_prerequisite_under_pr_xfinal"].strip()


def test_cost_control_modules_exist_on_disk() -> None:
    payload = _fixture()
    modules = payload["cost_control_modules"]
    for path in modules.values():
        assert (ROOT / path).is_file(), f"{path} must exist"


def test_matrix_dimension_stays_partial_and_incomplete() -> None:
    matrix = _matrix()
    assert matrix["matrix_complete"] is False
    dim = next(d for d in matrix["dimensions"] if d["id"] == "cost_rate_circuit_breaker_evidence")
    assert dim["status"] in {"not_ready", "partial"}


def test_doc_present_and_non_authority() -> None:
    assert DOC_PATH.is_file()
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "cost_rate_circuit_breaker_evidence" in text
    assert "PR-Xfinal" in text
