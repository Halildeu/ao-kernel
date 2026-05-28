from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / ".claude/plans/AO-MA-10O-CC9-NO-HUMAN-BOOTSTRAP-SUPERSESSION.md"
PCC = ROOT / ".claude/plans/PROGRAM-CHANGE-CONTROL.md"
SCRIPT = ROOT / "scripts/ao_ma10o_no_human_bootstrap.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_script():
    spec = importlib.util.spec_from_file_location("ao_ma10o_no_human_bootstrap", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ao_ma10o_decision_record_pins_dependencies_and_scope() -> None:
    text = _text(DOC)
    assert "https://github.com/Halildeu/ao-kernel/issues/683" in text
    assert "PR #682 and PR #684 landing first" in text
    assert "Supersedes:" in text and "PROGRAM-CHANGE-CONTROL.md` CC-9" in text
    assert "Only `scripts/ao_ma10o_no_human_bootstrap.py --apply`" in text
    assert "Halildeu/ao-kernel" in text
    assert "ruleset `16803733`" in text
    assert "--accepted-dry-run-plan" in text
    assert "PR #682 or PR #684 is not merged" in text
    assert "working tree is not clean `main` synced with `origin/main`" in text


def test_ao_ma10o_policy_updates_cc9_with_narrow_no_human_exception() -> None:
    text = _text(PCC)
    assert "AO-MA-10O narrow supersession for CC-9" in text
    assert "CC-9 remains the default rule." in text
    assert "scripts/ao_ma10o_no_human_bootstrap.py --apply" in text
    assert "ao-release-gate-technical" in text
    assert "ao-release-gate-review" in text
    assert "bypass_actors=[]" in text
    assert "preserve the classic CI required checks" in text


def test_ao_ma10o_script_is_narrowly_bound_to_expected_repo_ruleset_and_checks() -> None:
    script = _load_script()
    assert script.REPOSITORY == "Halildeu/ao-kernel"
    assert script.BRANCH == "main"
    assert script.RULESET_ID == 16803733
    assert script.GITHUB_ACTIONS_INTEGRATION_ID == 15368
    assert script.TECHNICAL_CHECK == "ao-release-gate-technical"
    assert script.REVIEW_CHECK == "ao-release-gate-review"
    assert script.APPLY_CONFIRMATION == "AO-MA-10O-CC9-SUPERSESSION-APPLY"
    assert script.CLASSIC_CI_CHECKS == (
        "lint",
        "test (3.11)",
        "test (3.12)",
        "test (3.13)",
        "coverage",
        "typecheck",
        "packaging-smoke",
    )


def test_ao_ma10o_build_plan_preserves_classic_ci_and_adds_dual_release_checks() -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "contexts": list(script.CLASSIC_CI_CHECKS),
            "checks": [{"context": check, "app_id": 15368} for check in script.CLASSIC_CI_CHECKS],
        },
    }
    plan = script.build_plan(ruleset=ruleset, branch_protection=branch_protection).to_json()

    assert plan["ai_output_release_authority"] is False
    assert plan["support_widening"] is False
    assert plan["production_platform_claim"] is False
    assert plan["live_adapter_execution"] is False
    assert plan["ruleset_patch"]["bypass_actors"] == []
    rule_types = [rule["type"] for rule in plan["ruleset_patch"]["rules"]]
    assert rule_types == ["deletion", "non_fast_forward", "required_status_checks"]
    status_rule = plan["ruleset_patch"]["rules"][2]
    assert status_rule["parameters"]["required_status_checks"] == [
        {"context": "ao-release-gate-technical", "integration_id": 15368},
        {"context": "ao-release-gate-review", "integration_id": 15368},
    ]
    assert plan["branch_review_mutation"]["method"] == "DELETE"
    assert plan["branch_review_mutation"]["preserve_classic_ci_checks"] == list(script.CLASSIC_CI_CHECKS)
    assert plan["apply_requires_pre_and_post_readiness_snapshots"] is True


def test_ao_ma10o_build_plan_refuses_bypass_actors_or_missing_classic_ci() -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [{"actor_id": 1}],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {"contexts": list(script.CLASSIC_CI_CHECKS), "checks": []},
    }
    try:
        script.build_plan(ruleset=ruleset, branch_protection=branch_protection)
    except script.BootstrapRefusal as exc:
        assert "bypass_actors must be empty" in str(exc)
    else:
        raise AssertionError("expected bypass actor refusal")

    ruleset["bypass_actors"] = []
    branch_protection["required_status_checks"]["contexts"] = ["lint"]
    try:
        script.build_plan(ruleset=ruleset, branch_protection=branch_protection)
    except script.BootstrapRefusal as exc:
        assert "classic CI checks missing" in str(exc)
    else:
        raise AssertionError("expected classic CI refusal")


