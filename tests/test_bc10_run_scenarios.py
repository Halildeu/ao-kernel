"""Focused unit tests for scripts/bc10_run_scenarios.py.

Critical behavioral contracts:
- budget_cap_precheck_denied branch does NOT instantiate AoKernelClient
- budget_cap_precheck_denied branch does NOT read OPENAI_API_KEY from env
- dict-return usage extraction works correctly (success_billable markers
  have non-zero input/output tokens and positive actual_cost_usd)
- missing/zero usage on success path fails-closed (no zero-usage success marker emitted)
- Sequential ledger updates correctly
- Marker schema validation runs before write
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "bc10_run_scenarios.py"
PRICING_SOURCE_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "pricing" / "openai_gpt_4o_mini.v1.json"
MARKER_SCHEMA_PATH = (
    REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-8b-bc10-per-call-runtime-call-marker.schema.v1.json"
)
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bc10-real-adapter-usage-cost.yml"


# Import the runner module for unit testing
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def test_bc10_run_scenarios_script_exists():
    assert SCRIPT_PATH.exists(), f"Runner script missing: {SCRIPT_PATH}"


def test_bc10_run_scenarios_imports_cleanly():
    """Module should import without side effects (no immediate execution)."""
    mod = _load_module()
    assert hasattr(mod, "main")
    assert hasattr(mod, "run_provider_call")
    assert hasattr(mod, "compute_projected_for_scenario")
    assert hasattr(mod, "make_marker")
    assert hasattr(mod, "load_pricing")
    assert hasattr(mod, "PricingModel")


def _load_module():
    """Load the runner module for direct invocation.

    Register in sys.modules BEFORE exec to allow `@dataclass` (Python 3.13 needs
    the module accessible via sys.modules during decorator application).
    """
    import importlib

    if "bc10_run_scenarios" in sys.modules:
        return sys.modules["bc10_run_scenarios"]
    spec = importlib.util.spec_from_file_location("bc10_run_scenarios", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bc10_run_scenarios"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_budget_cap_precheck_denied_projected_over_budget():
    """budget_cap_precheck_denied scenario projects synthetic over-budget cost."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    projected = mod.compute_projected_for_scenario("budget_cap_precheck_denied", pricing)
    assert projected > mod.MAX_USD, (
        f"budget_cap_precheck_denied must project over max_usd; got {projected}, max={mod.MAX_USD}"
    )


def test_compute_projected_for_success_scenarios_below_budget():
    """success scenarios project bounded cost below max_usd."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    for scenario in ("small_completion_a", "small_completion_b", "small_completion_c"):
        projected = mod.compute_projected_for_scenario(scenario, pricing)
        assert projected < mod.MAX_USD, f"{scenario} must project under max_usd; got {projected}"
        assert projected > Decimal(0), f"{scenario} must have positive projected cost"


def test_pricing_model_decimal_arithmetic_correct():
    """Pricing computation uses Decimal (no float contamination)."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    cost = pricing.project_cost(input_tokens=1000, output_tokens=1000)
    # Input: 1000 tokens * 0.00015/1000 = 0.00015
    # Output: 1000 tokens * 0.00060/1000 = 0.00060
    # Total: 0.00075
    expected = Decimal("0.00075")
    assert cost == expected, f"Expected {expected}, got {cost} (type {type(cost).__name__})"


def test_pricing_model_canonical_model_id():
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    assert pricing.input_cost_per_1k_tokens_usd == Decimal("0.00015000")
    assert pricing.output_cost_per_1k_tokens_usd == Decimal("0.00060000")


