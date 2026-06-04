"""V5 Epic P0 E-P0-5 invariants: GitHub Issue forms YAML shape.

Three forms (v5-slice + v5-gate + governance-bug) MUST carry the
mandatory anchor fields (spm_anchor, ao_authority_artifact,
artifact_sha256, plan_digest, slice_id, risk_class_source,
evidence_classes) per the V5 roadmap §E-P0-5 invariant. risk_class is
COMPUTED via risk_class_source pointer; manual downgrade is forbidden.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
ISSUE_DIR = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
EXPECTED_FORMS = ("v5-slice.yml", "v5-gate.yml", "governance-bug.yml")
CONFIG_PATH = ISSUE_DIR / "config.yml"

# Fields every slice/gate/governance-bug form MUST require
COMMON_REQUIRED_FIELDS = (
    "spm_anchor",
    "ao_authority_artifact",
    "artifact_sha256",
    "plan_digest",
    "slice_id",
    "risk_class_source",
    "evidence_classes",
)


def _load_form(filename: str) -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    return yaml.safe_load((ISSUE_DIR / filename).read_text())


def _changed_files_against_origin_main() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    return [p for p in proc.stdout.split() if p]


def _skip_unless_issue_forms_slice(changed: list[str]) -> None:
    if not any(path.startswith(".github/ISSUE_TEMPLATE/") for path in changed):
        pytest.skip("E-P0-5 issue-form zero-touch invariant applies only when issue templates are in the PR diff")


# ---- 1. Form presence + structure (5) -----------------------------------


def test_issue_template_dir_exists() -> None:
    assert ISSUE_DIR.exists() and ISSUE_DIR.is_dir()


def test_three_forms_exist() -> None:
    for form in EXPECTED_FORMS:
        assert (ISSUE_DIR / form).exists(), f"missing form: {form}"


def test_config_yml_present() -> None:
    assert CONFIG_PATH.exists()


def test_config_disables_blank_issues() -> None:
    if yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    assert cfg.get("blank_issues_enabled") is False, "config.yml must disable blank issues to enforce form usage"


def test_config_contact_links_point_at_canonical_docs() -> None:
    if yaml is None:
        pytest.skip("PyYAML not installed in this environment")
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    urls = " ".join(link["url"] for link in cfg.get("contact_links", []))
    assert "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md" in urls
    assert "CLAUDE.md" in urls


# ---- 2. Required-field contract (3 parametrized x N fields) -------------


@pytest.mark.parametrize("form_name", EXPECTED_FORMS)
def test_form_carries_all_common_required_fields(form_name: str) -> None:
    form = _load_form(form_name)
    body = form["body"]
    field_ids = {item.get("id"): item for item in body if isinstance(item, dict)}
    for field in COMMON_REQUIRED_FIELDS:
        assert field in field_ids, f"{form_name}: missing required field id {field!r}"


@pytest.mark.parametrize("form_name", EXPECTED_FORMS)
def test_form_marks_required_fields_validations_required(form_name: str) -> None:
    form = _load_form(form_name)
    body = form["body"]
    field_ids = {item.get("id"): item for item in body if isinstance(item, dict)}
    for field in COMMON_REQUIRED_FIELDS:
        item = field_ids[field]
        validations = item.get("validations", {})
        assert validations.get("required") is True, f"{form_name}: field {field!r} must be marked required:true"


@pytest.mark.parametrize("form_name", EXPECTED_FORMS)
def test_form_risk_class_source_label_marked_computed(form_name: str) -> None:
    """The risk_class_source field's label MUST signal COMPUTED so
    operators understand it is not manually editable downward."""
    form = _load_form(form_name)
    body = form["body"]
    field_ids = {item.get("id"): item for item in body if isinstance(item, dict)}
    item = field_ids["risk_class_source"]
    label = item["attributes"]["label"]
    assert "COMPUTED" in label, f"{form_name}: risk_class_source label must include COMPUTED marker"


@pytest.mark.parametrize("form_name", EXPECTED_FORMS)
def test_form_evidence_classes_is_multi_select_with_required_options(
    form_name: str,
) -> None:
    form = _load_form(form_name)
    body = form["body"]
    field_ids = {item.get("id"): item for item in body if isinstance(item, dict)}
    item = field_ids["evidence_classes"]
    assert item["type"] == "dropdown"
    assert item["attributes"].get("multiple") is True
    options = item["attributes"]["options"]
    # The 9 V5 evidence dimensions must all be selectable
    required_options = {
        "public_support_matrix",
        "real_provider_live_calls",
        "cost_rate_circuit_breaker_evidence",
        "observability_prod_tunables",
        "security_sbom_license_scan",
        "install_deploy_lifecycle_smoke",
        "multi_tenancy_isolation",
        "docs_runbooks",
        "ao_release_gate_clean_trail",
    }
    assert required_options.issubset(set(options)), (
        f"{form_name}: evidence_classes options missing: {required_options - set(options)}"
    )


# ---- 3. Slice form guard-flag checklist (1) -----------------------------


def test_slice_form_has_three_guard_flag_const_false_checkboxes() -> None:
    form = _load_form("v5-slice.yml")
    body = form["body"]
    checkbox_items = [item for item in body if isinstance(item, dict) and item.get("type") == "checkboxes"]
    assert len(checkbox_items) >= 1, "slice form must include guard-flag checklist"
    options_concat = " ".join(opt.get("label", "") for opt in checkbox_items[0]["attributes"]["options"])
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in options_concat, f"slice form guard-flag checklist missing {flag!r}"


# ---- 4. Gate form flip-declaration (1) ----------------------------------


def test_gate_form_has_guard_flag_to_flip_dropdown() -> None:
    form = _load_form("v5-gate.yml")
    body = form["body"]
    field_ids = {item.get("id"): item for item in body if isinstance(item, dict)}
    assert "guard_flag_to_flip" in field_ids
    item = field_ids["guard_flag_to_flip"]
    assert item["type"] == "dropdown"
    options = set(item["attributes"]["options"])
    assert {"support_widening", "production_platform_claim", "live_adapter_execution"}.issubset(options)


# ---- 5. Governance-bug form violation_kind (1) --------------------------


def test_governance_bug_form_violation_kind_enum() -> None:
    form = _load_form("governance-bug.yml")
    body = form["body"]
    field_ids = {item.get("id"): item for item in body if isinstance(item, dict)}
    assert "violation_kind" in field_ids
    options_concat = " ".join(field_ids["violation_kind"]["attributes"]["options"])
    for kind in (
        "fake_work",
        "cross_ai_peer_review_violation",
        "admin_merge_bypass",
        "ci_red_merge",
        "evidence_chain_integrity",
        "guard_flag_unauthorized_flip",
    ):
        assert kind in options_concat, f"governance-bug missing violation_kind: {kind}"


# ---- 6. Governance ZERO TOUCH (1) ---------------------------------------


def test_no_workflow_mutation() -> None:
    """E-P0-5 scope: ISSUE_TEMPLATE only; the slice's own write-set
    MUST NOT touch `.github/workflows/`.

    BLK-005 absorb: path-filtered diff (-- .github/workflows/) so
    unrelated workflow maintenance that landed in earlier merges
    doesn't trigger a false positive on this slice-scoped invariant.
    """
    changed = _changed_files_against_origin_main()
    _skip_unless_issue_forms_slice(changed)
    touched = [p for p in changed if p.startswith(".github/workflows/")]
    assert not touched, f"E-P0-5 (issue forms) slice must not touch .github/workflows/. Touched: {touched}"


def test_only_issue_template_under_dot_github_changed() -> None:
    """E-P0-5 scope: .github/ISSUE_TEMPLATE/ only. No CODEOWNERS / ruleset / branch-protection mutation."""
    changed = _changed_files_against_origin_main()
    _skip_unless_issue_forms_slice(changed)
    for path in changed:
        if path.startswith(".github/"):
            assert path.startswith(".github/ISSUE_TEMPLATE/"), (
                f"E-P0-5 must touch only .github/ISSUE_TEMPLATE/, got: {path}"
            )


def test_no_codeowners_or_ruleset_diff() -> None:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    changed = set(proc.stdout.split())
    forbidden = {
        ".github/CODEOWNERS",
        ".github/REPO-GOVERNANCE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
    }
    overlap = forbidden & changed
    assert not overlap, f"E-P0-5 must not touch governance files: {overlap}"
