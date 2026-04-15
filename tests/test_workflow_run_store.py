"""Tests for ``ao_kernel.workflow.run_store``.

Covers UUIDv4 path-traversal guard, lock-path shape, ``run_revision``
self-reference invariance, ``create_run`` happy path + duplicate
rejection, ``load_run`` round-trip + missing-record error,
``save_run_cas`` CAS conflict, ``update_run`` state transitions +
retry, schema rejection at the save boundary, and atomic write under
monkeypatched ``os.replace`` failure (plan v2 W10: no subprocess
crashes).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from ao_kernel.workflow import (
    WorkflowCASConflictError,
    WorkflowRunCorruptedError,
    WorkflowRunIdInvalidError,
    WorkflowRunNotFoundError,
    WorkflowSchemaValidationError,
    create_run,
    load_run,
    run_revision,
    save_run_cas,
    update_run,
)
from ao_kernel.workflow.run_store import _lock_path, _run_path


def _new_uuid4() -> str:
    return str(uuid.uuid4())


def _create_sample(ws: Path, run_id: str | None = None) -> tuple[dict[str, Any], str]:
    rid = run_id or _new_uuid4()
    return create_run(
        ws,
        run_id=rid,
        workflow_id="bug_fix_flow",
        workflow_version="1.0.0",
        intent={"kind": "inline_prompt", "payload": "test"},
        budget={"fail_closed_on_exhaust": True},
        policy_refs=[
            "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
        ],
        evidence_refs=[".ao/evidence/workflows/x/events.jsonl"],
    )


class TestRunIdGuard:
    @pytest.mark.parametrize(
        "bad_id",
        [
            "../etc/passwd",
            "not-a-uuid",
            "",
            "12345",
            # UUIDv1 (time-based) — parses as UUID but version != 4
            "ace8c7e6-0000-11ee-9cbb-0242ac120002",
        ],
    )
    def test_rejects_non_uuid4(self, tmp_path: Path, bad_id: str) -> None:
        with pytest.raises(WorkflowRunIdInvalidError) as ei:
            _run_path(tmp_path, bad_id)
        assert ei.value.run_id == bad_id

    def test_accepts_valid_uuid4(self, tmp_path: Path) -> None:
        rid = _new_uuid4()
        p = _run_path(tmp_path, rid)
        assert rid in str(p)
        assert p.name == "state.v1.json"


class TestLockPath:
    def test_lock_path_uses_with_name_not_double_suffix(self, tmp_path: Path) -> None:
        """Must be ``state.v1.json.lock``, NOT ``state.v1.v1.json.lock``."""
        rid = _new_uuid4()
        lp = _lock_path(tmp_path, rid)
        assert lp.name == "state.v1.json.lock"


class TestRunRevision:
    def test_self_reference_free(self) -> None:
        """Hash of identical content with different ``revision`` values is equal."""
        base: dict[str, Any] = {"a": 1, "b": [2, 3], "c": {"d": 4}}
        r1 = run_revision({**base, "revision": "one"})
        r2 = run_revision({**base, "revision": "two"})
        r3 = run_revision(base)  # no revision field
        assert r1 == r2 == r3

    def test_revision_is_64_hex_chars(self) -> None:
        r = run_revision({"a": 1})
        assert len(r) == 64
        int(r, 16)  # must be valid hex

    def test_different_content_different_revision(self) -> None:
        a = run_revision({"x": 1})
        b = run_revision({"x": 2})
        assert a != b


class TestCreateRun:
    def test_happy_create(self, tmp_path: Path) -> None:
        rec, rev = _create_sample(tmp_path)
        assert rec["state"] == "created"
        assert rec["adapter_refs"] == []
        assert len(rev) == 64

    def test_adapter_refs_default_empty(self, tmp_path: Path) -> None:
        rec, _ = _create_sample(tmp_path)
        assert rec["adapter_refs"] == []

    def test_adapter_refs_explicit(self, tmp_path: Path) -> None:
        rec, _ = create_run(
            tmp_path,
            run_id=_new_uuid4(),
            workflow_id="bug_fix_flow",
            workflow_version="1.0.0",
            intent={"kind": "inline_prompt", "payload": "x"},
            budget={"fail_closed_on_exhaust": True},
            policy_refs=[
                "ao_kernel/defaults/policies/policy_worktree_profile.v1.json"
            ],
            evidence_refs=[".ao/evidence/workflows/y/events.jsonl"],
            adapter_refs=["claude-code-cli", "gh-cli-pr"],
        )
        assert rec["adapter_refs"] == ["claude-code-cli", "gh-cli-pr"]

    def test_duplicate_create_raises_file_exists(self, tmp_path: Path) -> None:
        rid = _new_uuid4()
        _create_sample(tmp_path, run_id=rid)
        with pytest.raises(FileExistsError):
            _create_sample(tmp_path, run_id=rid)

    def test_bad_run_id_rejected_before_disk_touch(self, tmp_path: Path) -> None:
        with pytest.raises(WorkflowRunIdInvalidError):
            create_run(
                tmp_path,
                run_id="../escape",
                workflow_id="x",
                workflow_version="1.0.0",
                intent={"kind": "inline_prompt", "payload": "x"},
                budget={"fail_closed_on_exhaust": True},
                policy_refs=["x"],
                evidence_refs=["x"],
            )


class TestLoadRun:
    def test_roundtrip_record_and_revision(self, tmp_path: Path) -> None:
        rec, rev = _create_sample(tmp_path)
        rec2, rev2 = load_run(tmp_path, rec["run_id"])
        assert rec2 == rec
        assert rev2 == rev

    def test_missing_run_raises(self, tmp_path: Path) -> None:
        missing = _new_uuid4()
        with pytest.raises(WorkflowRunNotFoundError):
            load_run(tmp_path, missing)

    def test_corrupted_json_raises(self, tmp_path: Path) -> None:
        rec, _ = _create_sample(tmp_path)
        state_path = _run_path(tmp_path, rec["run_id"])
        state_path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(WorkflowRunCorruptedError) as ei:
            load_run(tmp_path, rec["run_id"])
        assert ei.value.reason == "json_decode"

    def test_schema_invalid_on_disk_raises(self, tmp_path: Path) -> None:
        rec, _ = _create_sample(tmp_path)
        state_path = _run_path(tmp_path, rec["run_id"])
        broken = dict(rec)
        broken["state"] = "nonsense"  # violates enum
        state_path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(WorkflowRunCorruptedError) as ei:
            load_run(tmp_path, rec["run_id"])
        assert ei.value.reason == "schema_invalid"


class TestSaveRunCAS:
    def test_cas_conflict_on_stale_revision(self, tmp_path: Path) -> None:
        rec, rev = _create_sample(tmp_path)
        # update once so the on-disk revision moves away from rev
        def _bump(r: dict[str, Any]) -> dict[str, Any]:
            r["state"] = "running"
            return r

        rec2, _ = update_run(tmp_path, rec["run_id"], mutator=_bump)
        assert rec2["state"] == "running"

        # now save with the stale revision
        with pytest.raises(WorkflowCASConflictError) as ei:
            save_run_cas(
                tmp_path,
                rec["run_id"],
                record=rec,
                expected_revision=rev,  # stale
            )
        assert ei.value.expected_revision == rev

    def test_save_requires_existing_record(self, tmp_path: Path) -> None:
        missing = _new_uuid4()
        with pytest.raises(WorkflowRunNotFoundError):
            save_run_cas(
                tmp_path,
                missing,
                record={
                    "run_id": missing,
                    "workflow_id": "x",
                    "workflow_version": "1.0.0",
                    "state": "created",
                    "created_at": "2026-04-15T12:00:00+03:00",
                    "revision": "a" * 64,
                    "intent": {"kind": "inline_prompt", "payload": "x"},
                    "steps": [],
                    "policy_refs": ["x"],
                    "adapter_refs": [],
                    "evidence_refs": ["x"],
                    "budget": {"fail_closed_on_exhaust": True},
                },
                expected_revision="a" * 64,
            )


class TestUpdateRun:
    def test_happy_transition(self, tmp_path: Path) -> None:
        rec, rev = _create_sample(tmp_path)

        def _start(r: dict[str, Any]) -> dict[str, Any]:
            r["state"] = "running"
            r["started_at"] = "2026-04-15T12:01:00+03:00"
            return r

        rec2, rev2 = update_run(tmp_path, rec["run_id"], mutator=_start)
        assert rec2["state"] == "running"
        assert rev2 != rev

    def test_invalid_schema_rejected_at_save_boundary(
        self, tmp_path: Path
    ) -> None:
        rec, _ = _create_sample(tmp_path)

        def _bad(r: dict[str, Any]) -> dict[str, Any]:
            r["state"] = "nonsense"
            return r

        with pytest.raises(WorkflowSchemaValidationError) as ei:
            update_run(tmp_path, rec["run_id"], mutator=_bad)
        validators = {e["validator"] for e in ei.value.errors}
        assert "enum" in validators


class TestAtomicity:
    def test_os_replace_failure_leaves_prior_state_intact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plan v2 W10: monkeypatch ``os.replace`` failure; no subprocess crash."""
        rec, rev = _create_sample(tmp_path)
        state_path = _run_path(tmp_path, rec["run_id"])
        original_bytes = state_path.read_bytes()
        original_revision = rev

        def _boom(*args: Any, **kwargs: Any) -> None:
            raise OSError("simulated rename failure")

        # write_text_atomic goes through os.replace to finalize; replace the
        # reference it imports.
        monkeypatch.setattr(
            "ao_kernel._internal.shared.utils.os.replace",
            _boom,
        )

        def _start(r: dict[str, Any]) -> dict[str, Any]:
            r["state"] = "running"
            return r

        with pytest.raises(OSError, match="simulated rename failure"):
            update_run(tmp_path, rec["run_id"], mutator=_start)

        # File on disk unchanged — bytes identical, revision still original.
        assert state_path.read_bytes() == original_bytes
        rec_again, rev_again = load_run(tmp_path, rec["run_id"])
        assert rev_again == original_revision
        assert rec_again["state"] == "created"


class TestConcurrencyLight:
    def test_second_creator_loses_to_first(self, tmp_path: Path) -> None:
        """Sequential create of same run_id: second raises FileExistsError.

        Real multi-process CAS races are covered by canonical_store's
        existing concurrency suite; this module reuses ``_mutate_with_cas``
        on the same lock primitive, so repeating the heavyweight race test
        here would duplicate coverage.
        """
        rid = _new_uuid4()
        _create_sample(tmp_path, run_id=rid)
        with pytest.raises(FileExistsError):
            _create_sample(tmp_path, run_id=rid)
