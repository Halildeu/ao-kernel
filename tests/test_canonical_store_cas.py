"""Tests for canonical_store CAS + lock contract (C5a, CNS-010)."""

from __future__ import annotations

import threading
import warnings

import pytest

from ao_kernel.context.canonical_store import (
    load_store,
    promote_decision,
    save_store,
    save_store_cas,
    store_revision,
)
from ao_kernel.errors import (
    CanonicalRevisionConflict,
    CanonicalStoreCorruptedError,
)


@pytest.fixture
def project_with_ao(tmp_path):
    (tmp_path / ".ao").mkdir()
    return tmp_path


class TestStoreRevision:
    def test_empty_store_has_stable_revision(self, project_with_ao):
        rev1 = store_revision(load_store(project_with_ao))
        rev2 = store_revision(load_store(project_with_ao))
        assert rev1 == rev2
        assert len(rev1) == 64

    def test_revision_changes_after_mutation(self, project_with_ao):
        rev_before = store_revision(load_store(project_with_ao))
        promote_decision(
            project_with_ao,
            key="runtime.python",
            value="3.11",
            confidence=0.9,
        )
        rev_after = store_revision(load_store(project_with_ao))
        assert rev_before != rev_after


class TestSaveStoreCAS:
    def test_first_write_with_none_revision_and_allow_overwrite(self, project_with_ao):
        initial = {"version": "v1", "decisions": {"k": {"value": 1}}, "facts": {}}
        new_rev = save_store_cas(
            project_with_ao, initial,
            expected_revision=None, allow_overwrite=True,
        )
        assert len(new_rev) == 64
        reloaded = load_store(project_with_ao)
        assert reloaded["decisions"]["k"]["value"] == 1

    def test_cas_match_succeeds(self, project_with_ao):
        store = load_store(project_with_ao)
        store["decisions"]["k"] = {"value": 1}
        new_rev = save_store_cas(
            project_with_ao, store,
            expected_revision=store_revision(load_store(project_with_ao)),
            allow_overwrite=False,
        )
        assert new_rev != ""

    def test_cas_mismatch_raises(self, project_with_ao):
        store1 = load_store(project_with_ao)
        stale_rev = store_revision(store1)
        # Concurrent-ish writer moves the store forward.
        promote_decision(
            project_with_ao, key="other", value=1, confidence=0.9,
        )
        store1["decisions"]["k"] = {"value": 1}
        with pytest.raises(CanonicalRevisionConflict):
            save_store_cas(
                project_with_ao, store1,
                expected_revision=stale_rev,
                allow_overwrite=False,
            )

    def test_allow_overwrite_bypasses_cas(self, project_with_ao):
        store1 = load_store(project_with_ao)
        stale_rev = store_revision(store1)
        promote_decision(
            project_with_ao, key="other", value=1, confidence=0.9,
        )
        store1["decisions"]["k"] = {"value": 1}
        # Even with a stale expected_revision, allow_overwrite wins.
        new_rev = save_store_cas(
            project_with_ao, store1,
            expected_revision=stale_rev,
            allow_overwrite=True,
        )
        # New revision matches post-write snapshot; store now holds our write.
        assert new_rev == store_revision(load_store(project_with_ao))
        assert load_store(project_with_ao)["decisions"]["k"]["value"] == 1


class TestPromoteDecisionCAS:
    def test_promote_default_behavior_unchanged(self, project_with_ao):
        cd = promote_decision(
            project_with_ao,
            key="x", value=1, confidence=0.9,
        )
        assert cd.key == "x"

    def test_promote_with_matching_revision(self, project_with_ao):
        rev = store_revision(load_store(project_with_ao))
        cd = promote_decision(
            project_with_ao,
            key="x", value=1, confidence=0.9,
            expected_revision=rev,
            allow_overwrite=False,
        )
        assert cd.key == "x"

    def test_promote_with_stale_revision_raises(self, project_with_ao):
        rev = store_revision(load_store(project_with_ao))
        promote_decision(
            project_with_ao, key="other", value=1, confidence=0.9,
        )
        with pytest.raises(CanonicalRevisionConflict):
            promote_decision(
                project_with_ao,
                key="x", value=1, confidence=0.9,
                expected_revision=rev,
                allow_overwrite=False,
            )


class TestCorruptionFailClosed:
    def test_load_store_raises_on_invalid_json(self, project_with_ao):
        (project_with_ao / ".ao" / "canonical_decisions.v1.json").write_text(
            "{not json"
        )
        with pytest.raises(CanonicalStoreCorruptedError):
            load_store(project_with_ao)

    def test_load_store_raises_on_non_object_root(self, project_with_ao):
        (project_with_ao / ".ao" / "canonical_decisions.v1.json").write_text("[]")
        with pytest.raises(CanonicalStoreCorruptedError):
            load_store(project_with_ao)


class TestSaveStoreDeprecation:
    def test_save_store_emits_deprecation_warning(self, project_with_ao):
        store = {"version": "v1", "decisions": {}, "facts": {}}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            save_store(project_with_ao, store)
        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecated, "expected save_store to emit DeprecationWarning"
        assert "save_store_cas" in str(deprecated[0].message)


class TestLockExclusivity:
    """Verify concurrent writers serialize through the lock.

    Two threads each do read-modify-write on different keys. With the lock
    the final store must contain both keys; without the lock (race), the
    later writer overwrites the earlier one.
    """

    def test_concurrent_promote_both_land(self, project_with_ao):
        def writer(tag: str) -> None:
            promote_decision(
                project_with_ao,
                key=f"concurrent.{tag}",
                value=tag,
                confidence=0.9,
            )

        threads = [
            threading.Thread(target=writer, args=("a",)),
            threading.Thread(target=writer, args=("b",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = load_store(project_with_ao)
        assert "concurrent.a" in final["decisions"]
        assert "concurrent.b" in final["decisions"]