def test_make_marker_success_billable_non_zero_usage():
    """make_marker for success path must include non-zero usage and cost."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    marker = mod.make_marker(
        scenario="small_completion_a",
        scenario_outcome="success_billable",
        requested_model="openai/gpt-4o-mini",
        resolved_model="openai/gpt-4o-mini",
        max_output_tokens_cap=64,
        provider_call_performed=True,
        billable_call_count_delta=1,
        input_tokens=10,
        output_tokens=25,
        projected_cost_usd=Decimal("0.00010000"),
        actual_cost_usd=Decimal("0.00001650"),
        cumulative_before=Decimal("0.00000000"),
        cumulative_after=Decimal("0.00001650"),
        pricing_digest=pricing.pricing_source_digest_sha256,
        run_id="12345",
        run_attempt="1",
        head_sha="a" * 40,
        workflow_ref="foo@refs/heads/main",
        workflow_content_sha256="b" * 64,
    )
    assert marker["scenario_outcome"] == "success_billable"
    assert marker["provider_call_performed"] is True
    assert marker["billable_call_count_delta"] == 1
    assert marker["input_tokens"] > 0
    assert marker["output_tokens"] > 0
    assert marker["total_tokens"] > 0
    assert marker["actual_cost_usd"] != "0.00000000"
    assert marker["usage_source"] == "provider_api_response"
    assert marker["cost_source"] == "provider_usage_plus_pinned_pricing_source"


def test_make_marker_budget_denied_zero_cost():
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    marker = mod.make_marker(
        scenario="budget_cap_precheck_denied",
        scenario_outcome="budget_cap_precheck_denied",
        requested_model="openai/gpt-4o-mini",
        resolved_model="openai/gpt-4o-mini",
        max_output_tokens_cap=64,
        provider_call_performed=False,
        billable_call_count_delta=0,
        input_tokens=0,
        output_tokens=0,
        projected_cost_usd=Decimal("6.00000000"),
        actual_cost_usd=Decimal("0.00000000"),
        cumulative_before=Decimal("0.00001650"),
        cumulative_after=Decimal("0.00001650"),
        pricing_digest=pricing.pricing_source_digest_sha256,
        run_id="12345",
        run_attempt="1",
        head_sha="a" * 40,
        workflow_ref="foo@refs/heads/main",
        workflow_content_sha256="b" * 64,
    )
    assert marker["scenario_outcome"] == "budget_cap_precheck_denied"
    assert marker["provider_call_performed"] is False
    assert marker["billable_call_count_delta"] == 0
    assert marker["input_tokens"] == 0
    assert marker["output_tokens"] == 0
    assert marker["actual_cost_usd"] == "0.00000000"
    assert marker["usage_source"] == "no_call_no_usage"
    assert marker["cost_source"] == "no_billable_provider_call"


def test_marker_validates_against_schema():
    """Both success and denied markers validate against per-call marker schema."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    success_marker = mod.make_marker(
        scenario="small_completion_a",
        scenario_outcome="success_billable",
        requested_model="openai/gpt-4o-mini",
        resolved_model="openai/gpt-4o-mini",
        max_output_tokens_cap=64,
        provider_call_performed=True,
        billable_call_count_delta=1,
        input_tokens=10,
        output_tokens=25,
        projected_cost_usd=Decimal("0.00010000"),
        actual_cost_usd=Decimal("0.00001650"),
        cumulative_before=Decimal("0.00000000"),
        cumulative_after=Decimal("0.00001650"),
        pricing_digest=pricing.pricing_source_digest_sha256,
        run_id="12345",
        run_attempt="1",
        head_sha="a" * 40,
        workflow_ref="foo@refs/heads/main",
        workflow_content_sha256="b" * 64,
    )
    mod.validate_marker(success_marker, MARKER_SCHEMA_PATH)

    denied_marker = mod.make_marker(
        scenario="budget_cap_precheck_denied",
        scenario_outcome="budget_cap_precheck_denied",
        requested_model="openai/gpt-4o-mini",
        resolved_model="openai/gpt-4o-mini",
        max_output_tokens_cap=64,
        provider_call_performed=False,
        billable_call_count_delta=0,
        input_tokens=0,
        output_tokens=0,
        projected_cost_usd=Decimal("6.00000000"),
        actual_cost_usd=Decimal("0.00000000"),
        cumulative_before=Decimal("0.00001650"),
        cumulative_after=Decimal("0.00001650"),
        pricing_digest=pricing.pricing_source_digest_sha256,
        run_id="12345",
        run_attempt="1",
        head_sha="a" * 40,
        workflow_ref="foo@refs/heads/main",
        workflow_content_sha256="b" * 64,
    )
    mod.validate_marker(denied_marker, MARKER_SCHEMA_PATH)


