"""Doc invariant test for RI-7.5 operator-verified runtime semantics evidence.

B-path slice 3 of 8 (after RI-7.1 slice-2 MERGED). Pins the schema,
8-invariant aggregate evidence, manifest transition, forbidden audit,
and cross-AI verdict equality.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.5-OPERATOR-VERIFIED-RUNTIME-SEMANTICS.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.5-OPERATOR-VERIFIED-RUNTIME-SEMANTICS.v1.json"
_SCHEMA_PATH = (
    _REPO_ROOT
    / "ao_kernel"
    / "defaults"
    / "schemas"
    / "ri7-operator-verified-runtime-semantics-evidence.schema.v1.json"
)
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ri7_operator_verified_runtime_semantics.py"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri75_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri75_evidence_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri75_eight_runtime_invariants_pinned_with_sha256() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_operator_verified_runtime_semantics_evidence"
    assert evidence["decision"] == "ri7_operator_verified_runtime_semantics_recorded"

    invariants = evidence["runtime_invariants"]
    assert len(invariants) == 8
    ids = {inv["id"] for inv in invariants}
    assert ids == {
        "no_hidden_prompt_injection",
        "no_context_compiler_auto_feed",
        "no_root_authority_file_write",
        "no_mcp_repo_intelligence_tool_exposed",
        "write_vectors_confirmation_token_required",
        "missing_backend_or_api_key_fail_closed",
        "repo_scan_query_read_only_boundary",
        "negative_prompt_injection_fixture",
    }
    for inv in invariants:
        assert inv["status"] == "verified"
        assert inv["evidence_class"] == "operator_script_verified"
        assert re.fullmatch(r"[0-9a-f]{64}", inv["sha256"]), inv["id"]
        assert inv["script_ref"].startswith("scripts/"), inv["id"]
        assert inv["result_summary"], inv["id"]


def test_ri75_operator_signature_fields() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    operator = evidence["operator"]
    assert operator["github_login"] == "Halildeu"
    assert operator["no_secret_assertion"] is True
    assert operator["observation_notes"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", operator["verification_timestamp"])


def test_ri75_manifest_transition_pinned() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    transition = evidence["manifest_transition"]
    assert transition["before"]["operator_verified_runtime_semantics"] is False
    assert transition["after"]["operator_verified_runtime_semantics"] is True


def test_ri75_manifest_flips_operator_verified_runtime_semantics_true() -> None:
    manifest = json.loads(_read(_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    assert manifest["operator_verified_runtime_semantics"] is True


def test_ri75_guard_flags_const_false() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_ri75_cross_ai_verdicts_match_review_evidence() -> None:
    """Cross-artifact verdict equality enforced (Codex RI-7.1 iter-1
    absorb pattern): RI-7.5 evidence `cross_ai_review_ref.final_verdict`
    MUST equal `local-ai-review-evidence.v1.json::reviewer.verdict`.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    review_path = _REPO_ROOT / "local-ai-review-evidence.v1.json"
    review = json.loads(_read(review_path))
    auth_verdict = evidence["cross_ai_review_ref"]["final_verdict"]
    review_verdict = review["reviewer"]["verdict"]
    assert auth_verdict == review_verdict, (
        f"verdict drift: RI-7.5 evidence={auth_verdict!r} vs local-ai-review={review_verdict!r}"
    )


def test_ri75_script_exists_and_emits_eight_results() -> None:
    """The script path referenced by every invariant must exist and
    accept `--emit json`. Smoke run is not required at test time; we
    just assert the file is present and the script_ref values resolve
    to it.
    """
    assert _SCRIPT_PATH.exists()
    evidence = json.loads(_read(_EVIDENCE_PATH))
    for inv in evidence["runtime_invariants"]:
        head, _sep, _func = inv["script_ref"].partition("::")
        assert (_REPO_ROOT / head).resolve() == _SCRIPT_PATH.resolve(), inv["script_ref"]


