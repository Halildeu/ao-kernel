"""Tests for the local GPP AI review gate (scripts/local_gpp_gate.py)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module() -> Any:
    module_path = _repo_root() / "scripts" / "local_gpp_gate.py"
    spec = importlib.util.spec_from_file_location("local_gpp_gate", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_template_module() -> Any:
    module_path = _repo_root() / "scripts" / "local_gpp_gate_review_template.py"
    spec = importlib.util.spec_from_file_location("local_gpp_gate_review_template", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(name: str) -> Path:
    return _repo_root() / "tests" / "fixtures" / "local_gpp_gate" / name


def _status_path() -> Path:
    return _repo_root() / ".claude" / "plans" / "gpp_status.v1.json"


def _run_gate(argv: list[str]) -> int:
    mod = _load_module()
    return int(mod.main(argv))


def _declared_changed_files(fixture_name: str) -> list[str]:
    """Return the reviewer-declared changed_files list from a fixture."""

    payload = json.loads(_fixture(fixture_name).read_text(encoding="utf-8"))
    return list(payload["scope_reviewed"]["changed_files"])


def _evaluate_fixture(
    fixture_name: str,
    *,
    actual_files: list[str] | None,
    tmp_path: Path,
    payload_override: dict[str, Any] | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
    repo: str | None = None,
    work_package: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Run the gate via ``evaluate_gate`` with an injected ``actual_files``.

    Most fixture tests want to exercise the gate logic without depending on
    the demo repo's real git diff. This helper calls ``evaluate_gate``
    directly with an explicit ``actual_files`` list (FIX 2), builds the
    artifact, writes it through ``write_gate_evidence``, and returns the
    artifact plus the equivalent return code so assertions stay simple.

    The trusted operator ``base_ref`` / ``head_ref`` / ``repo`` /
    ``work_package`` values default to the values declared in the
    ``reviewer_agree.v1.json`` fixture (so the happy path still produces
    ``operator_may_merge``); a test that wants to exercise a reviewer/
    operator mismatch passes explicit differing values.
    """

    mod = _load_module()
    if payload_override is not None:
        payload = payload_override
    else:
        payload = json.loads(_fixture(fixture_name).read_text(encoding="utf-8"))
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    review = mod.load_review_evidence(src)
    operator_base_ref = "origin/main" if base_ref is None else base_ref
    operator_head_ref = (
        "codex/local-gate-1-impl" if head_ref is None else head_ref
    )
    operator_repo = "Halildeu/ao-kernel" if repo is None else repo
    operator_work_package = "GPP-2ag" if work_package is None else work_package
    checks, gate_findings = mod.evaluate_gate(
        review,
        repo_root=_repo_root(),
        status_path=_status_path(),
        actual_files=actual_files,
        base_ref=operator_base_ref,
        head_ref=operator_head_ref,
        repo=operator_repo,
        work_package=operator_work_package,
    )
    artifact = mod.build_gate_evidence(
        review=review,
        checks=checks,
        gate_findings=gate_findings,
        repo=operator_repo,
        work_package=operator_work_package,
        generated_at=mod.utc_timestamp(),
    )
    output = tmp_path / "gate-evidence.json"
    mod.write_gate_evidence(output, artifact)
    code = 0 if artifact["decision"] == "operator_may_merge" else 1
    return artifact, code


def test_missing_reviewer_evidence_fails_closed(tmp_path: Path, capsys: Any) -> None:
    missing = tmp_path / "does-not-exist.json"
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(missing), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["gpp_2_status"] == "blocked"


def test_reviewer_revise_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_revise.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["reviewer_agree"] is False


def test_reviewer_block_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_block.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["reviewer_agree"] is False


def test_reviewer_unknown_verdict_fails_closed(tmp_path: Path) -> None:
    # An unknown verdict is rejected by the reviewer-evidence schema, so the
    # gate treats the file as schema-invalid and fails closed.
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["reviewer"]["verdict"] = "MAYBE"
    bad = tmp_path / "reviewer_unknown_verdict.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(bad), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["reviewer_agree"] is False


def test_same_provider_review_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_same_provider.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["cross_provider_verified"] is False


def test_reviewer_agree_with_passing_checks_succeeds(tmp_path: Path) -> None:
    # FIX 2: scope is verified against the actual git diff. The AGREE happy
    # path is exercised by injecting actual_files that exactly match the
    # fixture's reviewer-declared changed_files.
    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
    )

    assert code == 0
    assert artifact["decision"] == "operator_may_merge"
    assert all(artifact["checks"].values())
    assert artifact["gpp_2_status"] == "blocked"
    assert artifact["support_widening"] is False
    assert artifact["production_platform_claim"] is False
    assert artifact["live_adapter_execution"] is False