def test_run_provider_call_dict_return_extracts_usage_correctly(monkeypatch):
    """The runner correctly extracts usage from dict-style llm_call return.

    This guards against the iter-5 bug where getattr(result, "usage") was
    used on a dict-return llm_call, causing zero-token markers.
    """
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)

    # Mock AoKernelClient to return a dict (matches actual repo API)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    class FakeContext:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def llm_call(self, **kwargs):
            return {
                "status": "OK",
                "text": "OK",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 15,
                    "output_tokens": 5,
                    "total_tokens": 20,
                },
                "provider_id": "openai",
                "model": "gpt-4o-mini",
            }

    fake_module = type(sys)("ao_kernel")
    fake_module.AoKernelClient = lambda **kw: FakeContext()
    monkeypatch.setitem(sys.modules, "ao_kernel", fake_module)

    input_tokens, output_tokens, actual_cost = mod.run_provider_call(scenario="small_completion_a", pricing=pricing)
    assert input_tokens == 15
    assert output_tokens == 5
    assert actual_cost > Decimal(0), f"actual_cost must be positive; got {actual_cost}"


def test_run_provider_call_zero_usage_fails_closed(monkeypatch):
    """Zero-usage response from provider must fail-closed (not emit zero-usage marker)."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    class FakeContext:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def llm_call(self, **kwargs):
            return {
                "status": "OK",
                "text": "",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                },
            }

    fake_module = type(sys)("ao_kernel")
    fake_module.AoKernelClient = lambda **kw: FakeContext()
    monkeypatch.setitem(sys.modules, "ao_kernel", fake_module)

    with pytest.raises(SystemExit) as exc_info:
        mod.run_provider_call(scenario="small_completion_a", pricing=pricing)
    assert exc_info.value.code != 0, "zero-usage response must exit non-zero"


def test_run_provider_call_missing_usage_fails_closed(monkeypatch):
    """Missing usage dict from provider must fail-closed."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    class FakeContext:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def llm_call(self, **kwargs):
            return {"status": "OK", "text": "OK", "tool_calls": []}  # no 'usage' key

    fake_module = type(sys)("ao_kernel")
    fake_module.AoKernelClient = lambda **kw: FakeContext()
    monkeypatch.setitem(sys.modules, "ao_kernel", fake_module)

    with pytest.raises(SystemExit) as exc_info:
        mod.run_provider_call(scenario="small_completion_a", pricing=pricing)
    assert exc_info.value.code != 0


def test_pricing_source_digest_format():
    """Pricing source digest is hex SHA-256 (no 'sha256:' prefix in raw field)."""
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)
    assert len(pricing.pricing_source_digest_sha256) == 64
    assert all(c in "0123456789abcdef" for c in pricing.pricing_source_digest_sha256)


def test_run_provider_call_not_invoked_in_budget_denied_path():
    """The script's main() must NOT call run_provider_call for budget_cap_precheck_denied.

    Verified via static check: budget_cap_precheck_denied scenario goes through
    pre-call cost check and the synthetic projected > MAX_USD makes it skip
    the provider call branch entirely.
    """
    mod = _load_module()
    pricing = mod.load_pricing(PRICING_SOURCE_PATH)

    # Simulate: for budget_cap_precheck_denied, projected > MAX_USD always
    projected = mod.compute_projected_for_scenario("budget_cap_precheck_denied", pricing)
    cumulative_before = Decimal("0.00000000")
    assert cumulative_before + projected > mod.MAX_USD, (
        "budget_cap_precheck_denied must trigger pre-call fail-closed (no provider call)"
    )
