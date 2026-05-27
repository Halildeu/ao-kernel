"""AO-MA-9 GPP-2D integration evidence invariant tests.

Codex thread `019e6a6f-a3f7-7b92-9416-d6464668eafd` iter-2 AGREE
(ready_for_impl: true) absorb. AO-MA-1 §8 phased plan SON dilim AO-MA-9
(class: **gated closeout**). The AO-MA artifact chain is wired into
the GPP-2D required-check lane in **evidence-only** form — `wire_mode`
const-pinned `"evidence_manifest_only"`, `release_authority_claim` const
false. ao-release-gate payload remains unchanged. AO-MA-9 records the
chain; it does not extend the gate contract.

Invariants:

1. Receipt schema is a valid Draft 2020-12 document
2. Receipt parses + validates against schema
3. `wire_mode == "evidence_manifest_only"` (NOT payload field, NOT runtime hook)
4. `release_authority_claim is False`
5. All three guard_flags False
6. `ao_ma_chain_refs` records all 7 AO-MA PR numbers
7. `gpp_2d_artifact_refs` paths exist on disk
8. `ao_ma_8_chain_proof_refs` paths exist on disk
9. `gpp_status_invariants_at_closure` matches live `gpp_status.v1.json`
10. `ao-release-gate` payload module did NOT gain Option-B field-name keys
11. PR scope allowlist enforced (CI; multi-strategy resolver per AO-MA-8)
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parent.parent
_RECEIPT_PATH = _REPO_ROOT / ".claude" / "plans" / "AO-MA-9-GPP-INTEGRATION-EVIDENCE.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-9-gpp-integration-evidence.schema.v1.json"
_GPP_STATUS_PATH = _REPO_ROOT / ".claude" / "plans" / "gpp_status.v1.json"
_RELEASE_GATE_BUILD_PAYLOAD_PATH = _REPO_ROOT / "scripts" / "ao_release_gate_build_payload.py"

_AO_MA_CHAIN_PR_FIELDS = (
    "schemas_pr",
    "orchestrator_pr",
    "runner_pr",
    "integrator_pr",
    "reviewer_pr",
    "verifier_pr",
    "e2e_smoke_pr",
)


def _load_receipt() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_RECEIPT_PATH.read_text(encoding="utf-8"))
    return data


def _load_schema() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------------
# 1-2: Schema + receipt validation
# ---------------------------------------------------------------------------


def test_ao_ma_9_receipt_schema_valid_draft_2020_12() -> None:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_ao_ma_9_receipt_validates_against_schema() -> None:
    schema = _load_schema()
    receipt = _load_receipt()
    Draft202012Validator(schema).validate(receipt)


# ---------------------------------------------------------------------------
# 3-5: Wire mode + release authority + guard flag pins (Codex iter-1 must_close)
# ---------------------------------------------------------------------------


def test_ao_ma_9_wire_mode_is_evidence_manifest_only() -> None:
    """Codex iter-1 must_close #2: const-pinned 'evidence_manifest_only'.

    Future readers MUST NOT mis-interpret AO-MA-9 as a release-gate payload
    extension or runtime hook. Those would be a separate AO-MA-10 / GPP
    supersession slice.
    """

    receipt = _load_receipt()
    assert receipt["wire_mode"] == "evidence_manifest_only"


def test_ao_ma_9_release_authority_claim_is_false() -> None:
    """AO-MA artifacts are evidence layer, NOT release authority.

    The authoritative merge gate is ao-release-gate via GitHub branch ruleset
    (GPP-2D-5 cutover). AO-MA-9 cannot claim release authority.
    """

    receipt = _load_receipt()
    assert receipt["release_authority_claim"] is False


def test_ao_ma_9_guard_flags_all_closed() -> None:
    receipt = _load_receipt()
    # Top-level pins
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False
    # guard_flags object
    gf = receipt["guard_flags"]
    assert gf["support_widening"] is False
    assert gf["production_platform_claim"] is False
    assert gf["live_adapter_execution"] is False
    # gpp_status snapshot
    snap = receipt["gpp_status_invariants_at_closure"]
    assert snap["support_widening_allowed"] is False
    assert snap["production_platform_claim_allowed"] is False
    assert snap["live_adapter_execution_allowed"] is False


# ---------------------------------------------------------------------------
# 6-8: Chain refs + path existence
# ---------------------------------------------------------------------------


def test_ao_ma_9_ao_ma_chain_refs_record_all_seven_pr_numbers() -> None:
    """Receipt records the AO-MA chain's 7 PR references (informational).

    Codex iter-2 nice-to-have #1: PR-number string form is sufficient.
    Runtime-grade commit SHA pin is too heavy for this evidence-only receipt.
    """

    receipt = _load_receipt()
    chain = receipt["ao_ma_chain_refs"]
    assert set(chain.keys()) == set(_AO_MA_CHAIN_PR_FIELDS)
    pr_pattern = re.compile(r"^#[0-9]+$")
    for field in _AO_MA_CHAIN_PR_FIELDS:
        value = chain[field]
        assert pr_pattern.match(value), f"{field}={value!r} does not match #<num>"


def test_ao_ma_9_gpp_2d_artifact_refs_point_to_existing_paths() -> None:
    """GPP-2D closeout artifacts exist on disk (drift defense)."""

    receipt = _load_receipt()
    refs = receipt["gpp_2d_artifact_refs"]
    for label, rel_path in refs.items():
        full_path = _REPO_ROOT / rel_path
        assert full_path.is_file(), f"gpp_2d_artifact_refs.{label} missing: {full_path}"


def test_ao_ma_9_ao_ma_8_chain_proof_refs_point_to_existing_paths() -> None:
    """AO-MA-8 e2e smoke artifacts exist on disk — proof the chain works."""

    receipt = _load_receipt()
    refs = receipt["ao_ma_8_chain_proof_refs"]
    for label, rel_path in refs.items():
        full_path = _REPO_ROOT / rel_path
        assert full_path.is_file(), f"ao_ma_8_chain_proof_refs.{label} missing: {full_path}"


# ---------------------------------------------------------------------------
# 9: Receipt-vs-runtime drift defense (live gpp_status compare)
# ---------------------------------------------------------------------------


def test_ao_ma_9_gpp_status_invariants_match_runtime_authority() -> None:
    """Codex iter-2 question #3 absorb: snapshot + live compare.

    If live state changes (supersession), this test fails — receipt must
    be updated. NO auto-absorb; receipt is a decision record, not a mirror.
    """

    receipt = _load_receipt()
    snap = receipt["gpp_status_invariants_at_closure"]
    gpp = json.loads(_GPP_STATUS_PATH.read_text(encoding="utf-8"))

    current_wp = gpp.get("current_wp") or {}
    assert snap["current_wp_id"] == current_wp.get("id")
    assert snap["current_wp_status"] == current_wp.get("status")
    assert snap["support_widening_allowed"] == gpp.get("support_widening_allowed", False)
    assert snap["production_platform_claim_allowed"] == gpp.get("production_platform_claim_allowed", False)
    assert snap["live_adapter_execution_allowed"] == gpp.get("live_adapter_execution_allowed", False)
    # Codex post-impl iter-1 must_fix: previously only asserted "N/M" regex pattern,
    # which would pass through real progression (e.g. 8/8 after milestone added).
    # Now compute live progress_estimates.milestones value and assert exact equality
    # against the receipt snapshot — drift becomes a hard fail.
    progress = gpp.get("progress_estimates") or {}
    milestones = progress.get("milestones") or {}
    live_total = f"{milestones.get('done_count')}/{milestones.get('total_count')}"
    assert snap["milestones_done_total"] == live_total, (
        f"milestones_done_total drift: receipt snapshot={snap['milestones_done_total']!r}, "
        f"live progress_estimates.milestones={live_total!r}"
    )
    # Sanity: snapshot is still in "N/M" form (catch malformed manual edits).
    assert re.fullmatch(r"\d+/\d+", snap["milestones_done_total"])


# ---------------------------------------------------------------------------
# 10: No Option B payload field extension (Codex iter-2 nice-to-have #2)
# ---------------------------------------------------------------------------


def test_ao_ma_9_no_payload_field_extension_in_release_gate() -> None:
    """Codex iter-2 nice-to-have #2: exact field-name assertion (NOT raw text grep).

    AO-MA-9 is evidence-only (wire_mode='evidence_manifest_only'). Option B
    (runtime hook into the gate's payload constants) is explicitly NOT in
    this PR's scope. This test verifies the gate's payload module does not
    contain Option-B field-name *keys* — using exact identifier patterns,
    not naive 'AO-MA' string grep (the module already has 'AO-MA' in
    comments referring to the orchestration layer).
    """

    source = _RELEASE_GATE_BUILD_PAYLOAD_PATH.read_text(encoding="utf-8")
    # Parse the module's AST and collect every string-quoted key + identifier.
    tree = ast.parse(source)
    forbidden_field_names = (
        "ao_ma_integration_report_ref",
        "ao_ma_integration_overall_status",
        "ao_ma_chain_artifact_refs",
        "ao_ma_chain_refs",
        "ao_ma_required_status",
    )
    for node in ast.walk(tree):
        # String constants used as dict keys / values
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for forbidden in forbidden_field_names:
                assert node.value != forbidden, (
                    f"release-gate build_payload module contains Option-B field-name "
                    f"key {forbidden!r}; AO-MA-9 wire_mode='evidence_manifest_only' "
                    f"forbids payload-field extension. Move runtime hook to a separate "
                    f"AO-MA-10 / GPP supersession slice."
                )
        # Identifier references / function names / variable names
        if isinstance(node, ast.Name):
            for forbidden in forbidden_field_names:
                assert node.id != forbidden, (
                    f"release-gate build_payload module references identifier "
                    f"{forbidden!r}; AO-MA-9 wire_mode='evidence_manifest_only' "
                    f"forbids payload-field extension."
                )


# ---------------------------------------------------------------------------
# 11: PR scope allowlist (multi-strategy resolver per AO-MA-8 pattern)
# ---------------------------------------------------------------------------


def _git_capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(_REPO_ROOT), *args], capture_output=True, text=True, timeout=20)


def _resolve_pr_diff_base() -> tuple[str | None, str]:
    """Multi-strategy diff base resolver (mirrors AO-MA-8 / RI-7.2 pattern).

    Handles ``actions/checkout@v6`` default ``fetch-depth: 1`` where
    ``origin/main`` is not in the local db. Tries (in order):

    1. ``GITHUB_EVENT_PATH`` ``pull_request.base.sha`` — most authoritative
       in PR event; materialize via shallow fetch if not in local db.
    2. ``GITHUB_BASE_REF`` + shallow fetch (fallback).
    3. Local ``origin/main`` (local human runs).
    4. Local ``main`` (clones without remotes).
    """

    sha_pattern = re.compile(r"[0-9a-f]{40}")
    ref_pattern = re.compile(r"[A-Za-z0-9._/-]+")

    # Strategy 1: GitHub Actions PR event payload
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            base = (event.get("pull_request") or {}).get("base") or {}
            sha = base.get("sha")
            base_ref_in_event = base.get("ref")
            if isinstance(sha, str) and sha_pattern.fullmatch(sha):
                has = _git_capture(["cat-file", "-e", sha])
                if has.returncode != 0:
                    _git_capture(["fetch", "origin", sha, "--depth=1"])
                    if base_ref_in_event and ref_pattern.fullmatch(base_ref_in_event):
                        _git_capture(["fetch", "origin", base_ref_in_event, "--depth=1"])
                    has = _git_capture(["cat-file", "-e", sha])
                if has.returncode == 0:
                    return sha, "github_event_payload"
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    # Strategy 2: GITHUB_BASE_REF + shallow fetch
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref and ref_pattern.fullmatch(base_ref):
        fetch_proc = _git_capture(["fetch", "origin", base_ref, "--depth=1"])
        if fetch_proc.returncode == 0:
            mb = _git_capture(["merge-base", "HEAD", "FETCH_HEAD"])
            if mb.returncode == 0:
                sha = mb.stdout.strip()
                if sha_pattern.fullmatch(sha):
                    return sha, f"fetch:{base_ref}"

    # Strategy 3: local origin/main
    mb = _git_capture(["merge-base", "HEAD", "origin/main"])
    if mb.returncode == 0:
        sha = mb.stdout.strip()
        if sha_pattern.fullmatch(sha):
            return sha, "origin/main"

    # Strategy 4: local main
    mb = _git_capture(["merge-base", "HEAD", "main"])
    if mb.returncode == 0:
        sha = mb.stdout.strip()
        if sha_pattern.fullmatch(sha):
            return sha, "local_main"

    return None, "none"


def test_ao_ma_9_pr_scope_only_touches_allowlisted_files() -> None:
    """AO-MA-9 PR diff is restricted to 5 files (Codex iter-1 nice-to-have #2):

    1. .claude/plans/AO-MA-9-GPP-INTEGRATION.md
    2. .claude/plans/AO-MA-9-GPP-INTEGRATION-EVIDENCE.v1.json
    3. ao_kernel/defaults/schemas/ao-ma-9-gpp-integration-evidence.schema.v1.json
    4. tests/test_ao_ma_9_gpp_integration_invariant.py
    5. local-ai-review-evidence.v1.json

    Outside CI/PR context, skip (sandbox tarball; local exploration).
    Inside CI PR, fail-closed.
    """

    in_ci = os.environ.get("CI") == "true"
    in_pr_context = os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
    base, source = _resolve_pr_diff_base()
    if base is None:
        msg = (
            "no PR diff base could be resolved (tried github_event_payload, "
            "GITHUB_BASE_REF fetch, origin/main, local main)"
        )
        if in_ci and in_pr_context:
            pytest.fail(f"PR-scope invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    try:
        diff_proc = _git_capture(["diff", "--name-only", f"{base}..HEAD"])
    except subprocess.SubprocessError as exc:
        msg = f"git diff against base ({source}={base!r}) failed: {exc}"
        if in_ci and in_pr_context:
            pytest.fail(f"PR-scope invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)
    if diff_proc.returncode != 0:
        msg = f"git diff against base ({source}={base!r}) failed: {diff_proc.stderr.strip() or 'unknown error'}"
        if in_ci and in_pr_context:
            pytest.fail(f"PR-scope invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    changed = {line.strip() for line in diff_proc.stdout.splitlines() if line.strip()}
    # Self-gate (same systemic-fix pattern as AO-MA-8 PR #664). PR-scope
    # tests should only enforce within their own PR type. Trigger marker
    # is the AO-MA-9 plan doc: if THIS PR's diff does not touch
    # ``.claude/plans/AO-MA-9-GPP-INTEGRATION.md``, the PR is NOT an
    # AO-MA-9 PR and the AO-MA-9 allowlist is not the right scope to
    # enforce. Without this, every future AO-MA-N PR would fail this
    # test — the recurrence-defense rule the AO-MA-8 PR-scope fix
    # already codified.
    ao_ma_9_trigger = ".claude/plans/AO-MA-9-GPP-INTEGRATION.md"
    if ao_ma_9_trigger not in changed:
        pytest.skip(
            f"PR diff does not touch {ao_ma_9_trigger}; not an AO-MA-9 PR — "
            f"AO-MA-9 allowlist scope does not apply (self-gate)."
        )
    allowlist = {
        ".claude/plans/AO-MA-9-GPP-INTEGRATION.md",
        ".claude/plans/AO-MA-9-GPP-INTEGRATION-EVIDENCE.v1.json",
        "ao_kernel/defaults/schemas/ao-ma-9-gpp-integration-evidence.schema.v1.json",
        "tests/test_ao_ma_9_gpp_integration_invariant.py",
        "local-ai-review-evidence.v1.json",
    }
    extra = changed - allowlist
    assert not extra, f"AO-MA-9 PR touches files outside allowlist: {sorted(extra)}"
