#!/usr/bin/env python3
"""Local AI review gate for GPP-2A operator-merge evidence.

This gate codifies the operator's existing local trust model:

    implementer AI changes the repo
    reviewer AI reviews independently
    operator decides whether to merge

The gate consumes an independent reviewer evidence file, validates it
against a JSON Schema, runs a fixed set of fail-closed checks, and emits
a durable no-secret JSON artifact recording whether the operator may
merge.

The gate is local operator evidence only. It does not close GPP-2, change
branch protection, execute live adapters, widen support, or claim
production readiness. GPP-2 stays blocked.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

REVIEW_EVIDENCE_SCHEMA_NAME = "local-ai-review-evidence.schema.v1.json"
GATE_EVIDENCE_SCHEMA_NAME = "local-gpp-gate-evidence.schema.v1.json"

REVIEW_EVIDENCE_SCHEMA_VERSION = "local-ai-review-evidence.v1"
GATE_EVIDENCE_SCHEMA_VERSION = "local-gpp-gate-evidence.v1"

DEFAULT_STATUS_PATH = Path(".claude/plans/gpp_status.v1.json")
AGENTS_CONTRACT_PATH = Path("AGENTS.md")
STARTUP_PREFLIGHT_SCRIPT = Path("scripts/gpp_next.py")
STARTUP_PREFLIGHT_TIMEOUT_SECONDS = 30

# Conservative denylist of repository surfaces the local AI review gate is
# not permitted to recommend a merge for. These surfaces (branch
# protection, GitHub App config, live-adapter workflow dispatch) belong to
# the heavier protected-runtime path, not the local operator-merge slice.
# A reviewed change touching any of these is treated as scope mismatch and
# fails closed.
FORBIDDEN_SCOPE_SUBSTRINGS = (
    ".github/branch-protection",
    ".github/rulesets",
    ".github/workflows/live-adapter-gate",
    ".github/apps/",
    "branch_protection",
    "ruleset",
)

FORBIDDEN_FINDING_PREFIX = "FORBIDDEN:"

GATE_CHECK_NAMES = (
    "startup_preflight_passed",
    "gpp_status_checked",
    "scope_allowed",
    "tests_passed",
    "secret_scan_passed",
    "reviewer_agree",
    "cross_provider_verified",
    "forbidden_actions_absent",
)


class LocalGateInvocationError(RuntimeError):
    """Raised when the gate cannot produce a durable artifact at all.

    This is reserved for conditions where no fail-closed artifact can be
    written: a broken schema toolchain or an output-write failure. It maps
    to return code 2.

    Missing, malformed, or schema-invalid reviewer evidence is NOT an
    invocation error. Those conditions still produce a durable fail_closed
    artifact and return code 1.
    """


def repo_root_from_script() -> Path:
    """Return the repository root based on this script path."""

    return Path(__file__).resolve().parents[1]


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp with a trailing 'Z'."""

    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _schema_path(name: str) -> Path:
    """Return the bundled schema path for ``name``."""

    return repo_root_from_script() / "ao_kernel" / "defaults" / "schemas" / name