def test_reviewer_agree_renders_operator_may_merge(tmp_path: Path) -> None:
    # Render path: the summary text shows operator_may_merge when scope is
    # verified. evaluate_gate is called directly with matching actual_files,
    # then render_summary is exercised.
    mod = _load_module()
    review = mod.load_review_evidence(_fixture("reviewer_agree.v1.json"))
    checks, gate_findings = mod.evaluate_gate(
        review,
        repo_root=_repo_root(),
        status_path=_status_path(),
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        base_ref="origin/main",
        head_ref="codex/local-gate-1-impl",
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
    )
    artifact = mod.build_gate_evidence(
        review=review,
        checks=checks,
        gate_findings=gate_findings,
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
        generated_at=mod.utc_timestamp(),
    )
    summary = mod.render_summary(artifact)
    assert artifact["decision"] == "operator_may_merge"
    assert "operator_may_merge" in summary
    assert "Reviewer findings count:" in summary


def test_forbidden_action_flag_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_forbidden_action.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_support_widening_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_support_widening.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_production_platform_claim_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_production_claim.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_live_adapter_execution_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_live_adapter.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_tests_failed_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(
        ["--review-evidence", str(_fixture("reviewer_tests_failed.v1.json")), "--output", str(output)]
    )

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["tests_passed"] is False


def test_generated_evidence_contains_no_secret_material(tmp_path: Path) -> None:
    # Build a reviewer evidence file whose agent label carries a unique
    # sentinel string. The gate output is structurally constrained and must
    # not propagate reviewer agent identifiers, so the sentinel must never
    # appear in the artifact. The sentinel is deliberately not a
    # real-looking credential pattern so repo secret scanners stay quiet.
    sentinel = "SENTINEL-do-not-propagate-canary-9c3f1a2b7e"
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["implementer"]["agent"] = f"claude-{sentinel}"

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 0
    raw_output = json.dumps(artifact, sort_keys=True)
    # The sentinel was placed in an agent identifier field. The gate output
    # is structurally constrained and does not echo reviewer agent
    # identifiers, so the sentinel must not appear in the artifact.
    assert sentinel not in raw_output
    # The gate output keys are exactly the whitelisted set.
    assert set(artifact.keys()) == {
        "schema_version",
        "decision",
        "repo",
        "work_package",
        "generated_at",
        "checks",
        "findings",
        "reviewer_findings_count",
        "gpp_2_status",
        "support_widening",
        "production_platform_claim",
        "live_adapter_execution",
    }


def test_reviewer_finding_free_text_does_not_propagate(tmp_path: Path) -> None:
    # FIX 3 probe: a sentinel placed in a reviewer findings[] entry must not
    # propagate into the gate artifact. The gate now carries only a count of
    # reviewer findings, never the reviewer's free text. The sentinel is
    # deliberately not a real-looking credential pattern.
    sentinel = "SENTINEL-reviewer-finding-leak-probe-4d8e1f"
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["findings"] = [
        f"reviewer note carrying {sentinel}",
        "a second reviewer finding string",
    ]

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 0
    raw_output = json.dumps(artifact, sort_keys=True)
    # The reviewer free text (and its sentinel) must never appear.
    assert sentinel not in raw_output
    # Only the count is carried, not the strings themselves.
    assert artifact["reviewer_findings_count"] == 2
    # The gate findings array holds only gate-authored strings; none of the
    # reviewer free text leaks in.
    for finding in artifact["findings"]:
        assert sentinel not in finding
        assert not finding.startswith("reviewer finding:")


def test_forbidden_finding_does_not_echo_raw_entry(tmp_path: Path) -> None:
    # FIX 3: when a FORBIDDEN-prefixed reviewer finding is detected, the gate
    # finding must reference it by index only and must not echo the raw
    # reviewer text after the FORBIDDEN: prefix.
    sentinel = "SENTINEL-forbidden-entry-body-7a2c9b"
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["findings"] = [
        "a benign first finding",
        f"FORBIDDEN: {sentinel}",
    ]

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False
    raw_output = json.dumps(artifact, sort_keys=True)
    # The raw text after the FORBIDDEN: prefix must not be echoed.
    assert sentinel not in raw_output
    # The gate finding references the offending entry by index.
    forbidden_findings = [f for f in artifact["findings"] if "FORBIDDEN-prefixed finding" in f]
    assert forbidden_findings
    assert "index 1" in forbidden_findings[0]


