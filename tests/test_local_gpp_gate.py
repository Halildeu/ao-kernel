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
    operator_head_ref = "codex/local-gate-1-impl" if head_ref is None else head_ref
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
    assert artifact["gpp_2_status"] == "closed"


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

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_same_provider.v1.json")), "--output", str(output)])

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
    assert artifact["gpp_2_status"] == "closed"
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

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_forbidden_action.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_support_widening_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_support_widening.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_production_platform_claim_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_production_claim.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_live_adapter_execution_true_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_live_adapter.v1.json")), "--output", str(output)])

    assert code == 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail_closed"
    assert artifact["checks"]["forbidden_actions_absent"] is False


def test_tests_failed_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "gate-evidence.json"

    code = _run_gate(["--review-evidence", str(_fixture("reviewer_tests_failed.v1.json")), "--output", str(output)])

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
    assert payload["current_wp"]["status"] == "closed"
    assert payload["support_widening_allowed"] is False
    assert payload["production_platform_claim_allowed"] is False
    assert payload["live_adapter_execution_allowed"] is False
    # The gate artifact pins GPP-2 closed (terminal release-governance lifecycle
    # closure) but does not by itself close GPP-2; it remains local operator
    # evidence only.
    assert artifact["gpp_2_status"] == "closed"


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
        f for f in artifact["findings"] if "reviewer-declared base_ref" in f and "does not match operator base_ref" in f
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
        f for f in artifact["findings"] if "reviewer-declared head_ref" in f and "does not match operator head_ref" in f
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
        f for f in artifact["findings"] if "reviewer-declared repo" in f and "does not match operator repo" in f
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
        if "reviewer-declared work_package" in f and "does not match operator work_package" in f
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


# --- GPP-2D-2a: context-binding ---


def _gate_artifact_without_binding(mod: Any) -> dict[str, Any]:
    """Return a schema-valid gate artifact that carries no context_binding."""

    return mod.build_gate_evidence(
        review=None,
        checks={name: True for name in mod.GATE_CHECK_NAMES},
        gate_findings=[],
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
        generated_at=mod.utc_timestamp(),
    )


def test_build_context_binding_binds_head_and_diff() -> None:
    mod = _load_module()
    changed = ["scripts/local_gpp_gate.py", "tests/test_local_gpp_gate.py"]
    binding = mod.build_context_binding(
        repo_root=_repo_root(),
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=changed,
    )
    assert binding is not None
    assert binding["base_ref"] == "origin/main"
    assert binding["changed_files_count"] == 2
    assert len(binding["head_sha"]) == 40
    assert all(char in "0123456789abcdef" for char in binding["head_sha"])
    assert binding["diff_digest"].startswith("sha256:")
    assert len(binding["diff_digest"]) == len("sha256:") + 64


def test_build_context_binding_diff_digest_is_order_independent() -> None:
    mod = _load_module()
    forward = mod.build_context_binding(
        repo_root=_repo_root(),
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["a.py", "b.py"],
    )
    reverse = mod.build_context_binding(
        repo_root=_repo_root(),
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["b.py", "a.py"],
    )
    other = mod.build_context_binding(
        repo_root=_repo_root(),
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["a.py", "c.py"],
    )
    assert forward is not None and reverse is not None and other is not None
    # Same file set in any order binds to the same digest.
    assert forward["diff_digest"] == reverse["diff_digest"]
    # A different file set binds to a different digest.
    assert forward["diff_digest"] != other["diff_digest"]


def test_build_context_binding_omitted_when_diff_unverified() -> None:
    # changed_files=None models the --skip-git / git-failed path: the diff
    # was not verified, so no context binding is emitted.
    mod = _load_module()
    assert (
        mod.build_context_binding(
            repo_root=_repo_root(),
            base_ref="origin/main",
            head_ref="HEAD",
            changed_files=None,
        )
        is None
    )


def test_build_context_binding_omitted_outside_git_repo(tmp_path: Path) -> None:
    # A non-repository directory cannot resolve a head SHA, so no binding is
    # built even when a real changed-files list is supplied.
    mod = _load_module()
    assert (
        mod.build_context_binding(
            repo_root=tmp_path,
            base_ref="origin/main",
            head_ref="HEAD",
            changed_files=["scripts/local_gpp_gate.py"],
        )
        is None
    )


