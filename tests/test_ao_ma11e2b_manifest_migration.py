"""AO-MA-11E-2b manifest migration invariants.

Pins:
- 13/13 first_wave_issues[i].body_anchor has EXACTLY 5 fields (strict scope).
- 13/13 artifact_sha256 + plan_digest populated from issue_anchor_pin.
- 13/13 metadata field present with risk_class_source + evidence_classes.
- No unknown fields in body_anchor.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _REPO_ROOT / ".claude" / "plans" / "v5_issue_projection.v1.json"

_STRICT_ANCHOR_FIELDS = {
    "spm_anchor",
    "slice_id",
    "ao_authority_artifact",
    "artifact_sha256",
    "plan_digest",
}

_SHA_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _load() -> dict:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_all_13_issues_have_exactly_5_anchor_fields() -> None:
    data = _load()
    issues = data["first_wave_issues"]
    assert len(issues) == 13
    for issue in issues:
        anchor = issue["body_anchor"]
        assert set(anchor.keys()) == _STRICT_ANCHOR_FIELDS, (
            f"{issue['id']}: body_anchor fields = {set(anchor.keys())}, expected exactly {_STRICT_ANCHOR_FIELDS}"
        )


def test_all_13_anchor_sha_fields_are_populated() -> None:
    data = _load()
    pin = data["runtime_created_state"]["issue_anchor_pin"]
    expected_artifact = pin["artifact_sha256_at_issue_creation"]
    expected_plan = pin["plan_digest_at_issue_creation"]
    for issue in data["first_wave_issues"]:
        a = issue["body_anchor"]
        assert a["artifact_sha256"] == expected_artifact, (
            f"{issue['id']}: artifact_sha256 not copied from issue_anchor_pin"
        )
        assert a["plan_digest"] == expected_plan, f"{issue['id']}: plan_digest not copied from issue_anchor_pin"


def test_all_13_anchor_sha_format_is_valid() -> None:
    data = _load()
    for issue in data["first_wave_issues"]:
        a = issue["body_anchor"]
        for field in ("artifact_sha256", "plan_digest"):
            assert _SHA_PATTERN.match(a[field]), f"{issue['id']}.{field} format invalid: {a[field]!r}"


def test_all_13_metadata_field_present() -> None:
    data = _load()
    for issue in data["first_wave_issues"]:
        assert "metadata" in issue, f"{issue['id']}: metadata field missing"
        m = issue["metadata"]
        assert "risk_class_source" in m
        assert "evidence_classes" in m


def test_no_unknown_anchor_fields_remain() -> None:
    """Codex iter-2 §C: risk_class_source + evidence_classes must NOT be in body_anchor."""
    data = _load()
    for issue in data["first_wave_issues"]:
        a = issue["body_anchor"]
        assert "risk_class_source" not in a, (
            f"{issue['id']}: risk_class_source still in body_anchor (should be in metadata)"
        )
        assert "evidence_classes" not in a, (
            f"{issue['id']}: evidence_classes still in body_anchor (should be in metadata)"
        )
