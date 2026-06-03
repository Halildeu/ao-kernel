"""Shape + invariant tests for AO-MA-11E-2c/2d/2e workflow surface (Slice B).

These tests enforce the hard contract documented in
.claude/plans/AO-MA-11E-2c-d-e-WORKFLOWS.md without invoking GitHub Actions or
the runtime Slice A CLI. They run against the YAML/JSON sources committed in
this branch.

Provider note: YAML parse uses PyYAML which is **not** a runtime dependency of
ao-kernel. The tests use ``pytest.importorskip("yaml")`` so the suite degrades
gracefully if PyYAML is absent in stripped CI environments. In normal CI the
test extras (``[dev]``) pull in pyyaml transitively.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, TypeAlias, cast

import pytest
from jsonschema import Draft202012Validator

JsonObject: TypeAlias = dict[str, Any]
YamlObject: TypeAlias = dict[object, Any]

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

WF_2C = WORKFLOWS_DIR / "ao-ma-11e-2c-project-mirror-full-sync.yml"
WF_2D = WORKFLOWS_DIR / "ao-ma-11e-2d-pr-project-auto-link.yml"
WF_2E = WORKFLOWS_DIR / "ao-ma-11e-2e-label-cleanup-once.yml"

ALL_WORKFLOW_PATHS = [WF_2C, WF_2D, WF_2E]

EVIDENCE_PLAN_JSON = REPO_ROOT / ".claude" / "plans" / "AO-MA-11E-2c-d-e-WORKFLOWS.v1.json"
EVIDENCE_SCHEMA_JSON = (
    REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "ao-ma-11e-2c-d-e-workflows-evidence.schema.v1.json"
)

HIGH_RISK_DIR = REPO_ROOT / "ao-ma-10-high-risk-reviews" / "AO-MA-11e-2c-d-e-workflows"

GUARD_FLAG_KEYS = (
    "support_widening",
    "production_platform_claim",
    "live_adapter_execution",
)


def _load_yaml(path: Path) -> YamlObject:
    yaml = pytest.importorskip("yaml")
    text = path.read_text(encoding="utf-8")
    return cast(YamlObject, yaml.safe_load(text))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_executable_text(path: Path) -> str:
    """Return the workflow source with comment-only lines stripped.

    Forbidden-pattern checks (``pull_request_target``, ``git push origin main``,
    ``--admin``) must apply to the *executable* surface of the workflow, NOT
    to documentation comments that explain what the workflow does or does NOT
    do. A line is treated as a "comment-only" line if its first non-whitespace
    character is ``#``. We do not try to strip trailing inline comments —
    those are extremely rare in GHA YAML and false-positives there are still a
    legitimate signal.
    """
    out_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out_lines.append(line)
    return "\n".join(out_lines) + "\n"


def _yaml_top_on(doc: YamlObject) -> JsonObject:
    """PyYAML maps the GHA ``on`` key to Python ``True`` because YAML 1.1
    interprets the bareword ``on`` as a boolean. Normalise so tests can write
    ``doc_on["push"]`` regardless of dialect.
    """
    if True in doc:
        return cast(JsonObject, doc[True])
    if "on" in doc:
        return cast(JsonObject, doc["on"])
    raise AssertionError("workflow missing top-level 'on' trigger block")


def test_01_shape_workflow_files_exist() -> None:
    """All 3 workflow yml files exist on disk."""
    missing = [p for p in ALL_WORKFLOW_PATHS if not p.is_file()]
    assert not missing, f"missing workflow files: {missing}"


def test_02_shape_valid_yaml() -> None:
    """Each workflow parses as valid YAML and is a top-level mapping."""
    for path in ALL_WORKFLOW_PATHS:
        doc = _load_yaml(path)
        assert isinstance(doc, dict), f"{path.name} is not a YAML mapping"


def test_03_shape_required_keys() -> None:
    """Each workflow has ``name``, ``on``, ``permissions``, ``jobs``."""
    for path in ALL_WORKFLOW_PATHS:
        doc = _load_yaml(path)
        assert "name" in doc, f"{path.name} missing 'name'"
        assert (True in doc) or ("on" in doc), f"{path.name} missing 'on'"
        assert "permissions" in doc, f"{path.name} missing 'permissions'"
        assert "jobs" in doc and isinstance(doc["jobs"], dict), f"{path.name} missing 'jobs' mapping"


def test_04_2c_triggers_correct() -> None:
    """11e-2c has push:main + schedule + workflow_dispatch triggers."""
    doc = _load_yaml(WF_2C)
    on = _yaml_top_on(doc)
    assert "push" in on, "11e-2c missing push trigger"
    push_branches = on["push"].get("branches", [])
    assert "main" in push_branches, f"11e-2c push branches={push_branches}"

    assert "schedule" in on, "11e-2c missing schedule trigger"
    crons = [item.get("cron") for item in on["schedule"]]
    assert any("*/6" in (c or "") for c in crons), f"11e-2c schedule must include every-6h cron, got {crons}"

    assert "workflow_dispatch" in on, "11e-2c missing workflow_dispatch"
    dispatch = on["workflow_dispatch"]
    assert dispatch and "inputs" in dispatch, "11e-2c workflow_dispatch must declare inputs"
    assert "heal_mode" in dispatch["inputs"], "11e-2c workflow_dispatch missing heal_mode input"


def test_05_2d_uses_pull_request_NOT_target() -> None:
    """11e-2d MUST use pull_request (no _target) for security."""
    doc = _load_yaml(WF_2D)
    on = _yaml_top_on(doc)
    assert "pull_request" in on, "11e-2d missing pull_request trigger"
    assert "pull_request_target" not in on, "11e-2d MUST NOT use pull_request_target (fork secret exfil risk)"
    types = on["pull_request"].get("types", [])
    required_types = {
        "opened",
        "edited",
        "synchronize",
        "ready_for_review",
        "labeled",
        "unlabeled",
    }
    missing = required_types - set(types)
    assert not missing, f"11e-2d pull_request types missing: {missing}"

    text = _read_executable_text(WF_2D)
    assert "pull_request_target" not in text, (
        "11e-2d executable surface contains literal 'pull_request_target' — security violation"
    )


def test_06_2e_dispatch_only() -> None:
    """11e-2e MUST be workflow_dispatch ONLY (no push/PR/schedule)."""
    doc = _load_yaml(WF_2E)
    on = _yaml_top_on(doc)
    assert list(on.keys()) == ["workflow_dispatch"], (
        f"11e-2e triggers must be ONLY workflow_dispatch, got {list(on.keys())}"
    )

    text = _read_executable_text(WF_2E)
    for forbidden in ("push:", "pull_request:", "schedule:"):
        assert forbidden not in text, f"11e-2e executable surface contains forbidden trigger keyword '{forbidden}'"


def test_07_2e_confirmation_required() -> None:
    """11e-2e confirmation input must be declared with required: true."""
    doc = _load_yaml(WF_2E)
    on = _yaml_top_on(doc)
    inputs = on["workflow_dispatch"]["inputs"]
    assert "confirmation" in inputs, "11e-2e missing confirmation input"
    assert inputs["confirmation"].get("required") is True, "11e-2e confirmation must be required: true"
    assert "dry_run" in inputs, "11e-2e missing dry_run input"
    assert inputs["dry_run"].get("default") is True, "11e-2e dry_run must default to true (false-positive guard)"

    text = _read_text(WF_2E)
    assert "LABEL-CLEANUP-CONFIRM" in text, "11e-2e source must contain literal confirmation phrase"


def test_08_2c_no_direct_push_to_main() -> None:
    """11e-2c must NOT contain direct git push to main in the executable surface."""
    text = _read_executable_text(WF_2C)
    forbidden_patterns = [
        r"git\s+push\s+origin\s+main",
        r"git\s+push\s+.*\srefs/heads/main",
        r"git\s+push\s+--force\s+origin\s+main",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, text), (
            f"11e-2c executable surface contains forbidden direct push pattern: {pattern}"
        )


def test_09_all_no_admin() -> None:
    """No --admin flag in any workflow executable surface."""
    for path in ALL_WORKFLOW_PATHS:
        text = _read_executable_text(path)
        assert "--admin" not in text, f"{path.name} executable surface contains forbidden --admin flag"


def test_10_all_no_admin_via_workflow_id() -> None:
    """No permission grants `actions: write` (workflow ID write surface)."""
    for path in ALL_WORKFLOW_PATHS:
        doc = _load_yaml(path)
        perms = doc.get("permissions", {})
        if isinstance(perms, dict):
            actions_val = perms.get("actions")
            assert actions_val != "write", f"{path.name} top-level permissions has actions: write"
        for job_name, job in doc.get("jobs", {}).items():
            job_perms = job.get("permissions", {})
            if isinstance(job_perms, dict):
                actions_val = job_perms.get("actions")
                assert actions_val != "write", f"{path.name}::{job_name} has actions: write"


def test_11_permissions_minimal_per_workflow() -> None:
    """Each workflow grants exactly the permissions documented in the plan."""
    expected = {
        WF_2C: {
            "contents": "write",
            "issues": "write",
            "repository-projects": "write",
            "pull-requests": "write",
        },
        WF_2D: {
            "contents": "read",
            "pull-requests": "read",
            "repository-projects": "write",
        },
        WF_2E: {
            "contents": "read",
            "issues": "write",
            "repository-projects": "read",
        },
    }
    for path, want in expected.items():
        doc = _load_yaml(path)
        got = doc.get("permissions", {})
        assert got == want, f"{path.name} permissions mismatch.\n  expected: {want}\n  got: {got}"


def test_12_2c_2d_use_ao_kernel_cli() -> None:
    """11e-2c and 11e-2d bodies contain ao-kernel project CLI calls."""
    text_2c = _read_text(WF_2C)
    text_2d = _read_text(WF_2D)
    assert "ao-kernel project drift" in text_2c, "11e-2c missing `ao-kernel project drift` invocation"
    assert "ao-kernel project sync" in text_2c, "11e-2c missing `ao-kernel project sync` invocation"
    assert "ao-kernel project from-pr" in text_2d, "11e-2d missing `ao-kernel project from-pr` invocation"


def test_13_2e_uses_label_cleanup_subcommand() -> None:
    """11e-2e body contains `ao-kernel project label-cleanup` invocation."""
    text = _read_text(WF_2E)
    assert "ao-kernel project label-cleanup" in text, "11e-2e missing `ao-kernel project label-cleanup` invocation"


def test_14_no_existing_workflow_mutation() -> None:
    """git diff --name-only origin/main..HEAD shows only NEW workflow files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main..HEAD"],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"git unavailable for diff audit: {exc}")

    if result.returncode != 0:
        pytest.skip(f"git diff returned non-zero ({result.returncode}); stderr={result.stderr.strip()}")

    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    workflow_changes = [f for f in files if f.startswith(".github/workflows/")]
    if not workflow_changes:
        return

    allowed = {
        ".github/workflows/ao-ma-11e-2c-project-mirror-full-sync.yml",
        ".github/workflows/ao-ma-11e-2d-pr-project-auto-link.yml",
        ".github/workflows/ao-ma-11e-2e-label-cleanup-once.yml",
    }
    unexpected = sorted(set(workflow_changes) - allowed)
    assert not unexpected, f"branch mutates existing workflows beyond write-set: {unexpected}"