def test_build_gate_evidence_includes_context_binding_when_supplied() -> None:
    mod = _load_module()
    binding = {
        "head_sha": "0" * 40,
        "base_ref": "origin/main",
        "diff_digest": "sha256:" + "0" * 64,
        "changed_files_count": 1,
    }
    artifact = mod.build_gate_evidence(
        review=None,
        checks={name: True for name in mod.GATE_CHECK_NAMES},
        gate_findings=[],
        repo="Halildeu/ao-kernel",
        work_package="GPP-2ag",
        generated_at=mod.utc_timestamp(),
        context_binding=binding,
    )
    assert artifact["context_binding"] == binding
    mod.validate_gate_evidence(artifact)


def test_build_gate_evidence_omits_context_binding_when_none() -> None:
    # Non-breaking: an artifact with no context_binding stays schema-valid,
    # so existing local-gpp-gate-evidence.v1 artifacts keep validating.
    mod = _load_module()
    artifact = _gate_artifact_without_binding(mod)
    assert "context_binding" not in artifact
    mod.validate_gate_evidence(artifact)


def test_schema_rejects_context_binding_with_bad_head_sha() -> None:
    mod = _load_module()
    from jsonschema import Draft202012Validator

    artifact = _gate_artifact_without_binding(mod)
    artifact["context_binding"] = {
        "head_sha": "NOT-A-SHA",
        "base_ref": "origin/main",
        "diff_digest": "sha256:" + "0" * 64,
        "changed_files_count": 0,
    }
    errors = list(Draft202012Validator(mod.load_gate_evidence_schema()).iter_errors(artifact))
    assert errors


def test_schema_rejects_unknown_context_binding_field() -> None:
    mod = _load_module()
    from jsonschema import Draft202012Validator

    artifact = _gate_artifact_without_binding(mod)
    artifact["context_binding"] = {
        "head_sha": "0" * 40,
        "base_ref": "origin/main",
        "diff_digest": "sha256:" + "0" * 64,
        "changed_files_count": 0,
        "unexpected": "value",
    }
    errors = list(Draft202012Validator(mod.load_gate_evidence_schema()).iter_errors(artifact))
    assert errors


def test_schema_rejects_context_binding_missing_required_field() -> None:
    mod = _load_module()
    from jsonschema import Draft202012Validator

    artifact = _gate_artifact_without_binding(mod)
    artifact["context_binding"] = {
        "head_sha": "0" * 40,
        "base_ref": "origin/main",
        "diff_digest": "sha256:" + "0" * 64,
    }
    errors = list(Draft202012Validator(mod.load_gate_evidence_schema()).iter_errors(artifact))
    assert errors


def test_gate_run_emits_context_binding(tmp_path: Path) -> None:
    # End-to-end: a gate run over a verified git diff emits context_binding.
    # base-ref == head-ref gives a verified (empty) diff that does not depend
    # on the CI checkout depth, so the binding is still emitted deterministically.
    mod = _load_module()
    output = tmp_path / "gate-evidence.json"
    mod.main(
        [
            "--review-evidence",
            str(_fixture("reviewer_agree.v1.json")),
            "--output",
            str(output),
            "--base-ref",
            "HEAD",
            "--head-ref",
            "HEAD",
        ]
    )
    artifact = json.loads(output.read_text(encoding="utf-8"))
    binding = artifact["context_binding"]
    assert len(binding["head_sha"]) == 40
    assert binding["base_ref"] == "HEAD"
    assert binding["changed_files_count"] == 0
    assert binding["diff_digest"].startswith("sha256:")
    mod.validate_gate_evidence(artifact)


def test_gate_run_skip_git_omits_context_binding(tmp_path: Path) -> None:
    # --skip-git leaves the diff unverified, so the gate emits no context
    # binding and the artifact still validates against the schema.
    mod = _load_module()
    output = tmp_path / "gate-evidence.json"
    mod.main(
        [
            "--review-evidence",
            str(_fixture("reviewer_agree.v1.json")),
            "--output",
            str(output),
            "--skip-git",
        ]
    )
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert "context_binding" not in artifact
    mod.validate_gate_evidence(artifact)


def test_gate_run_invalid_head_ref_fails_closed_without_context_binding(tmp_path: Path) -> None:
    # An invalid --head-ref makes the git diff fail, leaving the diff
    # unverified: the gate decides fail_closed and emits no context binding,
    # so a future required check cannot trust an unverifiable head.
    mod = _load_module()
    output = tmp_path / "gate-evidence.json"
    code = mod.main(
        [
            "--review-evidence",
            str(_fixture("reviewer_agree.v1.json")),
            "--output",
            str(output),
            "--base-ref",
            "origin/main",
            "--head-ref",
            "no-such-ref-gpp2d2a",
        ]
    )
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert code == 1
    assert artifact["decision"] == "fail_closed"
    assert "context_binding" not in artifact
    mod.validate_gate_evidence(artifact)


