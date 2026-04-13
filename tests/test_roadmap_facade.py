"""Tests for ao_kernel.roadmap facade — compile + apply."""

from __future__ import annotations

from pathlib import Path


class TestRoadmapFacadeImport:
    def test_compile_roadmap_importable(self):
        from ao_kernel.roadmap import compile_roadmap
        assert hasattr(compile_roadmap, "__call__")

    def test_apply_roadmap_importable(self):
        from ao_kernel.roadmap import apply_roadmap
        assert hasattr(apply_roadmap, "__call__")

    def test_compile_requires_path(self):
        from ao_kernel.roadmap import compile_roadmap
        import pytest
        # compile_roadmap needs a real file path
        with pytest.raises((TypeError, FileNotFoundError, KeyError)):
            compile_roadmap(
                Path("/nonexistent/roadmap.json"),
                workspace_root=Path("/tmp"),
            )

    def test_apply_requires_valid_path(self):
        from ao_kernel.roadmap import apply_roadmap
        import pytest
        with pytest.raises(Exception):
            apply_roadmap(
                Path("/nonexistent/roadmap.json"),
                workspace_root=Path("/tmp"),
            )
