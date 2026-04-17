"""Tests for PR-B6 commit 3 — commit_message capability + schema +
codex-stub fixture + output_parse 2nd rule.

Pins:
- commit-message.schema.v1.json object shape
- capability_enum parity (agent-adapter-contract + workflow-definition
  both include commit_message)
- codex-stub manifest output_parse has 2 rules (review_findings +
  commit_message)
- codex-stub fixture emits commit_message as OBJECT (walker Mapping
  check)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from ao_kernel.config import load_default


def _bundled_adapter_manifest(name: str) -> dict:
    """Load a bundled adapter manifest directly.

    ``ao_kernel.config.load_default`` does not register an ``adapters``
    resource kind (its allow-list is policies/schemas/registry/catalogs/
    extensions/operations). This helper reads the bundled JSON directly
    — fine for tests that only need the payload, not the full resource
    resolver semantics.
    """
    import ao_kernel

    pkg_root = Path(ao_kernel.__file__).parent
    path = pkg_root / "defaults" / "adapters" / name
    return json.loads(path.read_text(encoding="utf-8"))


class TestCommitMessageSchema:
    def test_schema_loads(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        assert schema["$id"] == "urn:ao:commit-message:v1"
        assert schema["type"] == "object"
        assert "additionalProperties" in schema
        assert schema["additionalProperties"] is False

    def test_minimal_valid(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        payload = {"schema_version": "1", "subject": "chore: test"}
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == [], f"unexpected validation errors: {errors}"

    def test_full_valid(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        payload = {
            "schema_version": "1",
            "subject": "feat(api): add X",
            "body": "Multi-line body\n\nParagraph 2.",
            "breaking_change": True,
            "trailers": [
                "Co-Authored-By: alice <alice@example.com>",
                "Signed-off-by: bob <bob@example.com>",
            ],
        }
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        assert errors == [], f"unexpected validation errors: {errors}"

    def test_missing_subject_rejected(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        with pytest.raises(ValidationError):
            Draft202012Validator(schema).validate(
                {"schema_version": "1"}
            )

    def test_subject_length_max(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        too_long = "x" * 73  # 73 > 72 max
        with pytest.raises(ValidationError):
            Draft202012Validator(schema).validate(
                {"schema_version": "1", "subject": too_long}
            )

    def test_schema_version_pinned(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        with pytest.raises(ValidationError):
            # Wrong version literal
            Draft202012Validator(schema).validate(
                {"schema_version": "2", "subject": "x"}
            )

    def test_additional_properties_rejected(self) -> None:
        schema = load_default("schemas", "commit-message.schema.v1.json")
        with pytest.raises(ValidationError):
            Draft202012Validator(schema).validate({
                "schema_version": "1",
                "subject": "x",
                "extra_field": "foo",  # closed shape
            })


class TestCapabilityEnumParity:
    """PR-B6: commit_message added to both schemas; parity required
    (workflow-definition.schema.v1.json description pins the contract)."""

    def test_agent_adapter_contract_includes_commit_message(self) -> None:
        schema = load_default(
            "schemas", "agent-adapter-contract.schema.v1.json",
        )
        enum = schema["$defs"]["capability_enum"]["enum"]
        assert "commit_message" in enum

    def test_workflow_definition_includes_commit_message(self) -> None:
        schema = load_default(
            "schemas", "workflow-definition.schema.v1.json",
        )
        enum = schema["$defs"]["capability_enum"]["enum"]
        assert "commit_message" in enum

    def test_enums_are_byte_identical(self) -> None:
        """Drift guard — two capability_enum schemas must match."""
        a = load_default(
            "schemas", "agent-adapter-contract.schema.v1.json",
        )["$defs"]["capability_enum"]["enum"]
        b = load_default(
            "schemas", "workflow-definition.schema.v1.json",
        )["$defs"]["capability_enum"]["enum"]
        assert list(a) == list(b), (
            f"capability_enum drift:\n"
            f"  agent-adapter-contract: {a}\n"
            f"  workflow-definition:    {b}"
        )

    def test_commit_write_still_prohibited(self) -> None:
        """Invariant preservation: commit_message is distinct from a
        hypothetical commit_write — the schema's prohibition of
        commit_write remains intact (ao-kernel owns git commit)."""
        schema = load_default(
            "schemas", "agent-adapter-contract.schema.v1.json",
        )
        enum = schema["$defs"]["capability_enum"]["enum"]
        # Negative assertion: commit_write MUST NOT appear
        assert "commit_write" not in enum


class TestCodexStubManifestOutputParse:
    def test_two_rules_present(self) -> None:
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")
        rules = manifest["output_parse"]["rules"]
        assert len(rules) == 2

    def test_review_findings_rule(self) -> None:
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")
        rules = manifest["output_parse"]["rules"]
        review_rule = next(
            r for r in rules if r["capability"] == "review_findings"
        )
        assert review_rule["json_path"] == "$.review_findings"
        assert review_rule["schema_ref"] == "review-findings.schema.v1.json"

    def test_commit_message_rule(self) -> None:
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")
        rules = manifest["output_parse"]["rules"]
        commit_rule = next(
            r for r in rules if r["capability"] == "commit_message"
        )
        assert commit_rule["json_path"] == "$.commit_message"
        assert commit_rule["schema_ref"] == "commit-message.schema.v1.json"

    def test_capabilities_declared(self) -> None:
        manifest = _bundled_adapter_manifest("codex-stub.manifest.v1.json")
        caps = manifest["capabilities"]
        assert "commit_message" in caps
        assert "review_findings" in caps


class TestCodexStubFixtureEmitsObjectShape:
    """Walker contract: adapter_invoker._walk_output_parse only
    accepts Mapping payloads. commit_message MUST be dict-shape (not
    string). This regression test runs the fixture and parses stdout.
    """

    def test_fixture_emits_commit_message_object(self) -> None:
        # Run the stub fixture as a subprocess (mirrors the adapter
        # invocation path in test environments).
        # Subprocess uses pytest cwd so ao_kernel package is importable;
        # tmp_path isolation is not needed for fixture execution (no
        # workspace files read).
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ao_kernel.fixtures.codex_stub",
                "--run-id",
                "test-run-b6",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"fixture failed: {result.stderr}"

        envelope = json.loads(result.stdout.strip())
        # commit_message must be present and object-shape
        assert "commit_message" in envelope
        commit_msg = envelope["commit_message"]
        assert isinstance(commit_msg, dict), (
            f"commit_message must be object-shape (Mapping) for "
            f"walker to extract; got {type(commit_msg).__name__}: "
            f"{commit_msg!r}"
        )

    def test_fixture_commit_message_schema_valid(self) -> None:
        """Fixture output validates against commit-message.schema.v1.json."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ao_kernel.fixtures.codex_stub",
                "--run-id",
                "test-run-b6",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        envelope = json.loads(result.stdout.strip())

        schema = load_default("schemas", "commit-message.schema.v1.json")
        Draft202012Validator(schema).validate(envelope["commit_message"])