def test_gpp_next_still_reports_blocked(tmp_path: Path) -> None:
    # A successful gate run must not mutate GPP state; gpp_next still
    # reports GPP-2 blocked afterward. The gate is run via evaluate_gate
    # with matching actual_files so scope verification (FIX 2) passes.
    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
    )
    assert code == 0

    gpp_next_path = _repo_root() / "scripts" / "gpp_next.py"
    spec = importlib.util.spec_from_file_location("gpp_next", gpp_next_path)
    assert spec is not None and spec.loader is not None
    gpp_next = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gpp_next)

    payload = gpp_next.load_status(_status_path())
    assert payload["current_wp"]["id"] == "GPP-2"
    assert payload["current_wp"]["status"] == "blocked"
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False
    # The gate artifact also pins GPP-2 blocked.
    assert artifact["gpp_2_status"] == "blocked"


def test_gate_output_validates_against_gate_evidence_schema(tmp_path: Path) -> None:
    mod = _load_module()
    # operator_may_merge artifact (scope verified via injected actual_files).
    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
    )
    assert code == 0
    # Round-trips cleanly through the bundled gate evidence schema validator.
    mod.validate_gate_evidence(artifact)


def test_fail_closed_artifact_validates_against_schema(tmp_path: Path) -> None:
    # A fail_closed artifact (here from a missing reviewer file) must also
    # validate against the bundled gate evidence schema, including the new
    # required reviewer_findings_count field.
    mod = _load_module()
    missing = tmp_path / "does-not-exist.json"
    output = tmp_path / "gate-evidence.json"
    code = mod.main(["--review-evidence", str(missing), "--output", str(output)])
    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["reviewer_findings_count"] == 0
    mod.validate_gate_evidence(artifact)


def test_review_template_is_schema_valid_and_fails_gate_unedited(tmp_path: Path) -> None:
    mod = _load_module()
    template_mod = _load_template_module()
    template = template_mod.build_template()

    # The blank template must itself satisfy the reviewer-evidence schema.
    mod.validate_gate_evidence  # noqa: B018 - sanity reference
    schema = mod.load_review_evidence_schema()
    from jsonschema import Draft202012Validator

    Draft202012Validator(schema).validate(template)

    # An unedited template must fail the gate closed (verdict placeholder
    # is REVISE), proving reviewers cannot pass the gate without filling it.
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"
    code = mod.main(["--review-evidence", str(template_path), "--output", str(output)])
    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"


def test_no_output_path_still_prints_decision(capsys: Any) -> None:
    # Without --output the gate still runs and prints a decision. Run with
    # --skip-git: FIX 2 makes scope verification unavailable, so the decision
    # is fail_closed and the gate still prints it.
    code = _run_gate(["--review-evidence", str(_fixture("reviewer_agree.v1.json")), "--skip-git"])
    captured = capsys.readouterr()
    assert code == 1
    assert "fail_closed" in captured.out


def test_invocation_error_returns_two(tmp_path: Path, capsys: Any) -> None:
    # A non-JSON reviewer evidence file is treated as a fail-closed input,
    # not an invocation error; invocation errors (code 2) are reserved for
    # conditions where no durable artifact can be produced. Confirm bad JSON
    # fails closed (code 1).
    bad = tmp_path / "not-json.json"
    bad.write_text("this is not json", encoding="utf-8")
    output = tmp_path / "gate-evidence.json"
    code = _run_gate(["--review-evidence", str(bad), "--output", str(output)])
    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"


def test_scope_mismatch_fails_closed(tmp_path: Path) -> None:
    # FIX 2: when the reviewer-declared changed_files do not exactly match
    # the actual git diff, scope verification fails closed even with an
    # otherwise-AGREE reviewer evidence file.
    declared = _declared_changed_files("reviewer_agree.v1.json")
    # actual_files differs: drop one declared file, add one the reviewer
    # never listed.
    actual = sorted(declared[:-1] + ["scripts/some_other_unreviewed_file.py"])

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=actual,
        tmp_path=tmp_path,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False
    mismatch = [f for f in artifact["findings"] if "does not match the actual git diff" in f]
    assert mismatch
    # The finding reports the symmetric-difference counts.
    assert "1 missing from reviewer" in mismatch[0]
    assert "1 extra in reviewer" in mismatch[0]