def test_ao_ma10o_hard_stops_are_pinned() -> None:
    text = _text(DOC)
    for phrase in (
        "No `--admin` merge.",
        "No ruleset bypass actors.",
        "No removal of classic CI requirements.",
        "No support widening.",
        "No production platform claim.",
        "No live adapter execution.",
        "No testai/smee/deployment-protection callback dependency.",
        "No treating Claude, Codex, MiniMax, or any model output as release authority.",
    ):
        assert phrase in text


def test_ao_ma10o_apply_requires_pre_and_post_snapshot_outputs(monkeypatch, tmp_path) -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "contexts": list(script.CLASSIC_CI_CHECKS),
            "checks": [{"context": check, "app_id": 15368} for check in script.CLASSIC_CI_CHECKS],
        },
    }
    plan = script.build_plan(ruleset=ruleset, branch_protection=branch_protection)

    assert plan.to_json()["apply_requires_pre_and_post_readiness_snapshots"] is True
    monkeypatch.setattr(script, "collect_plan", lambda gh_bin: plan)

    try:
        script.main(
            [
                "--output",
                str(tmp_path / "plan.json"),
                "--apply",
                "--confirmation",
                script.APPLY_CONFIRMATION,
            ]
        )
    except script.BootstrapRefusal as exc:
        assert "--apply requires --pre-snapshot-output and --post-snapshot-output" in str(exc)
    else:
        raise AssertionError("expected pre/post snapshot refusal")


def test_ao_ma10o_apply_requires_cli_and_env_confirmation(monkeypatch, tmp_path) -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "contexts": list(script.CLASSIC_CI_CHECKS),
            "checks": [{"context": check, "app_id": 15368} for check in script.CLASSIC_CI_CHECKS],
        },
    }
    plan = script.build_plan(ruleset=ruleset, branch_protection=branch_protection)
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text(json.dumps(plan.to_json(), sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(script, "collect_plan", lambda gh_bin: plan)
    args = [
        "--output",
        str(tmp_path / "plan.json"),
        "--pre-snapshot-output",
        str(tmp_path / "pre.json"),
        "--post-snapshot-output",
        str(tmp_path / "post.json"),
        "--accepted-dry-run-plan",
        str(accepted_path),
        "--apply",
    ]

    try:
        script.main(args)
    except script.BootstrapRefusal as exc:
        assert "missing AO-MA-10O apply confirmation token" in str(exc)
    else:
        raise AssertionError("expected CLI confirmation refusal")

    try:
        script.main([*args, "--confirmation", script.APPLY_CONFIRMATION])
    except script.BootstrapRefusal as exc:
        assert "AO_MA10O_ALLOW_RULESET_MUTATION confirmation env is missing" in str(exc)
    else:
        raise AssertionError("expected env confirmation refusal")


def test_ao_ma10o_refuses_ruleset_condition_not_targeting_main() -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "contexts": list(script.CLASSIC_CI_CHECKS),
            "checks": [{"context": check, "app_id": 15368} for check in script.CLASSIC_CI_CHECKS],
        },
    }
    try:
        script.build_plan(ruleset=ruleset, branch_protection=branch_protection)
    except script.BootstrapRefusal as exc:
        assert "ruleset does not target main or default branch" in str(exc)
    else:
        raise AssertionError("expected ruleset target refusal")


def test_ao_ma10o_apply_preconditions_are_fail_closed(monkeypatch, tmp_path) -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "contexts": list(script.CLASSIC_CI_CHECKS),
            "checks": [{"context": check, "app_id": 15368} for check in script.CLASSIC_CI_CHECKS],
        },
    }
    plan = script.build_plan(ruleset=ruleset, branch_protection=branch_protection)
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(script, "assert_clean_synced_main", lambda: None)
    monkeypatch.setattr(script, "assert_supersession_present", lambda: None)
    monkeypatch.setattr(script, "assert_gpp_guard_flags_false", lambda: None)
    monkeypatch.setattr(script, "assert_dependency_prs_merged", lambda gh_bin: None)

    try:
        script.assert_apply_preconditions(
            gh_bin="gh",
            plan=plan,
            accepted_dry_run_plan=accepted_path,
        )
    except script.BootstrapRefusal as exc:
        assert "accepted dry-run plan does not match current plan" in str(exc)
    else:
        raise AssertionError("expected accepted dry-run mismatch refusal")

    accepted_path.write_text(json.dumps(plan.to_json(), sort_keys=True), encoding="utf-8")
    script.assert_apply_preconditions(
        gh_bin="gh",
        plan=plan,
        accepted_dry_run_plan=accepted_path,
    )