def test_ri75_schema_pins_id_to_script_ref_mapping() -> None:
    """Codex iter-2 absorb (BLOCKER #6): the schema MUST pin each
    invariant ID to its expected `_verify_*` function via the
    `allOf/contains` clause carrying `script_ref` const. This makes
    the id <-> script_ref mapping schema-enforced — a wrong-function
    binding cannot pass validation.
    """
    schema = json.loads(_read(_SCHEMA_PATH))
    all_of = schema["properties"]["runtime_invariants"]["allOf"]
    expected = {
        "no_hidden_prompt_injection": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_no_hidden_prompt_injection",
        "no_context_compiler_auto_feed": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_no_context_compiler_auto_feed",
        "no_root_authority_file_write": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_no_root_authority_file_write",
        "no_mcp_repo_intelligence_tool_exposed": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_no_mcp_repo_intelligence_tool_exposed",
        "write_vectors_confirmation_token_required": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_write_vectors_confirmation_token_required",
        "missing_backend_or_api_key_fail_closed": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_missing_backend_or_api_key_fail_closed",
        "repo_scan_query_read_only_boundary": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_repo_scan_query_read_only_boundary",
        "negative_prompt_injection_fixture": "scripts/ri7_operator_verified_runtime_semantics.py::_verify_negative_prompt_injection_fixture",
    }
    pinned: dict[str, str] = {}
    for clause in all_of:
        contains = clause.get("contains", {})
        props = contains.get("properties", {})
        id_const = props.get("id", {}).get("const")
        script_ref_const = props.get("script_ref", {}).get("const")
        assert id_const, f"allOf clause missing id const: {clause}"
        assert script_ref_const, f"allOf clause for {id_const} missing script_ref const"
        pinned[id_const] = script_ref_const
    assert pinned == expected, f"schema id->script_ref mapping drift: {pinned} != {expected}"


def test_ri75_script_rerun_matches_committed_evidence() -> None:
    """Codex iter-2 absorb (iter request #2): re-run the script with
    `--emit json` and assert the output matches the committed
    `runtime_invariants` array exactly (id, status, evidence_class,
    script_ref, result_summary, sha256 per entry). This binds the
    committed sha256 digests to a re-runnable behavioral check; sha256
    drift = drift between script and committed evidence and fails CI.
    """
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--emit", "json"],
        cwd=str(_REPO_ROOT),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, f"script exit {proc.returncode}; stderr={proc.stderr.strip()[:500]!r}"
    rerun_results = json.loads(proc.stdout)
    assert isinstance(rerun_results, list), type(rerun_results).__name__
    assert len(rerun_results) == 8, len(rerun_results)

    evidence = json.loads(_read(_EVIDENCE_PATH))
    committed = evidence["runtime_invariants"]
    rerun_by_id = {entry["id"]: entry for entry in rerun_results}
    committed_by_id = {entry["id"]: entry for entry in committed}
    assert set(rerun_by_id.keys()) == set(committed_by_id.keys()), (
        f"id set drift: rerun={set(rerun_by_id.keys())} committed={set(committed_by_id.keys())}"
    )
    for inv_id, rerun_entry in rerun_by_id.items():
        committed_entry = committed_by_id[inv_id]
        for field in ("status", "evidence_class", "script_ref", "result_summary", "sha256"):
            assert rerun_entry[field] == committed_entry[field], (
                f"drift on {inv_id}.{field}: rerun={rerun_entry[field]!r} committed={committed_entry[field]!r}"
            )


def test_ri75_forbidden_change_audit() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    surfaces = set(audit["forbidden_surfaces"])
    for required in (
        ".claude/plans/gpp_status.v1.json",
        "scripts/gp5_platform_claim_decision.py",
        ".github/workflows/",
        "ao_kernel/mcp_server.py",
        "ao_kernel/__init__.py",
        "ao_kernel/defaults/policies/",
        "docs/PUBLIC-BETA.md",
        "docs/SUPPORT-BOUNDARY.md",
        "docs/KNOWN-BUGS.md",
    ):
        assert required in surfaces, required


def test_ri75_plan_doc_records_eight_invariants_and_authority() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    for invariant_id in (
        "no_hidden_prompt_injection",
        "no_context_compiler_auto_feed",
        "no_root_authority_file_write",
        "no_mcp_repo_intelligence_tool_exposed",
        "write_vectors_confirmation_token_required",
        "missing_backend_or_api_key_fail_closed",
        "repo_scan_query_read_only_boundary",
        "negative_prompt_injection_fixture",
    ):
        assert invariant_id in flat, invariant_id
    assert "ri7_operator_verified_runtime_semantics_recorded" in flat
    assert "Halildeu" in flat
    assert "Operator-Verified-By" in flat


