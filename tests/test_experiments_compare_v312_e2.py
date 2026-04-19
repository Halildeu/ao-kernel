"""v3.12 E2 — ``ao_kernel.experiments.compare_variants`` read-only helper.

Pins the pairing contract:

- ``intent.metadata.variant_id`` (stamped by operator per E1 contract)
  is REQUIRED on every run passed to ``compare_variants`` — absence
  fails closed.
- ``step_record.capability_output_refs["review_findings"]`` is the
  artefact source; the first such ref across the run's steps wins.
- Artefact load failures (missing file, malformed JSON, non-dict
  payload) are packaged into ``VariantComparisonEntry.load_error``
  rather than raised — the row still ships with metadata.
- ``by_variant`` groups entries in the same order they're discovered
  across ``run_ids``.

E2 is read-only; it does NOT orchestrate runs. Operators start each
run manually per the E3 runbook.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.experiments import (
    VariantComparisonError,
    compare_variants,
)


def _fake_record(
    *,
    variant_id: str | None = "review.concise.v1",
    experiment_id: str | None = "exp-2026-04-19",
    review_findings_ref: str | None = None,
    include_metadata: bool = True,
) -> dict[str, Any]:
    """Build a minimal workflow-run record dict for monkeypatching."""
    intent: dict[str, Any] = {
        "kind": "inline_prompt",
        "payload": "test",
    }
    if include_metadata:
        meta: dict[str, Any] = {}
        if variant_id is not None:
            meta["variant_id"] = variant_id
        if experiment_id is not None:
            meta["experiment_id"] = experiment_id
        intent["metadata"] = meta

    steps: list[dict[str, Any]] = []
    if review_findings_ref is not None:
        steps.append(
            {
                "step_id": "invoke_review_agent",
                "step_name": "invoke_review_agent",
                "state": "completed",
                "capability_output_refs": {
                    "review_findings": review_findings_ref,
                },
            }
        )

    return {
        "run_id": "fake",
        "intent": intent,
        "steps": steps,
    }


class TestCompareVariantsContract:
    def test_missing_intent_metadata_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Record has no intent.metadata → fail closed.
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(include_metadata=False),
        )
        with pytest.raises(VariantComparisonError, match="intent.metadata"):
            compare_variants(["r1"], workspace_root=tmp_path)

    def test_missing_variant_id_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # intent.metadata exists but variant_id is None.
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(variant_id=None),
        )
        with pytest.raises(VariantComparisonError, match="variant_id"):
            compare_variants(["r1"], workspace_root=tmp_path)

    def test_empty_variant_id_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(variant_id=""),
        )
        with pytest.raises(VariantComparisonError, match="variant_id"):
            compare_variants(["r1"], workspace_root=tmp_path)


class TestCompareVariantsArtefactResolution:
    def test_no_review_findings_step_records_load_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Step list exists but no step has the capability ref.
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(review_findings_ref=None),
        )
        result = compare_variants(["r1"], workspace_root=tmp_path)
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.variant_id == "review.concise.v1"
        assert entry.review_findings_ref is None
        assert entry.review_findings is None
        assert entry.load_error == "no step emitted review_findings artefact"

    def test_missing_artefact_file_records_load_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Canonical ref format (run-dir-relative) per
        # workflow-run.schema.v1.json. No file at the resolved path →
        # load_error, row still ships.
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(
                review_findings_ref="artifacts/invoke_review_agent-review_findings-attempt1.json"
            ),
        )
        result = compare_variants(["r1"], workspace_root=tmp_path)
        entry = result.entries[0]
        assert entry.review_findings is None
        assert entry.load_error is not None
        assert "not found" in entry.load_error

    def test_malformed_artefact_records_load_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Canonical layout: workspace_root/.ao/evidence/workflows/<run_id>/<ref>
        run_id = "r1"
        art_ref = "artifacts/invoke_review_agent-review_findings-attempt1.json"
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id / "artifacts"
        run_dir.mkdir(parents=True)
        (run_dir / Path(art_ref).name).write_text("{not valid json", encoding="utf-8")

        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(review_findings_ref=art_ref),
        )
        result = compare_variants([run_id], workspace_root=tmp_path)
        entry = result.entries[0]
        assert entry.review_findings is None
        assert entry.load_error is not None
        assert "artefact load failed" in entry.load_error

    def test_successful_artefact_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        run_id = "r1"
        art_ref = "artifacts/invoke_review_agent-review_findings-attempt1.json"
        run_dir = tmp_path / ".ao" / "evidence" / "workflows" / run_id / "artifacts"
        run_dir.mkdir(parents=True)
        payload = {
            "schema_version": "1",
            "findings": [{"severity": "warning", "message": "nit about import order"}],
            "summary": "1 warning, no blockers",
        }
        (run_dir / Path(art_ref).name).write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(review_findings_ref=art_ref),
        )
        result = compare_variants([run_id], workspace_root=tmp_path)
        entry = result.entries[0]
        assert entry.review_findings == payload
        assert entry.load_error is None

    def test_ref_escape_outside_run_dir_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Codex iter-3 BLOCKER absorb: a malformed / malicious run
        # record could carry `review_findings_ref="../../../evil.json"`;
        # the helper MUST refuse rather than silently load an unrelated
        # file stamped as review_findings.
        run_id = "r1"
        # Materialize a real JSON file OUTSIDE the run-dir so only the
        # containment check (not `is_file` check) rejects it.
        outside = tmp_path / "outside.json"
        outside.write_text(
            json.dumps({"schema_version": "1", "findings": [], "summary": "evil"}),
            encoding="utf-8",
        )
        # ref climbs out of .ao/evidence/workflows/r1/ → tmp_path/outside.json
        escape_ref = "../../../../outside.json"

        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(review_findings_ref=escape_ref),
        )
        result = compare_variants([run_id], workspace_root=tmp_path)
        entry = result.entries[0]
        assert entry.review_findings is None
        assert entry.load_error is not None
        assert "escapes run directory" in entry.load_error


class TestCompareVariantsGrouping:
    def test_by_variant_groups_multiple_runs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 3 runs: 2 share variant, 1 different.
        records = {
            "run-a": _fake_record(variant_id="v.concise.v1"),
            "run-b": _fake_record(variant_id="v.concise.v1"),
            "run-c": _fake_record(variant_id="v.detailed.v1"),
        }
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: records[rid],
        )
        result = compare_variants(["run-a", "run-b", "run-c"], workspace_root=tmp_path)
        assert len(result.entries) == 3
        # entries preserve order
        assert [e.run_id for e in result.entries] == ["run-a", "run-b", "run-c"]
        # by_variant correctly groups
        assert set(result.by_variant.keys()) == {"v.concise.v1", "v.detailed.v1"}
        assert len(result.by_variant["v.concise.v1"]) == 2
        assert len(result.by_variant["v.detailed.v1"]) == 1

    def test_experiment_id_passes_through(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(experiment_id="exp-42"),
        )
        result = compare_variants(["r1"], workspace_root=tmp_path)
        assert result.entries[0].experiment_id == "exp-42"

    def test_missing_experiment_id_is_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "ao_kernel.experiments.compare._load_run_record",
            lambda ws, rid: _fake_record(experiment_id=None),
        )
        result = compare_variants(["r1"], workspace_root=tmp_path)
        assert result.entries[0].experiment_id is None
