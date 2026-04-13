"""MCP HTTP transport contract tests — serve_http function surface verification."""

from __future__ import annotations

import inspect

import pytest


class TestServeHttpContract:
    def test_serve_http_is_async_function(self):
        """serve_http is an async coroutine function (not sync)."""
        from ao_kernel.mcp_server import serve_http
        assert inspect.iscoroutinefunction(serve_http), "serve_http must be async"

    def test_serve_http_default_params(self):
        """serve_http defaults: host='127.0.0.1', port=8080."""
        from ao_kernel.mcp_server import serve_http
        sig = inspect.signature(serve_http)
        assert sig.parameters["host"].default == "127.0.0.1"
        assert sig.parameters["port"].default == 8080

    def test_serve_http_import_error_message(self):
        """Missing mcp-http deps raise ImportError with install hint."""
        import asyncio
        from unittest.mock import patch

        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name in ("mcp.server.streamable_http", "starlette.applications", "uvicorn"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        import importlib
        import ao_kernel.mcp_server as mod

        with patch("builtins.__import__", side_effect=mock_import):
            importlib.reload(mod)
            with pytest.raises(ImportError, match="starlette and uvicorn"):
                asyncio.run(mod.serve_http())

        # Restore module
        importlib.reload(mod)
