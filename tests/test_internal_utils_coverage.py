"""v3.9 post-release M1 (coverage tranche 2) — `_internal/utils/*` pins.

The two tiny helper modules (`budget.py`, `jsonio.py`) were already
~80-82% covered transitively but stayed in the `coverage.run.omit`
list. This file adds targeted pins for the last missing branches so
the tree can be pulled into the ratcheted coverage scope.

Pattern mirrors v3.8 H1 `_internal/secrets/*` tranche: small, mechanical,
no production-code change.
"""

from __future__ import annotations

import json
from pathlib import Path


class TestEstimateTokens:
    def test_empty_string_returns_zero(self) -> None:
        from ao_kernel._internal.utils.budget import estimate_tokens

        assert estimate_tokens("") == 0

    def test_non_string_input_returns_zero(self) -> None:
        # estimate_tokens must not raise on non-string input; the
        # fail-closed contract returns 0 so callers don't have to
        # null-check before feeding in whatever a provider hands them.
        from ao_kernel._internal.utils.budget import estimate_tokens

        assert estimate_tokens(None) == 0  # type: ignore[arg-type]
        assert estimate_tokens(123) == 0  # type: ignore[arg-type]
        assert estimate_tokens(b"bytes") == 0  # type: ignore[arg-type]

    def test_normal_text_ceils_length_over_four(self) -> None:
        # ~4 chars per token heuristic: ceil(len / 4).
        from ao_kernel._internal.utils.budget import estimate_tokens

        assert estimate_tokens("abcd") == 1
        assert estimate_tokens("abcde") == 2
        assert estimate_tokens("hello world") == 3  # len=11 → ceil(11/4)=3


class TestJsonIoRoundtrip:
    def test_save_then_load_roundtrip(self, tmp_path: Path) -> None:
        from ao_kernel._internal.utils.jsonio import load_json, save_json

        target = tmp_path / "sample.json"
        payload = {"kind": "decision", "score": 0.92, "tags": ["a", "b"]}
        save_json(target, payload)
        assert target.exists()
        loaded = load_json(target)
        assert loaded == payload

    def test_save_json_respects_indent_parameter(self, tmp_path: Path) -> None:
        # Non-default indent is passed straight through to the atomic
        # writer; verifying it here keeps the surface documented.
        from ao_kernel._internal.utils.jsonio import save_json

        target = tmp_path / "compact.json"
        save_json(target, {"a": 1}, indent=0)
        text = target.read_text(encoding="utf-8")
        # indent=0 still uses newline separators; non-empty content.
        assert text.strip().startswith("{")
        assert '"a"' in text


class TestToCanonicalJson:
    def test_sort_keys_produces_stable_output(self) -> None:
        from ao_kernel._internal.utils.jsonio import to_canonical_json

        a = to_canonical_json({"b": 2, "a": 1})
        b = to_canonical_json({"a": 1, "b": 2})
        # Canonical form must be identical regardless of insertion order.
        assert a == b
        # And the keys must be sorted lexicographically in the output.
        assert a == '{"a":1,"b":2}'

    def test_unicode_is_preserved_without_escaping(self) -> None:
        # `ensure_ascii=False` means non-ASCII characters round-trip
        # as themselves rather than \uXXXX escapes. Important for
        # canonical decision payloads written to evidence logs.
        from ao_kernel._internal.utils.jsonio import to_canonical_json

        out = to_canonical_json({"label": "Merhaba 🌍"})
        assert "Merhaba 🌍" in out
        # And it's still valid JSON.
        assert json.loads(out) == {"label": "Merhaba 🌍"}
