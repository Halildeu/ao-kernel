"""AST import-allowlist test for ao_kernel.orchestration.quality_profile.

AO-MA-11G-1 (CNS-20260601-002 Codex thread 019e8050 AGREE) pins the
quality profile module to a stdlib + jsonschema + yaml.safe_load only
import surface. A forbidden module (subprocess / socket / requests /
httpx / urllib / asyncio.subprocess / anthropic / openai / MCP / mavis
client) cannot be used without importing it; this test makes the
allowlist the binding structural guarantee.
"""

from __future__ import annotations

import ast
from importlib import resources
from pathlib import Path

import pytest


ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__future__",
        "collections",
        "collections.abc",
        "dataclasses",
        "datetime",
        "hashlib",
        "json",
        "pathlib",
        "re",
        "typing",
        "jsonschema",
        "yaml",
    }
)
"""Top-level imports allowed in quality_profile.py.

``yaml`` is allowed ONLY for the ``yaml.safe_load`` + ``yaml.YAMLError``
attributes; the AST attribute-denylist below catches every other
``yaml.<attr>`` use (load / FullLoader / UnsafeLoader / unsafe_load /
constructor / SafeLoader / dump / etc.)."""

ALLOWED_YAML_ATTRS: frozenset[str] = frozenset({"safe_load", "YAMLError"})


def _module_path() -> Path:
    pkg = resources.files("ao_kernel.orchestration")
    return Path(str(pkg.joinpath("quality_profile.py")))


def _parsed() -> ast.Module:
    text = _module_path().read_text(encoding="utf-8")
    return ast.parse(text, filename=str(_module_path()))


def test_imports_within_allowlist() -> None:
    tree = _parsed()
    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    offending.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if not module or root not in ALLOWED_MODULES:
                offending.append(f"from {module or '.'} import ...")
    assert not offending, f"quality_profile.py imports outside the allowlist: {offending}"


def test_yaml_attributes_restricted() -> None:
    """Only ``yaml.safe_load`` / ``yaml.YAMLError`` may be referenced."""

    tree = _parsed()
    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "yaml":
                if node.attr not in ALLOWED_YAML_ATTRS:
                    offending.append(f"yaml.{node.attr}")
    assert not offending, f"quality_profile.py uses non-allowlisted yaml attributes: {offending}"


def test_no_subprocess_socket_network_modules() -> None:
    text = _module_path().read_text(encoding="utf-8")
    forbidden_names = (
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "anthropic",
        "openai",
        "asyncio.subprocess",
        "asyncio",
        "mavis",
        "mcp.client",
        "smtplib",
        "ftplib",
        "ssl",
        "http.client",
    )
    for name in forbidden_names:
        assert f"import {name}" not in text and f"from {name}" not in text, (
            f"quality_profile.py contains forbidden import {name!r}"
        )


def test_no_os_module_imported() -> None:
    """``os`` is not needed by the pure profile module; reject if added."""

    text = _module_path().read_text(encoding="utf-8")
    assert "import os" not in text and "from os " not in text


def test_module_exports_pinned_constants() -> None:
    from ao_kernel.orchestration.quality_profile import (
        ADR_FILENAME_PATTERN,
        ADR_ID_PATTERN,
        ISO_25010_CHARACTERISTICS,
        REQUIRED_CHANGELOG_SECTIONS,
    )

    assert ADR_ID_PATTERN.match("ADR-0001")
    assert ADR_FILENAME_PATTERN.match("ADR-0001-x.md")
    assert sum(len(s) for s in ISO_25010_CHARACTERISTICS.values()) == 35
    assert REQUIRED_CHANGELOG_SECTIONS == frozenset(
        {
            "Added",
            "Changed",
            "Deprecated",
            "Removed",
            "Fixed",
            "Security",
        }
    )


# ---------------------------------------------------------------------------
# CLI forbidden flag pin (RI-7.8c)
# ---------------------------------------------------------------------------


def _build_main_parser():
    import argparse

    from ao_kernel.orchestration.quality_handlers import add_quality_subparser

    parser = argparse.ArgumentParser(prog="ao-kernel")
    sub = parser.add_subparsers(dest="command")
    add_quality_subparser(sub)
    return parser


@pytest.mark.parametrize(
    "subcommand",
    ["validate-adr", "build-index", "validate-iso-profile", "check-changelog"],
)
@pytest.mark.parametrize(
    "forbidden_flag",
    ["--adapter", "--prompt", "--model", "--api-key", "--url", "--pr-write"],
)
def test_cli_rejects_forbidden_flags_via_argparse(subcommand: str, forbidden_flag: str) -> None:
    parser = _build_main_parser()
    # Build a minimum-required argv for each subcommand; argparse must
    # reject the unknown forbidden flag with SystemExit before reaching
    # the handler.
    if subcommand == "validate-adr":
        base = ["quality", "validate-adr", "--file", "/tmp/x.md"]
    elif subcommand == "build-index":
        base = ["quality", "build-index", "--dir", "/tmp/x", "--out", "/tmp/o"]
    elif subcommand == "validate-iso-profile":
        base = ["quality", "validate-iso-profile", "--file", "/tmp/x.json"]
    else:  # check-changelog
        base = [
            "quality",
            "check-changelog",
            "--base-changelog",
            "/tmp/base.md",
            "--head-changelog",
            "/tmp/head.md",
            "--out",
            "/tmp/out.json",
        ]
    with pytest.raises(SystemExit):
        parser.parse_args(base + [forbidden_flag, "value"])