def load_review_evidence_schema() -> dict[str, Any]:
    """Load the bundled reviewer evidence JSON Schema."""

    path = _schema_path(REVIEW_EVIDENCE_SCHEMA_NAME)
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError as exc:
        raise LocalGateInvocationError(f"reviewer evidence schema not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LocalGateInvocationError(f"reviewer evidence schema is not valid JSON: {exc}") from exc


def load_gate_evidence_schema() -> dict[str, Any]:
    """Load the bundled gate evidence JSON Schema."""

    path = _schema_path(GATE_EVIDENCE_SCHEMA_NAME)
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError as exc:
        raise LocalGateInvocationError(f"gate evidence schema not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LocalGateInvocationError(f"gate evidence schema is not valid JSON: {exc}") from exc


def load_review_evidence(path: Path) -> dict[str, Any] | None:
    """Load and schema-validate a reviewer evidence file.

    Returns the parsed payload when it is present and schema-valid.
    Returns ``None`` when the file is missing, is not valid JSON, or
    fails schema validation; the caller treats ``None`` as a
    fail-closed input rather than an invocation error so the gate can
    still emit a durable fail-closed artifact.

    Raises ``LocalGateInvocationError`` only when the schema toolchain
    itself is broken.
    """

    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    schema = load_review_evidence_schema()
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:  # pragma: no cover - bundled schema is valid
        raise LocalGateInvocationError(f"reviewer evidence schema is invalid: {exc}") from exc
    try:
        validator.validate(payload)
    except ValidationError:
        return None
    return cast(dict[str, Any], payload)


def _all_checks(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Return every ``checks_considered`` entry matching ``name``.

    A required check is evaluated over all entries with the given name so a
    failing entry cannot hide behind an earlier passing duplicate.
    """

    checks = payload.get("checks_considered", [])
    if not isinstance(checks, list):
        return []
    return [check for check in checks if isinstance(check, dict) and check.get("name") == name]


def actual_changed_files(
    repo_root: Path, base_ref: str, head_ref: str
) -> list[str] | None:
    """Return the sorted git diff path list for ``base_ref...head_ref``.

    Uses ``git diff --name-only <base>...<head>`` (three-dot) so the diff
    is measured from the merge base, matching how a reviewer evaluates a
    branch. Returns ``None`` when git is unavailable, the directory is not
    a repository, the refs are invalid, or the command otherwise fails;
    the caller treats ``None`` as "scope cannot be verified" and fails the
    scope check closed.
    """

    if not base_ref or not head_ref:
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", f"{base_ref}...{head_ref}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=STARTUP_PREFLIGHT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return sorted(line for line in completed.stdout.splitlines() if line.strip())


def _evaluate_startup_preflight(repo_root: Path, status_path: Path, findings: list[str]) -> bool:
    """Run the real startup preflight for the local gate.

    The preflight requires the repo operating contract and GPP status file
    to exist and, on top of that, runs the canonical startup command
    ``scripts/gpp_next.py`` as a subprocess. The startup command must exit
    0; a missing script, a subprocess error, a timeout, or a non-zero exit
    fails the preflight closed. This makes ``startup_preflight_passed`` an
    honest check: it executes the same startup command an operator session
    runs, not just a file-existence probe.
    """

    agents_path = repo_root / AGENTS_CONTRACT_PATH
    ok = True
    if not agents_path.exists():
        findings.append(f"startup preflight: missing repo operating contract {AGENTS_CONTRACT_PATH}")
        ok = False
    if not status_path.exists():
        findings.append(f"startup preflight: missing GPP status file {status_path}")
        ok = False

    preflight_script = repo_root / STARTUP_PREFLIGHT_SCRIPT
    if not preflight_script.exists():
        findings.append(
            f"startup preflight: missing startup command {STARTUP_PREFLIGHT_SCRIPT}"
        )
        return False
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(preflight_script),
                "--status-path",
                str(status_path),
                "--skip-git",
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=STARTUP_PREFLIGHT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        findings.append(
            f"startup preflight: startup command {STARTUP_PREFLIGHT_SCRIPT} timed out "
            f"after {STARTUP_PREFLIGHT_TIMEOUT_SECONDS}s"
        )
        return False
    except OSError as exc:
        findings.append(
            f"startup preflight: startup command {STARTUP_PREFLIGHT_SCRIPT} could not run: {exc}"
        )
        return False
    if completed.returncode != 0:
        findings.append(
            f"startup preflight: startup command {STARTUP_PREFLIGHT_SCRIPT} exited "
            f"{completed.returncode}, expected 0"
        )
        return False
    return ok


def _evaluate_gpp_status(status_path: Path, findings: list[str]) -> bool:
    """Confirm GPP-2 is blocked and the promotion guards are all false."""

    if not status_path.exists():
        findings.append(f"gpp status: file not found {status_path}")
        return False
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(f"gpp status: unreadable status file: {exc}")
        return False
    if not isinstance(payload, dict):
        findings.append("gpp status: payload is not a JSON object")
        return False

    current_wp = payload.get("current_wp")
    if not isinstance(current_wp, dict):
        findings.append("gpp status: current_wp is missing or malformed")
        return False
    if current_wp.get("id") != "GPP-2":
        findings.append(
            f"gpp status: current_wp.id is {current_wp.get('id')!r}, expected 'GPP-2'"
        )
        return False
    if current_wp.get("status") != "blocked":
        findings.append(
            f"gpp status: current work package status is {current_wp.get('status')!r}, expected 'blocked'"
        )
        return False

    ok = True
    for guard in (
        "support_widening_allowed",
        "production_platform_claim_allowed",
        "live_adapter_execution_allowed",
    ):
        if payload.get(guard) is not False:
            findings.append(f"gpp status: {guard} must be false, found {payload.get(guard)!r}")
            ok = False
    return ok


def _evaluate_scope(
    review: dict[str, Any], actual_files: list[str] | None, findings: list[str]
) -> bool:
    """Confirm the reviewed scope is real, non-empty, and forbidden-path free.

    The reviewer-declared ``changed_files`` list is not trusted on its own:
    it is verified against the actual git diff (``actual_files``). When the
    actual diff is unavailable the scope check fails closed, and when the
    declared list does not exactly match the actual diff the scope check
    fails closed and the finding reports the symmetric difference.
    """

    scope = review.get("scope_reviewed")
    if not isinstance(scope, dict):
        findings.append("scope: scope_reviewed is missing or malformed")
        return False
    changed_files = scope.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        findings.append("scope: changed_files must be a non-empty list")
        return False
    if not all(isinstance(item, str) and item for item in changed_files):
        findings.append("scope: changed_files must contain only non-empty strings")
        return False

    ok = True
    for path in changed_files:
        for forbidden in FORBIDDEN_SCOPE_SUBSTRINGS:
            if forbidden in path:
                findings.append(
                    f"scope: changed file {path!r} touches forbidden surface {forbidden!r}"
                )
                ok = False

    if actual_files is None:
        findings.append(
            "scope: actual git diff unavailable (git skipped or failed); "
            "cannot verify reviewer-declared scope"
        )
        return False

    declared = set(changed_files)
    actual = set(actual_files)
    if declared != actual:
        missing_from_reviewer = sorted(actual - declared)
        extra_in_reviewer = sorted(declared - actual)
        findings.append(
            "scope: reviewer-declared changed_files does not match the actual git diff "
            f"({len(missing_from_reviewer)} missing from reviewer, "
            f"{len(extra_in_reviewer)} extra in reviewer); "
            f"missing={missing_from_reviewer} extra={extra_in_reviewer}"
        )
        ok = False
    return ok


def _evaluate_tests(review: dict[str, Any], findings: list[str]) -> bool:
    """Confirm every recorded 'tests' check passed.

    All ``tests`` entries are evaluated, so a duplicate failing entry
    cannot hide behind an earlier passing one.
    """

    checks = _all_checks(review, "tests")
    if not checks:
        findings.append("tests: reviewer evidence has no 'tests' check entry")
        return False
    failing = [check for check in checks if check.get("status") != "pass"]
    if failing:
        findings.append(
            f"tests: {len(failing)} of {len(checks)} 'tests' check entries are not 'pass'"
        )
        return False
    return True


def _evaluate_secret_scan(review: dict[str, Any], findings: list[str]) -> bool:
    """Confirm every 'secret_scan' check passed and no secrets were recorded.

    All ``secret_scan`` entries are evaluated, so a duplicate failing
    entry cannot hide behind an earlier passing one.
    """

    ok = True
    checks = _all_checks(review, "secret_scan")
    if not checks:
        findings.append("secret scan: reviewer evidence has no 'secret_scan' check entry")
        ok = False
    else:
        failing = [check for check in checks if check.get("status") != "pass"]
        if failing:
            findings.append(
                f"secret scan: {len(failing)} of {len(checks)} 'secret_scan' check "
                "entries are not 'pass'"
            )
            ok = False
    if review.get("secrets_recorded") is not False:
        findings.append("secret scan: secrets_recorded must be false")
        ok = False
    return ok


def _evaluate_reviewer_agree(review: dict[str, Any], findings: list[str]) -> bool:
    """Confirm the reviewer verdict is 'AGREE'."""

    reviewer = review.get("reviewer")
    if not isinstance(reviewer, dict):
        findings.append("reviewer verdict: reviewer block is missing or malformed")
        return False
    verdict = reviewer.get("verdict")
    if verdict != "AGREE":
        findings.append(f"reviewer verdict: verdict is {verdict!r}, expected 'AGREE'")
        return False
    return True


def _evaluate_cross_provider(review: dict[str, Any], findings: list[str]) -> bool:
    """Confirm the implementer and reviewer providers differ."""

    implementer = review.get("implementer")
    reviewer = review.get("reviewer")
    if not isinstance(implementer, dict) or not isinstance(reviewer, dict):
        findings.append("cross-provider: implementer or reviewer block is missing or malformed")
        return False
    implementer_provider = implementer.get("provider")
    reviewer_provider = reviewer.get("provider")
    if implementer_provider == reviewer_provider:
        findings.append(
            "cross-provider: implementer and reviewer share provider "
            f"{implementer_provider!r}; cross-provider review is required"
        )
        return False
    return True


def _evaluate_forbidden_actions(review: dict[str, Any], findings: list[str]) -> bool:
    """Confirm the reviewer evidence is free of forbidden actions."""

    ok = True
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        if review.get(flag) is not False:
            findings.append(f"forbidden actions: {flag} must be false, found {review.get(flag)!r}")
            ok = False
    review_findings = review.get("findings", [])
    if isinstance(review_findings, list):
        for i, entry in enumerate(review_findings):
            if isinstance(entry, str) and entry.startswith(FORBIDDEN_FINDING_PREFIX):
                findings.append(
                    "forbidden actions: reviewer evidence contains a "
                    f"FORBIDDEN-prefixed finding at index {i}"
                )
                ok = False
    return ok


def evaluate_gate(
    review: dict[str, Any] | None,
    *,
    repo_root: Path,
    status_path: Path,
    actual_files: list[str] | None,
) -> tuple[dict[str, bool], list[str]]:
    """Run all gate checks and return (check booleans, findings).

    ``review`` is ``None`` when the reviewer evidence file is missing or
    schema-invalid; in that case every reviewer-dependent check fails
    closed.

    ``actual_files`` is the actual git diff path list for the reviewed
    branch (or ``None`` when git was skipped or unavailable). The scope
    check verifies the reviewer-declared changed-files list against it and
    fails closed when it is ``None`` or does not match.
    """

    findings: list[str] = []
    checks: dict[str, bool] = {name: False for name in GATE_CHECK_NAMES}

    checks["startup_preflight_passed"] = _evaluate_startup_preflight(repo_root, status_path, findings)
    checks["gpp_status_checked"] = _evaluate_gpp_status(status_path, findings)

    if review is None:
        findings.append(
            "reviewer evidence: missing or schema-invalid reviewer evidence; failing closed"
        )
        return checks, findings

    checks["scope_allowed"] = _evaluate_scope(review, actual_files, findings)
    checks["tests_passed"] = _evaluate_tests(review, findings)
    checks["secret_scan_passed"] = _evaluate_secret_scan(review, findings)
    checks["reviewer_agree"] = _evaluate_reviewer_agree(review, findings)
    checks["cross_provider_verified"] = _evaluate_cross_provider(review, findings)
    checks["forbidden_actions_absent"] = _evaluate_forbidden_actions(review, findings)
    return checks, findings


def _reviewer_findings_count(review: dict[str, Any] | None) -> int:
    """Return the count of reviewer-authored finding strings.

    Only the count is carried into the gate artifact; the reviewer's free
    text is never propagated, so a sentinel placed in a reviewer finding
    cannot leak through the gate output.
    """

    if review is None:
        return 0
    review_findings = review.get("findings", [])
    if not isinstance(review_findings, list):
        return 0
    return len(review_findings)


def build_gate_evidence(
    *,
    review: dict[str, Any] | None,
    checks: dict[str, bool],
    gate_findings: list[str],
    repo: str,
    work_package: str,
    generated_at: str,
) -> dict[str, Any]:
    """Build the no-secret gate evidence artifact.

    The artifact shape is fixed: only check booleans, the decision,
    gate-authored finding strings, the reviewer finding count, the
    constant guard flags, and the repo/work-package refs. Reviewer free
    text is never embedded; ``findings`` holds only gate-authored strings.
    """

    decision = "operator_may_merge" if all(checks.values()) else "fail_closed"
    findings = list(gate_findings)
    return {
        "schema_version": GATE_EVIDENCE_SCHEMA_VERSION,
        "decision": decision,
        "repo": repo,
        "work_package": work_package,
        "generated_at": generated_at,
        "checks": {name: bool(checks[name]) for name in GATE_CHECK_NAMES},
        "findings": findings,
        "reviewer_findings_count": _reviewer_findings_count(review),
        "gpp_2_status": "blocked",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }


def validate_gate_evidence(artifact: object) -> None:
    """Validate a gate evidence artifact against the bundled schema."""

    schema = load_gate_evidence_schema()
    try:
        validator = Draft202012Validator(schema)
    except SchemaError as exc:  # pragma: no cover - bundled schema is valid
        raise LocalGateInvocationError(f"gate evidence schema is invalid: {exc}") from exc
    try:
        validator.validate(artifact)
    except ValidationError as exc:  # pragma: no cover - builder output is well-formed
        raise LocalGateInvocationError(f"gate evidence artifact failed schema validation: {exc.message}") from exc


def write_gate_evidence(path: Path, artifact: dict[str, Any]) -> None:
    """Write a validated gate evidence artifact to ``path``.

    An output-write failure (``mkdir`` or ``write_text`` raising
    ``OSError``) is wrapped as ``LocalGateInvocationError`` because the
    gate could not produce durable evidence; that maps to return code 2.
    """

    validate_gate_evidence(artifact)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise LocalGateInvocationError(
            f"could not write gate evidence to {path}: {exc}"
        ) from exc


def render_summary(artifact: dict[str, Any]) -> str:
    """Render a concise human-readable gate summary."""

    checks = artifact["checks"]
    lines = [
        "Local GPP AI review gate",
        f"Repo: {artifact['repo']}",
        f"Work package: {artifact['work_package']}",
        f"Generated at: {artifact['generated_at']}",
        f"Decision: {artifact['decision']}",
        "",
        "Checks:",
    ]
    for name in GATE_CHECK_NAMES:
        marker = "pass" if checks[name] else "fail"
        lines.append(f"- {name}: {marker}")
    lines.extend(["", f"Reviewer findings count: {artifact['reviewer_findings_count']}"])
    lines.extend(["", "Gate findings:"])
    if artifact["findings"]:
        for finding in artifact["findings"]:
            lines.append(f"- {finding}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"GPP-2 status: {artifact['gpp_2_status']}",
            "Note: local operator evidence only; does not close GPP-2, change branch "
            "protection, execute live adapters, widen support, or claim production readiness.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review-evidence",
        type=Path,
        required=True,
        help="Path to the independent reviewer evidence JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the durable no-secret gate evidence artifact.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (defaults to the repo containing this script).",
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        default=None,
        help="Path to gpp_status.v1.json (defaults to .claude/plans/gpp_status.v1.json).",
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help=(
            "Skip the actual-git-diff scope verification. When set, the "
            "scope check cannot verify the reviewer-declared changed files "
            "and fails closed."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint.

    Returns 0 when the decision is operator_may_merge, 1 when the decision
    is fail_closed, and 2 only on an invocation error. Return code 2 is
    reserved for conditions where the gate cannot produce a durable
    artifact at all (a broken schema toolchain or an output write
    failure). Missing, malformed, or schema-invalid reviewer evidence is
    not an invocation error: it produces a durable fail_closed artifact
    and returns 1.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_script()
    status_path = args.status_path.resolve() if args.status_path else repo_root / DEFAULT_STATUS_PATH
    review_path = args.review_evidence

    try:
        review = load_review_evidence(review_path)
        actual_files: list[str] | None = None
        if not args.skip_git and review is not None:
            scope = review.get("scope_reviewed")
            if isinstance(scope, dict):
                base_ref = scope.get("base_ref")
                head_ref = scope.get("head_ref")
                if isinstance(base_ref, str) and isinstance(head_ref, str):
                    actual_files = actual_changed_files(repo_root, base_ref, head_ref)
        checks, gate_findings = evaluate_gate(
            review,
            repo_root=repo_root,
            status_path=status_path,
            actual_files=actual_files,
        )
        repo = "unknown"
        work_package = "unknown"
        if review is not None:
            repo = str(review.get("repo", "unknown")) or "unknown"
            work_package = str(review.get("work_package", "unknown")) or "unknown"
        artifact = build_gate_evidence(
            review=review,
            checks=checks,
            gate_findings=gate_findings,
            repo=repo,
            work_package=work_package,
            generated_at=utc_timestamp(),
        )
        validate_gate_evidence(artifact)
        if args.output is not None:
            write_gate_evidence(args.output, artifact)
    except LocalGateInvocationError as exc:
        print(f"local_gpp_gate: {exc}", file=sys.stderr)
        return 2

    print(render_summary(artifact), end="")
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0 if artifact["decision"] == "operator_may_merge" else 1


if __name__ == "__main__":
    raise SystemExit(main())
