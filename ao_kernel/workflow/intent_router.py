"""Rule-based intent classifier.

Evaluates priority-ordered keyword / regex / combined rules against
input text and returns a ``ClassificationResult`` with the target
workflow id, optional version pin, confidence, and matching rule id.

No-match semantic (plan v2 B4):

- ``fallback_strategy="error_on_no_match"`` → ``classify()`` returns
  ``None``.
- ``fallback_strategy="use_default"`` → ``default_workflow_id`` MUST
  be non-null (schema conditional); classify returns a result with
  ``matched_rule_id="__default__"`` and ``match_type="default"``.
- ``fallback_strategy="llm_fallback"`` → classify raises
  ``NotImplementedError``; implementation ships in PR-A6 under the
  optional ``[llm]`` extra.

Rules are validated at load time:

- Schema validation via ``intent-classifier-rules.schema.v1.json``.
- Duplicate ``rule_id`` → ``IntentRulesCorruptedError(reason=
  "duplicate_rule_id")``.
- Invalid regex pattern → ``IntentRulesCorruptedError(reason=
  "regex_compile")``.
- Two rules at the same priority both matching at classify time →
  ``IntentRulesCorruptedError(reason="duplicate_priority_match")``.
"""

from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any, Literal, Mapping, Sequence

from jsonschema.validators import Draft202012Validator

from ao_kernel.workflow.errors import IntentRulesCorruptedError

