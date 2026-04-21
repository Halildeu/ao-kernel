"""v3.13 H2b-compiler — ``_internal/roadmap/compiler.py`` coverage.

``compiler.py`` was pulled out of ``coverage.run.omit`` in v3.12 H2a
(tranche 5A) but the defensive-guard pins were deferred because the
pre-existing class ``_TestCompilerInvariantGuards_DEFER`` in
``test_internal_roadmap_small_coverage.py`` targeted a stale
``plan_path=`` signature that doesn't exist in the live API (the real
``compile_roadmap`` takes explicit ``schema_path`` + ``cache_root`` and
writes the plan to ``cache_root/roadmap_plans/<plan_id>/plan.json``).

This file writes fresh pins directly against the live API — no
``plan_path`` kwarg, no ``"id"`` field (real roadmap uses ``"roadmap_id"``
per ``tests/test_roadmap_internal.py`` conventions). The deferred class
is deleted in the same PR.

Covered branches (missing-line inventory from 83% transitive baseline):
- validate_roadmap error message builder (json_path anchor)
- ROADMAP_SCHEMA_INVALID raise on schema-invalid payload
- ROADMAP_INVALID: non-list milestones
- ROADMAP_INVALID: empty ``milestone_ids`` filter
- ROADMAP_MILESTONE_NOT_FOUND for requested IDs absent from roadmap
- Non-dict milestone entries skipped silently during filter
- No-filter path: non-dict/non-string-id milestones gracefully skipped
- ISO core preflight step injection
- ``global_gates`` list → GLOBAL:G:NNN steps
- Deliverables fallback: ``steps`` field used when present; ``deliverables``
  field used when ``steps`` absent
- Optional ``out_path`` writes a second copy of the plan JSON
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


# Schema that requires `roadmap_id` + `version` + `milestones` so we can
# exercise the ROADMAP_SCHEMA_INVALID path with missing-required payloads.
_STRICT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["roadmap_id", "version", "milestones"],
    "properties": {
        "roadmap_id": {"type": "string", "minLength": 1},
        "version": {"type": "string"},
        "milestones": {"type": "array"},
    },
}

# Permissive schema that accepts any object — used when the test wants
# the *inner* fail-closed guards (non-list milestones, empty id filter,
# …) to fire rather than the schema validator.
_PERMISSIVE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
}


def _write_schema(tmp_path: Path, schema: dict[str, Any], name: str = "schema.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(schema), encoding="utf-8")
    return p


def _write_roadmap(tmp_path: Path, roadmap_obj: Any, name: str = "roadmap.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(roadmap_obj), encoding="utf-8")
    return p


class TestValidateRoadmapMessageFormat:
    def test_json_path_anchor_prefixes_error_message(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import validate_roadmap

        schema_path = _write_schema(tmp_path, _STRICT_SCHEMA)
        # `roadmap_id` absent → one required-field error.
        errors = validate_roadmap(
            {"version": "v1", "milestones": []},
            schema_path,
        )
        assert errors, "expected at least one schema error"
        assert all(":" in e for e in errors)
        # Either "$:" (top-level miss) or a nested path.
        assert any(e.startswith("$:") or ":" in e[:10] for e in errors)

    def test_empty_errors_when_valid(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import validate_roadmap

        schema_path = _write_schema(tmp_path, _STRICT_SCHEMA)
        assert (
            validate_roadmap(
                {"roadmap_id": "R1", "version": "v1", "milestones": []},
                schema_path,
            )
            == []
        )


class TestCompileRoadmapGuards:
    def test_schema_invalid_raises_roadmap_schema_invalid(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _STRICT_SCHEMA)
        roadmap_path = _write_roadmap(tmp_path, {"version": "v1"})  # missing roadmap_id + milestones
        with pytest.raises(ValueError, match="ROADMAP_SCHEMA_INVALID"):
            compile_roadmap(
                roadmap_path=roadmap_path,
                schema_path=schema_path,
                cache_root=tmp_path / ".cache",
            )

    def test_non_list_milestones_raises_roadmap_invalid(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        # Permissive schema so the compiler-level "must be a list" guard
        # fires rather than the jsonschema validator.
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": "not-a-list",
            },
        )
        with pytest.raises(ValueError, match="milestones must be a list"):
            compile_roadmap(
                roadmap_path=roadmap_path,
                schema_path=schema_path,
                cache_root=tmp_path / ".cache",
            )

    def test_empty_milestone_ids_filter_raises_roadmap_invalid(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {"roadmap_id": "R1", "version": "v1", "milestones": []},
        )
        with pytest.raises(ValueError, match="milestone_ids is empty"):
            compile_roadmap(
                roadmap_path=roadmap_path,
                schema_path=schema_path,
                cache_root=tmp_path / ".cache",
                milestone_ids=["", "   "],  # whitespace-only → filter to []
            )

    def test_missing_milestone_id_raises_not_found(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [{"id": "MS-1", "title": "a"}],
            },
        )
        with pytest.raises(ValueError, match="ROADMAP_MILESTONE_NOT_FOUND.*MS-9"):
            compile_roadmap(
                roadmap_path=roadmap_path,
                schema_path=schema_path,
                cache_root=tmp_path / ".cache",
                milestone_ids=["MS-9"],
            )

    def test_non_dict_milestone_skipped_during_filter(self, tmp_path: Path) -> None:
        """A stray non-dict entry in ``milestones`` must not kill the
        filter loop; only real dict entries with matching ``id`` are
        included.
        """
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    "stray-string-entry",
                    {"id": "MS-1", "title": "first"},
                    None,
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
            milestone_ids=["MS-1"],
        )
        assert result.status == "OK"
        assert result.milestones_included == ["MS-1"]


class TestCompileRoadmapHappyPath:
    def test_no_filter_skips_non_dict_entries_and_tracks_string_ids(self, tmp_path: Path) -> None:
        """No-filter path: non-dict entries skipped by ``isinstance`` guard
        (line 86); string-id dicts captured in ``milestones_included``
        (line 88-89); non-string-id dicts land in ``plan["milestones"]``
        but are excluded from ``milestones_included`` because
        ``isinstance(ms_id, str)`` is False.
        """
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    "bogus-string",  # not a dict → skipped (line 86)
                    {"id": "MS-1", "title": "a"},  # string id → included
                    {"id": 42, "title": "non-string-id-dict"},  # line 88 else
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        # Only the one with a *string* id lands in ``milestones_included``.
        assert result.milestones_included == ["MS-1"]
        # Both dict-shaped milestones appear in the plan header.
        assert len(result.plan["milestones"]) == 2

    def test_no_filter_skips_dict_without_id_in_render_loop(self, tmp_path: Path) -> None:
        """A dict-shaped milestone without ``id`` must be skipped instead
        of crashing the compiler."""
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {"title": "missing-id", "steps": [{"type": "noop"}]},
                    {"id": "MS-1", "title": "ok", "steps": [{"type": "noop"}]},
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        assert result.status == "OK"
        assert result.milestones_included == ["MS-1"]
        assert result.plan["milestones"] == [
            {
                "id": "MS-1",
                "title": "ok",
                "constraints": {},
                "deliverables_count": 1,
                "gates_count": 0,
            }
        ]
        assert all(step["milestone_id"] == "MS-1" for step in result.plan["steps"])

    def test_iso_core_required_injects_preflight_step(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "iso_core_required": True,
                "milestones": [
                    {"id": "MS-1", "title": "m", "steps": [{"type": "noop"}]},
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        step_ids = [s["step_id"] for s in result.plan["steps"]]
        assert "PREFLIGHT:ISO_CORE" in step_ids
        # Preflight step carries canonical default tenant + required files.
        preflight = next(s for s in result.plan["steps"] if s["step_id"] == "PREFLIGHT:ISO_CORE")
        assert preflight["template"]["tenant"] == "TENANT-DEFAULT"
        assert "context.v1.md" in preflight["template"]["required_files"]

    def test_global_gates_produce_sequential_ids(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "global_gates": [{"type": "lint"}, {"type": "coverage"}, {"type": "mypy"}],
                "milestones": [{"id": "MS-1", "title": "m", "steps": [{"type": "noop"}]}],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        step_ids = [s["step_id"] for s in result.plan["steps"]]
        # Zero-padded 3-digit sequence.
        assert "GLOBAL:G:001" in step_ids
        assert "GLOBAL:G:002" in step_ids
        assert "GLOBAL:G:003" in step_ids
        # And the plan header reports the count.
        assert result.plan["global_gates_count"] == 3

    def test_deliverables_fallback_from_steps_field(self, tmp_path: Path) -> None:
        """When the milestone has a ``steps`` field, it's used as the
        deliverables source (primary path)."""
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {
                        "id": "MS-1",
                        "title": "m",
                        "steps": [{"type": "t1"}, {"type": "t2"}],
                    }
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        d_steps = [s for s in result.plan["steps"] if s.get("phase") == "DELIVERABLE"]
        assert len(d_steps) == 2
        assert [s["step_id"] for s in d_steps] == ["MS-1:D:001", "MS-1:D:002"]

    def test_deliverables_fallback_from_deliverables_field(self, tmp_path: Path) -> None:
        """When ``steps`` is absent but ``deliverables`` is present,
        deliverables is used (elif branch)."""
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {
                        "id": "MS-1",
                        "title": "m",
                        "deliverables": [{"type": "d1"}, {"type": "d2"}],
                    }
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        d_steps = [s for s in result.plan["steps"] if s.get("phase") == "DELIVERABLE"]
        assert len(d_steps) == 2

    def test_milestone_gates_produce_phase_gate_steps(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {
                        "id": "MS-1",
                        "title": "m",
                        "steps": [],
                        "gates": [{"type": "g1"}, {"type": "g2"}],
                    }
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        g_steps = [s for s in result.plan["steps"] if s.get("phase") == "GATE" and s["milestone_id"] == "MS-1"]
        assert len(g_steps) == 2
        assert [s["step_id"] for s in g_steps] == ["MS-1:G:001", "MS-1:G:002"]

    def test_plan_persisted_to_cache_plan_dir(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [{"id": "MS-1", "title": "m", "steps": [{"type": "noop"}]}],
            },
        )
        cache_root = tmp_path / ".cache"
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=cache_root,
        )
        # plan.json ends up under cache_root/roadmap_plans/<plan_id>/.
        assert result.plan_path.is_file()
        assert result.plan_path.parent.parent == cache_root / "roadmap_plans"
        assert result.plan_path.name == "plan.json"
        # plan_id is a 16-char sha256 prefix.
        assert len(result.plan_id) == 16

    def test_out_path_writes_additional_copy(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [{"id": "MS-1", "title": "m", "steps": [{"type": "noop"}]}],
            },
        )
        out_path = tmp_path / "out-copy.json"
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
            out_path=out_path,
        )
        # Both the cached plan and the additional copy exist with the
        # same payload.
        assert out_path.is_file()
        assert result.plan_path.is_file()
        assert json.loads(out_path.read_text(encoding="utf-8")) == json.loads(
            result.plan_path.read_text(encoding="utf-8")
        )

    def test_plan_id_fingerprint_differs_on_milestone_filter(self, tmp_path: Path) -> None:
        """Same roadmap + different ``milestone_ids`` subsets must
        produce different plan_ids (the selection fingerprint is part of
        the hash input)."""
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {"id": "MS-1", "title": "a", "steps": []},
                    {"id": "MS-2", "title": "b", "steps": []},
                ],
            },
        )
        r_all = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache-all",
        )
        r_subset = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache-subset",
            milestone_ids=["MS-1"],
        )
        assert r_all.plan_id != r_subset.plan_id

    def test_plan_header_captures_deliverables_and_gates_counts(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {
                        "id": "MS-1",
                        "title": "m",
                        "constraints": {"max_lines": 100},
                        "steps": [{"type": "t1"}, {"type": "t2"}],
                        "gates": [{"type": "g1"}],
                    }
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        ms_header = result.plan["milestones"][0]
        assert ms_header["id"] == "MS-1"
        assert ms_header["constraints"] == {"max_lines": 100}
        assert ms_header["deliverables_count"] == 2
        assert ms_header["gates_count"] == 1

    def test_missing_constraints_defaults_to_empty_dict(self, tmp_path: Path) -> None:
        from ao_kernel._internal.roadmap.compiler import compile_roadmap

        schema_path = _write_schema(tmp_path, _PERMISSIVE_SCHEMA)
        roadmap_path = _write_roadmap(
            tmp_path,
            {
                "roadmap_id": "R1",
                "version": "v1",
                "milestones": [
                    {"id": "MS-1", "title": "m", "steps": []},
                ],
            },
        )
        result = compile_roadmap(
            roadmap_path=roadmap_path,
            schema_path=schema_path,
            cache_root=tmp_path / ".cache",
        )
        assert result.plan["milestones"][0]["constraints"] == {}
