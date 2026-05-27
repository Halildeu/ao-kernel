"""Doc invariant test for RI-7.1 operator authorization record evidence.

B-path slice 2 of 8 (after BC vocabulary fix slice-1, before RI-7.5 runtime
semantics). Pins the operator authorization schema, evidence, manifest
transition, forbidden-change audit, and cross-AI review reference.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.1-OPERATOR-AUTHORIZATION.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.1-OPERATOR-AUTHORIZATION.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-operator-authorization-evidence.schema.v1.json"
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri71_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri71_evidence_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri71_evidence_records_authorization_decision() -> None:
    """The evidence artifact MUST record the no-guard-flag-flip decision,
    the named operator Halildeu, both authorization scopes, and all
    three guard flags as false.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_operator_authorization_evidence"
    assert evidence["decision"] == "ri7_operator_authorization_recorded_no_guard_flag_flip"

    operator = evidence["operator"]
    assert operator["github_login"] == "Halildeu"
    assert operator["no_secret_assertion"] is True
    # Authorization timestamp must parse as ISO 8601.
    timestamp = operator["authorization_timestamp"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", timestamp), (
        f"authorization_timestamp not ISO 8601 UTC: {timestamp!r}"
    )

    assert set(evidence["authorization_scope"]) == {
        "ri_supersession",
        "general_purpose_platform_claim_target",
    }
    assert evidence["ri_supersession_authorized"] is True
    assert evidence["general_purpose_platform_claim_target_authorized"] is True
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False


def test_ri71_evidence_records_manifest_transition() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    transition = evidence["manifest_transition"]
    assert transition["before"]["explicit_operator_authorization"] is False
    assert transition["before"]["general_purpose_platform_claim_authorization"] is False
    assert transition["after"]["explicit_operator_authorization"] is True
    assert transition["after"]["general_purpose_platform_claim_authorization"] is True


