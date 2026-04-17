"""Tests for ``extract_usage_strict`` — sentinel None for absent
token fields (PR-B2 v3 iter-1 B3 absorb).

The existing ``extract_usage`` helper defaults absent fields to 0;
B2 cost middleware needs to distinguish "adapter didn't surface"
from "actual 0 tokens", hence the strict variant.
"""

from __future__ import annotations

import json

from ao_kernel._internal.prj_kernel_api.llm_response_normalizer import (
    UsagePresence,
    extract_usage,
    extract_usage_strict,
)


def _resp(obj: dict) -> bytes:
    return json.dumps(obj).encode("utf-8")


class TestStrictPresent:
    def test_anthropic_style_input_output(self) -> None:
        p = extract_usage_strict(
            _resp({"usage": {"input_tokens": 100, "output_tokens": 50}})
        )
        assert p.tokens_input == 100
        assert p.tokens_output == 50
        assert p.cached_tokens is None

    def test_openai_style_prompt_completion(self) -> None:
        p = extract_usage_strict(
            _resp({"usage": {"prompt_tokens": 80, "completion_tokens": 40}})
        )
        assert p.tokens_input == 80
        assert p.tokens_output == 40

    def test_anthropic_cache_read(self) -> None:
        p = extract_usage_strict(
            _resp({
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 50,
                    "cache_read_input_tokens": 100,
                }
            })
        )
        assert p.cached_tokens == 100

    def test_openai_cached_tokens(self) -> None:
        p = extract_usage_strict(
            _resp({
                "usage": {
                    "prompt_tokens": 300,
                    "completion_tokens": 60,
                    "cached_tokens": 150,
                }
            })
        )
        assert p.cached_tokens == 150


class TestStrictAbsent:
    def test_missing_input_is_none(self) -> None:
        p = extract_usage_strict(
            _resp({"usage": {"output_tokens": 50}})
        )
        assert p.tokens_input is None
        assert p.tokens_output == 50

    def test_missing_output_is_none(self) -> None:
        p = extract_usage_strict(
            _resp({"usage": {"input_tokens": 100}})
        )
        assert p.tokens_input == 100
        assert p.tokens_output is None

    def test_no_usage_dict_all_none(self) -> None:
        p = extract_usage_strict(_resp({"text": "hello"}))
        assert p == UsagePresence(None, None, None)

    def test_non_dict_usage_all_none(self) -> None:
        p = extract_usage_strict(_resp({"usage": "not a dict"}))
        assert p == UsagePresence(None, None, None)

    def test_non_int_values_treated_as_absent(self) -> None:
        """Schema contract says int; provider bug (string) → None."""
        p = extract_usage_strict(
            _resp({"usage": {"input_tokens": "200", "output_tokens": 40}})
        )
        # "200" is str, not int → None
        assert p.tokens_input is None
        assert p.tokens_output == 40

    def test_non_json_response_all_none(self) -> None:
        p = extract_usage_strict(b"not valid json")
        assert p == UsagePresence(None, None, None)

    def test_non_object_root_all_none(self) -> None:
        """JSON list or scalar at root → all None (defensive)."""
        p = extract_usage_strict(_resp([1, 2, 3]))  # type: ignore[arg-type]
        assert p == UsagePresence(None, None, None)


class TestStrictVsLegacy:
    def test_legacy_extract_usage_still_zero_fallback(self) -> None:
        """PR-A extract_usage keeps 0-default — no regression."""
        u = extract_usage(_resp({"usage": {"input_tokens": 100}}))
        # Missing output_tokens → 0 (legacy behavior)
        assert u == {"input_tokens": 100, "output_tokens": 0}

    def test_strict_and_legacy_diverge_on_missing(self) -> None:
        """Same response → different semantics by design."""
        resp = _resp({"usage": {"input_tokens": 100}})
        strict = extract_usage_strict(resp)
        legacy = extract_usage(resp)
        assert strict.tokens_output is None
        assert legacy["output_tokens"] == 0


class TestZeroVsMissing:
    def test_actual_zero_preserved(self) -> None:
        """``tokens_output=0`` in usage dict is PRESERVED (distinct from
        absent → None). B2 cost middleware treats 0 as valid 'no
        completion generated' case."""
        p = extract_usage_strict(
            _resp({"usage": {"input_tokens": 50, "output_tokens": 0}})
        )
        assert p.tokens_output == 0  # not None
        assert p.tokens_input == 50

    def test_explicit_null_treated_as_absent(self) -> None:
        """JSON null → Python None → treated as absent (str isinstance check
        fails); B2 middleware flags usage_missing."""
        p = extract_usage_strict(
            _resp({"usage": {"input_tokens": None, "output_tokens": 50}})
        )
        assert p.tokens_input is None
        assert p.tokens_output == 50