def test_scope_skip_git_fails_closed(tmp_path: Path) -> None:
    # FIX 2: with git skipped the gate cannot verify the reviewer-declared
    # scope against the actual diff, so scope_allowed fails closed.
    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=None,
        tmp_path=tmp_path,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False
    unavailable = [f for f in artifact["findings"] if "actual git diff unavailable" in f]
    assert unavailable


def test_scope_skip_git_via_cli_fails_closed(tmp_path: Path) -> None:
    # End-to-end: the --skip-git CLI flag makes scope verification
    # unavailable and the gate fails closed.
    output = tmp_path / "gate-evidence.json"
    code = _run_gate(
        [
            "--review-evidence",
            str(_fixture("reviewer_agree.v1.json")),
            "--output",
            str(output),
            "--skip-git",
        ]
    )
    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False


def test_reviewer_declared_base_ref_mismatch_fails_closed(tmp_path: Path) -> None:
    # FIX A: the git diff base/head refs are operator-controlled. When the
    # reviewer evidence's scope_reviewed.base_ref does not equal the
    # operator --base-ref, the untrusted reviewer cannot narrow the diff
    # range: the scope check fails closed.
    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        base_ref="origin/some-narrowing-ref",
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False
    mismatch = [
        f
        for f in artifact["findings"]
        if "reviewer-declared base_ref" in f and "does not match operator base_ref" in f
    ]
    assert mismatch


def test_reviewer_declared_head_ref_mismatch_fails_closed(tmp_path: Path) -> None:
    # FIX A: same operator-control guarantee for the head ref. A reviewer
    # head_ref that does not match the operator --head-ref fails closed.
    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        head_ref="some-other-head-ref",
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False
    mismatch = [
        f
        for f in artifact["findings"]
        if "reviewer-declared head_ref" in f and "does not match operator head_ref" in f
    ]
    assert mismatch


def test_reviewer_declared_repo_mismatch_fails_closed(tmp_path: Path) -> None:
    # FIX B: a sentinel planted in the reviewer evidence's top-level repo
    # field must not reach the artifact. When reviewer repo != operator
    # --repo the scope check fails closed, and the sentinel value appears
    # neither in the artifact nor on stdout.
    sentinel = "SENTINEL-reviewer-repo-leak-probe-3f9a1d"
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["repo"] = f"evil/{sentinel}"

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False
    mismatch = [
        f
        for f in artifact["findings"]
        if "reviewer-declared repo" in f and "does not match operator repo" in f
    ]
    assert mismatch
    # The sentinel from the reviewer-declared repo never reaches the
    # artifact or any rendered output.
    raw_output = json.dumps(artifact, sort_keys=True)
    assert sentinel not in raw_output
    mod = _load_module()
    assert sentinel not in mod.render_summary(artifact)
    assert artifact["repo"] == "Halildeu/ao-kernel"


def test_reviewer_declared_work_package_mismatch_fails_closed(tmp_path: Path) -> None:
    # FIX B: same guarantee for the work_package field. A reviewer-declared
    # work_package that does not match the operator --work-package fails
    # closed, and a sentinel planted there never echoes.
    sentinel = "SENTINEL-reviewer-wp-leak-probe-8b2e4c"
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["work_package"] = f"WP-{sentinel}"

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["scope_allowed"] is False
    mismatch = [
        f
        for f in artifact["findings"]
        if "reviewer-declared work_package" in f
        and "does not match operator work_package" in f
    ]
    assert mismatch
    raw_output = json.dumps(artifact, sort_keys=True)
    assert sentinel not in raw_output
    mod = _load_module()
    assert sentinel not in mod.render_summary(artifact)
    assert artifact["work_package"] == "GPP-2ag"


def test_artifact_repo_and_work_package_come_from_operator_args(tmp_path: Path) -> None:
    # FIX B: the artifact repo / work_package are sourced from the operator
    # args, never the reviewer evidence. Operator values that differ from
    # the reviewer evidence are a mismatch (fail_closed); operator values
    # that match produce a successful gate whose artifact carries exactly
    # the operator-supplied values.

    # Operator args differ from the reviewer evidence -> fail_closed.
    artifact_mismatch, code_mismatch = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        repo="Halildeu/ao-kernel-fork",
        work_package="GPP-9zz",
    )
    assert code_mismatch == 1
    assert artifact_mismatch["decision"] == "fail_closed"
    assert artifact_mismatch["checks"]["scope_allowed"] is False
    # Even on a mismatch the artifact still carries the operator values,
    # never the reviewer-declared ones.
    assert artifact_mismatch["repo"] == "Halildeu/ao-kernel-fork"
    assert artifact_mismatch["work_package"] == "GPP-9zz"

    # Operator args match the reviewer evidence -> operator_may_merge, and
    # the artifact repo / work_package are exactly the operator values.
    artifact_match, code_match = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
    )
    assert code_match == 0
    assert artifact_match["decision"] == "operator_may_merge"
    assert artifact_match["repo"] == "Halildeu/ao-kernel"
    assert artifact_match["work_package"] == "GPP-2ag"


