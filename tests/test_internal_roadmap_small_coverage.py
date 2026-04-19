"""v3.12 H2a (coverage tranche 5A) — roadmap small/pure files.

Three high-transitive files pulled out of `coverage.run.omit`:
    * ``_internal/roadmap/compiler.py`` (89% transitive at H2a; fresh
      pins written directly against the live API land in
      ``test_internal_roadmap_compiler_coverage.py`` in v3.13 H2b;
      the previous ``_TestCompilerInvariantGuards_DEFER`` class that
      sat here targeted a stale ``plan_path=`` signature and has been
      removed per Codex plan-time directive)
    * ``_internal/roadmap/roadmap_checkpoint.py`` (97%)
    * ``_internal/roadmap/exec_contracts.py`` (93%)

v3.13 H2b1 (tranche 5B) additionally pulls
``_internal/roadmap/{change_proposals,sanitize,evidence}.py`` out of
omit — their pins live in
``test_internal_roadmap_small_trio_coverage.py``. Deeper siblings
(``step_templates``, ``exec_evidence``, ``exec_steps``, ``executor``)
stay omitted and are candidated for v3.13+ tranches.
"""

from __future__ import annotations

import json
from pathlib import Path


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


# NOTE: the prior ``_TestCompilerInvariantGuards_DEFER`` class that
# used to live here targeted a stale ``plan_path=`` argument that is
# not part of the live ``compile_roadmap`` signature (real API:
# explicit ``schema_path`` + ``cache_root`` keywords; plan is written
# to ``cache_root/roadmap_plans/<plan_id>/plan.json``). Per v3.13
# H2b-compiler plan-time Codex directive the stub was removed and
# fresh pins written from scratch in
# ``tests/test_internal_roadmap_compiler_coverage.py``.
