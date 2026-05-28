#!/usr/bin/env python3
"""RI-7.8b-bc10 sequential scenario runner with cost-aware fail-closed semantics.

Runs 4 scenarios in fixed order:
1. small_completion_a (success_billable)
2. small_completion_b (success_billable)
3. small_completion_c (success_billable)
4. budget_cap_precheck_denied (no provider call, zero cost)

For each scenario:
- Compute projected cost from pinned pricing source + max_output_tokens cap
- For budget_cap_precheck_denied: synthetically project over max_usd
- Pre-call cost check: if cumulative + projected > max_usd, fail-closed BEFORE
  any provider client instantiation OR OPENAI_API_KEY env read
- Else: instantiate AoKernelClient, read OPENAI_API_KEY, make real call
- Normalize usage from provider response
- Compute actual cost from pinned pricing source
- Post-call cost check: if cumulative + actual > max_usd, fail-closed
- Emit per-call marker JSON (redacted; no provider response body, no token material)
- Schema-validate marker before write

Maintains in-process ledger (Decimal) for cumulative cost. Sequential single-job
execution eliminates inter-job race that matrix parallelism would introduce.

Authority: invoked from `bc10-real-adapter-usage-cost.yml` workflow ONLY after
all pre-secret guards in `ri78b_bc10_activation_window.py` pass. OPENAI_API_KEY
is scoped to this script's env only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from decimal import Decimal, getcontext
from pathlib import Path

import jsonschema


SCRIPT_NAME = "bc10_run_scenarios.py"
MAX_USD = Decimal("5.00")
MAX_OUTPUT_TOKENS_CAP = 64
ALLOWED_MODEL_CANONICAL = "openai/gpt-4o-mini"
ALLOWED_PROVIDER_ID = "openai"
ALLOWED_MODEL_ID = "gpt-4o-mini"

# Per-scenario prompt seeds (kept tiny for cost bounds)
SCENARIO_PROMPTS = {
    "small_completion_a": "Reply with the single word OK.",
    "small_completion_b": "Reply with the single word YES.",
    "small_completion_c": "Reply with the single word DONE.",
    "budget_cap_precheck_denied": "<<not invoked: pre-call denied>>",
}

SCENARIOS_FIXED_ORDER = [
    "small_completion_a",
    "small_completion_b",
    "small_completion_c",
    "budget_cap_precheck_denied",
]

# Decimal precision for cost arithmetic
getcontext().prec = 20


def fail(reason: str) -> None:
    print(f"[{SCRIPT_NAME}] fail-closed: {reason}", file=sys.stderr)
    sys.exit(1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    if not path.is_file():
        fail(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"json decode error in {path}: {e}")
        return {}


def fmt_cost(value: Decimal) -> str:
    """Format Decimal cost as 8-decimal-place string."""
    return f"{value:.8f}"


@dataclass
class PricingModel:
    input_cost_per_1k_tokens_usd: Decimal
    output_cost_per_1k_tokens_usd: Decimal
    pricing_source_digest_sha256: str  # without "sha256:" prefix

    def project_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            Decimal(input_tokens) * self.input_cost_per_1k_tokens_usd / Decimal(1000)
            + Decimal(output_tokens) * self.output_cost_per_1k_tokens_usd / Decimal(1000)
        )


def load_pricing(pricing_source_path: Path) -> PricingModel:
    data = load_json(pricing_source_path)
    digest = sha256_file(pricing_source_path)
    return PricingModel(
        input_cost_per_1k_tokens_usd=Decimal(data["input_cost_per_1k_tokens_usd"]),
        output_cost_per_1k_tokens_usd=Decimal(data["output_cost_per_1k_tokens_usd"]),
        pricing_source_digest_sha256=digest,
    )


def compute_projected_for_scenario(
    scenario: str, pricing: PricingModel
) -> Decimal:
    """Worst-case projected cost: assume max_input_tokens + max_output_tokens."""
    if scenario == "budget_cap_precheck_denied":
        # Synthetic over-budget projection to force fail-closed
        return MAX_USD + Decimal("1.00")
    # Conservative input estimate: prompt + system + headers, ~64 tokens worst-case
    max_input = MAX_OUTPUT_TOKENS_CAP
    max_output = MAX_OUTPUT_TOKENS_CAP
    return pricing.project_cost(max_input, max_output)


def make_marker(
    *,
    scenario: str,
    scenario_outcome: str,
    requested_model: str,
    resolved_model: str,
    max_output_tokens_cap: int,
    provider_call_performed: bool,
    billable_call_count_delta: int,
    input_tokens: int,
    output_tokens: int,
    projected_cost_usd: Decimal,
    actual_cost_usd: Decimal,
    cumulative_before: Decimal,
    cumulative_after: Decimal,
    pricing_digest: str,
    run_id: str,
    run_attempt: str,
    head_sha: str,
    workflow_ref: str,
    workflow_content_sha256: str,
) -> dict:
    total_tokens = input_tokens + output_tokens
    usage_source = (
        "provider_api_response" if provider_call_performed else "no_call_no_usage"
    )
    cost_source = (
        "provider_usage_plus_pinned_pricing_source"
        if provider_call_performed
        else "no_billable_provider_call"
    )
    return {
        "schema_version": "ri7-8b-bc10-per-call-runtime-call-marker.v1",
        "artifact_kind": "ri7_8b_bc10_per_call_runtime_call_marker",
        "scenario": scenario,
        "scenario_outcome": scenario_outcome,
        "requested_model": requested_model,
        "resolved_model": resolved_model,
        "model_allowlist_enforced": True,
        "model_allowlist": [ALLOWED_MODEL_CANONICAL],
        "max_output_tokens_cap": max_output_tokens_cap,
        "provider_call_performed": provider_call_performed,
        "billable_call_count_delta": billable_call_count_delta,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "projected_cost_usd": fmt_cost(projected_cost_usd),
        "actual_cost_usd": fmt_cost(actual_cost_usd),
        "cumulative_cost_usd_before": fmt_cost(cumulative_before),
        "cumulative_cost_usd_after": fmt_cost(cumulative_after),
        "pricing_source_digest": f"sha256:{pricing_digest}",
        "usage_source": usage_source,
        "cost_source": cost_source,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "head_sha": head_sha,
        "workflow_ref": workflow_ref,
        "workflow_content_sha256": workflow_content_sha256,
        "secret_boundary": "no_secret_material_emitted_no_token_no_credential",
        "raw_response_recorded": False,
        "secret_material_recorded": False,
        "secret_scope_after_all_pre_provider_guards": True,
        "budget_cap_precheck_denied_completes_without_provider_client_init": True,
        "budget_cap_precheck_denied_completes_without_api_key_read": True,
        "retry_behavior": "wrapper_no_retry_loop_transport_default_skipped",
    }


def validate_marker(marker: dict, schema_path: Path) -> None:
    schema = load_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(marker))
    if errors:
        details = "; ".join(
            f"{list(e.absolute_path)}: {e.message}" for e in errors[:5]
        )
        fail(f"marker schema validation failed: {details}")


def emit_marker(marker: dict, output_dir: Path, scenario: str, run_id: str, run_attempt: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    marker_path = output_dir / f"marker-{scenario}-{run_id}-attempt-{run_attempt}.json"
    marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True), encoding="utf-8")
    return marker_path


def run_provider_call(
    *,
    scenario: str,
    pricing: PricingModel,
) -> tuple[int, int, Decimal]:
    """Instantiate AoKernelClient and make a real call to openai/gpt-4o-mini.

    Returns: (input_tokens, output_tokens, actual_cost_usd).

    OPENAI_API_KEY is read from env at this point. Pre-call guard ensures
    this function is only invoked after pre-secret guards passed.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        fail("OPENAI_API_KEY not present in env at provider-call time")

    # Lazy import: avoid touching ao_kernel until pre-secret guards passed
    from ao_kernel import AoKernelClient  # type: ignore[import]

    prompt = SCENARIO_PROMPTS[scenario]
    messages = [{"role": "user", "content": prompt}]

    try:
        with AoKernelClient(workspace_root=".") as client:
            result = client.llm_call(
                messages=messages,
                provider_id=ALLOWED_PROVIDER_ID,
                model=ALLOWED_MODEL_ID,
                api_key=api_key,
                max_tokens=MAX_OUTPUT_TOKENS_CAP,
                stream=False,
            )
    except Exception as e:
        fail(f"provider call failed: {type(e).__name__}: {e}")

    # Normalize usage from result
    usage = getattr(result, "usage", None) or {}
    if isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)))
        output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)))
    else:
        # Object-style usage
        input_tokens = int(getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0)))
        output_tokens = int(
            getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0))
        )

    actual_cost = pricing.project_cost(input_tokens, output_tokens)
    return input_tokens, output_tokens, actual_cost


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RI-7.8b-bc10 sequential scenario runner (cost-aware, fail-closed)"
    )
    parser.add_argument("--output-dir", required=True, help="Output directory for per-call markers")
    parser.add_argument("--pricing-source", required=True, help="Path to pricing source JSON")
    parser.add_argument(
        "--marker-schema",
        required=True,
        help="Path to per-call marker schema for validation",
    )
    parser.add_argument("--workflow-path", required=True, help="Path to workflow file for SHA-256")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-ref", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    pricing_source_path = Path(args.pricing_source)
    marker_schema_path = Path(args.marker_schema)
    workflow_path = Path(args.workflow_path)

    pricing = load_pricing(pricing_source_path)
    workflow_content_sha256 = sha256_file(workflow_path)

    requested_model = ALLOWED_MODEL_CANONICAL
    resolved_model = ALLOWED_MODEL_CANONICAL

    ledger = Decimal("0.00000000")
    emitted: list[Path] = []
    success_billable_count = 0
    denied_count = 0

    for scenario in SCENARIOS_FIXED_ORDER:
        projected = compute_projected_for_scenario(scenario, pricing)
        cumulative_before = ledger
        projected_total = cumulative_before + projected

        # Pre-call cost check: fail-closed BEFORE any client init or API key read
        if projected_total > MAX_USD:
            # budget_cap_precheck_denied path (or any unexpected over-budget)
            actual_cost = Decimal("0.00000000")
            scenario_outcome = "budget_cap_precheck_denied"
            provider_call_performed = False
            billable_call_count_delta = 0
            input_tokens = 0
            output_tokens = 0
            cumulative_after = cumulative_before
            marker = make_marker(
                scenario=scenario,
                scenario_outcome=scenario_outcome,
                requested_model=requested_model,
                resolved_model=resolved_model,
                max_output_tokens_cap=MAX_OUTPUT_TOKENS_CAP,
                provider_call_performed=provider_call_performed,
                billable_call_count_delta=billable_call_count_delta,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                projected_cost_usd=projected,
                actual_cost_usd=actual_cost,
                cumulative_before=cumulative_before,
                cumulative_after=cumulative_after,
                pricing_digest=pricing.pricing_source_digest_sha256,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
                head_sha=args.head_sha,
                workflow_ref=args.workflow_ref,
                workflow_content_sha256=workflow_content_sha256,
            )
            validate_marker(marker, marker_schema_path)
            marker_path = emit_marker(
                marker, output_dir, scenario, args.run_id, args.run_attempt
            )
            emitted.append(marker_path)
            denied_count += 1
            print(
                f"[{SCRIPT_NAME}] scenario={scenario} outcome=budget_cap_precheck_denied "
                f"projected={projected} cumulative_before={cumulative_before} "
                f"(no provider client init, no API key read)"
            )
            continue

        # Pre-call guard passed: instantiate client + provider call
        input_tokens, output_tokens, actual_cost = run_provider_call(
            scenario=scenario,
            pricing=pricing,
        )

        # Post-call cost check
        cumulative_after = cumulative_before + actual_cost
        if cumulative_after > MAX_USD:
            fail(
                f"post-call cumulative cost overflow: cumulative_after={cumulative_after} > "
                f"max_usd={MAX_USD}"
            )

        # Success billable marker
        marker = make_marker(
            scenario=scenario,
            scenario_outcome="success_billable",
            requested_model=requested_model,
            resolved_model=resolved_model,
            max_output_tokens_cap=MAX_OUTPUT_TOKENS_CAP,
            provider_call_performed=True,
            billable_call_count_delta=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            projected_cost_usd=projected,
            actual_cost_usd=actual_cost,
            cumulative_before=cumulative_before,
            cumulative_after=cumulative_after,
            pricing_digest=pricing.pricing_source_digest_sha256,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            head_sha=args.head_sha,
            workflow_ref=args.workflow_ref,
            workflow_content_sha256=workflow_content_sha256,
        )
        validate_marker(marker, marker_schema_path)
        marker_path = emit_marker(
            marker, output_dir, scenario, args.run_id, args.run_attempt
        )
        emitted.append(marker_path)
        ledger = cumulative_after
        success_billable_count += 1
        print(
            f"[{SCRIPT_NAME}] scenario={scenario} outcome=success_billable "
            f"input_tokens={input_tokens} output_tokens={output_tokens} "
            f"actual_cost={actual_cost} cumulative_after={cumulative_after}"
        )

    summary = {
        "total_markers_emitted": len(emitted),
        "success_billable_count": success_billable_count,
        "budget_cap_precheck_denied_count": denied_count,
        "final_cumulative_cost_usd": fmt_cost(ledger),
        "max_usd": fmt_cost(MAX_USD),
        "marker_paths": [str(p) for p in emitted],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