def test_ri71_manifest_flips_both_operator_keys_true() -> None:
    """The committed manifest reflects the operator authorization. Both
    `explicit_operator_authorization` and
    `general_purpose_platform_claim_authorization` are true after this
    slice; `operator_verified_runtime_semantics` remains false (RI-7.5
    owner).
    """
    manifest = json.loads(_read(_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    assert manifest["explicit_operator_authorization"] is True
    assert manifest["general_purpose_platform_claim_authorization"] is True
    assert manifest["operator_verified_runtime_semantics"] is False


def test_ri71_evidence_records_forbidden_change_audit() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    surfaces = set(audit["forbidden_surfaces"])
    for required_surface in (
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
        assert required_surface in surfaces, required_surface


def test_ri71_cross_ai_review_provider_split_is_recorded() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    ref = evidence["cross_ai_review_ref"]
    assert ref["implementer_provider"] == "anthropic"
    assert ref["reviewer_provider"] == "openai"
    assert ref["implementer_provider"] != ref["reviewer_provider"]
    # Codex iter-1 absorb: final_verdict can be REVISE during the iter
    # cycle; the final commit MUST land with AGREE. The cross-artifact
    # verdict equality test below enforces no drift between this
    # artifact and `local-ai-review-evidence.v1.json`.
    assert ref["final_verdict"] in {"REVISE", "AGREE"}
    assert ref["thread_id"], "cross-AI review thread id MUST be recorded"


def test_ri71_cross_ai_verdicts_match_review_evidence() -> None:
    """Codex iter-1 absorb: the operator authorization evidence's
    `cross_ai_review_ref.final_verdict` and the
    `local-ai-review-evidence.v1.json::reviewer.verdict` MUST agree.
    This prevents the 'AGREE pre-fill in one artifact, REVISE in the
    other' inconsistency the iter-1 review identified as a BLOCKER.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    review_path = _REPO_ROOT / "local-ai-review-evidence.v1.json"
    review = json.loads(_read(review_path))

    auth_verdict = evidence["cross_ai_review_ref"]["final_verdict"]
    review_verdict = review["reviewer"]["verdict"]
    assert auth_verdict == review_verdict, (
        f"cross-AI verdict drift: RI-7.1 evidence carries {auth_verdict!r} "
        f"but local-ai-review-evidence.v1.json carries {review_verdict!r}"
    )


def test_ri71_parent_plan_row_uses_same_decision_string() -> None:
    """Codex iter-1 absorb: the RI-7 parent plan tracking table row for
    RI-7.1 MUST cite the same exit decision string this artifact uses.
    Drift here was the 'no_flag_flip vs no_guard_flag_flip' bug.
    """
    parent_path = _REPO_ROOT / ".claude" / "plans" / "RI-7-REPO-INTELLIGENCE-TIER-PROMOTION-READINESS.md"
    parent_text = _read(parent_path)
    evidence = json.loads(_read(_EVIDENCE_PATH))
    decision = evidence["decision"]
    assert decision == "ri7_operator_authorization_recorded_no_guard_flag_flip"
    assert decision in parent_text, (
        f"parent RI-7 plan does not cite the RI-7.1 decision string {decision!r}; "
        "drift between parent tracking row and child artifact"
    )


def test_ri71_no_secret_assertion_is_schema_required() -> None:
    """Codex iter-1 absorb: schema MUST require `operator.no_secret_assertion`
    (previous version had it `const true` but optional, so an evidence
    artifact could omit the assertion and still pass validation).
    Negative test: removing the field must cause schema validation to
    fail.
    """
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    # Positive: current artifact has the field and validates.
    assert "no_secret_assertion" in evidence["operator"]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]

    # Negative: removing the field must raise a validation error.
    bad = json.loads(json.dumps(evidence))  # deep copy
    del bad["operator"]["no_secret_assertion"]
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "schema accepted operator artifact without no_secret_assertion"


def test_ri71_invalid_timestamp_is_rejected_by_schema_pattern() -> None:
    """Codex iter-1 absorb: schema's `authorization_timestamp` carries a
    strict ISO 8601 UTC pattern in addition to `format: date-time`,
    because jsonschema's default validator does NOT enforce
    `format`-only assertions. Negative test: a non-conformant timestamp
    must be rejected.
    """
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))

    bad = json.loads(json.dumps(evidence))
    bad["operator"]["authorization_timestamp"] = "not-a-date"
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
    assert errors, "schema accepted operator.authorization_timestamp='not-a-date'"

    bad2 = json.loads(json.dumps(evidence))
    bad2["operator"]["authorization_timestamp"] = "2026-05-27T16:00:00+00:00"  # non-UTC suffix
    errors2 = list(jsonschema.Draft202012Validator(schema).iter_errors(bad2))
    assert errors2, "schema accepted non-Z-suffixed authorization_timestamp"


def test_ri71_plan_doc_records_decision_and_authority_boundary() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    assert "ri7_operator_authorization_recorded_no_guard_flag_flip" in flat
    assert "support_widening" in flat
    assert "production_platform_claim" in flat
    assert "live_adapter_execution" in flat
    assert "Halildeu" in flat
    assert "Operator-Authorized-By" in flat


# ----------------------------------------------------------------------
# Forbidden-diff invariant (CI fail-closed in PR context).
# Same pattern as PR #656 (B-path slice-1 inherits this).
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
    """Multi-strategy diff base detection (see PR #656 invariant test for
    full rationale)."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            pr = event.get("pull_request") or {}
            base = pr.get("base") or {}
            sha = base.get("sha")
            base_ref_in_event = base.get("ref")
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha):
                has = _git(["cat-file", "-e", sha])
                if has.returncode != 0:
                    _git(["fetch", "origin", sha, "--depth=1"])
                    if base_ref_in_event and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref_in_event):
                        _git(["fetch", "origin", base_ref_in_event, "--depth=1"])
                    has = _git(["cat-file", "-e", sha])
                if has.returncode == 0:
                    return sha, "github_event_payload"
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
        fetch_proc = _git(["fetch", "origin", base_ref, "--depth=1"])
        if fetch_proc.returncode == 0:
            mb = _git(["merge-base", "HEAD", "FETCH_HEAD"])
            if mb.returncode == 0:
                sha = mb.stdout.strip()
                if re.fullmatch(r"[0-9a-f]{40}", sha):
                    return sha, f"fetch:{base_ref}"

    mb = _git(["merge-base", "HEAD", "origin/main"])
    if mb.returncode == 0:
        sha = mb.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha, "origin/main"

    mb = _git(["merge-base", "HEAD", "main"])
    if mb.returncode == 0:
        sha = mb.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha, "local_main"

    return None, "none"


def test_ri71_forbidden_surfaces_actually_unchanged_in_diff() -> None:
    """CI fail-closed in PR context: forbidden surfaces in the artifact
    MUST not actually appear in `git diff --name-only base..HEAD`.
    """
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
        msg = f"git diff against base ({source}={base!r}) failed: {diff_proc.stderr.strip() or 'unknown'}"
        if _in_ci() and _in_pr_context():
            pytest.fail(f"forbidden-diff invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    changed_files = {line.strip() for line in diff_proc.stdout.splitlines() if line.strip()}
    offenders: list[str] = []
    for surface in surfaces:
        if surface.endswith("/"):
            offenders.extend(f for f in changed_files if f.startswith(surface))
        else:
            offenders.extend(f for f in changed_files if f == surface)

    assert not offenders, (
        f"forbidden surfaces touched (base source={source}): {sorted(offenders)}; "
        f"forbidden_change_audit.all_unchanged=true is therefore false"
    )
