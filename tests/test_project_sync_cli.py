"""Argparse smoke tests for ao_kernel.project_sync.cli."""

from __future__ import annotations

import argparse

import pytest

from ao_kernel.project_sync.cli import add_project_subparser


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ao-kernel")
    sub = parser.add_subparsers(dest="command")
    add_project_subparser(sub)
    return parser


def test_cli_project_sync_help_lists_label_flag() -> None:
    """sync --help mentions the scope --label flag."""
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["project", "sync", "--help"])
    assert exc_info.value.code == 0


def test_cli_project_drift_strict_flag_is_recognised() -> None:
    """drift --strict parses and sets the namespace attribute."""
    parser = _build_parser()
    args = parser.parse_args(["project", "drift", "--strict"])
    assert args.strict is True
    assert args.command == "project"
    assert args.project_command == "drift"


def test_cli_project_add_slice_requires_core_flags() -> None:
    """Missing required flags exit with argparse error."""
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["project", "add-slice"])


def test_cli_project_add_slice_parses_full_invocation() -> None:
    """Full add-slice line populates the namespace with typed values."""
    parser = _build_parser()
    args = parser.parse_args(
        [
            "project",
            "add-slice",
            "--epic",
            "1",
            "--slice-id",
            "E-1-3",
            "--title",
            "[Epic 1 | E-1-3] CI changelog",
            "--risk",
            "normal",
            "--plan-ref",
            ".claude/plans/E-1-3.md",
            "--consensus",
            "2-way",
            "--guard",
            "live_adapter",
            "--depends-on",
            "774,775",
            "--estimate-days",
            "3.5",
            "--dry-run",
        ]
    )
    assert args.epic == "1"
    assert args.slice_id == "E-1-3"
    assert args.risk == "normal"
    assert args.consensus == "2-way"
    assert args.guard == "live_adapter"
    assert args.estimate_days == 3.5
    assert args.dry_run is True


def test_cli_project_field_set_requires_item_field_value() -> None:
    """field-set parses --item / --field / --value triple."""
    parser = _build_parser()
    args = parser.parse_args(["project", "field-set", "--item", "774", "--field", "Risk", "--value", "high"])
    assert args.item == 774
    assert args.field == "Risk"
    assert args.value == "high"


def test_cli_project_label_cleanup_default_is_dry_run_false_but_label_set() -> None:
    """label-cleanup defaults: --dry-run False, --label 'mirror:authority'."""
    parser = _build_parser()
    args = parser.parse_args(["project", "label-cleanup"])
    assert args.dry_run is False
    assert args.label == "mirror:authority"


def test_cli_project_from_pr_takes_positional_number() -> None:
    """from-pr accepts the PR number as a positional arg."""
    parser = _build_parser()
    args = parser.parse_args(["project", "from-pr", "770"])
    assert args.pr_number == 770


def test_cli_project_dispatch_without_subcommand_errors() -> None:
    """`ao-kernel project` with no subcommand returns 2 via dispatch."""
    from ao_kernel.project_sync.cli import dispatch

    parser = _build_parser()
    args = parser.parse_args(["project"])
    assert dispatch(args) == 2