def test_ao_ma10o_clean_synced_main_precondition_refuses_non_main_dirty_or_diverged(
    monkeypatch,
) -> None:
    script = _load_script()

    def fake_run_text_factory(outputs: dict[tuple[str, ...], str]):
        def fake_run_text(command, *, timeout=30):
            return outputs[tuple(command)]

        return fake_run_text

    cases = [
        (
            {
                ("git", "branch", "--show-current"): "feature",
            },
            "apply must run from main",
        ),
        (
            {
                ("git", "branch", "--show-current"): "main",
                ("git", "status", "--short"): " M scripts/example.py",
            },
            "apply requires a clean working tree",
        ),
        (
            {
                ("git", "branch", "--show-current"): "main",
                ("git", "status", "--short"): "",
                ("git", "rev-list", "--left-right", "--count", "HEAD...origin/main"): "1\t0",
            },
            "main must be synced with origin/main",
        ),
    ]
    for outputs, expected in cases:
        monkeypatch.setattr(script, "_run_text", fake_run_text_factory(outputs))
        try:
            script.assert_clean_synced_main()
        except script.BootstrapRefusal as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"expected refusal: {expected}")


def test_ao_ma10o_gpp_guard_precondition_refuses_true_or_missing_flags(monkeypatch) -> None:
    script = _load_script()
    for output in (
        "\n".join(
            [
                "Support widening allowed: true",
                "Production platform claim allowed: false",
                "Live adapter execution allowed: false",
            ]
        ),
        "\n".join(
            [
                "Support widening allowed: false",
                "Live adapter execution allowed: false",
            ]
        ),
    ):
        monkeypatch.setattr(script, "_run_text", lambda command, *, timeout=30: output)
        try:
            script.assert_gpp_guard_flags_false()
        except script.BootstrapRefusal as exc:
            assert "gpp guard flags are not all false" in str(exc)
        else:
            raise AssertionError("expected GPP guard flag refusal")


def test_ao_ma10o_dependency_pr_precondition_refuses_unmerged_or_unreadable_prs(
    monkeypatch,
) -> None:
    script = _load_script()

    monkeypatch.setattr(script, "_gh_pr_json", lambda gh_bin, number: {"state": "OPEN"})
    try:
        script.assert_dependency_prs_merged("gh")
    except script.BootstrapRefusal as exc:
        assert "dependency PR #682 is not merged" in str(exc)
    else:
        raise AssertionError("expected unmerged dependency PR refusal")

    def raise_read_failure(gh_bin, number):
        raise script.BootstrapRefusal("command failed: gh pr view")

    monkeypatch.setattr(script, "_gh_pr_json", raise_read_failure)
    try:
        script.assert_dependency_prs_merged("gh")
    except script.BootstrapRefusal as exc:
        assert "command failed: gh pr view" in str(exc)
    else:
        raise AssertionError("expected dependency PR read failure refusal")


def test_ao_ma10o_apply_preconditions_call_all_guards(monkeypatch, tmp_path) -> None:
    script = _load_script()
    ruleset = {
        "id": 16803733,
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
    }
    branch_protection = {
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "contexts": list(script.CLASSIC_CI_CHECKS),
            "checks": [{"context": check, "app_id": 15368} for check in script.CLASSIC_CI_CHECKS],
        },
    }
    plan = script.build_plan(ruleset=ruleset, branch_protection=branch_protection)
    accepted_path = tmp_path / "accepted.json"
    accepted_path.write_text(json.dumps(plan.to_json(), sort_keys=True), encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(script, "assert_clean_synced_main", lambda: calls.append("clean-main"))
    monkeypatch.setattr(script, "assert_supersession_present", lambda: calls.append("supersession"))
    monkeypatch.setattr(script, "assert_gpp_guard_flags_false", lambda: calls.append("gpp-flags"))
    monkeypatch.setattr(
        script,
        "assert_dependency_prs_merged",
        lambda gh_bin: calls.append(f"dependency-prs:{gh_bin}"),
    )

    script.assert_apply_preconditions(
        gh_bin="gh",
        plan=plan,
        accepted_dry_run_plan=accepted_path,
    )

    assert calls == ["clean-main", "supersession", "gpp-flags", "dependency-prs:gh"]