# ----------------------------------------------------------------------
# Forbidden-diff invariant (CI fail-closed in PR context).
# Same pattern as RI-7.1 / RI-7.2 invariant tests.
# ----------------------------------------------------------------------


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(_REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _in_ci() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def _in_pr_context() -> bool:
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        return True
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            if isinstance(event.get("pull_request"), dict):
                return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False
    return False


def _resolve_diff_base() -> tuple[str | None, str]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            pr = event.get("pull_request") or {}
            base = pr.get("base") or {}
            sha = base.get("sha")
            base_ref = base.get("ref")
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha):
                has = _git(["cat-file", "-e", sha])
                if has.returncode != 0:
                    _git(["fetch", "origin", sha, "--depth=1"])
                    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
                        _git(["fetch", "origin", base_ref, "--depth=1"])
                    has = _git(["cat-file", "-e", sha])
                if has.returncode == 0:
                    return sha, "github_event_payload"
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
        fetch = _git(["fetch", "origin", base_ref, "--depth=1"])
        if fetch.returncode == 0:
            mb = _git(["merge-base", "HEAD", "FETCH_HEAD"])
            if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
                return mb.stdout.strip(), f"fetch:{base_ref}"
    mb = _git(["merge-base", "HEAD", "origin/main"])
    if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
        return mb.stdout.strip(), "origin/main"
    mb = _git(["merge-base", "HEAD", "main"])
    if mb.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", mb.stdout.strip()):
        return mb.stdout.strip(), "local_main"
    return None, "none"


def _is_ri75_introducer_pr() -> bool:
    """True if THIS PR adds the RI-7.5 evidence artifact (newly ADDED in
    diff vs base). State-at-landing pin: forbidden-diff dynamic check
    only runs on the RI-7.5 introducer PR; successor B-path slices
    (RI-7.8b-*) legitimately touch surfaces this list rejects, and the
    const digest pins continue to enforce RI-7.5 state-at-landing on
    every successor PR via the structural invariants above.
    """
    base, _src = _resolve_diff_base()
    if base is None:
        return False
    diff_proc = _git(["diff", "--diff-filter=A", "--name-only", f"{base}..HEAD"])
    if diff_proc.returncode != 0:
        return False
    added = {line.strip() for line in diff_proc.stdout.splitlines() if line.strip()}
    return str(_EVIDENCE_PATH.relative_to(_REPO_ROOT)) in added


def test_ri75_forbidden_surfaces_actually_unchanged_in_diff() -> None:
    """State-at-landing pin (RI-7.8b-bc1-6b inline systemic fix): dynamic
    forbidden-diff check runs only on the RI-7.5 introducer PR. Successor
    B-path slices (RI-7.8b-bc1-6b adds workflows + gpp_status entries)
    legitimately touch surfaces this list rejects; const digest pins
    continue to enforce RI-7.5 state-at-landing on every successor PR.
    """
    if not _is_ri75_introducer_pr():
        pytest.skip("RI-7.5 state-at-landing pin: forbidden-diff dynamic check only runs on the introducer PR")
    evidence = json.loads(_read(_EVIDENCE_PATH))
    surfaces = evidence["forbidden_change_audit"]["forbidden_surfaces"]

    base, source = _resolve_diff_base()
    if base is None:
        msg = "no PR diff base could be resolved"
        if _in_ci() and _in_pr_context():
            pytest.fail(f"forbidden-diff invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    diff_proc = _git(["diff", "--name-only", f"{base}..HEAD"])
    if diff_proc.returncode != 0:
        msg = f"git diff failed: {diff_proc.stderr.strip()}"
        if _in_ci() and _in_pr_context():
            pytest.fail(f"forbidden-diff invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    changed = {line.strip() for line in diff_proc.stdout.splitlines() if line.strip()}
    offenders: list[str] = []
    for surface in surfaces:
        if surface.endswith("/"):
            offenders.extend(f for f in changed if f.startswith(surface))
        else:
            offenders.extend(f for f in changed if f == surface)
    assert not offenders, f"forbidden surfaces touched (base source={source}): {sorted(offenders)}"
