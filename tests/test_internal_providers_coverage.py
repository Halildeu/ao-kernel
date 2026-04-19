"""v3.11 P3 (coverage tranche 4) — `_internal/providers/*` pins.

Two modules:

- ``capability_model.py`` (~73% transitive): registry load + resolve
  matrix + probe-state overlay. Pinned with direct unit tests.
- ``token_counter.py`` (~36% transitive): heuristic + tiktoken paths +
  ``UsageTracker`` budget / record / summary. Tiktoken path tested
  via monkeypatched fake module so coverage does not require the
  optional ``[llm]`` extra at CI time (Codex P3 plan-time note).

Follows the v3.8 H1 / v3.9 M1 / v3.11 P4 tranche pattern: omit
cleanup + targeted pins without touching production code.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


class TestCapabilityManifestSupports:
    """`CapabilityManifest.supports` + `supports_str` branch matrix."""

    def test_supports_returns_true_for_declared_capability(self) -> None:
        from ao_kernel._internal.providers.capability_model import (
            CapabilityManifest,
            ProviderCapability,
        )

        m = CapabilityManifest(
            provider_id="p",
            model="m",
            capabilities=frozenset({ProviderCapability.CHAT}),
            experimental=frozenset(),
            wire_api="openai",
            auth_header="Authorization",
            default_model="m",
        )
        assert m.supports(ProviderCapability.CHAT) is True

    def test_supports_returns_true_for_experimental_capability(self) -> None:
        from ao_kernel._internal.providers.capability_model import (
            CapabilityManifest,
            ProviderCapability,
        )

        m = CapabilityManifest(
            provider_id="p",
            model="m",
            capabilities=frozenset(),
            experimental=frozenset({ProviderCapability.VISION}),
            wire_api="openai",
            auth_header="Authorization",
            default_model="m",
        )
        assert m.supports(ProviderCapability.VISION) is True

    def test_supports_str_returns_false_for_unknown_string(self) -> None:
        from ao_kernel._internal.providers.capability_model import (
            CapabilityManifest,
        )

        m = CapabilityManifest(
            provider_id="p",
            model="m",
            capabilities=frozenset(),
            experimental=frozenset(),
            wire_api="openai",
            auth_header="Authorization",
            default_model="m",
        )
        assert m.supports_str("not_a_real_capability_xyz") is False


class TestLoadCapabilityRegistry:
    """Registry file discovery: repo_root > cwd > bundled fallback."""

    def test_load_falls_back_to_bundled_when_no_workspace_copy(self, tmp_path: Path) -> None:
        # tmp_path has no `registry/` dir → bundled default is used.
        from ao_kernel._internal.providers.capability_model import (
            load_capability_registry,
        )

        reg = load_capability_registry(repo_root=tmp_path)
        assert reg.get("version") == "v1"
        assert isinstance(reg.get("providers", {}), dict)

    def test_load_prefers_workspace_copy_over_bundled(self, tmp_path: Path) -> None:
        from ao_kernel._internal.providers.capability_model import (
            load_capability_registry,
        )

        reg_dir = tmp_path / "registry"
        reg_dir.mkdir()
        (reg_dir / "provider_capability_registry.v1.json").write_text(
            '{"version": "v1", "providers": {"ws_only": {"default_model": "m1"}}}',
            encoding="utf-8",
        )
        reg = load_capability_registry(repo_root=tmp_path)
        assert "ws_only" in reg.get("providers", {})


class TestResolveManifest:
    """`resolve_manifest` covers the happy path, unknown provider,
    non-dict provider_data guard, and probe-state overlay."""

    def test_resolve_unknown_provider_returns_empty_manifest(self) -> None:
        from ao_kernel._internal.providers.capability_model import (
            resolve_manifest,
        )

        m = resolve_manifest(
            "nonexistent_provider_v311",
            registry={"providers": {}},
        )
        assert m.provider_id == "nonexistent_provider_v311"
        assert m.capabilities == frozenset()

    def test_resolve_non_dict_provider_data_returns_empty(self) -> None:
        # Defensive guard: registry entry is a scalar, not a dict.
        from ao_kernel._internal.providers.capability_model import (
            resolve_manifest,
        )

        m = resolve_manifest(
            "broken",
            registry={"providers": {"broken": "not_a_dict"}},
        )
        assert m.capabilities == frozenset()
        assert m.wire_api == "unknown"

    def test_resolve_probe_overlay_adds_experimental(self) -> None:
        # probe_state with probe_status=ok AND capability not already
        # supported → promoted to experimental.
        from ao_kernel._internal.providers.capability_model import (
            ProviderCapability,
            resolve_manifest,
        )

        registry = {
            "providers": {
                "acme": {
                    "default_model": "m",
                    "capabilities": {"chat": "supported"},
                }
            }
        }
        probe_state = {
            "providers": {
                "acme": {
                    "vision": {"probe_status": "ok"},
                }
            }
        }
        m = resolve_manifest("acme", registry=registry, probe_state=probe_state)
        assert ProviderCapability.CHAT in m.capabilities
        assert ProviderCapability.VISION in m.experimental


class TestCountTokensHeuristic:
    def test_heuristic_text_content(self) -> None:
        from ao_kernel._internal.providers.token_counter import (
            count_tokens_heuristic,
        )

        messages = [
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": "reply"},
        ]
        n = count_tokens_heuristic(messages)
        # Heuristic is deterministic; just assert positive.
        assert n >= 1

    def test_heuristic_list_content(self) -> None:
        from ao_kernel._internal.providers.token_counter import (
            count_tokens_heuristic,
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"text": "part one"},
                    "part two",
                    {"type": "image"},  # no "text" key — contributes 0
                ],
            }
        ]
        n = count_tokens_heuristic(messages)
        assert n >= 1


class TestCountTokensTiktoken:
    """Tiktoken path tested via monkeypatched fake module. No real
    tiktoken install required at CI time (optional [llm] extra)."""

    def test_import_error_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from ao_kernel._internal.providers import token_counter

        # Force ImportError by stubbing sys.modules["tiktoken"] = None.
        saved = sys.modules.pop("tiktoken", None)
        monkeypatch.setitem(sys.modules, "tiktoken", None)  # type: ignore[arg-type]
        try:
            result = token_counter.count_tokens_tiktoken([{"role": "user", "content": "x"}], "gpt-4o")
            assert result is None
        finally:
            if saved is not None:
                sys.modules["tiktoken"] = saved
            else:
                sys.modules.pop("tiktoken", None)

    def test_monkeypatched_encoding_returns_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Build a fake tiktoken module with deterministic encoding.
        fake = types.ModuleType("tiktoken")

        class _FakeEncoding:
            def encode(self, s: str) -> list[int]:
                return [0] * max(1, len(s) // 2)

        def _encoding_for_model(model: str) -> _FakeEncoding:
            if "gpt" in model:
                return _FakeEncoding()
            raise KeyError(model)

        def _get_encoding(name: str) -> _FakeEncoding:
            return _FakeEncoding()

        fake.encoding_for_model = _encoding_for_model  # type: ignore[attr-defined]
        fake.get_encoding = _get_encoding  # type: ignore[attr-defined]

        saved = sys.modules.get("tiktoken")
        monkeypatch.setitem(sys.modules, "tiktoken", fake)
        try:
            from ao_kernel._internal.providers.token_counter import (
                count_tokens_tiktoken,
            )

            n = count_tokens_tiktoken([{"role": "user", "content": "hello"}], "gpt-4o")
            assert isinstance(n, int) and n > 0
        finally:
            if saved is not None:
                sys.modules["tiktoken"] = saved

    def test_get_encoding_fallback_on_unknown_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # encoding_for_model raises KeyError → falls back to cl100k_base.
        fake = types.ModuleType("tiktoken")

        class _FakeEncoding:
            def encode(self, s: str) -> list[int]:
                return list(range(len(s)))

        def _encoding_for_model(model: str) -> _FakeEncoding:
            raise KeyError(model)

        def _get_encoding(name: str) -> _FakeEncoding:
            return _FakeEncoding()

        fake.encoding_for_model = _encoding_for_model  # type: ignore[attr-defined]
        fake.get_encoding = _get_encoding  # type: ignore[attr-defined]

        monkeypatch.setitem(sys.modules, "tiktoken", fake)
        from ao_kernel._internal.providers.token_counter import (
            count_tokens_tiktoken,
        )

        n = count_tokens_tiktoken([{"role": "user", "content": "abc"}], "obscure-model")
        assert isinstance(n, int) and n > 0


class TestCountTokensDispatch:
    def test_openai_uses_tiktoken_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # With a working fake tiktoken, dispatch picks tiktoken for openai.
        fake = types.ModuleType("tiktoken")

        class _FakeEncoding:
            def encode(self, s: str) -> list[int]:
                return [0, 1, 2]

        fake.encoding_for_model = lambda m: _FakeEncoding()  # type: ignore[attr-defined]
        fake.get_encoding = lambda n: _FakeEncoding()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "tiktoken", fake)

        from ao_kernel._internal.providers.token_counter import count_tokens

        result = count_tokens(
            [{"role": "user", "content": "x"}],
            provider_id="openai",
            model="gpt-4o",
        )
        assert result["method"] == "tiktoken"
        assert result["is_exact"] is True

    def test_non_openai_uses_heuristic(self) -> None:
        from ao_kernel._internal.providers.token_counter import count_tokens

        result = count_tokens(
            [{"role": "user", "content": "x"}],
            provider_id="anthropic",
            model="claude-3-5-sonnet",
        )
        assert result["method"] == "heuristic"
        assert result["is_exact"] is False


class TestUsageRecordAndTracker:
    def test_usage_record_to_dict(self) -> None:
        from ao_kernel._internal.providers.token_counter import UsageRecord

        r = UsageRecord(provider_id="openai", model="gpt-4o", input_tokens=10, output_tokens=20)
        d = r.to_dict()
        assert d["provider_id"] == "openai"
        assert d["input_tokens"] == 10
        assert d["output_tokens"] == 20
        assert d["timestamp"]  # non-empty default

    def test_tracker_check_budget_unlimited(self) -> None:
        from ao_kernel._internal.providers.token_counter import UsageTracker

        t = UsageTracker(max_tokens_per_run=0)
        within, remaining = t.check_budget(1_000_000)
        assert within is True
        assert remaining == -1

    def test_tracker_record_updates_totals_and_summary(self) -> None:
        from ao_kernel._internal.providers.token_counter import (
            UsageRecord,
            UsageTracker,
        )

        t = UsageTracker(max_tokens_per_run=100)
        t.record_estimate(40)
        t.record(
            UsageRecord(
                provider_id="openai",
                model="gpt-4o",
                input_tokens=30,
                output_tokens=20,
                estimated_cost_usd=0.001234,
            )
        )
        summary = t.summary()
        assert summary["estimated_total_tokens"] == 40
        assert summary["actual_total_tokens"] == 50
        assert summary["call_count"] == 1
        assert summary["max_tokens_per_run"] == 100
        assert summary["budget_remaining"] == 50

    def test_tracker_check_budget_denies_when_exceeds(self) -> None:
        from ao_kernel._internal.providers.token_counter import (
            UsageRecord,
            UsageTracker,
        )

        t = UsageTracker(max_tokens_per_run=100)
        t.record(
            UsageRecord(
                provider_id="openai",
                model="gpt-4o",
                input_tokens=95,
                output_tokens=0,
            )
        )
        within, remaining = t.check_budget(10)
        assert within is False
        assert remaining == 5
