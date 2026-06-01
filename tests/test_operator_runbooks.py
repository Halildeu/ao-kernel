"""Invariant test suite for V5 E-Ops: Operator action runbooks.

Codex 019e84c6 cross-AI plan-time AGREE (3 iters: REVISE/REVISE/AGREE).

6 BLOCKER + 5 BLOCKER + 3 hardening absorbed:
- MC-1 Repo-contract drift fix (workflow/secret/env names)
- MC-2 PAT classic + fine-grained sections; minimal scopes
- MC-3 AO-MA-11A-2 operator does NOT dispatch
- MC-4 Mirror-sync environment as separate 4th action
- MC-5 TestPyPI removed (not supported)
- MC-6 Audit-grade schema fields
- R1 PyPI environment name pin (`pypi`)
- R2 Secret regex token-prefix-only (sha256 false-positive removed)
- R3 Affirmative-claim semantic
- R4 Fine-grained PAT minimal (PR Read only)
- R5 `agent_executed_external_action` rename

~30 invariants across 10 sections.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_DIR = REPO_ROOT / "docs" / "operator-runbooks"
README_PATH = RUNBOOK_DIR / "README.md"
CHECKLIST_PATH = RUNBOOK_DIR / "operator-action-checklist.v1.json"
SCHEMA_PATH = REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "operator-action-checklist.schema.v1.json"
RUNBOOK_FILES = (
    RUNBOOK_DIR / "01-pypi-publish.md",
    RUNBOOK_DIR / "02-plan-approval-environment.md",
    RUNBOOK_DIR / "03-mirror-pat-secret.md",
    RUNBOOK_DIR / "04-mirror-sync-environment.md",
)
ALL_DOCS = (*RUNBOOK_FILES, README_PATH)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Section 1 — Schema validity (6 invariants)
# ---------------------------------------------------------------------------


def test_schema_is_valid_draft_2020_12():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_schema_additional_properties_false_root():
    assert _load(SCHEMA_PATH).get("additionalProperties") is False


def test_schema_const_pins():
    schema = _load(SCHEMA_PATH)
    props = schema["properties"]
    assert props["schema_version"]["const"] == "operator-action-checklist.v1"
    assert props["service"]["const"] == "ao-kernel"
    assert props["artifact_kind"]["const"] == "operator-action-checklist"


def test_schema_guard_flags_const_false():
    schema = _load(SCHEMA_PATH)
    gf = schema["properties"]["guard_flags"]["properties"]
    assert gf["support_widening_allowed"]["const"] is False
    assert gf["production_platform_claim_allowed"]["const"] is False
    assert gf["live_adapter_execution_allowed"]["const"] is False


def test_schema_runbook_disclaimer_const_true():
    """Codex R5 absorb: 3 disclaimer const true."""
    schema = _load(SCHEMA_PATH)
    disc = schema["properties"]["runbook_disclaimer"]["properties"]
    assert disc["agent_prepared_only"]["const"] is True
    assert disc["operator_action_required"]["const"] is True
    assert disc["no_credential_committed"]["const"] is True


def test_schema_claim_boundary_const_true():
    """Codex H3 absorb: 4 claim_boundary const true."""
    schema = _load(SCHEMA_PATH)
    cb = schema["properties"]["claim_boundary"]["properties"]
    for key in (
        "visibility_not_authority",
        "repo_ssot_not_github_ui",
        "no_production_ready_claim",
        "no_live_adapter_execution_authority",
    ):
        assert cb[key]["const"] is True


# ---------------------------------------------------------------------------
# Section 2 — Schema negative (3 invariants)
# ---------------------------------------------------------------------------


def _validate(instance: dict):
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        pytest.skip("jsonschema not installed")
    Draft202012Validator(_load(SCHEMA_PATH)).validate(instance)


def test_schema_rejects_production_platform_claim_true():
    checklist = _load(CHECKLIST_PATH)
    checklist["guard_flags"]["production_platform_claim_allowed"] = True
    with pytest.raises(Exception):
        _validate(checklist)


def test_schema_rejects_credential_material_committed_true():
    """Codex R5 absorb: credential_material_committed const false."""
    checklist = _load(CHECKLIST_PATH)
    checklist["actions"][0]["credential_material_committed"] = True
    with pytest.raises(Exception):
        _validate(checklist)


def test_schema_rejects_agent_executed_external_action_true():
    """Codex R5 absorb: agent_executed_external_action const false."""
    checklist = _load(CHECKLIST_PATH)
    checklist["actions"][0]["agent_executed_external_action"] = True
    with pytest.raises(Exception):
        _validate(checklist)


# ---------------------------------------------------------------------------
# Section 3 — Checklist content (5 invariants)
# ---------------------------------------------------------------------------


def test_checklist_validates_against_schema():
    _validate(_load(CHECKLIST_PATH))


def test_checklist_has_exactly_four_actions():
    """Codex MC-4 absorb: 4 actions (PyPI + plan-approval + PAT + mirror-env)."""
    actions = _load(CHECKLIST_PATH)["actions"]
    assert len(actions) == 4


def test_checklist_action_ids_unique():
    actions = _load(CHECKLIST_PATH)["actions"]
    ids = [a["id"] for a in actions]
    assert len(ids) == len(set(ids))


def test_checklist_workflow_paths_exist_in_repo():
    """Codex MC-1 absorb: exact workflow filename pins."""
    actions = _load(CHECKLIST_PATH)["actions"]
    for action in actions:
        wf_path = action.get("workflow_path")
        if wf_path is None:
            continue
        assert (REPO_ROOT / wf_path).exists(), f"workflow missing: {wf_path}"


def test_checklist_environment_name_allowlist():
    """Codex R1 absorb: environment enum {pypi, ao-ma-plan-approval, ao-ma-mirror-sync, null}."""
    actions = _load(CHECKLIST_PATH)["actions"]
    allowed = {None, "pypi", "ao-ma-plan-approval", "ao-ma-mirror-sync"}
    for action in actions:
        assert action["environment_name"] in allowed


# ---------------------------------------------------------------------------
# Section 4 — Runbook structure (4 invariants)
# ---------------------------------------------------------------------------


def test_all_four_runbook_files_exist():
    for path in RUNBOOK_FILES:
        assert path.exists(), f"missing runbook: {path.name}"


def test_each_runbook_has_core_sections():
    required_sections = (
        "## Prerequisites",
        "## Steps",
        "## Verification",
        "## Rollback",
        "## Stop and contact owner if",
        "## References",
    )
    for path in RUNBOOK_FILES:
        text = path.read_text()
        for section in required_sections:
            assert section in text, f"{path.name} missing section: {section}"


def test_readme_links_all_four_runbooks():
    text = README_PATH.read_text()
    for path in RUNBOOK_FILES:
        assert path.name in text, f"README missing link to: {path.name}"


def test_readme_links_checklist_and_schema():
    text = README_PATH.read_text()
    assert "operator-action-checklist.v1.json" in text
    assert "operator-action-checklist.schema.v1.json" in text


# ---------------------------------------------------------------------------
# Section 5 — Credential discipline (5 invariants)
# ---------------------------------------------------------------------------


# Codex R2 absorb: token-prefix-only secret scan; no sha256 false-positive.
SECRET_PATTERNS = (
    re.compile(r"\bghp_[A-Za-z0-9]{36,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}"),
    re.compile(r"\bgho_[A-Za-z0-9]{36,}"),
    re.compile(r"\bghu_[A-Za-z0-9]{36,}"),
    re.compile(r"\bghs_[A-Za-z0-9]{36,}"),
    re.compile(r"\bghr_[A-Za-z0-9]{36,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
)


def test_no_pat_or_secret_committed_in_docs():
    for path in ALL_DOCS:
        text = path.read_text()
        for pat in SECRET_PATTERNS:
            assert not pat.search(text), f"secret-like pattern in {path.name}: {pat.pattern}"


def test_no_pat_or_secret_committed_in_checklist():
    text = CHECKLIST_PATH.read_text()
    for pat in SECRET_PATTERNS:
        assert not pat.search(text), f"secret-like pattern in checklist: {pat.pattern}"


def test_pat_runbook_documents_stdin_pipe_pattern():
    """Codex H3 absorb: stdin pipe pattern (HARD RULE D43)."""
    text = (RUNBOOK_DIR / "03-mirror-pat-secret.md").read_text()
    assert "stdin pipe" in text.lower() or "--body-file -" in text


def test_pat_runbook_forbids_body_and_echo():
    text = (RUNBOOK_DIR / "03-mirror-pat-secret.md").read_text()
    lowered = text.lower()
    assert "do not use" in lowered or "forbidden seeding patterns" in lowered
    assert '--body "ghp' in text or '--body "' in text  # demonstrates the forbidden form


def test_pat_runbook_classic_and_fine_grained_sections():
    """Codex MC-2 + R4 absorb: classic + fine-grained sections distinct."""
    text = (RUNBOOK_DIR / "03-mirror-pat-secret.md").read_text()
    assert "Classic PAT" in text
    assert "Fine-grained PAT" in text


# ---------------------------------------------------------------------------
# Section 6 — Plan-approval discipline (2 invariants)
# ---------------------------------------------------------------------------


def test_plan_approval_runbook_states_operator_does_not_dispatch():
    """Codex MC-3 absorb: operator does NOT dispatch the workflow."""
    text = (RUNBOOK_DIR / "02-plan-approval-environment.md").read_text()
    assert "does NOT dispatch" in text or "does not dispatch" in text.lower()


def test_plan_approval_runbook_names_environment_exactly():
    text = (RUNBOOK_DIR / "02-plan-approval-environment.md").read_text()
    assert "ao-ma-plan-approval" in text


# ---------------------------------------------------------------------------
# Section 7 — PyPI discipline (3 invariants)
# ---------------------------------------------------------------------------


def test_pypi_runbook_does_not_mention_testpypi_as_executable():
    """Codex MC-5 absorb: TestPyPI is NOT a supported executable step."""
    text = (RUNBOOK_DIR / "01-pypi-publish.md").read_text()
    assert "TestPyPI" not in text  # do not name an unsupported feature at all


def test_pypi_runbook_uses_yank_not_delete():
    """Codex H7 absorb: rollback uses yank, not delete."""
    text = (RUNBOOK_DIR / "01-pypi-publish.md").read_text()
    assert "yank" in text.lower()
    # `delete` is OK but only in negation context
    for line in text.splitlines():
        if " delete" in line.lower():
            assert "NOT" in line or "not" in line.lower(), f"unqualified 'delete' in PyPI runbook: {line!r}"


def test_pypi_runbook_documents_v_tag_guard():
    text = (RUNBOOK_DIR / "01-pypi-publish.md").read_text()
    assert "v-tag" in text.lower() or "v4.1.0" in text


# ---------------------------------------------------------------------------
# Section 8 — Public claim discipline (3 invariants — Codex R3 absorb)
# ---------------------------------------------------------------------------


_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_FENCED_CODE_RE = re.compile(r"^(\s*)```")


def _iter_prose_lines(text: str):
    in_fence = False
    for line in text.splitlines():
        if _FENCED_CODE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _INLINE_CODE_RE.sub("", line)
        yield line, prose


# Codex R3 absorb: affirmative claim semantic; negation context allowed.
AFFIRMATIVE_FORBIDDEN_TOKENS = (
    "production-ready",
    "we guarantee",
    "production sla",
    "guaranteed performance",
)
NEGATION_MARKERS = ("not ", "never ", "no ", "non-", "forbidden", "prohibited", "yasak")
DISCIPLINE_MARKERS = (
    "forbidden_claims",
    "claim_boundary",
    "no_production_ready_claim",
    "no_live_adapter_execution_authority",
    "not supported",
    "do not",
    "do NOT",
    "wording",
    "boundary",
)


def test_no_affirmative_public_claim_in_docs():
    for path in ALL_DOCS:
        text = path.read_text()
        for raw_line, prose in _iter_prose_lines(text):
            lowered_raw = raw_line.lower()
            lowered_prose = prose.lower()
            if any(marker.lower() in lowered_raw for marker in DISCIPLINE_MARKERS):
                continue
            for token in AFFIRMATIVE_FORBIDDEN_TOKENS:
                if token in lowered_prose:
                    if any(neg in lowered_prose for neg in NEGATION_MARKERS):
                        continue
                    pytest.fail(f"affirmative claim in {path.name}: token={token!r}; line={raw_line!r}")


def test_readme_states_agent_prepared_only():
    text = README_PATH.read_text()
    assert "Agent-prepared only" in text or "agent prepared" in text.lower()


def test_readme_states_no_credential_committed():
    text = README_PATH.read_text()
    assert "No credential material is committed" in text or "no credential" in text.lower()


# ---------------------------------------------------------------------------
# Section 9 — Repo-contract drift (3 invariants — Codex MC-1 absorb)
# ---------------------------------------------------------------------------


def test_mirror_workflow_file_exists():
    assert (REPO_ROOT / ".github" / "workflows" / "ao-ma-11e-2b-mirror-sync.yml").exists()


def test_plan_approval_workflow_file_exists():
    assert (REPO_ROOT / ".github" / "workflows" / "ao-ma-11a-plan-approval.yml").exists()


def test_publish_workflow_file_exists():
    assert (REPO_ROOT / ".github" / "workflows" / "publish.yml").exists()


# ---------------------------------------------------------------------------
# Section 10 — Governance (2 invariants)
# ---------------------------------------------------------------------------


def test_no_github_workflow_change_in_pr_diff():
    """Conservative low-risk lane: no .github/workflows mutation."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("git not available or origin/main not fetched")
    if result.returncode != 0:
        pytest.skip(f"git diff failed: {result.stderr}")
    for line in result.stdout.splitlines():
        assert not line.startswith(".github/workflows/"), f"E-Ops must not touch workflows: {line}"


def test_all_checklist_actions_pending():
    """E-Ops v1: every action starts in pending state."""
    actions = _load(CHECKLIST_PATH)["actions"]
    for action in actions:
        assert action["operator_action_status"] == "pending"
        assert action["agent_prep_status"] == "done"
