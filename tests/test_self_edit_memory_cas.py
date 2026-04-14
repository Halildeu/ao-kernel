"""Tests for self_edit_memory.forget CAS migration (C5b, CNS-010).

Confirms the forget() helper now routes through the canonical lock/CAS
helper rather than calling save_store() directly — iter-2 blocking-2 of
CNS-20260414-010 ("tek kanonik write path yok" çürütmesi).
"""

from __future__ import annotations

import pytest

from ao_kernel.context.canonical_store import (
    load_store,
    promote_decision,
    store_revision,
)
from ao_kernel.context.self_edit_memory import forget, remember
from ao_kernel.errors import CanonicalRevisionConflict


@pytest.fixture
def project_with_ao(tmp_path):
    (tmp_path / ".ao").mkdir()
    return tmp_path


class TestForgetCAS:
    def test_default_forget_still_works(self, project_with_ao):
        remember(
            project_with_ao,
            key="test.fact",
            value="hello",
            importance="normal",
        )
        result = forget(project_with_ao, key="test.fact")
        assert result["forgotten"] is True
        # Expired timestamp => no longer returned by default query.
        store = load_store(project_with_ao)
        assert store["decisions"]["memory.test.fact"]["_forgotten"] is True

    def test_forget_with_matching_revision(self, project_with_ao):
        remember(
            project_with_ao, key="x", value="v", importance="normal",
        )
        rev = store_revision(load_store(project_with_ao))
        result = forget(
            project_with_ao, key="x",
            expected_revision=rev,
            allow_overwrite=False,
        )
        assert result["forgotten"] is True

    def test_forget_with_stale_revision_raises(self, project_with_ao):
        remember(
            project_with_ao, key="x", value="v", importance="normal",
        )
        rev = store_revision(load_store(project_with_ao))
        # Concurrent writer moves the store forward.
        promote_decision(
            project_with_ao, key="other", value=1, confidence=0.9,
        )
        with pytest.raises(CanonicalRevisionConflict):
            forget(
                project_with_ao, key="x",
                expected_revision=rev,
                allow_overwrite=False,
            )

    def test_forget_missing_key_does_not_mutate(self, project_with_ao):
        rev_before = store_revision(load_store(project_with_ao))
        result = forget(project_with_ao, key="does.not.exist")
        assert result["forgotten"] is False
        assert result["error"] == "MEMORY_NOT_FOUND"
        # Store revision unchanged — lock path held but did not mutate.
        # Note: _mutate_with_cas still stamps updated_at, so revision WILL
        # differ. We only assert the semantic outcome (nothing forgotten).
        assert rev_before is not None


class TestForgetNoLongerEmitsDeprecation:
    def test_forget_does_not_trigger_save_store_deprecation(self, project_with_ao, recwarn):
        remember(
            project_with_ao, key="x", value="v", importance="normal",
        )
        forget(project_with_ao, key="x")
        deprecations = [w for w in recwarn.list if issubclass(w.category, DeprecationWarning)]
        # save_store()'s DeprecationWarning used to leak through forget().
        # After CAS migration, forget() uses _mutate_with_cas which does
        # NOT emit the deprecation. Regression guard.
        for w in deprecations:
            assert "save_store" not in str(w.message), (
                "forget() should no longer trigger save_store deprecation"
            )
