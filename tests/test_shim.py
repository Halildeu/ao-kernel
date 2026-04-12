"""Smoke tests for src/ compat shim — imports and resource loading."""

from __future__ import annotations

import warnings

import pytest


class TestShimDeprecationWarning:
    def test_src_import_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            import importlib
            importlib.reload(importlib.import_module("src"))
            future_warnings = [x for x in w if issubclass(x.category, FutureWarning)]
            assert len(future_warnings) >= 1
            assert "deprecated" in str(future_warnings[0].message).lower()


class TestShimModuleImports:
    """Verify all allowlisted modules are importable."""

    def test_shared_utils(self):
        from src.shared.utils import load_json, write_json_atomic, now_iso8601
        assert callable(load_json)
        assert callable(write_json_atomic)
        assert callable(now_iso8601)

    def test_shared_logger(self):
        from src.shared.logger import get_logger
        assert callable(get_logger)

    def test_prj_kernel_api_guardrails(self):
        from src.prj_kernel_api.api_guardrails import load_guardrails_policy
        assert callable(load_guardrails_policy)

    def test_prj_kernel_api_provider_guardrails(self):
        from src.prj_kernel_api.provider_guardrails import load_guardrails
        assert callable(load_guardrails)

    def test_prj_kernel_api_circuit_breaker(self):
        from src.prj_kernel_api.circuit_breaker import ProviderCircuitBreaker
        assert ProviderCircuitBreaker is not None

    def test_prj_kernel_api_llm_request_builder(self):
        from src.prj_kernel_api.llm_request_builder import build_live_request
        assert callable(build_live_request)

    def test_prj_kernel_api_llm_transport(self):
        import src.prj_kernel_api.llm_transport
        assert src.prj_kernel_api.llm_transport is not None

    def test_prj_kernel_api_rate_limiter(self):
        from src.prj_kernel_api.rate_limiter import TokenBucketRateLimiter
        assert TokenBucketRateLimiter is not None

    def test_prj_kernel_api_tool_calling(self):
        import src.prj_kernel_api.tool_calling
        assert src.prj_kernel_api.tool_calling is not None

    def test_prj_kernel_api_prompt_registry(self):
        import src.prj_kernel_api.prompt_registry
        assert src.prj_kernel_api.prompt_registry is not None

    def test_prj_kernel_api_llm_router(self):
        from src.prj_kernel_api.llm_router import resolve
        assert callable(resolve)

    def test_providers_capability_model(self):
        import src.providers.capability_model
        assert src.providers.capability_model is not None

    def test_providers_response_parser(self):
        import src.providers.response_parser
        assert src.providers.response_parser is not None

    def test_providers_structured_output(self):
        import src.providers.structured_output
        assert src.providers.structured_output is not None

    def test_providers_token_counter(self):
        from src.providers.token_counter import count_tokens_heuristic
        assert callable(count_tokens_heuristic)

    def test_orchestrator_eval_harness(self):
        from src.orchestrator.eval_harness import run_eval_suite
        assert callable(run_eval_suite)

    def test_orchestrator_quality_gate(self):
        import src.orchestrator.quality_gate
        assert src.orchestrator.quality_gate is not None

    def test_roadmap_executor(self):
        from src.roadmap.executor import apply_roadmap
        assert callable(apply_roadmap)

    def test_roadmap_compiler(self):
        import src.roadmap.compiler
        assert src.roadmap.compiler is not None


class TestResourceLoader:
    def test_load_policy(self):
        from src.shared.resource_loader import load_resource
        data = load_resource("policies", "policy_autonomy.v1.json")
        assert isinstance(data, dict)

    def test_load_operations(self):
        from src.shared.resource_loader import load_resource
        data = load_resource("operations", "llm_class_registry.v1.json")
        assert isinstance(data, dict)

    def test_load_schema(self):
        from src.shared.resource_loader import load_resource
        data = load_resource("schemas", "active-context-profile.schema.v1.json")
        assert isinstance(data, dict)

    def test_load_resource_path(self):
        from src.shared.resource_loader import load_resource_path
        path = load_resource_path("policies", "policy_autonomy.v1.json")
        # In editable install, should return a Path
        # In wheel install, might return None
        if path is not None:
            assert path.is_file()