_SCHEMA_PACKAGE = "ao_kernel.defaults.schemas"
_SCHEMA_FILENAME = "intent-classifier-rules.schema.v1.json"
_BUNDLED_RULES_PACKAGE = "ao_kernel.defaults.intent_rules"
_BUNDLED_RULES_FILENAME = "default_rules.v1.json"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentRule:
    """Compiled intent classifier rule. Immutable."""

    rule_id: str
    workflow_id: str
    workflow_version: str | None
    priority: int
    match_type: Literal["keyword", "regex", "combined"]
    keywords: tuple[str, ...]
    regex_any: tuple[re.Pattern[str], ...]
    confidence: float
    description: str


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of ``IntentRouter.classify``."""

    workflow_id: str
    workflow_version: str | None
    confidence: float
    matched_rule_id: str
    match_type: Literal["keyword", "regex", "combined", "default", "llm_fallback"]


# ---------------------------------------------------------------------------
# Schema + validator cache
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _load_schema() -> Mapping[str, Any]:
    text = (
        resources.files(_SCHEMA_PACKAGE)
        .joinpath(_SCHEMA_FILENAME)
        .read_text(encoding="utf-8")
    )
    schema: Mapping[str, Any] = json.loads(text)
    return schema


@functools.lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def load_default_rules() -> tuple[tuple[IntentRule, ...], str | None, str]:
    """Load + validate bundled ``default_rules.v1.json``.

    Returns a tuple ``(rules, default_workflow_id, fallback_strategy)``
    so ``IntentRouter`` can be constructed with the bundled config.
    Cached per-process. Raises ``IntentRulesCorruptedError`` on any
    load-time invariant miss.
    """
    text = (
        resources.files(_BUNDLED_RULES_PACKAGE)
        .joinpath(_BUNDLED_RULES_FILENAME)
        .read_text(encoding="utf-8")
    )
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IntentRulesCorruptedError(
            source_path=f"{_BUNDLED_RULES_PACKAGE}/{_BUNDLED_RULES_FILENAME}",
            reason="read_error",
            details=str(exc),
        ) from exc
    rules, default_wf, strategy = _compile_rules_payload(
        raw,
        source_path=f"{_BUNDLED_RULES_PACKAGE}/{_BUNDLED_RULES_FILENAME}",
    )
    return rules, default_wf, strategy


def compile_rules_from_dict(
    raw: Mapping[str, Any],
    *,
    source_path: str | None = None,
) -> tuple[tuple[IntentRule, ...], str | None, str]:
    """Validate + compile a raw rules document into compiled rules.

    Exposed for workspace override loading. ``source_path`` is used only
    for exception messages.
    """
    return _compile_rules_payload(raw, source_path=source_path)


def _compile_rules_payload(
    raw: Any,
    *,
    source_path: str | None,
) -> tuple[tuple[IntentRule, ...], str | None, str]:
    errors = list(_validator().iter_errors(raw))
    if errors:
        summary = "; ".join(
            f"{e.json_path}: {e.message}" for e in errors[:3]
        )
        if len(errors) > 3:
            summary += f" (+{len(errors) - 3} more)"
        raise IntentRulesCorruptedError(
            source_path=source_path,
            reason="schema_invalid",
            details=summary,
        )

    seen_ids: set[str] = set()
    compiled: list[IntentRule] = []
    for raw_rule in raw["rules"]:
        rule_id = raw_rule["rule_id"]
        if rule_id in seen_ids:
            raise IntentRulesCorruptedError(
                source_path=source_path,
                reason="duplicate_rule_id",
                details=f"rule_id={rule_id!r} appears more than once",
            )
        seen_ids.add(rule_id)
        patterns: list[re.Pattern[str]] = []
        for pattern in raw_rule.get("regex_any", ()):
            try:
                patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as exc:
                raise IntentRulesCorruptedError(
                    source_path=source_path,
                    reason="regex_compile",
                    details=(
                        f"rule_id={rule_id!r} pattern={pattern!r}: {exc}"
                    ),
                ) from exc
        compiled.append(IntentRule(
            rule_id=rule_id,
            workflow_id=raw_rule["workflow_id"],
            workflow_version=raw_rule.get("workflow_version"),
            priority=int(raw_rule["priority"]),
            match_type=raw_rule["match_type"],
            keywords=tuple(raw_rule.get("keywords", ())),
            regex_any=tuple(patterns),
            confidence=float(raw_rule["confidence"]),
            description=str(raw_rule.get("description", "")),
        ))
    # Priority DESC stable sort (rule_id lexical tie-break; guaranteed
    # distinct by the duplicate check above).
    compiled.sort(key=lambda r: (-r.priority, r.rule_id))
    return tuple(compiled), raw.get("default_workflow_id"), raw["fallback_strategy"]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class IntentRouter:
    """Deterministic intent classifier.

    Construction options:

    - Default: ``IntentRouter()`` loads bundled ``default_rules.v1.json``.
    - With explicit rules:
      ``IntentRouter(rules=..., default_workflow_id=..., fallback_strategy=...)``.
    """

    def __init__(
        self,
        rules: Sequence[IntentRule] | None = None,
        *,
        default_workflow_id: str | None = None,
        fallback_strategy: Literal[
            "error_on_no_match",
            "use_default",
            "llm_fallback",
        ] = "error_on_no_match",
    ) -> None:
        if rules is None:
            loaded_rules, default_wf, strategy = load_default_rules()
            self._rules = loaded_rules
            self._default_workflow_id = default_wf
            self._fallback_strategy = strategy
        else:
            # Caller-supplied rules; validate consistency.
            if fallback_strategy == "use_default" and not default_workflow_id:
                raise ValueError(
                    "fallback_strategy=use_default requires a non-empty "
                    "default_workflow_id"
                )
            # Ensure rules are priority-sorted (caller may have passed
            # pre-sorted or not; we guarantee sort order here).
            self._rules = tuple(
                sorted(rules, key=lambda r: (-r.priority, r.rule_id))
            )
            self._default_workflow_id = default_workflow_id
            self._fallback_strategy = fallback_strategy

    @property
    def rules(self) -> tuple[IntentRule, ...]:
        return self._rules

    @property
    def default_workflow_id(self) -> str | None:
        return self._default_workflow_id

    @property
    def fallback_strategy(self) -> str:
        return self._fallback_strategy

    def classify(self, input_text: str) -> ClassificationResult | None:
        """Classify ``input_text`` against loaded rules.

        Iterates rules in priority DESC order; first match wins. Two
        rules at the same priority both matching the input surfaces as
        ``IntentRulesCorruptedError(reason="duplicate_priority_match")``
        so the operator sees the ambiguity rather than a silent
        nondeterministic pick.
        """
        matching: list[IntentRule] = [
            r for r in self._rules if _rule_matches(r, input_text)
        ]
        if not matching:
            return self._fallback_result(input_text)

        top_priority = matching[0].priority
        tied = [r for r in matching if r.priority == top_priority]
        if len(tied) > 1:
            raise IntentRulesCorruptedError(
                source_path=None,
                reason="duplicate_priority_match",
                details=(
                    f"rules {[r.rule_id for r in tied]!r} share priority "
                    f"{top_priority} and all match the same input"
                ),
            )
        winner = tied[0]
        return ClassificationResult(
            workflow_id=winner.workflow_id,
            workflow_version=winner.workflow_version,
            confidence=winner.confidence,
            matched_rule_id=winner.rule_id,
            match_type=winner.match_type,
        )

    def _fallback_result(self, input_text: str = "") -> ClassificationResult | None:
        if self._fallback_strategy == "error_on_no_match":
            return None
        if self._fallback_strategy == "use_default":
            # Schema conditional guarantees default_workflow_id non-null
            # when strategy is use_default; assert defensively.
            assert self._default_workflow_id is not None
            return ClassificationResult(
                workflow_id=self._default_workflow_id,
                workflow_version=None,
                confidence=0.0,
                matched_rule_id="__default__",
                match_type="default",
            )
        if self._fallback_strategy == "llm_fallback":
            return self._llm_classify(input_text)
        # Unreachable per schema enum; loud fail for safety.
        raise RuntimeError(
            f"Unknown fallback_strategy: {self._fallback_strategy!r}"
        )

    def _llm_classify(self, input_text: str) -> ClassificationResult:
        """LLM-based intent classification fallback (PR-A6 B4 absorb).

        Requires ``ao-kernel[llm]`` (tenacity + tiktoken). Lazy import
        so the core package does not pull in LLM deps.

        Prompt: ask the model to return one workflow_id from available ids.
        Parse: exact match against available ids. Fail-closed on any
        mismatch, transport error, or missing ``[llm]`` extra.
        """
        from ao_kernel.workflow.errors import IntentClassificationError

        try:
            from ao_kernel.llm import build_request, execute_request, normalize_response
        except ImportError as exc:
            raise IntentClassificationError(
                intent_text=input_text,
                reason="llm_extra_missing",
                details="llm_fallback requires ao-kernel[llm]",
            ) from exc

        available_ids = sorted(self._available_workflow_ids)
        if not available_ids:
            raise IntentClassificationError(
                intent_text=input_text,
                reason="no_available_workflows",
                details="no workflow ids registered for llm_fallback to choose from",
            )

        prompt = (
            f"Given the following intent text, return ONLY one of these "
            f"workflow IDs (nothing else): {', '.join(available_ids)}.\n\n"
            f"Intent: {input_text}\n\nWorkflow ID:"
        )
        messages = [{"role": "user", "content": prompt}]

        try:
            # Use default route — caller should have env vars set
            from ao_kernel.llm import resolve_route
            route = resolve_route(intent="FAST_TEXT")
            req = build_request(
                provider_id=route.get("provider_id", "openai"),
                model=route.get("model", "gpt-4"),
                messages=messages,
                base_url=route.get("base_url", ""),
                api_key=route.get("api_key", ""),
            )
            raw_result = execute_request(
                url=req["url"],
                headers=req["headers"],
                body_bytes=req["body_bytes"],
                timeout_seconds=30.0,
                provider_id=route.get("provider_id", "openai"),
                request_id="llm_fallback",
            )
            resp_bytes = raw_result.get("resp_bytes", b"")
            resp = normalize_response(resp_bytes, provider_id=route.get("provider_id", "openai"))
            candidate = resp.get("text", "").strip()
        except Exception as exc:
            raise IntentClassificationError(
                intent_text=input_text,
                reason="llm_transport_error",
                details=str(exc),
            ) from exc

        if candidate not in available_ids:
            raise IntentClassificationError(
                intent_text=input_text,
                reason="llm_invalid_response",
                details=f"LLM returned {candidate!r}, not in {available_ids}",
            )

        return ClassificationResult(
            workflow_id=candidate,
            workflow_version=None,
            confidence=0.5,  # LLM classification → lower confidence
            matched_rule_id="__llm_fallback__",
            match_type="llm_fallback",
        )

    @property
    def _available_workflow_ids(self) -> frozenset[str]:
        """Collect workflow_ids from all registered rules."""
        return frozenset(
            r.workflow_id for r in self._rules if r.workflow_id
        )


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------


def _rule_matches(rule: IntentRule, input_text: str) -> bool:
    keyword_hit = _any_keyword_matches(rule.keywords, input_text)
    regex_hit = _any_regex_matches(rule.regex_any, input_text)
    if rule.match_type == "keyword":
        return keyword_hit
    if rule.match_type == "regex":
        return regex_hit
    # combined
    return keyword_hit and regex_hit


def _any_keyword_matches(keywords: tuple[str, ...], input_text: str) -> bool:
    for kw in keywords:
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        if pattern.search(input_text):
            return True
    return False


def _any_regex_matches(
    patterns: tuple[re.Pattern[str], ...],
    input_text: str,
) -> bool:
    for p in patterns:
        if p.search(input_text):
            return True
    return False


__all__ = [
    "IntentRule",
    "ClassificationResult",
    "IntentRouter",
    "load_default_rules",
    "compile_rules_from_dict",
]