def test_duplicate_check_with_one_fail_fails_closed(tmp_path: Path) -> None:
    # FIX 5: a duplicate required-check name where one entry fails must not
    # let the failing entry hide behind an earlier passing one. checks_
    # considered carries tests=pass AND tests=fail; the gate must fail
    # closed.
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["checks_considered"] = [
        {"name": "tests", "status": "pass"},
        {"name": "tests", "status": "fail"},
        {"name": "secret_scan", "status": "pass"},
    ]

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["tests_passed"] is False


def test_duplicate_secret_scan_with_one_fail_fails_closed(tmp_path: Path) -> None:
    # FIX 5: same hardening for the secret_scan required check.
    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["checks_considered"] = [
        {"name": "tests", "status": "pass"},
        {"name": "secret_scan", "status": "pass"},
        {"name": "secret_scan", "status": "fail"},
    ]

    artifact, code = _evaluate_fixture(
        "reviewer_agree.v1.json",
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        tmp_path=tmp_path,
        payload_override=payload,
    )

    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["secret_scan_passed"] is False


def test_wrong_gpp_id_fails_closed(tmp_path: Path) -> None:
    # FIX 4: gpp_status_checked requires current_wp.id == "GPP-2". A status
    # file pinned to a different work package fails the check closed.
    mod = _load_module()
    status_payload = json.loads(_status_path().read_text(encoding="utf-8"))
    status_payload["current_wp"]["id"] = "GPP-9"
    bad_status = tmp_path / "gpp_status_wrong_id.json"
    bad_status.write_text(json.dumps(status_payload), encoding="utf-8")

    review = mod.load_review_evidence(_fixture("reviewer_agree.v1.json"))
    checks, gate_findings = mod.evaluate_gate(
        review,
        repo_root=_repo_root(),
        status_path=bad_status,
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        base_ref="origin/main",
        head_ref="codex/local-gate-1-impl",
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
    )
    assert checks["gpp_status_checked"] is False
    wrong_id = [f for f in gate_findings if "expected 'GPP-2'" in f]
    assert wrong_id


def test_startup_preflight_runs_gpp_next(tmp_path: Path) -> None:
    # FIX 1: the startup preflight runs scripts/gpp_next.py as a subprocess.
    # With a valid repo + status file the preflight passes; with a status
    # file that gpp_next.py rejects, the subprocess exits non-zero and the
    # preflight fails closed.
    mod = _load_module()

    # Healthy preflight: gpp_next.py exits 0 against the real status file.
    review = mod.load_review_evidence(_fixture("reviewer_agree.v1.json"))
    checks, _ = mod.evaluate_gate(
        review,
        repo_root=_repo_root(),
        status_path=_status_path(),
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        base_ref="origin/main",
        head_ref="codex/local-gate-1-impl",
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
    )
    assert checks["startup_preflight_passed"] is True

    # Broken preflight: a status file missing required keys makes gpp_next.py
    # exit non-zero, so the preflight subprocess check fails.
    bad_status = tmp_path / "gpp_status_broken.json"
    bad_status.write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")
    checks_bad, findings_bad = mod.evaluate_gate(
        review,
        repo_root=_repo_root(),
        status_path=bad_status,
        actual_files=_declared_changed_files("reviewer_agree.v1.json"),
        base_ref="origin/main",
        head_ref="codex/local-gate-1-impl",
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
    )
    assert checks_bad["startup_preflight_passed"] is False
    preflight_findings = [f for f in findings_bad if f.startswith("startup preflight:")]
    assert preflight_findings


def test_output_write_failure_returns_two(tmp_path: Path, capsys: Any) -> None:
    # FIX 6: an output-write failure means the gate could not produce
    # durable evidence, so it is an invocation error and returns 2.
    mod = _load_module()
    # Point --output at a path whose parent is a regular file, so mkdir of
    # the parent directory raises OSError.
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    output = blocker / "sub" / "gate-evidence.json"
    code = mod.main(
        ["--review-evidence", str(_fixture("reviewer_agree.v1.json")), "--output", str(output), "--skip-git"]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "could not write gate evidence" in captured.err
