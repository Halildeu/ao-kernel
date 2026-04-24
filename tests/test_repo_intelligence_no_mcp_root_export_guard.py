from __future__ import annotations

import pytest

from ao_kernel.cli import _build_parser, main
from ao_kernel.mcp_server import TOOL_DEFINITIONS, TOOL_DISPATCH


DISALLOWED_REPO_MCP_TOOL_NAMES = {
    "ao_repo_scan",
    "ao_repo_index",
    "ao_repo_query",
    "ao_repo_export",
    "ao_repo_export_plan",
    "ao_repo_intelligence",
}

DISALLOWED_REPO_CLI_FLAGS = {
    "--mcp",
    "--mcp-tool",
    "--root-export",
    "--export-root",
    "--write-root",
}


def test_repo_intelligence_is_not_exposed_as_mcp_tool() -> None:
    tool_names = {str(tool["name"]) for tool in TOOL_DEFINITIONS}

    assert tool_names == set(TOOL_DISPATCH)
    assert tool_names.isdisjoint(DISALLOWED_REPO_MCP_TOOL_NAMES)
    assert not any(name.startswith("ao_repo_") for name in tool_names)
    assert not any("repo_intelligence" in name for name in tool_names)


def test_repo_cli_has_no_root_export_or_mcp_subcommand() -> None:
    # argparse keeps subparser choices behind protected attributes; this test
    # intentionally reads them to pin the public CLI contract.
    parser = _build_parser()
    command_subparsers = [action for action in parser._subparsers._group_actions if action.dest == "command"]
    assert len(command_subparsers) == 1

    repo_parser = command_subparsers[0].choices["repo"]
    repo_subparsers = [action for action in repo_parser._subparsers._group_actions if action.dest == "repo_command"]
    assert len(repo_subparsers) == 1
    assert set(repo_subparsers[0].choices) == {"scan", "index", "query", "export-plan", "export"}


@pytest.mark.parametrize(
    "argv",
    [
        ["repo", "--help"],
        ["repo", "scan", "--help"],
        ["repo", "index", "--help"],
        ["repo", "query", "--help"],
        ["repo", "export-plan", "--help"],
    ],
)
def test_repo_cli_help_does_not_advertise_root_export_or_mcp_flags(argv: list[str], capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.err == ""
    for flag in DISALLOWED_REPO_CLI_FLAGS:
        assert flag not in captured.out
    if argv[-1] != "export":
        assert "--confirm-root-export" not in captured.out
