"""LLM output evaluation harness — 6 deterministic heuristic-based checks.

NOTE: These are rule-based/heuristic checks, NOT LLM-based evaluation.
Groundedness uses word overlap, citation uses substring match,
refusal uses keyword detection. For LLM-based eval, use external tools.

Checks:
    json_conformance       — JSON parse + optional jsonschema validation
    groundedness           — word overlap heuristic (30% threshold)
    citation_completeness  — substring search for expected refs (80% threshold)
    tool_result_consistency — tool output values reflected in response
    refusal_correctness    — keyword-based refusal detection
    truncation_safety      — brace count + sentence termination heuristic
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from ao_kernel._internal.shared.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class EvalResult:
    """Single evaluation check result."""
    check_id: str
    passed: bool
    score: float  # 0.0 - 1.0
    reason: str
    evidence: Dict[str, Any]


def check_json_conformance(
    output: str,
    schema: Dict[str, Any] | None = None,
) -> EvalResult:
    """Check if output is valid JSON and optionally conforms to schema."""
    try:
        obj = json.loads(output.strip())
    except (json.JSONDecodeError, ValueError):
        return EvalResult("json_conformance", False, 0.0, "Output is not valid JSON", {"raw_length": len(output)})

    if not isinstance(obj, dict):
        return EvalResult("json_conformance", False, 0.2, "JSON is not an object", {"type": type(obj).__name__})

    if schema is None:
        return EvalResult("json_conformance", True, 1.0, "Valid JSON object", {"keys": list(obj.keys())[:10]})

    try:
        from jsonschema import Draft202012Validator
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(obj))
        if not errors:
            return EvalResult("json_conformance", True, 1.0, "Schema valid", {"keys": list(obj.keys())[:10]})
        return EvalResult(
            "json_conformance", False, max(0.0, 1.0 - len(errors) * 0.2),
            f"{len(errors)} schema errors",
            {"errors": [e.message for e in errors[:3]]},
        )
    except ImportError:
        return EvalResult("json_conformance", True, 0.8, "JSON valid (no schema validation)", {})


def check_groundedness(
    output: str,
    context_sources: List[str],
    *,
    use_embedding: bool = False,
    embedding_config: Dict[str, Any] | None = None,
) -> EvalResult:
    """Check if output claims are grounded in context sources.

    Two modes:
    1. Heuristic (default): word overlap between output and context
    2. Embedding (use_embedding=True): cosine similarity between embeddings

    Embedding mode requires API key in embedding_config.
    Falls back to heuristic if embedding unavailable.
    """
    if not context_sources:
        return EvalResult("groundedness", True, 1.0, "No context to check against", {})

    # Try embedding-based groundedness if requested
    if use_embedding and embedding_config:
        emb_result = _check_groundedness_embedding(output, context_sources, embedding_config)
        if emb_result is not None:
            return emb_result

    # Fallback: word overlap heuristic
    context_text = " ".join(context_sources).lower()
    context_words = set(re.findall(r"\b\w{4,}\b", context_text))

    output_words = set(re.findall(r"\b\w{4,}\b", output.lower()))
    if not output_words:
        return EvalResult("groundedness", True, 1.0, "No substantive output words", {})

    overlap = output_words & context_words
    score = len(overlap) / len(output_words) if output_words else 1.0
    passed = score >= 0.3  # At least 30% word overlap

    return EvalResult(
        "groundedness", passed, round(score, 3),
        f"{len(overlap)}/{len(output_words)} words grounded ({score:.0%})",
        {"overlap_count": len(overlap), "output_word_count": len(output_words)},
    )


def _check_groundedness_embedding(
    output: str,
    context_sources: List[str],
    config: Dict[str, Any],
) -> EvalResult | None:
    """Embedding-based groundedness check. Returns None on failure (triggers heuristic fallback)."""
    try:
        from ao_kernel.context.semantic_retrieval import cosine_similarity, embed_text

        api_key = config.get("api_key", "")
        provider_id = config.get("provider_id", "openai")
        model = config.get("model", "text-embedding-3-small")
        base_url = config.get("base_url", "https://api.openai.com/v1")

        output_emb = embed_text(output, provider_id=provider_id, model=model, base_url=base_url, api_key=api_key)
        if not output_emb:
            return None

        context_text = " ".join(context_sources)
        context_emb = embed_text(context_text, provider_id=provider_id, model=model, base_url=base_url, api_key=api_key)
        if not context_emb:
            return None

        score = cosine_similarity(output_emb, context_emb)
        passed = score >= 0.5  # Embedding similarity threshold

        return EvalResult(
            "groundedness", passed, round(max(0, score), 3),
            f"Embedding similarity: {score:.2f} (threshold: 0.5)",
            {"method": "embedding", "similarity": round(score, 4), "model": model},
        )
    except Exception:
        return None  # Fallback to heuristic


def check_citation_completeness(
    output: str,
    expected_refs: List[str],
) -> EvalResult:
    """Check if expected references appear in output."""
    if not expected_refs:
        return EvalResult("citation_completeness", True, 1.0, "No expected refs", {})

    found = []
    missing = []
    for ref in expected_refs:
        if ref.lower() in output.lower():
            found.append(ref)
        else:
            missing.append(ref)

    score = len(found) / len(expected_refs)
    passed = score >= 0.8  # At least 80% of refs present

    return EvalResult(
        "citation_completeness", passed, round(score, 3),
        f"{len(found)}/{len(expected_refs)} refs found",
        {"found": found, "missing": missing},
    )


def check_tool_result_consistency(
    tool_calls: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    output: str,
) -> EvalResult:
    """Check if tool results are reflected in the output."""
    if not tool_calls or not tool_results:
        return EvalResult("tool_consistency", True, 1.0, "No tool calls to check", {})

    # Check that each tool result's key values appear in output
    reflected = 0
    total_checks = 0
    for result in tool_results:
        if not isinstance(result, dict):
            continue
        output_data = result.get("output")
        if isinstance(output_data, dict):
            for key, val in output_data.items():
                total_checks += 1
                if str(val).lower() in output.lower():
                    reflected += 1
        elif isinstance(output_data, str) and output_data:
            total_checks += 1
            if output_data[:50].lower() in output.lower():
                reflected += 1

    if total_checks == 0:
        return EvalResult("tool_consistency", True, 1.0, "No tool data to verify", {})

    score = reflected / total_checks
    passed = score >= 0.5

    return EvalResult(
        "tool_consistency", passed, round(score, 3),
        f"{reflected}/{total_checks} tool values reflected in output",
        {"reflected": reflected, "total_checks": total_checks},
    )


def check_refusal_correctness(
    output: str,
    should_refuse: bool = False,
) -> EvalResult:
    """Check if the model correctly refused or accepted the request."""
    refusal_indicators = [
        "i cannot", "i can't", "i'm unable", "i am unable",
        "i'm not able", "i must decline", "i won't", "i will not",
        "sorry, but i", "i apologize, but",
    ]
    output_lower = output.lower()
    is_refusal = any(indicator in output_lower for indicator in refusal_indicators)

    if should_refuse and is_refusal:
        return EvalResult("refusal_correctness", True, 1.0, "Correctly refused", {"detected_refusal": True})
    if should_refuse and not is_refusal:
        return EvalResult("refusal_correctness", False, 0.0, "Should have refused but didn't", {"detected_refusal": False})
    if not should_refuse and is_refusal:
        return EvalResult("refusal_correctness", False, 0.3, "Incorrectly refused", {"detected_refusal": True})
    return EvalResult("refusal_correctness", True, 1.0, "Correctly accepted", {"detected_refusal": False})


def check_truncation_safety(
    output: str,
    max_tokens_requested: int | None = None,
) -> EvalResult:
    """Check if output appears truncated and still usable."""
    if not output:
        return EvalResult("truncation_safety", False, 0.0, "Empty output", {})

    stripped = output.strip()
    # Truncation indicators
    ends_mid_sentence = stripped and stripped[-1] not in ".!?}])\"\n"
    ends_mid_json = stripped.count("{") > stripped.count("}")

    if ends_mid_json:
        return EvalResult(
            "truncation_safety", False, 0.2,
            "Output appears truncated mid-JSON",
            {"open_braces": stripped.count("{"), "close_braces": stripped.count("}")},
        )
    if ends_mid_sentence and len(stripped) > 100:
        return EvalResult(
            "truncation_safety", False, 0.5,
            "Output may be truncated mid-sentence",
            {"last_char": stripped[-1], "length": len(stripped)},
        )
    return EvalResult("truncation_safety", True, 1.0, "Output appears complete", {"length": len(stripped)})


def run_eval_suite(
    output: str,
    *,
    schema: Dict[str, Any] | None = None,
    context_sources: List[str] | None = None,
    expected_refs: List[str] | None = None,
    tool_calls: List[Dict[str, Any]] | None = None,
    tool_results: List[Dict[str, Any]] | None = None,
    should_refuse: bool = False,
    max_tokens: int | None = None,
) -> List[EvalResult]:
    """Run all applicable eval checks."""
    results: list[EvalResult] = []

    # Always run truncation check
    results.append(check_truncation_safety(output, max_tokens))

    # JSON conformance (if output looks like JSON)
    if output.strip().startswith("{") or schema is not None:
        results.append(check_json_conformance(output, schema))

    # Groundedness (if context provided)
    if context_sources:
        results.append(check_groundedness(output, context_sources))

    # Citation completeness (if refs expected)
    if expected_refs:
        results.append(check_citation_completeness(output, expected_refs))

    # Tool consistency (if tool calls present)
    if tool_calls or tool_results:
        results.append(check_tool_result_consistency(
            tool_calls or [], tool_results or [], output,
        ))

    # Refusal correctness
    results.append(check_refusal_correctness(output, should_refuse))

    return results


def eval_scorecard(results: List[EvalResult]) -> Dict[str, Any]:
    """Aggregate eval results into a scorecard."""
    if not results:
        return {"total_checks": 0, "passed": 0, "failed": 0, "avg_score": 0.0, "all_passed": True}

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    avg_score = sum(r.score for r in results) / len(results)

    return {
        "total_checks": len(results),
        "passed": passed,
        "failed": failed,
        "avg_score": round(avg_score, 3),
        "all_passed": failed == 0,
        "worst_check": min(results, key=lambda r: r.score).check_id if results else None,
        "checks": [
            {"check_id": r.check_id, "passed": r.passed, "score": r.score, "reason": r.reason}
            for r in results
        ],
    }
