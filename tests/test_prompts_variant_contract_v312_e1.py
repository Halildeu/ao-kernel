"""v3.12 E1 — Prompt variant contract + registry loader.

Pins the declarative surface:

- ``prompt-variant.schema.v1.json`` meta-validity + bundled registry
  validates against it.
- ``PromptVariant.from_dict`` contract (required fields, enum guard,
  metadata shape).
- ``load_prompt_variants`` workspace override precedence, bundled
  fallback, duplicate-id guard, schema violations → ``PromptVariantError``.
- ``intent.metadata.variant_id`` is a free-form field on the existing
  workflow-run schema — operator responsibility to stamp, not a
  runtime orchestration point (yet).

E1 ships the contract only. E2 (compare helper) + E3 (runbook) wire
the operator-facing workflow; A/B runtime orchestration itself is
deferred until operator-validated real-adapter smokes exist (Codex
plan-time precondition).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


class TestPromptVariantSchema:
    def test_schema_is_draft_2020_12_meta_valid(self) -> None:
        schema = load_default("schemas", "prompt-variant.schema.v1.json")
        Draft202012Validator.check_schema(schema)
        assert schema.get("$id", "").startswith("urn:ao:prompt-variant:")

    def test_bundled_registry_validates_against_registry_shape(self) -> None:
        # The bundled registry ships an empty `variants` array; its
        # shape (object with `variants` list) must match operator
        # expectations documented in the loader.
        registry = load_default("registry", "prompt_variant_registry.v1.json")
        assert isinstance(registry, dict)
        assert "variants" in registry
        assert isinstance(registry["variants"], list)
        assert registry["variants"] == []  # bundled ships empty

    def test_sample_variant_validates_against_schema(self) -> None:
        schema = load_default("schemas", "prompt-variant.schema.v1.json")
        sample = {
            "variant_id": "review.concise.v1",
            "version": "1.0.0",
            "prompt_template": "Summarize findings in 3 bullets max.",
            "expected_capability": "review_findings",
            "metadata": {
                "experiment_id": "exp-2026-04-19",
                "branch": "feat/review-tuning",
            },
        }
        errors = list(Draft202012Validator(schema).iter_errors(sample))
        assert errors == [], [e.message for e in errors]

    def test_invalid_variant_id_pattern_rejected(self) -> None:
        schema = load_default("schemas", "prompt-variant.schema.v1.json")
        # variant_id must start alphanumeric; `-foo` should fail the pattern.
        bad = {
            "variant_id": "-bad-starts-with-dash",
            "version": "1",
            "prompt_template": "x",
        }
        errors = list(Draft202012Validator(schema).iter_errors(bad))
        assert errors, "pattern violation should surface as schema error"


class TestPromptVariantDataclass:
    def test_from_dict_accepts_minimum_required(self) -> None:
        from ao_kernel.prompts import PromptVariant

        v = PromptVariant.from_dict(
            {
                "variant_id": "minimum.v1",
                "version": "1",
                "prompt_template": "Hello",
            }
        )
        assert v.variant_id == "minimum.v1"
        assert v.version == "1"
        assert v.prompt_template == "Hello"
        assert v.expected_capability is None
        assert v.metadata == {}

    def test_from_dict_missing_required_raises(self) -> None:
        from ao_kernel.prompts import PromptVariant, PromptVariantError

        with pytest.raises(PromptVariantError, match="missing required field"):
            PromptVariant.from_dict({"variant_id": "no-body.v1", "version": "1"})

    def test_from_dict_unknown_expected_capability_raises(self) -> None:
        from ao_kernel.prompts import PromptVariant, PromptVariantError

        with pytest.raises(PromptVariantError, match="expected_capability"):
            PromptVariant.from_dict(
                {
                    "variant_id": "bad-cap.v1",
                    "version": "1",
                    "prompt_template": "x",
                    "expected_capability": "unknown_capability_xyz",
                }
            )

    def test_from_dict_metadata_not_mapping_raises(self) -> None:
        from ao_kernel.prompts import PromptVariant, PromptVariantError

        with pytest.raises(PromptVariantError, match="metadata"):
            PromptVariant.from_dict(
                {
                    "variant_id": "bad-meta.v1",
                    "version": "1",
                    "prompt_template": "x",
                    "metadata": ["not", "a", "dict"],
                }
            )


class TestLoadPromptVariants:
    def test_bundled_fallback_returns_empty_list(self, tmp_path: Path) -> None:
        # No workspace override → bundled empty registry used.
        from ao_kernel.prompts import load_prompt_variants

        variants = load_prompt_variants(workspace_root=tmp_path)
        assert variants == []

    def test_workspace_override_precedence(self, tmp_path: Path) -> None:
        from ao_kernel.prompts import load_prompt_variants

        override_dir = tmp_path / ".ao" / "registry"
        override_dir.mkdir(parents=True)
        (override_dir / "prompt_variant_registry.v1.json").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "variants": [
                        {
                            "variant_id": "ws.a.v1",
                            "version": "1",
                            "prompt_template": "A prompt",
                            "expected_capability": "review_findings",
                        },
                        {
                            "variant_id": "ws.b.v1",
                            "version": "1",
                            "prompt_template": "B prompt",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        variants = load_prompt_variants(workspace_root=tmp_path)
        assert len(variants) == 2
        ids = {v.variant_id for v in variants}
        assert ids == {"ws.a.v1", "ws.b.v1"}

    def test_duplicate_variant_id_raises(self, tmp_path: Path) -> None:
        from ao_kernel.prompts import load_prompt_variants, PromptVariantError

        override_dir = tmp_path / ".ao" / "registry"
        override_dir.mkdir(parents=True)
        (override_dir / "prompt_variant_registry.v1.json").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "variants": [
                        {
                            "variant_id": "dup.v1",
                            "version": "1",
                            "prompt_template": "first",
                        },
                        {
                            "variant_id": "dup.v1",  # same id
                            "version": "2",
                            "prompt_template": "second",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(PromptVariantError, match="Duplicate variant_id"):
            load_prompt_variants(workspace_root=tmp_path)

    def test_missing_variants_key_raises(self, tmp_path: Path) -> None:
        from ao_kernel.prompts import load_prompt_variants, PromptVariantError

        override_dir = tmp_path / ".ao" / "registry"
        override_dir.mkdir(parents=True)
        (override_dir / "prompt_variant_registry.v1.json").write_text(
            json.dumps({"version": "v1"}),  # no variants key
            encoding="utf-8",
        )

        with pytest.raises(PromptVariantError, match="variants"):
            load_prompt_variants(workspace_root=tmp_path)

    def test_non_dict_variant_entry_raises(self, tmp_path: Path) -> None:
        from ao_kernel.prompts import load_prompt_variants, PromptVariantError

        override_dir = tmp_path / ".ao" / "registry"
        override_dir.mkdir(parents=True)
        (override_dir / "prompt_variant_registry.v1.json").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "variants": ["not-a-dict"],  # string entry
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(PromptVariantError, match="must be objects"):
            load_prompt_variants(workspace_root=tmp_path)


class TestIntentMetadataVariantIdContract:
    """`intent.metadata.variant_id` is supported by the existing
    workflow-run schema without further changes — verify the field
    passes through `create_run` and round-trips via `load_run`."""

    def test_create_run_accepts_variant_id_in_intent_metadata(self, tmp_path: Path) -> None:
        import uuid

        from ao_kernel.workflow import create_run, load_run

        run_id = str(uuid.uuid4())
        create_run(
            tmp_path,
            run_id=run_id,
            workflow_id="review_ai_flow",
            workflow_version="1.0.0",
            intent={
                "kind": "inline_prompt",
                "payload": "demo prompt",
                "metadata": {
                    "variant_id": "review.concise.v1",
                    "experiment_id": "exp-2026-04-19",
                },
            },
            budget={
                "time_seconds": {"limit": 120.0, "spent": 0.0, "remaining": 120.0},
                "fail_closed_on_exhaust": True,
            },
            policy_refs=["ao_kernel/defaults/policies/policy_worktree_profile.v1.json"],
            evidence_refs=[f".ao/evidence/workflows/{run_id}/events.jsonl"],
            adapter_refs=["codex-stub"],
        )

        record, _ = load_run(tmp_path, run_id)
        assert record["intent"]["metadata"]["variant_id"] == "review.concise.v1"
        assert record["intent"]["metadata"]["experiment_id"] == "exp-2026-04-19"