# ---------------------------------------------------------------------------
# GPP-2D-3c dual-ref API (head-side, Codex iter-1+2 absorb,
#                         threads 019e5a21 / 019e5a32)
# ---------------------------------------------------------------------------
#
# scripts/local_gpp_gate.py exposes a dual-ref CLI surface so a future
# caller can split reviewer-visible ref labels from diff-resolving
# refs:
#
#   --review-base-ref / --review-head-ref  # scope-check labels (string
#                                          # equality against the
#                                          # committed reviewer evidence)
#   --diff-base-ref   / --diff-head-ref    # git diff + context_binding refs
#   --base-ref        / --head-ref         # backward-compatible legacy
#                                          # single-ref alias (defaults
#                                          # when --review-* / --diff-*
#                                          # are absent)
#
# This head-side API is READY in this PR (the script change landed in
# commit a445780). The active CI workflow in this slice does NOT use it
# yet — it uses the legacy alias path because the workflow checks the
# script out from the PR base SHA (trusted-base discipline), and the
# base copy on main predates the dual-ref flags. Once the dual-ref
# CLI reaches main, a follow-up slice can upgrade the workflow.
#
# The first three tests below pin three invariants of the dual-ref API:
#   1. --review-* drive the scope check, even when --diff-* and the
#      legacy --base-ref / --head-ref values differ.
#   2. --review-* mismatches against the committed reviewer evidence
#      fail scope check closed, even when --diff-* / legacy refs match.
#   3. When --review-* are absent, --base-ref / --head-ref serve as
#      the legacy single-ref alias and drive scope check, so older
#      callers and tests keep working unchanged.
#
# The fourth test below builds a deterministic tmp git repo and runs
# main() end-to-end through the dual-ref invocation pattern, pinning
# the accepting-artifact happy path. The fifth test simulates the
# actual GitHub Actions shape of the active workflow (detached base
# checkout + SHA fetch + branch ref binding + legacy alias path) and
# pins the same accepting-artifact outcome there.
# ---------------------------------------------------------------------------


def test_review_refs_drive_scope_check_when_diff_and_legacy_refs_differ(tmp_path: Path) -> None:
    """GPP-2D-3c dual-ref invariant #1: --review-base-ref /
    --review-head-ref drive the scope check (string equality with the
    committed reviewer evidence) even when --diff-* and the legacy
    --base-ref / --head-ref values are entirely different. This pins
    that scope check is routed to the reviewer-visible labels, not to
    the diff-resolving SHAs."""

    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["scope_reviewed"]["base_ref"] = "PR-base-branch"
    payload["scope_reviewed"]["head_ref"] = "PR-head-branch"
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    mod = _load_module()
    mod.main(
        [
            "--review-evidence",
            str(src),
            "--output",
            str(output),
            "--review-base-ref",
            "PR-base-branch",
            "--review-head-ref",
            "PR-head-branch",
            "--diff-base-ref",
            "deadbeef0000000000000000000000000000beef",
            "--diff-head-ref",
            "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00",
            "--base-ref",
            "legacy-base-ref-that-must-not-match",
            "--head-ref",
            "legacy-head-ref-that-must-not-match",
            "--skip-git",
            "--repo",
            "Halildeu/ao-kernel",
            "--work-package",
            "GPP-2ag",
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))
    findings = " ".join(artifact.get("findings", []))
    assert "reviewer-declared base_ref does not match" not in findings, (
        f"scope check must route to --review-base-ref, not --diff-base-ref or --base-ref. findings: {findings}"
    )
    assert "reviewer-declared head_ref does not match" not in findings, (
        f"scope check must route to --review-head-ref, not --diff-head-ref or --head-ref. findings: {findings}"
    )


