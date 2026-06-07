"""Epic 9 PR-Xfinal supersession decision invariants.

Records that the Epic 9 all-or-none V5 production-promotion path (atomic flip of
``live_adapter_execution`` + ``support_widening`` + ``production_platform_claim``
plus a v5.0.0 production-platform claim) is SUPERSEDED — not failed, not deferred
— by an explicit operator decision to keep ao-kernel a CLI-only / operator-
mediated governed control-plane. The three guard flags stay const false; the
pre-existing blocker and pre-supersession checklist are reinterpreted as
superseded / not applicable, never deleted. AI output is evidence only; release
authority remains the repo-owned ``ao-release-gate`` required check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ao_kernel.config import load_default


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "epic9-xfinal-supersession-decision.schema.v1.json"
SCHEMA_PATH = ROOT / "ao_kernel" / "defaults" / "schemas" / SCHEMA_NAME
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "epic9" / "epic9-xfinal-supersession-decision.current.json"
MATRIX_PATH = ROOT / "tests" / "fixtures" / "epic9" / "v5-production-readiness-matrix.current.json"
CLOSEOUT_DOC = ROOT / ".claude" / "plans" / "EPIC-9-PR-XFINAL-SUPERSESSION-CLOSEOUT.md"


EXPECTED_ALLOWED = {
    "installable_governed_control_plane",
    "fail_closed_policy_engine",
    "self_hosted_jsonl_evidence_trail",
    "governed_context_pipeline",
    "api_keyless_consumer_use",
}

EXPECTED_FORBIDDEN = {
    "general_purpose_production_platform",
    "autonomous_provider_api_execution",
    "support_widening_active",
    "live_adapter_runtime_active",
    "all_or_none_v5_production_promotion_satisfied",
}


def _schema() -> dict[str, Any]:
    return load_default("schemas", SCHEMA_NAME)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def test_schema_present_valid_and_strict() -> None:
    assert SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:epic9-xfinal-supersession-decision:v1"

    def object_nodes(node: Any) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        if isinstance(node, dict):
            if node.get("type") == "object":
                nodes.append(node)
            for value in node.values():
                nodes.extend(object_nodes(value))
        elif isinstance(node, list):
            for value in node:
                nodes.extend(object_nodes(value))
        return nodes

    for node in object_nodes(schema):
        assert node.get("additionalProperties") is False
        assert node.get("unevaluatedProperties") is False


def test_current_fixture_validates_and_pins_superseded_state() -> None:
    payload = _fixture()
    assert _valid(payload)
    assert payload["work_package"] == "E-9-1"
    assert payload["decision"].startswith("superseded_by_operator_cli_only_decision")
    # The three guard flags stay false — the supersession's final state.
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    final = payload["guard_flags_final_state"]
    assert final["live_adapter_execution"] is False
    assert final["support_widening"] is False
    assert final["production_platform_claim"] is False
    intent = payload["operator_intent"]
    assert intent["cli_only"] is True
    assert intent["no_provider_api_calls"] is True
    assert intent["ao_kernel_as_governed_control_plane"] is True
    # AI output is never release authority; repo-owned gate is.
    assert payload["source_authority"]["ai_output_is_release_authority"] is False
    assert payload["source_authority"]["repo_owned_required_check_is_release_authority"] is True
    assert payload["non_authority_boundary"]["authorizes_guard_flag_flip"] is False


def test_schema_rejects_any_guard_flip() -> None:
    for field in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        payload = _fixture()
        payload[field] = True
        assert not _valid(payload), f"top-level {field}=True must fail closed"
        payload = _fixture()
        payload["guard_flags_final_state"][field] = True
        assert not _valid(payload), f"guard_flags_final_state.{field}=True must fail closed"

    payload = _fixture()
    payload["non_authority_boundary"]["authorizes_guard_flag_flip"] = True
    assert not _valid(payload), "authorizing a guard flip must fail closed"

    payload = _fixture()
    payload["source_authority"]["ai_output_is_release_authority"] = True
    assert not _valid(payload), "AI output as release authority must fail closed"


def test_allowed_and_forbidden_claims_match_exact_sets() -> None:
    payload = _fixture()
    assert set(payload["allowed_claims"]) == EXPECTED_ALLOWED
    assert set(payload["forbidden_claims"]) == EXPECTED_FORBIDDEN


def test_schema_pins_exact_forbidden_claims() -> None:
    # Duplicate one forbidden claim (drop another) -> uniqueItems + maxItems fail.
    payload = _fixture()
    payload["forbidden_claims"][0] = payload["forbidden_claims"][1]
    assert not _valid(payload), "duplicate forbidden claim must fail closed"

    # Omit a forbidden claim (4 instead of 5) -> minItems=5 fail.
    payload = _fixture()
    payload["forbidden_claims"] = payload["forbidden_claims"][:4]
    assert not _valid(payload), "missing a forbidden claim must fail closed"

    # An out-of-enum forbidden claim must fail.
    payload = _fixture()
    payload["forbidden_claims"][0] = "some_unlisted_claim"
    assert not _valid(payload), "unlisted forbidden claim must fail closed"


def test_supersedes_pins_four_distinct_artifacts() -> None:
    payload = _fixture()
    arts = [item["artifact"] for item in payload["supersedes"]]
    assert set(arts) == {
        "tests/fixtures/epic9/xfinal-readiness-blocker.current.json",
        ".claude/plans/EPIC-9-FINAL-SUPERSESSION-PR.md",
        ".claude/plans/EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md",
        ".claude/plans/V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md",
    }

    # Drop one superseded artifact -> minItems=4 + contains fail.
    payload = _fixture()
    payload["supersedes"] = payload["supersedes"][:3]
    assert not _valid(payload), "missing a superseded artifact must fail closed"

    # Duplicate one (lose another) -> exactly-once contains fail.
    payload = _fixture()
    payload["supersedes"][0]["artifact"] = payload["supersedes"][1]["artifact"]
    assert not _valid(payload), "duplicate superseded artifact must fail closed"


def test_referenced_artifacts_exist_on_disk() -> None:
    # Machine-enforced, not self-attestation: every path the decision names must
    # actually exist in the repo.
    payload = _fixture()
    sa = payload["source_authority"]
    for rel in (sa["ri78c_final_promote_decision_path"], sa["gpp_status_path"]):
        assert (ROOT / rel).is_file(), f"missing source authority: {rel}"
    for item in payload["supersedes"]:
        assert (ROOT / item["artifact"]).is_file(), f"missing superseded artifact: {item['artifact']}"
    for item in payload["impact_on_existing_artifacts"]:
        assert (ROOT / item["path"]).is_file(), f"missing impacted artifact: {item['path']}"


def test_cross_ai_review_distinct_providers_and_agree() -> None:
    ref = _fixture()["cross_ai_review_ref"]
    assert ref["implementer_provider"] != ref["reviewer_provider"]
    assert ref["implementer_provider"] == "anthropic"
    assert ref["reviewer_provider"] == "openai"
    assert ref["final_verdict"] == "AGREE"


def test_matrix_stays_partial_consistent_with_supersession() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert matrix["matrix_complete"] is False
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        # The matrix must not have flipped any guard flag.
        if flag in matrix:
            assert matrix[flag] is False


def _normalized(path: Path) -> str:
    """Lowercased, whitespace-collapsed text so banner phrases that wrap across
    markdown blockquote lines still match as contiguous substrings. Leading
    blockquote ``>`` markers are stripped per line so a phrase that wraps onto a
    ``> `` continuation line (e.g. ``must not be\n> opened``) stays contiguous."""
    cleaned: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        while stripped.startswith(">"):
            stripped = stripped[1:].lstrip()
        cleaned.append(stripped)
    return " ".join(" ".join(cleaned).split()).lower()


def test_closeout_doc_present_and_non_authority() -> None:
    assert CLOSEOUT_DOC.is_file()
    text = _normalized(CLOSEOUT_DOC)
    assert "superseded" in text
    assert "governed control-plane" in text
    assert "pr-xfinal" in text
    # Binding language, not just the bare phrase: the closeout must say the
    # supersession is a boundary change and forbid the production-platform claim.
    assert "not a failure or deferral" in text or "conscious product-boundary change" in text
    assert "no guard flag flip is authorized" in text
    # Must explicitly forbid (not assert) a production-platform claim.
    assert "no production-platform claim" in text or "production-platform claim" in text


def test_superseded_markdown_docs_carry_binding_banner() -> None:
    # Machine-enforced content invariant (not just path existence): every
    # superseded markdown route must carry a SUPERSEDED banner and bound its body
    # as historical, so no leftover active-route language reads as canonical.
    draft = ROOT / ".claude" / "plans" / "EPIC-9-FINAL-SUPERSESSION-PR.md"
    checklist = ROOT / ".claude" / "plans" / "EPIC-9-PR-Xfinal-PRE-SUPERSESSION-CHECKLIST.md"
    roadmap = ROOT / ".claude" / "plans" / "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md"
    for path in (draft, checklist, roadmap):
        assert path.is_file(), f"missing superseded doc: {path}"
        text = _normalized(path)
        assert "superseded" in text, f"{path.name} missing SUPERSEDED banner"
        assert "historical" in text, f"{path.name} must bound its body as historical"

    # The two active-route docs (draft + checklist) must explicitly neutralize
    # their leftover active language and forbid any flip.
    for path in (draft, checklist):
        text = _normalized(path)
        assert "historical record only" in text, f"{path.name} must bound body as historical record only"
        assert "no guard flag flip is authorized" in text, f"{path.name} must forbid a guard-flag flip"

    draft_text = _normalized(draft)
    assert "must not be opened" in draft_text
    checklist_text = _normalized(checklist)
    assert "no longer an active prerequisite contract" in checklist_text
