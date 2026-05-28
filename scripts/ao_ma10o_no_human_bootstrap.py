#!/usr/bin/env python3
"""AO-MA-10O constrained no-human GitHub enforcement bootstrap.

Dry-run is the default. ``--apply`` is intentionally guarded and may only be
used after PR #682, PR #684, and the AO-MA-10O supersession PR have landed.

The script is narrow by construction: it can only prepare the AO-MA-10 live
autonomous merge enforcement cutover for Halildeu/ao-kernel main.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPOSITORY = "Halildeu/ao-kernel"
BRANCH = "main"
RULESET_ID = 16803733
GITHUB_ACTIONS_INTEGRATION_ID = 15368
TECHNICAL_CHECK = "ao-release-gate-technical"
REVIEW_CHECK = "ao-release-gate-review"
CLASSIC_CI_CHECKS = (
    "lint",
    "test (3.11)",
    "test (3.12)",
    "test (3.13)",
    "coverage",
    "typecheck",
    "packaging-smoke",
)
PRESERVED_RULE_TYPES = ("deletion", "non_fast_forward")
APPLY_CONFIRMATION = "AO-MA-10O-CC9-SUPERSESSION-APPLY"
ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_PRS = (682, 684)
SUPERSESSION_DOC = ROOT / ".claude/plans/AO-MA-10O-CC9-NO-HUMAN-BOOTSTRAP-SUPERSESSION.md"
SUPERSESSION_MARKER = "AO-MA-10O - CC-9 No-Human Bootstrap Supersession"


class BootstrapRefusal(RuntimeError):
    """Raised when the requested bootstrap would exceed the supersession."""


@dataclass(frozen=True)
class BootstrapPlan:
    repository: str
    branch: str
    ruleset_id: int
    ruleset_patch: dict[str, Any]
    branch_review_mutation: dict[str, Any]
    hard_stops: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": "ao-ma-10o-no-human-bootstrap-plan.v1",
            "artifact_kind": "ao_ma_10o_no_human_bootstrap_plan",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "repository": self.repository,
            "branch": self.branch,
            "ruleset_id": self.ruleset_id,
            "release_authority": "ao-release-gate+github-ruleset",
            "ai_output_release_authority": False,
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
            "ruleset_patch": self.ruleset_patch,
            "branch_review_mutation": self.branch_review_mutation,
            "hard_stops": self.hard_stops,
            "apply_requires_pre_and_post_readiness_snapshots": True,
        }


def _run_json(command: list[str], *, timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise BootstrapRefusal(f"command failed: {' '.join(command)}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise BootstrapRefusal(f"command returned invalid json: {' '.join(command)}") from exc
    if not isinstance(data, dict):
        raise BootstrapRefusal(f"command returned non-object json: {' '.join(command)}")
    return data


def _run_text(command: list[str], *, timeout: int = 30) -> str:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    if proc.returncode != 0:
        raise BootstrapRefusal(f"command failed: {' '.join(command)}")
    return proc.stdout.strip()


def _gh_api_json(gh_bin: str, path: str) -> dict[str, Any]:
    return _run_json([gh_bin, "api", path])


def _gh_pr_json(gh_bin: str, number: int) -> dict[str, Any]:
    return _run_json([gh_bin, "pr", "view", str(number), "--repo", REPOSITORY, "--json", "state,headRefOid"])


def _required_status_rule() -> dict[str, Any]:
    return {
        "type": "required_status_checks",
        "parameters": {
            "strict_required_status_checks_policy": True,
            "required_status_checks": [
                {"context": TECHNICAL_CHECK, "integration_id": GITHUB_ACTIONS_INTEGRATION_ID},
                {"context": REVIEW_CHECK, "integration_id": GITHUB_ACTIONS_INTEGRATION_ID},
            ],
        },
    }


def _preserved_rules(current_rules: list[Any]) -> list[dict[str, Any]]:
    preserved: dict[str, dict[str, Any]] = {}
    for item in current_rules:
        if not isinstance(item, dict):
            continue
        rule_type = item.get("type")
        if rule_type in PRESERVED_RULE_TYPES:
            preserved[str(rule_type)] = {"type": str(rule_type)}
    missing = [rule for rule in PRESERVED_RULE_TYPES if rule not in preserved]
    if missing:
        raise BootstrapRefusal(f"ruleset is missing preserved rule types: {', '.join(missing)}")
    return [preserved[rule_type] for rule_type in PRESERVED_RULE_TYPES]


def _ruleset_targets_main(ruleset: dict[str, Any]) -> bool:
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        return False
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return False
    include = ref_name.get("include")
    exclude = ref_name.get("exclude")
    include_values = include if isinstance(include, list) else []
    exclude_values = exclude if isinstance(exclude, list) else []
    accepted = {"~DEFAULT_BRANCH", "refs/heads/main", "main"}
    if any(item in exclude_values for item in accepted):
        return False
    return any(item in include_values for item in accepted)


def _branch_required_checks(branch_protection: dict[str, Any]) -> set[str]:
    checks = set()
    status_checks = branch_protection.get("required_status_checks")
    if not isinstance(status_checks, dict):
        return checks
    for context in status_checks.get("contexts") or []:
        if isinstance(context, str):
            checks.add(context)
    for item in status_checks.get("checks") or []:
        if isinstance(item, dict) and isinstance(item.get("context"), str):
            checks.add(item["context"])
    return checks


def build_plan(*, ruleset: dict[str, Any], branch_protection: dict[str, Any]) -> BootstrapPlan:
    if ruleset.get("id") != RULESET_ID:
        raise BootstrapRefusal("unexpected ruleset id")
    if ruleset.get("target") != "branch":
        raise BootstrapRefusal("ruleset target is not branch")
    if ruleset.get("enforcement") != "active":
        raise BootstrapRefusal("ruleset enforcement is not active")
    if not _ruleset_targets_main(ruleset):
        raise BootstrapRefusal("ruleset does not target main or default branch")
    if ruleset.get("bypass_actors") not in ([], None):
        raise BootstrapRefusal("ruleset bypass_actors must be empty")

    existing_rules = ruleset.get("rules")
    if not isinstance(existing_rules, list):
        raise BootstrapRefusal("ruleset rules must be a list")

    branch_checks = _branch_required_checks(branch_protection)
    missing_classic = [check for check in CLASSIC_CI_CHECKS if check not in branch_checks]
    if missing_classic:
        raise BootstrapRefusal(f"classic CI checks missing from branch protection: {', '.join(missing_classic)}")

    enforce_admins = branch_protection.get("enforce_admins")
    if not isinstance(enforce_admins, dict) or enforce_admins.get("enabled") is not True:
        raise BootstrapRefusal("branch protection enforce_admins=true must be preserved")

    rules = [*_preserved_rules(existing_rules), _required_status_rule()]
    ruleset_patch = {
        "name": ruleset.get("name") or "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": ruleset.get("conditions") or {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": rules,
    }
    return BootstrapPlan(
        repository=REPOSITORY,
        branch=BRANCH,
        ruleset_id=RULESET_ID,
        ruleset_patch=ruleset_patch,
        branch_review_mutation={
            "method": "DELETE",
            "path": f"repos/{REPOSITORY}/branches/{BRANCH}/protection/required_pull_request_reviews",
            "purpose": "remove native human review gate after ao-release-gate-review becomes the high-risk authority",
            "preserve_enforce_admins": True,
            "preserve_classic_ci_checks": list(CLASSIC_CI_CHECKS),
        },
        hard_stops=[
            "no_admin_bypass",
            "no_ruleset_bypass_actors",
            "no_classic_ci_removal",
            "no_support_widening",
            "no_production_platform_claim",
            "no_live_adapter_execution",
            "no_testai_smee_dependency",
            "ai_output_is_evidence_not_release_authority",
        ],
    )


def collect_plan(gh_bin: str) -> BootstrapPlan:
    ruleset = _gh_api_json(gh_bin, f"repos/{REPOSITORY}/rulesets/{RULESET_ID}")
    protection = _gh_api_json(gh_bin, f"repos/{REPOSITORY}/branches/{BRANCH}/protection")
    return build_plan(ruleset=ruleset, branch_protection=protection)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assert_clean_synced_main() -> None:
    branch = _run_text(["git", "branch", "--show-current"])
    if branch != BRANCH:
        raise BootstrapRefusal("apply must run from main")
    status = _run_text(["git", "status", "--short"])
    if status:
        raise BootstrapRefusal("apply requires a clean working tree")
    divergence = _run_text(["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"])
    if divergence.replace("\t", " ") != "0 0":
        raise BootstrapRefusal("main must be synced with origin/main")


def assert_gpp_guard_flags_false() -> None:
    output = _run_text([sys.executable, "scripts/gpp_next.py"], timeout=60)
    required = (
        "Support widening allowed: false",
        "Production platform claim allowed: false",
        "Live adapter execution allowed: false",
    )
    if any(line not in output for line in required):
        raise BootstrapRefusal("gpp guard flags are not all false")


def assert_dependency_prs_merged(gh_bin: str) -> None:
    for number in DEPENDENCY_PRS:
        payload = _gh_pr_json(gh_bin, number)
        if payload.get("state") != "MERGED":
            raise BootstrapRefusal(f"dependency PR #{number} is not merged")


def assert_supersession_present() -> None:
    if not SUPERSESSION_DOC.exists():
        raise BootstrapRefusal("AO-MA-10O supersession document is missing")
    text = SUPERSESSION_DOC.read_text(encoding="utf-8")
    if SUPERSESSION_MARKER not in text:
        raise BootstrapRefusal("AO-MA-10O supersession document marker is missing")


def assert_accepted_dry_run_plan_matches(path: Path, plan: BootstrapPlan) -> None:
    if not path.exists():
        raise BootstrapRefusal("accepted dry-run plan is missing")
    try:
        accepted = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BootstrapRefusal("accepted dry-run plan is invalid json") from exc
    current = plan.to_json()
    for key in ("repository", "branch", "ruleset_id", "ruleset_patch", "branch_review_mutation"):
        if accepted.get(key) != current.get(key):
            raise BootstrapRefusal(f"accepted dry-run plan does not match current plan: {key}")


def assert_apply_preconditions(*, gh_bin: str, plan: BootstrapPlan, accepted_dry_run_plan: Path) -> None:
    assert_clean_synced_main()
    assert_supersession_present()
    assert_gpp_guard_flags_false()
    assert_dependency_prs_merged(gh_bin)
    assert_accepted_dry_run_plan_matches(accepted_dry_run_plan, plan)


def collect_readiness_snapshot(*, gh_bin: str, output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ao_ma10_github_readiness_snapshot.py"),
            "--repository",
            REPOSITORY,
            "--branch",
            BRANCH,
            "--gh-bin",
            gh_bin,
            "--output",
            str(output),
        ],
        check=True,
        cwd=ROOT,
        timeout=60,
    )


def apply_plan(*, gh_bin: str, plan: BootstrapPlan) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        json.dump(plan.ruleset_patch, handle)
        handle.write("\n")
        payload_path = handle.name
    try:
        subprocess.run(
            [
                gh_bin,
                "api",
                "--method",
                "PUT",
                f"repos/{REPOSITORY}/rulesets/{RULESET_ID}",
                "--input",
                payload_path,
            ],
            check=True,
            timeout=30,
        )
        subprocess.run(
            [
                gh_bin,
                "api",
                "--method",
                "DELETE",
                f"repos/{REPOSITORY}/branches/{BRANCH}/protection/required_pull_request_reviews",
            ],
            check=True,
            timeout=30,
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gh-bin", default="gh")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pre-snapshot-output", default="")
    parser.add_argument("--post-snapshot-output", default="")
    parser.add_argument("--accepted-dry-run-plan", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--confirmation",
        default="",
        help=f"Required with --apply. Must equal {APPLY_CONFIRMATION}.",
    )
    args = parser.parse_args(argv)

    plan = collect_plan(args.gh_bin)
    _write_json(Path(args.output), plan.to_json())

    if args.apply:
        if not args.pre_snapshot_output or not args.post_snapshot_output:
            raise BootstrapRefusal("--apply requires --pre-snapshot-output and --post-snapshot-output")
        if not args.accepted_dry_run_plan:
            raise BootstrapRefusal("--apply requires --accepted-dry-run-plan")
        if args.confirmation != APPLY_CONFIRMATION:
            raise BootstrapRefusal("missing AO-MA-10O apply confirmation token")
        if os.environ.get("AO_MA10O_ALLOW_RULESET_MUTATION") != APPLY_CONFIRMATION:
            raise BootstrapRefusal("AO_MA10O_ALLOW_RULESET_MUTATION confirmation env is missing")
        assert_apply_preconditions(
            gh_bin=args.gh_bin,
            plan=plan,
            accepted_dry_run_plan=Path(args.accepted_dry_run_plan),
        )
        collect_readiness_snapshot(gh_bin=args.gh_bin, output=Path(args.pre_snapshot_output))
        apply_plan(gh_bin=args.gh_bin, plan=plan)
        collect_readiness_snapshot(gh_bin=args.gh_bin, output=Path(args.post_snapshot_output))
    else:
        print("dry-run only; no GitHub mutations performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
