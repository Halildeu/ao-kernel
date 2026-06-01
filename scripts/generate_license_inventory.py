"""Generate dependency license inventory from CycloneDX 1.5 SBOM + policy.

V5 Epic 6 E-6-4 generator. Reads a CycloneDX 1.5 JSON SBOM and a license
compliance policy JSON, then emits a deterministic per-component policy
tier match report.

Codex 019e83df cross-AI plan-time AGREE.

Discipline:
- stdlib JSON parsing only (no cyclonedx-python-lib runtime dependency)
- Simple SPDX identifier match in v1; composite expressions, exceptions,
  LicenseRef, NOASSERTION, NONE, name-only, url-only, and unknown identifiers
  all fall to review_required (Codex F1+H2+H3 absorb).
- Deterministic output: no wall-clock timestamps; components sorted stably;
  json.dumps(sort_keys=True, indent=2) + trailing newline.
- Source provenance: SBOM + policy SHA256 + bom_format + spec_version
  recorded in inventory header.

Usage:
    python scripts/generate_license_inventory.py \
        --policy docs/license-compliance/license-compliance-policy.v1.json \
        --sbom tests/fixtures/sample-sbom.cdx.json \
        --output docs/license-compliance/dependency-license-inventory.v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

GENERATOR_NAME = "scripts/generate_license_inventory.py"
GENERATOR_VERSION = "v1.0.0"

# Repo root: scripts/.. — used to normalize source path strings so the
# committed inventory stays byte-equal across machines / cwd choices.
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_relative(path: Path) -> str:
    """Return path as POSIX-style repo-relative string for deterministic output.

    Falls back to the basename if the path is outside the repo (e.g. a
    user-supplied SBOM elsewhere on disk). Codex F5 absorb: drift-test
    safety across machines.
    """
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(_REPO_ROOT)
    except ValueError:
        return resolved.name
    return rel.as_posix()

# SPDX `LicenseRef-*` prefix per spec.
LICENSE_REF_PREFIX = "LicenseRef-"

# Special SPDX-defined "no license declared" tokens that must always fall to review.
SPDX_REVIEW_TOKENS = {"NOASSERTION", "NONE"}


def _sha256_hex(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _classify_license(
    license_obj: dict[str, Any] | None,
    policy: dict[str, Any],
) -> tuple[str | None, str | None, str | None, str, str, str | None]:
    """Classify a single license entry from a CycloneDX component.

    Returns (license_id, license_expression, license_name, policy_tier,
    policy_decision, review_reason).

    Codex F1 + H2 + H3 absorb: every non-simple-identifier path → review.
    """
    if license_obj is None:
        return (None, None, None, "n/a", "review", "missing_license")

    # CycloneDX expression form: {"expression": "MIT OR Apache-2.0"}
    if "expression" in license_obj:
        expr = license_obj["expression"]
        return (None, expr, None, "n/a", "review", "unsupported_expression")

    inner = license_obj.get("license", {})
    if not isinstance(inner, dict):
        return (None, None, None, "n/a", "review", "missing_license")

    spdx_id = inner.get("id")
    spdx_name = inner.get("name")
    spdx_url = inner.get("url")

    if spdx_id:
        # Simple identifier path.
        if spdx_id in SPDX_REVIEW_TOKENS:
            reason = "noassertion" if spdx_id == "NOASSERTION" else "none_declared"
            return (spdx_id, None, None, "n/a", "review", reason)
        if spdx_id.startswith(LICENSE_REF_PREFIX):
            return (spdx_id, None, None, "n/a", "review", "license_ref")
        # Composite expression embedded in id (e.g. "MIT AND Apache-2.0") — rare;
        # SPDX expressions belong in `expression` field. Defensive review.
        if any(op in spdx_id for op in (" AND ", " OR ", " WITH ")):
            return (None, spdx_id, None, "n/a", "review", "unsupported_expression")

        tiers = policy["tiers"]
        if spdx_id in tiers["allow"]:
            return (spdx_id, None, None, "allow", "pass", None)
        if spdx_id in tiers["review"]:
            return (spdx_id, None, None, "review", "review", "policy_review_tier")
        if spdx_id in tiers["deny"]:
            return (spdx_id, None, None, "deny", "deny", None)
        # Unknown identifier: fail-closed to review (F2 absorb).
        return (spdx_id, None, None, "n/a", "review", "unknown_identifier")

    if spdx_name:
        return (None, None, spdx_name, "n/a", "review", "unresolved_name")

    if spdx_url:
        return (None, None, None, "n/a", "review", "unresolved_url")

    return (None, None, None, "n/a", "review", "missing_license")


def _component_record(
    component: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    name = component.get("name") or "<unknown>"
    version = component.get("version") or "<unknown>"
    purl = component.get("purl")
    bom_ref = component.get("bom-ref")

    licenses = component.get("licenses") or []
    # v1: classify by the FIRST license entry; multi-license components with
    # composite semantics already declared in `expression` are handled above.
    # If multiple `license.id` entries appear, fall to review (we cannot pick).
    if len(licenses) > 1:
        first = licenses[0]
        license_id, expr, name_field, _tier, _decision, _reason = _classify_license(first, policy)
        return {
            "name": name,
            "version": version,
            "purl": purl,
            "bom_ref": bom_ref,
            "license_id": license_id,
            "license_expression": expr,
            "license_name": name_field,
            "policy_tier": "n/a",
            "policy_decision": "review",
            "review_reason": "unsupported_expression",
        }

    if not licenses:
        return {
            "name": name,
            "version": version,
            "purl": purl,
            "bom_ref": bom_ref,
            "license_id": None,
            "license_expression": None,
            "license_name": None,
            "policy_tier": "n/a",
            "policy_decision": "review",
            "review_reason": "missing_license",
        }

    license_id, expr, name_field, tier, decision, reason = _classify_license(
        licenses[0], policy
    )
    return {
        "name": name,
        "version": version,
        "purl": purl,
        "bom_ref": bom_ref,
        "license_id": license_id,
        "license_expression": expr,
        "license_name": name_field,
        "policy_tier": tier,
        "policy_decision": decision,
        "review_reason": reason,
    }


def _component_sort_key(rec: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        rec["name"],
        rec["version"],
        rec.get("purl") or "",
        rec.get("bom_ref") or "",
    )


def _derive_status(records: list[dict[str, Any]]) -> str:
    if any(r["policy_decision"] == "deny" for r in records):
        return "blocked_by_deny_license"
    if any(r["policy_decision"] == "review" for r in records):
        return "review_required"
    return "pass_no_deny_matches"


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "component_count": len(records),
        "pass_count": sum(1 for r in records if r["policy_decision"] == "pass"),
        "review_count": sum(1 for r in records if r["policy_decision"] == "review"),
        "deny_count": sum(1 for r in records if r["policy_decision"] == "deny"),
    }


def generate_inventory(
    policy_path: Path,
    sbom_path: Path,
) -> tuple[dict[str, Any], str]:
    """Build inventory dict + serialized JSON text.

    Returns (inventory_dict, json_text). Text is deterministic (no wall-clock).
    """
    policy = json.loads(policy_path.read_text())
    sbom = json.loads(sbom_path.read_text())

    if sbom.get("bomFormat") != "CycloneDX":
        # Fail closed: invalid input
        invalid: dict[str, Any] = {
            "schema_version": "dependency-license-inventory.v1",
            "service": "ao-kernel",
            "source_sbom_path": _repo_relative(sbom_path),
            "source_sbom_sha256": _sha256_hex(sbom_path),
            "source_sbom_bom_format": "CycloneDX",
            "source_sbom_spec_version": "1.5",
            "source_policy_path": _repo_relative(policy_path),
            "source_policy_sha256": _sha256_hex(policy_path),
            "generator_name": GENERATOR_NAME,
            "generator_version": GENERATOR_VERSION,
            "report_status": "invalid_input",
            "summary": {
                "component_count": 0,
                "pass_count": 0,
                "review_count": 0,
                "deny_count": 0,
            },
            "components": [],
        }
        return invalid, _canonical_json(invalid)

    components_in = sbom.get("components", []) or []
    records = [_component_record(c, policy) for c in components_in]
    records.sort(key=_component_sort_key)

    inventory: dict[str, Any] = {
        "schema_version": "dependency-license-inventory.v1",
        "service": "ao-kernel",
        "source_sbom_path": _repo_relative(sbom_path),
        "source_sbom_sha256": _sha256_hex(sbom_path),
        "source_sbom_bom_format": "CycloneDX",
        "source_sbom_spec_version": str(sbom.get("specVersion", "1.5")),
        "source_policy_path": _repo_relative(policy_path),
        "source_policy_sha256": _sha256_hex(policy_path),
        "generator_name": GENERATOR_NAME,
        "generator_version": GENERATOR_VERSION,
        "report_status": _derive_status(records),
        "summary": _summary(records),
        "components": records,
    }
    return inventory, _canonical_json(inventory)


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def render_markdown_summary(inventory: dict[str, Any]) -> str:
    """Render an operator-facing Markdown summary of the inventory."""
    lines: list[str] = []
    lines.append("# ao-kernel Dependency License Inventory (V5 Epic 6 E-6-4)")
    lines.append("")
    lines.append("> **Not legal counsel.** **Not legal advice.** **Operator responsibility.**")
    lines.append("> Generated from "
                 f"`{inventory['source_sbom_path']}` "
                 f"(SHA256: `{inventory['source_sbom_sha256'][:12]}...`) and policy "
                 f"`{inventory['source_policy_path']}` "
                 f"(SHA256: `{inventory['source_policy_sha256'][:12]}...`). Do not "
                 f"edit by hand; regenerate via `python {inventory['generator_name']}`.")
    lines.append("")
    lines.append(f"**Report status:** `{inventory['report_status']}`")
    lines.append("")
    summary = inventory["summary"]
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Component count: **{summary['component_count']}**")
    lines.append(f"- Pass (allow tier match): **{summary['pass_count']}**")
    lines.append(f"- Review required: **{summary['review_count']}**")
    lines.append(f"- Deny tier match: **{summary['deny_count']}**")
    lines.append("")
    lines.append("## Components")
    lines.append("")
    lines.append("| Component | Version | License (id / expression / name) | Tier | Decision | Review reason |")
    lines.append("|---|---|---|---|---|---|")
    for rec in inventory["components"]:
        lic = rec["license_id"] or rec["license_expression"] or rec["license_name"] or "(none)"
        reason = rec["review_reason"] or "-"
        lines.append(
            f"| `{rec['name']}` | `{rec['version']}` | `{lic}` | "
            f"`{rec['policy_tier']}` | `{rec['policy_decision']}` | `{reason}` |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate dependency license inventory")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help="Optional Markdown summary output path",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit non-zero when report_status is review_required",
    )
    args = parser.parse_args(argv)

    inventory, json_text = generate_inventory(args.policy, args.sbom)
    args.output.write_text(json_text)
    if args.markdown_output:
        args.markdown_output.write_text(render_markdown_summary(inventory))

    if inventory["report_status"] == "blocked_by_deny_license":
        return 1
    if inventory["report_status"] == "review_required" and args.fail_on_review:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
