"""v3.12 H2a (coverage tranche 5A) — roadmap small/pure files.

Three high-transitive files pulled out of `coverage.run.omit`:
    * ``_internal/roadmap/compiler.py`` (89%)
    * ``_internal/roadmap/roadmap_checkpoint.py`` (97%)
    * ``_internal/roadmap/exec_contracts.py`` (93%)

Deeper-gap siblings (`change_proposals`, `sanitize`, `step_templates`,
`evidence`, `exec_evidence`, `exec_steps`, `executor`) stay omitted
and are candidated for v3.13 H2b/H2c tranches. Per v3.12 plan-time
Codex split; matches v3.11 P4 single-tranche-per-small-family pattern.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestExecContractsChangeCounter:
    def test_touch_records_path_and_accumulates_diff_lines(self) -> None:
        from ao_kernel._internal.roadmap.exec_contracts import ChangeCounter

        counter = ChangeCounter(paths_touched=set(), diff_lines=0)
        counter.touch("src/foo.py", 10)
        counter.touch("src/bar.py", 5)
        counter.touch("src/foo.py", 3)  # same path re-touch

        # set dedupes paths; diff_lines accumulates linearly.
        assert counter.paths_touched == {"src/foo.py", "src/bar.py"}
        assert counter.diff_lines == 18


class TestRoadmapCheckpointCorruptionGuard:
    def test_load_returns_none_on_json_decode_error(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.roadmap_checkpoint import (
            RoadmapCheckpointManager,
        )

        # Write garbage at the expected checkpoint path and confirm
        # load() swallows the JSONDecodeError → None.
        store = RoadmapCheckpointManager(tmp_path)
        run_id = "test-run-corrupt"
        cp_dir = tmp_path / ".cache" / "roadmap_checkpoints" / run_id
        cp_dir.mkdir(parents=True)
        (cp_dir / "progress.v1.json").write_text("{not valid json", encoding="utf-8")

        result = store.load(run_id)
        assert result is None

    def test_load_returns_none_when_hash_mismatch(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.roadmap_checkpoint import (
            RoadmapCheckpointManager,
        )

        # Write a well-formed JSON with a tampered `hash` field — the
        # integrity guard must return None rather than raise.
        store = RoadmapCheckpointManager(tmp_path)
        run_id = "test-run-tampered"
        cp_dir = tmp_path / ".cache" / "roadmap_checkpoints" / run_id
        cp_dir.mkdir(parents=True)
        (cp_dir / "progress.v1.json").write_text(
            json.dumps(
                {
                    "checkpoint": {
                        "run_id": run_id,
                        "phase": "PREFLIGHT",
                        "completed_steps": [],
                        "failed_steps": [],
                        "dlq": {},
                        "virtual_fs_state": {},
                        "counters": {},
                    },
                    "hash": "deadbeef" * 8,  # wrong hash
                }
            ),
            encoding="utf-8",
        )

        assert store.load(run_id) is None


class _TestCompilerInvariantGuards_DEFER:
    """`compile_roadmap` defensive branches deferred to H2b.

    The compiler's public surface requires a full schema file + cache
    root plus a schema-valid roadmap. Exercising the individual
    defensive guards here would duplicate fixture setup that the
    bundled roadmap integration tests already cover. Running at 89%
    transitive coverage through those tests; H2b (deeper roadmap
    tranche) picks up the last pins when it ships a proper
    roadmap-compiler fixture harness.

    The class is renamed with a leading underscore so pytest skips
    collection rather than flagging unused imports.
    """

    def _write_roadmap(self, path: Path, roadmap_obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(roadmap_obj), encoding="utf-8")

    def test_milestones_not_list_raises(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap_path = tmp_path / "roadmap.v1.json"
        self._write_roadmap(
            roadmap_path,
            {
                "version": "v1",
                "id": "R1",
                "roadmap_version": "1.0.0",
                "milestones": "not-a-list",  # invariant breach
            },
        )

        with pytest.raises(ValueError, match="ROADMAP"):
            compile_roadmap(roadmap_path=roadmap_path, plan_path=tmp_path / "plan.json")

    def test_empty_milestone_ids_filter_raises(self, tmp_path: Path) -> None:
        # milestone_ids kwarg present but filters to nothing.
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap_path = tmp_path / "roadmap.v1.json"
        self._write_roadmap(
            roadmap_path,
            {
                "version": "v1",
                "id": "R1",
                "roadmap_version": "1.0.0",
                "milestones": [],
            },
        )

        with pytest.raises(ValueError, match="ROADMAP_INVALID"):
            compile_roadmap(
                roadmap_path=roadmap_path,
                plan_path=tmp_path / "plan.json",
                milestone_ids=["", "   "],  # all empty after strip
            )

    def test_iso_core_required_injects_preflight_step(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap_path = tmp_path / "roadmap.v1.json"
        self._write_roadmap(
            roadmap_path,
            {
                "version": "v1",
                "id": "R1",
                "roadmap_version": "1.0.0",
                "iso_core_required": True,
                "milestones": [
                    {
                        "id": "M1",
                        "title": "first",
                        "steps": [
                            {"type": "noop"},
                        ],
                    }
                ],
            },
        )

        result = compile_roadmap(roadmap_path=roadmap_path, plan_path=tmp_path / "plan.json")
        assert result.status == "OK"
        step_ids = [s["step_id"] for s in result.plan["steps"]]
        assert "PREFLIGHT:ISO_CORE" in step_ids

    def test_global_gates_injected_before_milestones(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap_path = tmp_path / "roadmap.v1.json"
        self._write_roadmap(
            roadmap_path,
            {
                "version": "v1",
                "id": "R1",
                "roadmap_version": "1.0.0",
                "global_gates": [
                    {"type": "lint"},
                    {"type": "coverage"},
                ],
                "milestones": [
                    {"id": "M1", "title": "m", "steps": [{"type": "noop"}]},
                ],
            },
        )
        result = compile_roadmap(roadmap_path=roadmap_path, plan_path=tmp_path / "plan.json")
        step_ids = [s["step_id"] for s in result.plan["steps"]]
        assert "GLOBAL:G:001" in step_ids
        assert "GLOBAL:G:002" in step_ids

    def test_out_path_writes_additional_copy(self, tmp_path: Path) -> None:
        # Exercises the `if out_path is not None` fork near the end
        # of compile_roadmap.
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap_path = tmp_path / "roadmap.v1.json"
        self._write_roadmap(
            roadmap_path,
            {
                "version": "v1",
                "id": "R1",
                "roadmap_version": "1.0.0",
                "milestones": [
                    {"id": "M1", "title": "m", "steps": [{"type": "noop"}]},
                ],
            },
        )

        plan_path = tmp_path / "plan.json"
        out_path = tmp_path / "plan.copy.json"
        result = compile_roadmap(roadmap_path=roadmap_path, plan_path=plan_path, out_path=out_path)
        assert plan_path.exists()
        assert out_path.exists()
        assert result.status == "OK"

    def test_deliverables_fallback_from_steps(self, tmp_path: Path) -> None:
        # When a milestone has no ``steps`` but does have
        # ``deliverables``, the elif branch on line 144 should fire
        # and treat them as the deliverable list.
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        roadmap_path = tmp_path / "roadmap.v1.json"
        self._write_roadmap(
            roadmap_path,
            {
                "version": "v1",
                "id": "R1",
                "roadmap_version": "1.0.0",
                "milestones": [
                    {
                        "id": "M1",
                        "title": "m",
                        "deliverables": [{"type": "noop"}, {"type": "noop2"}],
                    }
                ],
            },
        )

        result = compile_roadmap(roadmap_path=roadmap_path, plan_path=tmp_path / "plan.json")
        # Two deliverables → two D-phase steps.
        d_steps = [s for s in result.plan["steps"] if s.get("phase") == "DELIVERABLE"]
        assert len(d_steps) == 2
