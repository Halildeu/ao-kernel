"""Tests for ``ao_kernel.cost.policy`` — typed policy loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from ao_kernel.cost.policy import (
    RoutingByCost,
    load_cost_policy,
)


def _valid_policy_dict(**overrides: Any) -> dict[str, Any]:
    base = {
        "version": "v1",
        "enabled": False,
        "price_catalog_path": ".ao/cost/catalog.v1.json",
        "spend_ledger_path": ".ao/cost/spend.jsonl",
        "fail_closed_on_exhaust": True,
        "strict_freshness": False,
        "fail_closed_on_missing_usage": True,
        "idempotency_window_lines": 1000,
        "routing_by_cost": {"enabled": False},
    }
    base.update(overrides)
    return base


class TestLoadBundledDefault:
    def test_bundled_ships_dormant(self, tmp_path: Path) -> None:
        """Bundled policy is dormant-by-default — operators opt in
        by dropping a workspace override."""
        policy = load_cost_policy(tmp_path)
        assert policy.enabled is False

    def test_bundled_default_knobs(self, tmp_path: Path) -> None:
        policy = load_cost_policy(tmp_path)
        assert policy.price_catalog_path == ".ao/cost/catalog.v1.json"
        assert policy.spend_ledger_path == ".ao/cost/spend.jsonl"
        assert policy.fail_closed_on_exhaust is True
        assert policy.strict_freshness is False
        assert policy.fail_closed_on_missing_usage is True
        assert policy.idempotency_window_lines == 1000
        assert policy.routing_by_cost.enabled is False
        assert policy.routing_by_cost.priority == "provider_priority"
        assert policy.routing_by_cost.fail_closed_on_catalog_missing is True


class TestWorkspaceOverride:
    def _write_override(self, workspace_root: Path, doc: dict[str, Any]) -> None:
        path = workspace_root / ".ao" / "policies" / "policy_cost_tracking.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, sort_keys=True))

    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        self._write_override(
            tmp_path,
            _valid_policy_dict(enabled=True, idempotency_window_lines=5000),
        )
        policy = load_cost_policy(tmp_path)
        assert policy.enabled is True
        assert policy.idempotency_window_lines == 5000

    def test_override_malformed_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / ".ao" / "policies" / "policy_cost_tracking.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json {{{")
        with pytest.raises(json.JSONDecodeError):
            load_cost_policy(tmp_path)

    def test_override_schema_invalid_raises(self, tmp_path: Path) -> None:
        """Fail-closed: operator error surfaces, not silently fall back
        to the bundled dormant default."""
        doc = _valid_policy_dict()
        del doc["strict_freshness"]  # violate required
        self._write_override(tmp_path, doc)
        with pytest.raises(ValidationError):
            load_cost_policy(tmp_path)


class TestInlineOverride:
    def test_inline_override_bypasses_filesystem(self, tmp_path: Path) -> None:
        """Callers can pass a dict directly without touching .ao/policies/."""
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(enabled=True, idempotency_window_lines=250),
        )
        assert policy.enabled is True
        assert policy.idempotency_window_lines == 250

    def test_inline_override_schema_invalid_raises(self, tmp_path: Path) -> None:
        bad = _valid_policy_dict()
        bad["idempotency_window_lines"] = 50  # schema violation (minimum: 100)
        with pytest.raises(ValidationError):
            load_cost_policy(tmp_path, override=bad)


class TestFailClosedOnExhaustConst:
    def test_schema_locks_true(self, tmp_path: Path) -> None:
        """CNS-007 invariant: fail_closed_on_exhaust MUST be true; any
        override attempting to set it false fails schema validation."""
        bad = _valid_policy_dict(fail_closed_on_exhaust=False)
        with pytest.raises(ValidationError):
            load_cost_policy(tmp_path, override=bad)


class TestFailClosedOnMissingUsage:
    def test_defaults_true(self, tmp_path: Path) -> None:
        policy = load_cost_policy(tmp_path)
        assert policy.fail_closed_on_missing_usage is True

    def test_operator_can_set_false(self, tmp_path: Path) -> None:
        """Audit-only deployments can opt into warn-log-and-continue."""
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(fail_closed_on_missing_usage=False),
        )
        assert policy.fail_closed_on_missing_usage is False


class TestIdempotencyWindowBounds:
    def test_minimum_100(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            load_cost_policy(
                tmp_path,
                override=_valid_policy_dict(idempotency_window_lines=99),
            )

    def test_maximum_100000(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            load_cost_policy(
                tmp_path,
                override=_valid_policy_dict(idempotency_window_lines=100001),
            )

    def test_boundary_values_accepted(self, tmp_path: Path) -> None:
        p_min = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(idempotency_window_lines=100),
        )
        assert p_min.idempotency_window_lines == 100

        p_max = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(idempotency_window_lines=100000),
        )
        assert p_max.idempotency_window_lines == 100000


class TestRoutingByCost:
    def test_defaults_disabled(self, tmp_path: Path) -> None:
        policy = load_cost_policy(tmp_path)
        assert isinstance(policy.routing_by_cost, RoutingByCost)
        assert policy.routing_by_cost.enabled is False

    def test_operator_enables(self, tmp_path: Path) -> None:
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(routing_by_cost={"enabled": True}),
        )
        assert policy.routing_by_cost.enabled is True

    def test_priority_defaults_provider_priority(self, tmp_path: Path) -> None:
        """PR-B3: pre-B3 behavior preserved when operator omits priority."""
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(routing_by_cost={"enabled": True}),
        )
        assert policy.routing_by_cost.priority == "provider_priority"

    def test_operator_enables_lowest_cost(self, tmp_path: Path) -> None:
        """Operator opts into cost-aware selection."""
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(
                routing_by_cost={
                    "enabled": True,
                    "priority": "lowest_cost",
                    "fail_closed_on_catalog_missing": False,
                },
            ),
        )
        assert policy.routing_by_cost.enabled is True
        assert policy.routing_by_cost.priority == "lowest_cost"
        assert policy.routing_by_cost.fail_closed_on_catalog_missing is False

    def test_priority_invalid_enum_raises(self, tmp_path: Path) -> None:
        """Schema closed-enum rejects typos at load time."""
        with pytest.raises(ValidationError):
            load_cost_policy(
                tmp_path,
                override=_valid_policy_dict(
                    routing_by_cost={"enabled": True, "priority": "cheapest"},
                ),
            )

    def test_override_omits_optional_fields_uses_defaults(self, tmp_path: Path) -> None:
        """Optional new fields (priority + fail_closed_on_catalog_missing)
        may be omitted; loader applies bundled defaults."""
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(routing_by_cost={"enabled": True}),
        )
        assert policy.routing_by_cost.priority == "provider_priority"
        assert policy.routing_by_cost.fail_closed_on_catalog_missing is True


class TestFailClosedOnCatalogMissing:
    def test_defaults_true(self, tmp_path: Path) -> None:
        """PR-B3 default: fail-closed when active mode + catalog missing."""
        policy = load_cost_policy(tmp_path)
        assert policy.routing_by_cost.fail_closed_on_catalog_missing is True

    def test_operator_can_relax(self, tmp_path: Path) -> None:
        """Operators can downgrade to warn-log fallback."""
        policy = load_cost_policy(
            tmp_path,
            override=_valid_policy_dict(
                routing_by_cost={
                    "enabled": True,
                    "priority": "lowest_cost",
                    "fail_closed_on_catalog_missing": False,
                },
            ),
        )
        assert policy.routing_by_cost.fail_closed_on_catalog_missing is False
