"""Shared fixtures for ao-kernel tests."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_workspace(tmp_path: Path):
    """Create a temporary .ao/ workspace and cd into it."""
    ws = tmp_path / ".ao"
    ws.mkdir()
    for d in ("policies", "schemas", "registry", "extensions"):
        (ws / d).mkdir()
    ws_json = ws / "workspace.json"
    ws_json.write_text(json.dumps({
        "version": "0.1.0",
        "created_at": "2026-01-01T00:00:00Z",
        "kind": "ao-workspace",
    }) + "\n")
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield ws
    os.chdir(old_cwd)


@pytest.fixture()
def empty_dir(tmp_path: Path):
    """cd into a temp dir with no workspace."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


@pytest.fixture()
def legacy_workspace(tmp_path: Path):
    """Create a legacy .cache/ws_customer_default workspace."""
    legacy = tmp_path / ".cache" / "ws_customer_default"
    legacy.mkdir(parents=True)
    ws_json = legacy / "workspace.json"
    ws_json.write_text(json.dumps({
        "version": "0.0.9",
        "created_at": "2025-01-01T00:00:00Z",
        "kind": "ao-workspace",
    }) + "\n")
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield legacy
    os.chdir(old_cwd)
