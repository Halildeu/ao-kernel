"""Tests for _internal LLM router — resolve/fallback/priority."""

from __future__ import annotations

from datetime import datetime, timezone

from ao_kernel._internal.prj_kernel_api.llm_router import (
    _eligible,
    _is_stale,
    _merge_state,
    resolve,
)

NOW = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat().replace("+00:00", "Z")


class TestHelpers:
    def test_is_stale_none_ts(self):
        assert _is_stale(None, 72, NOW) is True

    def test_is_stale_within_ttl(self):
        assert _is_stale(NOW_ISO, 72, NOW) is False

    def test_is_stale_expired(self):
        old_ts = "2020-01-01T00:00:00Z"
        assert _is_stale(old_ts, 72, NOW) is True

    def test_eligible_verified_ok(self):
        model = {"stage": "verified", "probe_status": "ok", "probe_last_at": NOW_ISO}
        assert _eligible(model, 72, NOW) is True

    def test_eligible_not_verified(self):
        model = {"stage": "pending", "probe_status": "ok", "probe_last_at": NOW_ISO}
        assert _eligible(model, 72, NOW) is False

    def test_eligible_probe_failed(self):
        model = {"stage": "verified", "probe_status": "error", "probe_last_at": NOW_ISO}
        assert _eligible(model, 72, NOW) is False


class TestMergeState:
    def test_merge_overlays_probe_data(self):
        provider_map = {
            "classes": {
                "REASONING": {
                    "providers": {
                        "openai": {
                            "models": [{"model_id": "gpt-4", "stage": "verified"}]
                        }
                    }
                }
            }
        }
        probe_state = {
            "classes": {
                "REASONING": {
                    "providers": {
                        "openai": {
                            "models": {
                                "gpt-4": {"probe_status": "ok", "probe_last_at": "2026-04-13T00:00:00Z"}
                            }
                        }
                    }
                }
            }
        }
        merged = _merge_state(provider_map, probe_state)
        model = merged["classes"]["REASONING"]["providers"]["openai"]["models"][0]
        assert model["probe_status"] == "ok"

    def test_merge_empty_probe_state(self):
        provider_map = {"classes": {"X": {"providers": {}}}}
        merged = _merge_state(provider_map, {"classes": {}})
        assert merged == provider_map


class TestResolve:
    def test_unknown_intent_fails(self):
        result = resolve({"intent": "nonexistent_intent_xyz"})
        assert result["status"] == "FAIL"
        assert result["reason"] == "UNKNOWN_INTENT"

    def test_model_override_blocked(self):
        result = resolve({"intent": "REVIEW", "model": "custom-model"})
        assert result["status"] == "FAIL"
        assert result["reason"] == "MODEL_OVERRIDE_NOT_ALLOWED"

    def test_params_override_blocked(self):
        result = resolve({"intent": "REVIEW", "params_override": {"temp": 0.5}})
        assert result["status"] == "FAIL"
        assert result["reason"] == "PROFILE_PARAM_OVERRIDE_NOT_ALLOWED"

    def test_resolve_returns_dict(self):
        """Resolve returns a dict regardless of outcome."""
        result = resolve({"intent": "REVIEW"})
        assert isinstance(result, dict)
        assert "status" in result