def test_15_no_guard_flag_keys_in_workflow_output() -> None:
    """Workflow YAML must not set any of the 3 guard flags to true."""
    for path in ALL_WORKFLOW_PATHS:
        text = _read_text(path)
        for key in GUARD_FLAG_KEYS:
            pattern = rf"{re.escape(key)}\s*:\s*true\b"
            assert not re.search(pattern, text, re.IGNORECASE), (
                f"{path.name} sets guard flag '{key}: true' — invariant violation"
            )
            cli_pattern = rf"--{re.escape(key.replace('_', '-'))}(=|\s+)true"
            assert not re.search(cli_pattern, text, re.IGNORECASE), (
                f"{path.name} sets guard flag '--{key.replace('_', '-')} true' via CLI — invariant violation"
            )


def test_16_evidence_validates() -> None:
    """Plan evidence JSON validates against its Draft 2020-12 schema."""
    assert EVIDENCE_PLAN_JSON.is_file(), f"missing plan evidence: {EVIDENCE_PLAN_JSON}"
    assert EVIDENCE_SCHEMA_JSON.is_file(), f"missing evidence schema: {EVIDENCE_SCHEMA_JSON}"
    schema = json.loads(EVIDENCE_SCHEMA_JSON.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PLAN_JSON.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: list(e.path))
    assert not errors, "evidence does not validate; errors:\n  " + "\n  ".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_17_high_risk_evidence_pair_exists() -> None:
    """3 distinct provider review evidence files exist under high-risk dir."""
    required = {
        "openai.local-ai-review-evidence.v1.json",
        "anthropic.local-ai-review-evidence.v1.json",
        "minimax.local-ai-review-evidence.v1.json",
        "local-ai-review-evidence.v1.json",
    }
    assert HIGH_RISK_DIR.is_dir(), f"missing high-risk review dir: {HIGH_RISK_DIR}"
    present = {p.name for p in HIGH_RISK_DIR.iterdir() if p.is_file()}
    missing = required - present
    assert not missing, f"missing high-risk evidence files: {missing}"


def test_18_3way_cross_ai_provider_distinct() -> None:
    """The 3 provider evidence files declare distinct providers."""
    providers_seen = set()
    for name in (
        "openai.local-ai-review-evidence.v1.json",
        "anthropic.local-ai-review-evidence.v1.json",
        "minimax.local-ai-review-evidence.v1.json",
    ):
        path = HIGH_RISK_DIR / name
        assert path.is_file(), f"missing {path}"
        doc = json.loads(path.read_text(encoding="utf-8"))
        provider = doc.get("provider")
        assert provider in ("openai", "anthropic", "minimax"), f"{name} declares unknown provider: {provider}"
        providers_seen.add(provider)
    assert providers_seen == {"openai", "anthropic", "minimax"}, (
        f"providers must be distinct across openai/anthropic/minimax, got {providers_seen}"
    )

    summary_path = HIGH_RISK_DIR / "local-ai-review-evidence.v1.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    verdicts = summary.get("verdicts", [])
    assert len(verdicts) == 3, f"summary must enumerate 3 verdicts, got {len(verdicts)}"
    summary_providers = {v.get("provider") for v in verdicts}
    assert summary_providers == {"openai", "anthropic", "minimax"}, f"summary providers mismatch: {summary_providers}"
