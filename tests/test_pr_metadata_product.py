from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

from ao_kernel.cli import main as cli_main
from ao_kernel.pr_metadata import (
    extract_pr_delivery_metadata_block,
    pr_delivery_metadata_template_json,
    validate_pr_delivery_metadata_markdown,
)


def _valid_body() -> str:
    return "## Delivery metadata\n\n```json pr-delivery-metadata\n" + pr_delivery_metadata_template_json() + "\n```\n"


def test_extract_pr_delivery_metadata_requires_explicit_info_string() -> None:
    assert extract_pr_delivery_metadata_block("```json\n{\"issue\":\"N/A\"}\n```") is None
    assert extract_pr_delivery_metadata_block(_valid_body()) is not None


def test_validate_pr_delivery_metadata_markdown_accepts_valid_body() -> None:
    result = validate_pr_delivery_metadata_markdown(_valid_body())
    assert result.present is True
    assert result.valid is True
    assert result.finding_code == "pr_delivery_metadata_ok"
    assert result.risk_class == "normal"
    assert result.release_authority_impact == "none"


def test_validate_pr_delivery_metadata_markdown_reports_missing_block_without_echoing_body() -> None:
    result = validate_pr_delivery_metadata_markdown("## Summary\nno metadata here\n")
    assert result.present is False
    assert result.valid is False
    assert result.finding_code == "pr_delivery_metadata_absent"
    assert "no metadata here" not in result.message


def test_validate_pr_delivery_metadata_markdown_reports_malformed_json_without_echoing_body() -> None:
    body = "```json pr-delivery-metadata\n{\"issue\": SECRET_TOKEN\n```\n"
    result = validate_pr_delivery_metadata_markdown(body)
    assert result.present is True
    assert result.valid is False
    assert result.finding_code == "pr_delivery_metadata_malformed_json"
    assert "SECRET_TOKEN" not in result.message


def test_validate_pr_delivery_metadata_markdown_rejects_schema_invalid_payload() -> None:
    body = '```json pr-delivery-metadata\n{"issue":"not-an-issue"}\n```\n'
    result = validate_pr_delivery_metadata_markdown(body)
    assert result.present is True
    assert result.valid is False
    assert result.finding_code == "pr_delivery_metadata_schema_invalid"
    assert "not-an-issue" not in result.message


def test_validate_pr_delivery_metadata_schema_error_does_not_echo_invalid_values() -> None:
    body = '```json pr-delivery-metadata\n{"risk_class":"invalid-sensitive-value-redacted-check"}\n```\n'
    result = validate_pr_delivery_metadata_markdown(body)
    assert result.present is True
    assert result.valid is False
    assert result.finding_code == "pr_delivery_metadata_schema_invalid"
    assert "invalid-sensitive-value-redacted-check" not in result.message
    assert "validator=" in result.message


def test_pr_metadata_cli_schema_outputs_bundled_schema(capsys) -> None:
    rc = cli_main(["pr-metadata", "schema"])
    captured = capsys.readouterr()
    assert rc == 0
    schema = json.loads(captured.out)
    assert schema["$id"] == "urn:ao:pr-delivery-metadata:v1"


def test_pr_metadata_cli_template_outputs_valid_block(capsys) -> None:
    rc = cli_main(["pr-metadata", "template"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "```json pr-delivery-metadata" in captured.out
    assert validate_pr_delivery_metadata_markdown(captured.out).valid is True


def test_pr_metadata_cli_validate_json_success(tmp_path: Path, capsys) -> None:
    body_path = tmp_path / "pr-body.md"
    body_path.write_text(_valid_body(), encoding="utf-8")

    rc = cli_main(["pr-metadata", "validate", "--body-file", str(body_path), "--output", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["valid"] is True
    assert payload["finding_code"] == "pr_delivery_metadata_ok"


def test_pr_metadata_cli_validate_accepts_stdin(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", StringIO(_valid_body()))

    rc = cli_main(["pr-metadata", "validate", "--body-file", "-", "--output", "json"])

    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["valid"] is True


def test_pr_metadata_cli_validate_text_failure(tmp_path: Path, capsys) -> None:
    body_path = tmp_path / "pr-body.md"
    body_path.write_text("no metadata", encoding="utf-8")

    rc = cli_main(["pr-metadata", "validate", "--body-file", str(body_path)])

    captured = capsys.readouterr()
    assert rc == 1
    assert "INVALID: pr_delivery_metadata_absent" in captured.out
