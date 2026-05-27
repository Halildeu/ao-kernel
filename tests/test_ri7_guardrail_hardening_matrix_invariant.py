"""Doc invariant test for RI-7.2 guardrail hardening matrix evidence
(fast-follow PR that closes the schema-backed JSON evidence pattern gap left
by the original RI-7.2 plan-doc + tests merge).

Pins the canonical RI-7.2 schema, evidence artifact, manifest flip, and the
forbidden-change audit so future drift is caught.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path

import jsonschema
import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_PLAN_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.2-REPO-INTELLIGENCE-GUARDRAIL-HARDENING-MATRIX.md"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7.2-REPO-INTELLIGENCE-GUARDRAIL-HARDENING-MATRIX.v1.json"
_SCHEMA_PATH = (
    _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ri7-guardrail-hardening-matrix-evidence.schema.v1.json"
)
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "RI-7-EVIDENCE-MANIFEST.v1.json"


def _read(path: Path) -> str:
    assert path.exists(), f"missing artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_ri72_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    jsonschema.Draft202012Validator.check_schema(schema)


def test_ri72_evidence_validates_against_schema() -> None:
    schema = json.loads(_read(_SCHEMA_PATH))
    evidence = json.loads(_read(_EVIDENCE_PATH))
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(evidence))
    assert errors == [], [e.message for e in errors]


def test_ri72_evidence_records_all_six_guardrail_rows() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    assert evidence["artifact_kind"] == "ri7_guardrail_hardening_matrix_evidence"
    assert evidence["decision"] == "ri7_guardrail_hardening_matrix_ready"
    assert evidence["support_widening"] is False
    assert evidence["production_platform_claim"] is False
    assert evidence["live_adapter_execution"] is False

    rows_by_id = {r["id"]: r for r in evidence["rows"]}
    assert set(rows_by_id) == {
        "ast_chunk_edge_cases",
        "namespace_isolation",
        "stale_vector_cleanup",
        "no_implicit_root_authority_write",
        "no_auto_feed",
        "no_mcp_exposure",
    }
    for row in evidence["rows"]:
        assert row["status"] == "hardened", row["id"]


def test_ri72_evidence_refs_cite_real_files_and_functions() -> None:
    """Codex iter-1+2 absorb: every implementation_ref MUST point at a
    real repo file under ``ao_kernel/`` or ``scripts/``, and every
    regression_ref of the form ``tests/<file>.py::<func>`` MUST point at
    a real test function (``def`` or ``async def``) defined in that
    file. Path-traversal segments (``..``) are rejected via fully
    resolved-path containment check, not lexical containment — schema
    pattern already forbids ``..`` segments in directory components, and
    this resolved-path check defends against any ref that slips past.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    repo_root_resolved = _REPO_ROOT.resolve()
    allowed_impl_roots = [
        (repo_root_resolved / "ao_kernel").resolve(),
        (repo_root_resolved / "scripts").resolve(),
    ]
    allowed_tests_root = (repo_root_resolved / "tests").resolve()

    for row in evidence["rows"]:
        # Implementation refs MUST exist and resolve inside ao_kernel/ or scripts/.
        for impl_ref in row["implementation_refs"]:
            impl_path = (_REPO_ROOT / impl_ref).resolve()
            assert impl_path.exists(), f"implementation_ref missing: {impl_path}"
            assert impl_path.is_file(), f"implementation_ref not a file: {impl_path}"
            assert any(impl_path.is_relative_to(root) for root in allowed_impl_roots), (
                f"implementation_ref resolved outside ao_kernel/ or scripts/: {impl_path}"
            )

        # Regression refs MUST exist (file resolved under tests/) AND, if
        # of the tests/<file>.py::<func> form, the function must be defined.
        for reg_ref in row["regression_refs"]:
            head, _sep, func_name = reg_ref.partition("::")
            assert head.startswith("tests/"), f"regression_ref must start with tests/: {reg_ref}"
            test_file = (_REPO_ROOT / head).resolve()
            assert test_file.exists(), f"regression_ref points at missing test file: {test_file}"
            assert test_file.is_relative_to(allowed_tests_root), f"regression_ref resolved outside tests/: {test_file}"

            if func_name:
                module = ast.parse(test_file.read_text(encoding="utf-8"))
                defined = {
                    node.name for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                assert func_name in defined, (
                    f"regression_ref {reg_ref} points at missing function {func_name} in {test_file}"
                )


def test_ri72_evidence_records_forbidden_change_audit() -> None:
    evidence = json.loads(_read(_EVIDENCE_PATH))
    audit = evidence["forbidden_change_audit"]
    assert audit["all_unchanged"] is True
    surfaces = set(audit["forbidden_surfaces"])
    # Codex iter-1 absorb: forbidden-change audit MUST be machine-enforced
    # and record the specific surfaces a guardrail evidence slice may not
    # touch. These are the slice-level forbidden surfaces; RI-7.8 promote
    # is the only PR allowed to touch any of them.
    for required_surface in (
        ".claude/plans/gpp_status.v1.json",
        "scripts/gp5_platform_claim_decision.py",
        ".github/workflows/",
        "ao_kernel/mcp_server.py",
        "ao_kernel/__init__.py",
        "ao_kernel/cli.py",
        "ao_kernel/defaults/policies/",
        "docs/PUBLIC-BETA.md",
        "docs/SUPPORT-BOUNDARY.md",
        "docs/KNOWN-BUGS.md",
    ):
        assert required_surface in surfaces, required_surface


def test_ri72_manifest_records_guardrail_hardening_matrix_true() -> None:
    """The RI-7 evidence manifest committed with this fast-follow PR flips
    `guardrail_hardening_matrix` to true.

    Codex iter-2 absorb: this pin is NOT a permanent invariant of the
    RI-7 program. It only encodes the state of the program at the moment
    this fast-follow PR landed: three operator-bound slices (RI-7.1
    explicit operator authorization, RI-7.5 operator-verified runtime
    semantics, plus the GP-platform-claim authorization half of RI-7.1)
    had not yet been signed. When their evidence artifacts land, those
    slices' OWN invariant tests will own pinning the corresponding
    manifest keys as ``true`` — and this test is expected to be
    superseded or loosened in that landing PR. Treating "operator-bound
    keys forever false" as a permanent invariant is explicitly out of
    scope for this slice.
    """
    manifest = json.loads(_read(_MANIFEST_PATH))
    assert manifest["artifact_kind"] == "ri7_evidence_manifest"
    assert manifest["guardrail_hardening_matrix"] is True
    # State-at-landing pin only — see docstring. Operator-bound landings
    # will revise this.
    for key in (
        "explicit_operator_authorization",
        "general_purpose_platform_claim_authorization",
        "operator_verified_runtime_semantics",
    ):
        assert manifest[key] is False, key


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Codex iter-3 absorb: keep stderr separate from stdout so a Git
    warning (e.g. xcrun_db) cannot corrupt the captured SHA. Caller
    inspects ``returncode`` and uses ``stdout``/``stderr`` independently.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(_REPO_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _in_ci() -> bool:
    """Codex iter-3 absorb: in CI, missing git/origin-main must NOT
    silently skip — the forbidden-diff invariant must enforce fail-closed.
    Outside CI (source-tarball, sandboxed evaluator), skip is acceptable.
    """
    return os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def _in_pr_context() -> bool:
    """Codex iter-5 absorb (kalıcı çözüm): the forbidden-diff invariant
    is only meaningful in a pull-request context. A bare ``push`` event
    (or any non-PR CI run) has no concept of "base ref to diff against"
    — so the test should skip there, even in CI, instead of fail-closing
    on a missing base.

    Detection priority:
      * GitHub Actions ``GITHUB_EVENT_NAME == "pull_request"`` is the
        canonical PR signal.
      * Falling back to "event payload carries a ``pull_request`` block"
        catches custom CI setups that emulate the same shape.
    """
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
    """Codex iter-4 absorb (kalıcı çözüm rule): a single source for the
    PR diff base is fragile. ``actions/checkout@v6`` defaults to
    ``fetch-depth: 1`` so ``origin/main`` may not exist locally inside
    the CI runner — the test would have to either fail-close on a CI
    misconfig (which traps every PR until the workflow is patched) or
    silently skip (which destroys the invariant). Both are wrong. The
    durable fix is to try multiple base-detection strategies, in this
    order:

    1. ``GITHUB_EVENT_PATH``'s ``pull_request.base.sha`` — the most
       authoritative source in a GitHub Actions PR workflow, requires
       no extra fetch, and is set by GitHub itself.
    2. ``GITHUB_BASE_REF`` + ``git fetch origin <ref> --depth=1`` — when
       the event payload is missing, ask Git to bring the base in.
    3. Local ``origin/main`` — works for local human runs that already
       fetched main.
    4. Local ``main`` branch ref — works for clones without remotes.

    Returns ``(base_sha_or_None, source_label)``. The base SHA, when
    returned, is always a validated 40-hex string.
    """
    # Strategy 1: GitHub Actions PR event payload
    # Codex iter-6 absorb (kalıcı çözüm rule): the payload-supplied SHA
    # is only useful if Git actually has the object. Under
    # ``actions/checkout@v6`` default ``fetch-depth: 1``, the base SHA
    # exists on the remote but not yet in the runner's local db — so
    # ``git diff <sha>...HEAD`` fails with "Invalid symmetric difference
    # expression". We first try to materialize the base SHA via
    # ``git fetch origin <sha> --depth=1``; if Git refuses the
    # ``--depth=1`` partial fetch (some server configs disallow it), we
    # fall back to a shallow fetch of the base ref. Only when the SHA
    # is reachable in the local db do we accept this strategy.
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding="utf-8"))
            pr = event.get("pull_request") or {}
            base = pr.get("base") or {}
            sha = base.get("sha")
            base_ref_in_event = base.get("ref")
            if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha):
                # Check if the SHA is already in the local db.
                has = _git(["cat-file", "-e", sha])
                if has.returncode != 0:
                    # Fetch the SHA shallowly so ``git diff <sha>...HEAD``
                    # has the commit object.
                    _git(["fetch", "origin", sha, "--depth=1"])
                    if base_ref_in_event and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref_in_event):
                        _git(["fetch", "origin", base_ref_in_event, "--depth=1"])
                    has = _git(["cat-file", "-e", sha])
                if has.returncode == 0:
                    return sha, "github_event_payload"
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    # Strategy 2: GITHUB_BASE_REF + shallow fetch
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref and re.fullmatch(r"[A-Za-z0-9._/-]+", base_ref):
        fetch_proc = _git(["fetch", "origin", base_ref, "--depth=1"])
        if fetch_proc.returncode == 0:
            mb = _git(["merge-base", "HEAD", "FETCH_HEAD"])
            if mb.returncode == 0:
                sha = mb.stdout.strip()
                if re.fullmatch(r"[0-9a-f]{40}", sha):
                    return sha, f"fetch:{base_ref}"

    # Strategy 3: local origin/main
    mb = _git(["merge-base", "HEAD", "origin/main"])
    if mb.returncode == 0:
        sha = mb.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha, "origin/main"

    # Strategy 4: local main branch
    mb = _git(["merge-base", "HEAD", "main"])
    if mb.returncode == 0:
        sha = mb.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha, "local_main"

    return None, "none"


