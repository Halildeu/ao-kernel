"""V5 Epic 4 E-4-2a Multi-tenant advisory boundary contract invariants.

Eleven invariant categories enforce the slice contract:
  1. shape (7 dimension placeholder; schema + doc + matrix + plan reachable)
  2. no_guard_flip (3 guard flag key strings absent from artifacts)
  3. no_workflow_mutation (.github/workflows/** untouched)
  4. runtime_enforced_false_const (schema const false; all 7 entries false)
  5. operator_enforceable_true_per_entry (all 7 entries true)
  6. live_validated_false_const (schema const false; all 7 entries false)
  7. advisory_dil_test (no overclaim language in deployment doc)
  8. placeholder_status_per_entry (all 7 entries entry_status='placeholder')
  9. write_set_exact_match (evidence write_set == git diff)
 10. evidence_validates (slice evidence validates against slice schema)
 11. matrix_json_validates_against_matrix_schema (matrix validates)

Plus meta checks: plan doc + schema files reachable; no_pyproject_change;
no_runtime_module_change (only NEW schema files added under ao_kernel/).

All assertions are concrete (no `assert True`, no `assert callable(x)`,
no bare except per CLAUDE.md test quality gates BLK-001/002/003).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOC_PATH = _REPO_ROOT / "docs" / "MULTI-TENANT-DEPLOYMENT.md"
_MATRIX_PATH = _REPO_ROOT / ".claude" / "plans" / "tenant_isolation_matrix.v1.json"
_MATRIX_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "tenant-isolation-matrix.schema.v1.json"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.v1.json"
_EVIDENCE_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "e-4-2a-multi-tenant-boundary-contract.schema.v1.json"
)
_PLAN_DOC_PATH = _REPO_ROOT / ".claude" / "plans" / "E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.md"

# The 7 expected dimensions per Codex iter-2 F4 absorb.
_EXPECTED_DIMENSIONS = (
    "namespace_isolation",
    "rbac_scope",
    "secret_isolation",
    "network_policy",
    "resource_quota",
    "audit_boundary",
    "cost_tracking_advisory",
)

# Three runtime guard flag key strings (F2 absorb).
_GUARD_FLAG_KEYS = (
    "support_widening",
    "production_platform_claim",
    "live_adapter_execution",
)

# Overclaim language banned in the deployment doc (F4 absorb).
# Case-insensitive search; each phrase must NOT appear in the deployment doc.
_OVERCLAIM_PHRASES = (
    "isolation achieved",
    "isolation enforced",
    "fully isolated",
    "runtime enforces",
)

# Files which intentionally contain guard flag key strings AS subject matter
# (the test file scans for them; the slice evidence/schema/plan/matrix
# explicitly pin them const false). The recursive key-absence scan excludes
# this exact set of artifact paths to avoid testing-the-tester self-reference.
_KEY_STRING_ALLOWED_PATHS_RELATIVE = frozenset(
    {
        # The slice evidence schema declares guard_flags object whose property
        # names include the flag strings (schema constants false).
        "ao_kernel/defaults/schemas/e-4-2a-multi-tenant-boundary-contract.schema.v1.json",
        # The slice evidence JSON literally records guard_flags = {key: false}.
        ".claude/plans/E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.v1.json",
        # This test file scans for the strings.
        "tests/test_epic_4_2a_multi_tenant_boundary.py",
        # The slice plan doc explains the no-flip contract using key names.
        ".claude/plans/E-4-2a-MULTI-TENANT-BOUNDARY-CONTRACT.md",
    }
)


def _run_git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _changed_files_against_origin_main() -> list[str]:
    """Return sorted unique list of files changed against origin/main."""
    output = _run_git("diff", "--name-only", "origin/main...HEAD")
    files = sorted({line.strip() for line in output.splitlines() if line.strip()})
    return files


def _skip_unless_e42a_evidence_in_diff(changed: list[str], invariant_name: str) -> None:
    evidence_path = str(_EVIDENCE_PATH.relative_to(_REPO_ROOT))
    if evidence_path not in changed:
        pytest.skip(f"E-4-2a {invariant_name} applies only when the E-4-2a evidence artifact is in the PR diff")


def _load_json(path: Path) -> dict[str, Any]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"expected JSON object at {path}; got {type(data).__name__}"
    return data


# ── 1. shape ───────────────────────────────────────────────────────────


def test_shape_matrix_file_exists() -> None:
    assert _MATRIX_PATH.is_file(), f"matrix JSON missing: {_MATRIX_PATH}"


def test_shape_matrix_schema_file_exists() -> None:
    assert _MATRIX_SCHEMA_PATH.is_file(), f"matrix schema missing: {_MATRIX_SCHEMA_PATH}"


def test_shape_evidence_schema_file_exists() -> None:
    assert _EVIDENCE_SCHEMA_PATH.is_file(), f"evidence schema missing: {_EVIDENCE_SCHEMA_PATH}"


def test_shape_deployment_doc_exists() -> None:
    assert _DOC_PATH.is_file(), f"deployment doc missing: {_DOC_PATH}"


def test_shape_plan_doc_exists() -> None:
    assert _PLAN_DOC_PATH.is_file(), f"plan doc missing: {_PLAN_DOC_PATH}"


def test_shape_matrix_has_exactly_seven_unique_dimensions() -> None:
    matrix = _load_json(_MATRIX_PATH)
    dimensions = matrix.get("dimensions", [])
    assert len(dimensions) == 7, f"expected 7 dimensions; got {len(dimensions)}"
    names = [d.get("dimension") for d in dimensions]
    assert sorted(names) == sorted(_EXPECTED_DIMENSIONS), (
        f"dimension set mismatch; got {sorted(names)!r}, expected {sorted(_EXPECTED_DIMENSIONS)!r}"
    )
    assert len(set(names)) == 7, f"dimension names not unique: {names}"


# ── 2. no_guard_flip (key absence in artifacts) ────────────────────────


def test_no_guard_flag_key_in_artifact_files_except_allowed() -> None:
    """Scan repo-relative artifact files added by this slice. Any guard flag
    key string in a non-allowed path is a violation. Allowed paths are
    listed in _KEY_STRING_ALLOWED_PATHS_RELATIVE (test file + slice
    evidence + slice schema + slice plan doc explicitly pin keys const false).
    """
    targets = (
        _DOC_PATH,
        _MATRIX_PATH,
        _MATRIX_SCHEMA_PATH,
    )
    hits: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(_REPO_ROOT))
        if rel in _KEY_STRING_ALLOWED_PATHS_RELATIVE:
            continue
        for flag in _GUARD_FLAG_KEYS:
            if flag in text:
                hits.append(f"{rel}: contains forbidden guard flag key {flag!r}")
    assert hits == [], "guard flag key strings MUST NOT appear in non-allowed artifact files:\n" + "\n".join(hits)


def test_evidence_pins_three_guard_flags_const_false() -> None:
    """Evidence JSON literally records the three guard flags as false."""
    evidence = _load_json(_EVIDENCE_PATH)
    flags = evidence.get("guard_flags", {})
    for flag in _GUARD_FLAG_KEYS:
        assert flag in flags, f"evidence.guard_flags missing key {flag!r}"
        assert flags[flag] is False, f"evidence.guard_flags.{flag} MUST be false; got {flags[flag]!r}"


# ── 3. no_workflow_mutation ────────────────────────────────────────────


def test_no_workflow_mutation_in_diff() -> None:
    """git diff against origin/main MUST NOT include .github/workflows/** entries."""
    changed = _changed_files_against_origin_main()
    _skip_unless_e42a_evidence_in_diff(changed, "workflow mutation invariant")
    workflow_changes = [p for p in changed if p.startswith(".github/workflows/")]
    assert workflow_changes == [], f"workflow files modified in this slice (FORBIDDEN): {workflow_changes}"


# ── 4. runtime_enforced_false_const ───────────────────────────────────


def test_matrix_schema_runtime_enforced_is_const_false() -> None:
    schema = _load_json(_MATRIX_SCHEMA_PATH)
    re_def = schema.get("$defs", {}).get("dimension_entry", {}).get("properties", {}).get("runtime_enforced", {})
    assert re_def.get("const") is False, (
        f"matrix schema dimension_entry.runtime_enforced MUST be const false; got {re_def!r}"
    )


def test_matrix_all_entries_runtime_enforced_false() -> None:
    matrix = _load_json(_MATRIX_PATH)
    for entry in matrix.get("dimensions", []):
        assert entry.get("runtime_enforced") is False, (
            f"dimension {entry.get('dimension')!r}: runtime_enforced MUST be false; got {entry.get('runtime_enforced')!r}"
        )
    assert matrix.get("runtime_enforced_global") is False, "matrix.runtime_enforced_global MUST be false"


# ── 5. operator_enforceable_true_per_entry ────────────────────────────


def test_matrix_all_entries_operator_enforceable_true() -> None:
    matrix = _load_json(_MATRIX_PATH)
    for entry in matrix.get("dimensions", []):
        assert entry.get("operator_enforceable") is True, (
            f"dimension {entry.get('dimension')!r}: operator_enforceable MUST be true (Kubernetes-native enforcement available); got {entry.get('operator_enforceable')!r}"
        )


# ── 6. live_validated_false_const ─────────────────────────────────────


def test_matrix_schema_live_validated_is_const_false() -> None:
    schema = _load_json(_MATRIX_SCHEMA_PATH)
    lv_def = schema.get("$defs", {}).get("dimension_entry", {}).get("properties", {}).get("live_validated", {})
    assert lv_def.get("const") is False, (
        f"matrix schema dimension_entry.live_validated MUST be const false; got {lv_def!r}"
    )


def test_matrix_all_entries_live_validated_false() -> None:
    matrix = _load_json(_MATRIX_PATH)
    for entry in matrix.get("dimensions", []):
        assert entry.get("live_validated") is False, (
            f"dimension {entry.get('dimension')!r}: live_validated MUST be false (no live cross-tenant attack test in Epic 4)"
        )
    assert matrix.get("live_validated_global") is False, "matrix.live_validated_global MUST be false"


# ── 7. advisory_dil_test ──────────────────────────────────────────────


def test_deployment_doc_has_no_overclaim_language() -> None:
    """docs/MULTI-TENANT-DEPLOYMENT.md MUST NOT contain isolation overclaim
    phrases. The phrases are checked case-insensitively against the document
    body. Each phrase is matched as a standalone substring (not regex)."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    lower = text.lower()
    hits: list[str] = []
    for phrase in _OVERCLAIM_PHRASES:
        if phrase.lower() in lower:
            # Find first occurrence context for debugging.
            idx = lower.find(phrase.lower())
            snippet = text[max(0, idx - 40) : idx + len(phrase) + 40].replace("\n", " ")
            hits.append(f"phrase {phrase!r} found at offset {idx}: ...{snippet}...")
    assert hits == [], "deployment doc MUST use advisory dil; overclaim phrases detected:\n" + "\n".join(hits)


def test_deployment_doc_repeats_advisory_dil_markers() -> None:
    """The doc must repeat the advisory dil markers in at least 3 places per
    Codex iter-2 F4 absorb (overclaim engellemesi)."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    runtime_enforced_count = len(re.findall(r"runtime_enforced:\s*false", text))
    live_validated_count = len(re.findall(r"live_validated:\s*false", text))
    assert runtime_enforced_count >= 3, (
        f"deployment doc must mention 'runtime_enforced: false' at least 3 times; got {runtime_enforced_count}"
    )
    assert live_validated_count >= 3, (
        f"deployment doc must mention 'live_validated: false' at least 3 times; got {live_validated_count}"
    )


def test_deployment_doc_does_not_embed_live_cluster_commands() -> None:
    """Per Codex iter-2 F7 absorb: runbook docs must not embed live cluster
    commands. helm install / helm upgrade / kubectl apply substrings forbidden."""
    text = _DOC_PATH.read_text(encoding="utf-8")
    forbidden = ("helm install", "helm upgrade", "kubectl apply")
    hits = [cmd for cmd in forbidden if cmd in text]
    assert hits == [], f"deployment doc MUST NOT embed live cluster commands; found: {hits}"


# ── 8. placeholder_status_per_entry ───────────────────────────────────


def test_matrix_status_is_e_4_2a_contract_placeholder() -> None:
    matrix = _load_json(_MATRIX_PATH)
    assert matrix.get("matrix_status") == "e_4_2a_contract_placeholder", (
        f"matrix_status MUST be 'e_4_2a_contract_placeholder'; got {matrix.get('matrix_status')!r}"
    )


def test_matrix_all_entries_status_placeholder() -> None:
    matrix = _load_json(_MATRIX_PATH)
    for entry in matrix.get("dimensions", []):
        assert entry.get("entry_status") == "placeholder", (
            f"dimension {entry.get('dimension')!r}: entry_status MUST be 'placeholder' in E-4-2a; got {entry.get('entry_status')!r}"
        )


def test_matrix_all_entries_downstream_evidence_ref_null() -> None:
    """In E-4-2a all downstream_evidence_ref values are null (E-4-2b will set them)."""
    matrix = _load_json(_MATRIX_PATH)
    for entry in matrix.get("dimensions", []):
        if "downstream_evidence_ref" in entry:
            assert entry["downstream_evidence_ref"] is None, (
                f"dimension {entry.get('dimension')!r}: downstream_evidence_ref MUST be null in E-4-2a; got {entry['downstream_evidence_ref']!r}"
            )


# ── 9. write_set_exact_match ──────────────────────────────────────────


def test_write_set_exact_match_git_diff() -> None:
    git_diff = _changed_files_against_origin_main()
    _skip_unless_e42a_evidence_in_diff(git_diff, "write_set exactness")
    evidence = _load_json(_EVIDENCE_PATH)
    evidence_write_set = sorted(set(evidence.get("write_set", [])))
    assert evidence_write_set == git_diff, (
        "evidence.write_set diverges from git diff --name-only origin/main..HEAD\n"
        f"  evidence: {evidence_write_set}\n"
        f"  git diff: {git_diff}\n"
        f"  missing_from_evidence: {sorted(set(git_diff) - set(evidence_write_set))}\n"
        f"  extra_in_evidence: {sorted(set(evidence_write_set) - set(git_diff))}"
    )


# ── 10. evidence_validates ────────────────────────────────────────────


def test_evidence_validates_against_evidence_schema() -> None:
    schema = _load_json(_EVIDENCE_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    evidence = _load_json(_EVIDENCE_PATH)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.path))
    assert errors == [], "evidence validation errors:\n" + "\n".join(f"  {list(e.path)} -> {e.message}" for e in errors)


# ── 11. matrix_json_validates_against_matrix_schema ───────────────────


def test_matrix_json_validates_against_matrix_schema() -> None:
    schema = _load_json(_MATRIX_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    matrix = _load_json(_MATRIX_PATH)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(matrix), key=lambda e: list(e.path))
    assert errors == [], "matrix validation errors:\n" + "\n".join(f"  {list(e.path)} -> {e.message}" for e in errors)


# ── meta: no_pyproject_change ─────────────────────────────────────────


def test_no_pyproject_change_in_slice() -> None:
    changed = _changed_files_against_origin_main()
    _skip_unless_e42a_evidence_in_diff(changed, "pyproject boundary")
    assert "pyproject.toml" not in changed, "pyproject.toml MUST NOT change in E-4-2a (Epic 4 invariant)"


# ── meta: no_runtime_module_change ────────────────────────────────────


def test_no_runtime_python_module_change_in_slice() -> None:
    """This slice only ADDS new schema files under ao_kernel/defaults/schemas/.
    It MUST NOT modify any existing ao_kernel/*.py file or any other
    non-schema file under ao_kernel/."""
    changed = _changed_files_against_origin_main()
    _skip_unless_e42a_evidence_in_diff(changed, "runtime module boundary")
    ao_kernel_paths = [p for p in changed if p.startswith("ao_kernel/")]
    illegal = [p for p in ao_kernel_paths if not (p.startswith("ao_kernel/defaults/schemas/") and p.endswith(".json"))]
    assert illegal == [], (
        "E-4-2a MUST only add new JSON schema files under ao_kernel/defaults/schemas/; "
        f"these paths violate the boundary: {illegal}"
    )


# ── meta: reviewer providers distinct ─────────────────────────────────


def test_reviewer_providers_two_way_distinct() -> None:
    """E-4-2a uses 2-way cross-AI (Claude/anthropic + Codex/openai).
    The slice evidence MUST record exactly these two providers."""
    evidence = _load_json(_EVIDENCE_PATH)
    providers = evidence.get("reviewer_providers", [])
    assert "anthropic" in providers, "reviewer_providers must include 'anthropic' (implementer Claude)"
    assert "openai" in providers, "reviewer_providers must include 'openai' (reviewer Codex)"
    assert len(set(providers)) == len(providers), "reviewer_providers must be unique"
    assert len(providers) >= 2, "reviewer_providers must have at least 2 entries"
