"""Parity guard: `_LEGAL_CATEGORIES` runtime set must equal
`workflow-run.schema.v1.json::error.category.enum` (PR-B6 v4 iter-2
B4 absorb).

Prior drift (pre-B6): runtime had `adapter_error` that schema did NOT
carry; schema had `invocation_failed`, `output_parse_failed`,
`adapter_crash` that runtime did NOT carry. The `_legal_error_category`
fallback-to-"other" masked this drift. This test ensures the two
source-of-truths stay byte-identical.
"""

from __future__ import annotations

from ao_kernel.config import load_default
from ao_kernel.executor.multi_step_driver import _LEGAL_CATEGORIES


def _schema_error_categories() -> set[str]:
    """Extract the workflow-run schema's `error.category.enum` set.

    `error` property is a `$ref` to `#/$defs/error_record`; resolve via
    the $defs dict (no external resolver required — single-file schema).
    """
    schema = load_default("schemas", "workflow-run.schema.v1.json")
    error_record = schema["$defs"]["error_record"]
    enum_values = error_record["properties"]["category"]["enum"]
    return set(enum_values)


class TestErrorCategoryParity:
    def test_runtime_set_matches_schema_enum(self) -> None:
        """Strict equality — drift in either direction fails."""
        schema_set = _schema_error_categories()
        assert _LEGAL_CATEGORIES == schema_set, (
            f"Drift detected between runtime _LEGAL_CATEGORIES and "
            f"workflow-run schema error.category.enum.\n"
            f"  Only in runtime: {_LEGAL_CATEGORIES - schema_set}\n"
            f"  Only in schema:  {schema_set - _LEGAL_CATEGORIES}"
        )

    def test_ten_values_present(self) -> None:
        """Shape check: 10 values (timeout, invocation_failed,
        output_parse_failed, policy_denied, budget_exhausted,
        adapter_crash, approval_denied, ci_failed, apply_conflict,
        other)."""
        assert len(_LEGAL_CATEGORIES) == 10

    def test_output_parse_failed_present(self) -> None:
        """PR-B6 v4 §2.2 absorb: output_parse_failed must be runtime-
        legal for capability artifact write failure + walker failure
        translations."""
        assert "output_parse_failed" in _LEGAL_CATEGORIES

    def test_invocation_failed_present(self) -> None:
        """PR-B6 v4 iter-2 B2 absorb: invocation_failed must be runtime-
        legal for AdapterInvocationFailedError transport fallback."""
        assert "invocation_failed" in _LEGAL_CATEGORIES

    def test_adapter_crash_present(self) -> None:
        """PR-B6 v4 iter-2 B2 absorb: adapter_crash maps subprocess_crash
        reason."""
        assert "adapter_crash" in _LEGAL_CATEGORIES

    def test_legacy_adapter_error_removed(self) -> None:
        """Pre-B6 drift: `adapter_error` was present in runtime but
        NOT in schema. Removal is part of the parity fix."""
        assert "adapter_error" not in _LEGAL_CATEGORIES