def test_review_ref_mismatch_fails_scope_check_even_when_diff_and_legacy_match(tmp_path: Path) -> None:
    """GPP-2D-3c dual-ref invariant #2: a --review-base-ref /
    --review-head-ref value that disagrees with the committed reviewer
    evidence fails scope check closed, even when --diff-* and the
    legacy --base-ref / --head-ref values match the reviewer evidence.
    This pins that scope check looks at --review-* exclusively and
    cannot be silently routed back to --diff-* or the legacy alias."""

    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["scope_reviewed"]["base_ref"] = "main"
    payload["scope_reviewed"]["head_ref"] = "feature-x"
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    mod = _load_module()
    mod.main(
        [
            "--review-evidence",
            str(src),
            "--output",
            str(output),
            "--review-base-ref",
            "main",
            "--review-head-ref",
            "DIFFERENT-HEAD-REF-THAT-MUST-FAIL-SCOPE",
            "--diff-base-ref",
            "main",
            "--diff-head-ref",
            "feature-x",
            "--base-ref",
            "main",
            "--head-ref",
            "feature-x",
            "--skip-git",
            "--repo",
            "Halildeu/ao-kernel",
            "--work-package",
            "GPP-2ag",
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))
    findings = " ".join(artifact.get("findings", []))
    assert (
        "reviewer-declared head_ref does not match operator head_ref 'DIFFERENT-HEAD-REF-THAT-MUST-FAIL-SCOPE'"
        in findings
    ), f"expected the --review-head-ref mismatch to fail scope check, but findings did not contain it: {findings}"
    assert artifact["decision"] == "fail_closed", f"a --review-head-ref mismatch must fail closed, got: {artifact}"


def test_legacy_base_head_ref_alias_drives_scope_check_when_review_refs_absent(tmp_path: Path) -> None:
    """GPP-2D-3c dual-ref invariant #3 (backward compatibility): when
    --review-base-ref / --review-head-ref are not supplied, --base-ref
    / --head-ref serve as the legacy single-ref alias for both scope
    check and the git diff. This pins that older callers (including
    pre-GPP-2D-3c tests inside this file) keep working unchanged."""

    payload = json.loads(_fixture("reviewer_agree.v1.json").read_text(encoding="utf-8"))
    payload["scope_reviewed"]["base_ref"] = "legacy-base"
    payload["scope_reviewed"]["head_ref"] = "legacy-head"
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    mod = _load_module()
    mod.main(
        [
            "--review-evidence",
            str(src),
            "--output",
            str(output),
            # Intentionally only the legacy single-ref alias; no --review-* / --diff-*.
            "--base-ref",
            "legacy-base",
            "--head-ref",
            "legacy-head",
            "--skip-git",
            "--repo",
            "Halildeu/ao-kernel",
            "--work-package",
            "GPP-2ag",
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))
    findings = " ".join(artifact.get("findings", []))
    assert "reviewer-declared base_ref does not match" not in findings, (
        f"legacy single-ref alias must drive scope check when --review-* is absent. findings: {findings}"
    )
    assert "reviewer-declared head_ref does not match" not in findings, (
        f"legacy single-ref alias must drive scope check when --review-* is absent. findings: {findings}"
    )


# ---------------------------------------------------------------------------
# GPP-2D-3c end-to-end dogfood (Codex iter-2 absorb, thread 019e5a32)
# ---------------------------------------------------------------------------
#
# Iter-2 still flagged the dogfood drift-guard as REVISE because the three
# scope-routing tests above all use --skip-git and only assert the absence
# of ref-mismatch findings. They do not prove the dual-ref happy path
# emits an accepting local-gpp-gate-evidence.v1 artifact with the runtime
# head SHA bound. A future regression could keep scope routing correct
# but, for example, route context_binding back to the reviewer-visible
# head ref, omit the binding, or otherwise fail to produce
# operator_may_merge in dual-ref mode — and the committed regression test
# would not catch it.
#
# This end-to-end dogfood addresses that gap. It builds a deterministic
# tmp git repo, calls main() with the exact workflow arg pattern, and
# pins:
#   - exit code 0
#   - decision == operator_may_merge
#   - checks.scope_allowed True
#   - context_binding.head_sha == runtime --diff-head-ref SHA
#   - context_binding.changed_files_count matches the actual diff
#   - context_binding.diff_digest is a 64-hex SHA256
# ---------------------------------------------------------------------------