def test_ri72_forbidden_surfaces_actually_unchanged_in_diff() -> None:
    """Codex iter-2+3+4 absorb: ``forbidden_change_audit.all_unchanged=true``
    in the artifact is self-attestation and not sufficient on its own. A
    PR could touch ``.github/workflows/`` and still write
    ``all_unchanged: true``. This test runs ``git diff --name-only`` of
    the current branch against the PR base (detected via multiple
    strategies — see ``_resolve_diff_base``) and asserts that no listed
    forbidden surface is present in the diff.

    Codex iter-3 absorb (fail-closed in CI) + iter-4 absorb (durable
    multi-strategy base detection per kalıcı-çözüm rule): when run
    inside GitHub Actions or ``CI=true``, the test fail-closes only
    when EVERY strategy fails to find a base — that is a genuine
    misconfiguration, not just ``origin/main`` missing in a shallow
    checkout. Outside CI (source-tarball test runs, sandboxed
    evaluators), skip is acceptable because forbidden-diff enforcement
    is then the CI side's job. The base SHA is validated against a
    strict 40-hex regex so that Git warnings on stderr cannot smuggle a
    non-SHA token into the diff range and silently invalidate the
    check.
    """
    evidence = json.loads(_read(_EVIDENCE_PATH))
    surfaces = evidence["forbidden_change_audit"]["forbidden_surfaces"]

    base, source = _resolve_diff_base()
    if base is None:
        msg = (
            "no PR diff base could be resolved (tried github_event_payload, "
            "GITHUB_BASE_REF fetch, origin/main, local main)"
        )
        # Codex iter-5 absorb: fail-closed only fires in CI AND in a
        # PR context. A bare push/scheduled CI run has no "base" to
        # diff against, so requiring a base there is a category error,
        # not a misconfiguration. The forbidden-diff guarantee for
        # such runs is supplied by the corresponding PR run.
        if _in_ci() and _in_pr_context():
            pytest.fail(f"forbidden-diff invariant cannot run in CI PR: {msg}")
        pytest.skip(msg)

    diff_proc = _git(["diff", "--name-only", f"{base}...HEAD"])
    if diff_proc.returncode != 0:
        msg = f"git diff against base ({source}={base!r}) failed: {diff_proc.stderr.strip() or 'unknown error'}"
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
        f"forbidden surfaces touched by this PR's diff (base source={source}): "
        f"{sorted(offenders)}; forbidden_change_audit.all_unchanged=true is therefore false"
    )


def test_ri72_plan_doc_records_six_rows_and_exit_decision() -> None:
    text = _read(_PLAN_PATH)
    flat = " ".join(text.split())
    # Six row section anchors.
    for header in (
        "3.1 AST / chunk edge cases",
        "3.2 Namespace isolation",
        "3.3 Stale vector cleanup",
        "3.4 No implicit / unconfirmed root authority write",
        "3.5 No auto-feed (no hidden context compiler injection)",
        "3.6 No MCP exposure",
    ):
        assert header in flat, header
    assert "ri7_guardrail_hardening_matrix_ready" in flat
    assert (
        "support_widening: false" in flat
        or "support_widening=false" in flat
        or "Support widening: false" in flat
        or "**Support widening:** false" in flat
    )
    assert (
        "production_platform_claim: false" in flat
        or "production_platform_claim=false" in flat
        or "Production platform claim: false" in flat
        or "**Production platform claim:** false" in flat
    )
    assert (
        "live_adapter_execution: false" in flat
        or "live_adapter_execution=false" in flat
        or "Live adapter execution: false" in flat
        or "**Live adapter execution:** false" in flat
    )