def _make_dual_ref_dogfood_repo(tmp_path: Path, head_only_files: list[str]) -> tuple[Path, str, str]:
    """Build a deterministic git repo with two commits on two branches.

    Base commit on ``main`` ships the AGENTS.md + gpp_status.v1.json +
    scripts/gpp_next.py minimal preflight surface
    ``scripts/local_gpp_gate.py`` expects. The head branch ``feature-x``
    adds the files listed in ``head_only_files`` so the
    ``git diff main...feature-x`` matches those paths exactly.

    Returns the repo path, the base SHA, and the head SHA.
    """

    import subprocess

    repo = tmp_path / "demo-repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def git_capture(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
        ).strip()

    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
    )
    git("config", "user.email", "dogfood@example.com")
    git("config", "user.name", "Dogfood")
    git("config", "commit.gpgsign", "false")

    # Minimal repo operating contract + GPP status file + startup command
    # so _evaluate_startup_preflight can succeed inside the tmp repo.
    (repo / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    plans_dir = repo / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "gpp_status.v1.json").write_text(
        json.dumps(
            {
                "current_wp": {"id": "GPP-2", "status": "closed"},
                "support_widening_allowed": False,
                "production_platform_claim_allowed": False,
                "live_adapter_execution_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    # Minimal gpp_next.py: accept the flags the gate passes, exit 0. The
    # gate calls it with --status-path <path> --skip-git as a subprocess
    # (see _evaluate_startup_preflight).
    (scripts_dir / "gpp_next.py").write_text(
        "import argparse, sys\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--status-path')\n"
        "parser.add_argument('--skip-git', action='store_true')\n"
        "parser.parse_known_args()\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    git("add", "AGENTS.md", ".claude/plans/gpp_status.v1.json", "scripts/gpp_next.py")
    git("commit", "-m", "base")
    base_sha = git_capture("rev-parse", "HEAD")

    # Head branch adds the head-only files so the diff matches.
    git("checkout", "-b", "feature-x")
    for fname in head_only_files:
        target = repo / fname
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("dogfood feature content\n", encoding="utf-8")
    git("add", *head_only_files)
    git("commit", "-m", "feature")
    head_sha = git_capture("rev-parse", "HEAD")

    return repo, base_sha, head_sha


def test_dual_ref_workflow_pattern_produces_accepting_runtime_artifact(tmp_path: Path) -> None:
    """End-to-end GPP-2D-3c dogfood (Codex iter-2 absorb): exercise the
    workflow's actual dual-ref invocation pattern against a deterministic
    tmp git repo and pin that the resulting gate evidence artifact is
    accepting, with the context_binding.head_sha bound to the runtime
    --diff-head-ref SHA. This catches future regressions where scope
    routing stays correct but the rest of the dual-ref happy path
    silently breaks."""

    head_only_files = ["src/feature.py"]
    repo, base_sha, head_sha = _make_dual_ref_dogfood_repo(tmp_path, head_only_files)

    reviewer_evidence = {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": "Halildeu/ao-kernel",
        "work_package": "GPP-2",
        "implementer": {"agent": "claude", "provider": "anthropic"},
        "reviewer": {"agent": "codex", "provider": "openai", "verdict": "AGREE"},
        "scope_reviewed": {
            "base_ref": "main",
            "head_ref": "feature-x",
            "changed_files": head_only_files,
        },
        "checks_considered": [
            {"name": "tests", "status": "pass"},
            {"name": "secret_scan", "status": "pass"},
        ],
        "findings": ["dual-ref dogfood test"],
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(reviewer_evidence), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    mod = _load_module()
    code = mod.main(
        [
            "--review-evidence",
            str(src),
            "--output",
            str(output),
            "--review-base-ref",
            "main",
            "--review-head-ref",
            "feature-x",
            "--diff-base-ref",
            base_sha,
            "--diff-head-ref",
            head_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--work-package",
            "GPP-2",
            "--repo-root",
            str(repo),
            "--status-path",
            str(repo / ".claude" / "plans" / "gpp_status.v1.json"),
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))

    assert code == 0, f"expected exit 0, got {code}; artifact: {artifact}"
    assert artifact["decision"] == "operator_may_merge", (
        f"dual-ref dogfood expected operator_may_merge, got {artifact['decision']}; "
        f"findings: {artifact.get('findings')}"
    )

    checks = artifact.get("checks", {})
    assert checks.get("scope_allowed") is True, (
        f"checks.scope_allowed must be True in the dual-ref happy path. got checks: {checks}"
    )

    context_binding = artifact.get("context_binding")
    assert context_binding is not None, "context_binding must be present when decision == operator_may_merge"
    assert context_binding["head_sha"] == head_sha, (
        "context_binding.head_sha must equal the --diff-head-ref runtime SHA, "
        f"not any reviewer-visible label. Expected {head_sha}, got {context_binding['head_sha']}"
    )
    assert context_binding.get("changed_files_count") == len(head_only_files), (
        "context_binding.changed_files_count must equal the actual git diff size. "
        f"Expected {len(head_only_files)}, got {context_binding.get('changed_files_count')}"
    )
    diff_digest = context_binding.get("diff_digest")
    # The gate evidence schema emits the digest as "sha256:<64-hex>" (the
    # canonical ao_kernel.ao_release_gate.diff_digest format) so the
    # required-check verifier can drop the prefix and reject any other
    # algorithm.
    assert isinstance(diff_digest, str) and diff_digest.startswith("sha256:"), (
        f"context_binding.diff_digest must start with 'sha256:' prefix; got {diff_digest!r}"
    )
    digest_hex = diff_digest.split(":", 1)[1]
    assert len(digest_hex) == 64 and all(c in "0123456789abcdef" for c in digest_hex), (
        f"context_binding.diff_digest must be sha256:<64-hex>; got {diff_digest!r}"
    )

    mod.validate_gate_evidence(artifact)


def test_actions_shape_legacy_alias_with_ref_binding_produces_accepting_artifact(tmp_path: Path) -> None:
    """End-to-end GPP-2D-3c Actions-shape dogfood (Codex iter-3+4
    absorb, threads 019e5a41 / 019e5a4b): simulate the actual GitHub
    Actions trusted-base checkout shape (``actions/checkout@v4`` with
    ``ref: github.event.pull_request.base.sha`` + ``fetch-depth: 1``)
    where branch names like ``main`` and ``codex/...`` are NOT
    guaranteed to exist as local refs. The workflow's ref-binding step
    (``git check-ref-format`` + ``git update-ref``) is what makes the
    legacy alias path (``--base-ref refs/heads/<label>`` /
    ``--head-ref refs/heads/<label>``) resolvable in that detached
    clone.

    This test exercises the full chain:

      1. Build a real two-commit repo (main + feature-x).
      2. Detach HEAD at the base SHA and delete both branch refs to
         match the workflow's detached / fetch-depth=1 shape.
      3. Run the workflow's ref-binding step (validate refs, then
         ``git update-ref`` from $BASE_REF -> $BASE_SHA and
         $HEAD_REF -> $HEAD_SHA).
      4. Run ``main()`` with --base-ref / --head-ref FULLY-QUALIFIED
         refs (``refs/heads/main`` / ``refs/heads/feature-x``) — the
         legacy alias path the workflow uses, with the iter-4
         unqualified-revision-lookup drift closed — and pin:
           - code == 0
           - artifact["decision"] == "operator_may_merge"
           - checks.scope_allowed True
           - context_binding.head_sha == API-reported head SHA
           - context_binding.changed_files_count matches diff
           - artifact passes validate_gate_evidence

    Without step 3, ``git diff refs/heads/main...refs/heads/feature-x``
    and ``git rev-parse refs/heads/feature-x`` would fail because those
    refs have no entry in the local ref DB. With step 3, the
    fully-qualified legacy alias path emits the same accepting
    artifact the workflow expects.
    """

    import subprocess

    head_only_files = ["src/feature_actions.py"]
    repo, base_sha, head_sha = _make_dual_ref_dogfood_repo(tmp_path, head_only_files)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    # Step 2: detach HEAD at base SHA + delete both branch refs. This
    # mirrors actions/checkout@v4 with ref: <SHA> and fetch-depth: 1:
    # the worktree is detached at the base SHA and the branch names
    # do not exist as local refs.
    git("checkout", "--detach", base_sha)
    git("branch", "-D", "main")
    git("branch", "-D", "feature-x")

    # Verify the detached shape: neither branch label should resolve.
    list_result = subprocess.run(
        ["git", "-C", str(repo), "branch", "-a"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "main" not in list_result.stdout and "feature-x" not in list_result.stdout, (
        f"branches must be absent after detached checkout simulation; got: {list_result.stdout!r}"
    )
    # Confirm the resolver actually fails without ref-binding (i.e.
    # the bug Codex iter-3 flagged would actually bite).
    rev_parse_before = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "main"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rev_parse_before.returncode != 0, (
        "pre-binding: branch label 'main' must NOT resolve in the detached "
        "clone, otherwise this test would not catch the ref-binding gap"
    )

    # Step 3: workflow ref-binding (validate + update-ref).
    git("check-ref-format", "refs/heads/main")
    git("check-ref-format", "refs/heads/feature-x")
    git("update-ref", "refs/heads/main", base_sha)
    git("update-ref", "refs/heads/feature-x", head_sha)

    # Confirm post-binding resolution.
    rev_parse_after = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "main"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert rev_parse_after.returncode == 0 and rev_parse_after.stdout.strip() == base_sha, (
        "post-binding: branch label 'main' must resolve to BASE_SHA"
    )

    # Step 4: legacy alias path, mirroring the workflow's
    # local_gpp_gate.py invocation.
    reviewer_evidence = {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": "Halildeu/ao-kernel",
        "work_package": "GPP-2",
        "implementer": {"agent": "claude", "provider": "anthropic"},
        "reviewer": {"agent": "codex", "provider": "openai", "verdict": "AGREE"},
        "scope_reviewed": {
            "base_ref": "refs/heads/main",
            "head_ref": "refs/heads/feature-x",
            "changed_files": head_only_files,
        },
        "checks_considered": [
            {"name": "tests", "status": "pass"},
            {"name": "secret_scan", "status": "pass"},
        ],
        "findings": ["actions-shape legacy-alias dogfood"],
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(reviewer_evidence), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    mod = _load_module()
    code = mod.main(
        [
            "--review-evidence",
            str(src),
            "--output",
            str(output),
            # Legacy alias path mirroring the workflow, with the iter-4
            # fully-qualified ref discipline so a same-named tag or
            # other object can never drift the resolution off the branch
            # ref we just bound via git update-ref.
            "--base-ref",
            "refs/heads/main",
            "--head-ref",
            "refs/heads/feature-x",
            "--repo",
            "Halildeu/ao-kernel",
            "--work-package",
            "GPP-2",
            "--repo-root",
            str(repo),
            "--status-path",
            str(repo / ".claude" / "plans" / "gpp_status.v1.json"),
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))

    assert code == 0, f"expected exit 0, got {code}; artifact: {artifact}"
    assert artifact["decision"] == "operator_may_merge", (
        "actions-shape legacy-alias dogfood expected operator_may_merge, "
        f"got {artifact['decision']}; findings: {artifact.get('findings')}"
    )

    checks = artifact.get("checks", {})
    assert checks.get("scope_allowed") is True, f"checks.scope_allowed must be True after ref-binding; got {checks}"

    context_binding = artifact.get("context_binding")
    assert context_binding is not None, "context_binding must be present when decision == operator_may_merge"
    assert context_binding["head_sha"] == head_sha, (
        "context_binding.head_sha must equal the API-reported head SHA "
        f"after ref-binding. Expected {head_sha}, got {context_binding['head_sha']}"
    )
    assert context_binding.get("changed_files_count") == len(head_only_files), (
        f"changed_files_count drift: expected {len(head_only_files)}, got {context_binding.get('changed_files_count')}"
    )

    mod.validate_gate_evidence(artifact)


def test_actions_shape_fully_qualified_refs_resist_tag_branch_ambiguity(tmp_path: Path) -> None:
    """End-to-end GPP-2D-3c ambiguity dogfood (Codex iter-4 absorb,
    thread 019e5a4b): Git's unqualified revision lookup can drift
    from a branch label to a same-named tag (or any other object),
    silently breaking the gate evidence ``context_binding.head_sha``
    contract. Passing fully-qualified refs (``refs/heads/<label>``)
    instead of unqualified labels pins resolution to the local
    branch ref the workflow's ref-binding step just created, and
    rejects same-named tag ambiguity.

    Test setup:
      1. Build the standard dogfood repo (main + feature-x).
      2. Detach HEAD at the base SHA and delete both branch refs
         (Actions shape).
      3. Run the workflow's ref-binding step.
      4. Create a TAG named ``feature-x`` pointing to the BASE SHA
         (not the head SHA). This is the ambiguity surface.
      5. PRE-ASSERT that ``git rev-parse feature-x`` (unqualified)
         returns the TAG's SHA (base_sha), confirming the ambiguity
         is real in this repo.
      6. PRE-ASSERT that ``git rev-parse refs/heads/feature-x``
         (fully-qualified) returns the BRANCH ref's SHA (head_sha),
         confirming the fully-qualified form bypasses the ambiguity.
      7. Run ``main()`` with --head-ref refs/heads/feature-x
         (fully-qualified) and pin context_binding.head_sha ==
         head_sha. With the unqualified label this would bind to
         base_sha (the tag's target) instead, and the gate evidence
         would be wrong without producing a parse error.
    """

    import subprocess

    head_only_files = ["src/feature_ambig.py"]
    repo, base_sha, head_sha = _make_dual_ref_dogfood_repo(tmp_path, head_only_files)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def git_capture(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            text=True,
        ).strip()

    # Step 2: detached shape.
    git("checkout", "--detach", base_sha)
    git("branch", "-D", "main")
    git("branch", "-D", "feature-x")

    # Step 3: workflow ref-binding.
    git("check-ref-format", "refs/heads/main")
    git("check-ref-format", "refs/heads/feature-x")
    git("update-ref", "refs/heads/main", base_sha)
    git("update-ref", "refs/heads/feature-x", head_sha)

    # Step 4: create a tag named "feature-x" pointing to BASE SHA
    # (NOT head SHA). This is the ambiguity surface.
    git("tag", "feature-x", base_sha)

    # Step 5: confirm the ambiguity is real for the unqualified label.
    # Git's unqualified rev-parse prefers the tag here, returning
    # base_sha rather than the branch ref's head_sha. (Some Git
    # versions may pick differently; the key invariant we're pinning
    # is that the fully-qualified ref ALWAYS gives the branch.)
    unqualified_sha = git_capture("rev-parse", "feature-x")
    assert unqualified_sha != head_sha, (
        "ambiguity precondition: unqualified 'feature-x' rev-parse must "
        f"NOT equal the branch's head_sha when a same-named tag exists. "
        f"Got {unqualified_sha} == head_sha {head_sha}; the ambiguity "
        "surface this test needs is absent."
    )

    # Step 6: confirm the fully-qualified ref pins to the branch.
    fq_sha = git_capture("rev-parse", "refs/heads/feature-x")
    assert fq_sha == head_sha, f"refs/heads/feature-x must resolve to the branch's head_sha {head_sha}, got {fq_sha}"

    # Step 7: invoke main() with fully-qualified refs (workflow contract).
    reviewer_evidence = {
        "schema_version": "local-ai-review-evidence.v1",
        "repo": "Halildeu/ao-kernel",
        "work_package": "GPP-2",
        "implementer": {"agent": "claude", "provider": "anthropic"},
        "reviewer": {"agent": "codex", "provider": "openai", "verdict": "AGREE"},
        "scope_reviewed": {
            "base_ref": "refs/heads/main",
            "head_ref": "refs/heads/feature-x",
            "changed_files": head_only_files,
        },
        "checks_considered": [
            {"name": "tests", "status": "pass"},
            {"name": "secret_scan", "status": "pass"},
        ],
        "findings": ["actions-shape ambiguity dogfood"],
        "secrets_recorded": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
    }
    src = tmp_path / "reviewer.json"
    src.write_text(json.dumps(reviewer_evidence), encoding="utf-8")
    output = tmp_path / "gate-evidence.json"

    mod = _load_module()
    code = mod.main(
        [
            "--review-evidence",
            str(src),
            "--output",
            str(output),
            "--base-ref",
            "refs/heads/main",
            "--head-ref",
            "refs/heads/feature-x",
            "--repo",
            "Halildeu/ao-kernel",
            "--work-package",
            "GPP-2",
            "--repo-root",
            str(repo),
            "--status-path",
            str(repo / ".claude" / "plans" / "gpp_status.v1.json"),
        ]
    )

    artifact = json.loads(output.read_text(encoding="utf-8"))

    assert code == 0, f"expected exit 0, got {code}; artifact: {artifact}"
    assert artifact["decision"] == "operator_may_merge", (
        "fully-qualified refs must produce operator_may_merge even with a "
        f"same-named tag pointing to a different SHA. Got decision "
        f"{artifact['decision']}; findings: {artifact.get('findings')}"
    )

    context_binding = artifact.get("context_binding")
    assert context_binding is not None, "context_binding must be present"
    # The crucial pin: with the same-named tag pointing at base_sha,
    # an unqualified label would bind here to base_sha. The
    # fully-qualified ref pins to head_sha — that is what this slice's
    # workflow contract guarantees.
    assert context_binding["head_sha"] == head_sha, (
        "context_binding.head_sha must equal the BRANCH ref's head_sha "
        f"({head_sha}), not the same-named tag's SHA ({base_sha}). "
        f"Got {context_binding['head_sha']}. A regression that switched "
        "the workflow back to unqualified labels would bind to the wrong "
        "object here."
    )

    mod.validate_gate_evidence(artifact)
