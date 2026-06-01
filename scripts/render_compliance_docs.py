"""Render SOC2/ISO compliance Markdown from control-evidence-catalog.v1.json.

V5 Epic 6 E-6-3 generator (Option C: JSON SSOT + committed Markdown render +
byte-equal drift test).

Codex 019e83d1 cross-AI plan-time AGREE.

Run: python scripts/render_compliance_docs.py
Drift test: tests/test_compliance_documentation.py::test_drift_committed_matches_generated
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPO_ROOT / "docs" / "compliance" / "control-evidence-catalog.v1.json"
SOC2_MD_PATH = REPO_ROOT / "docs" / "compliance" / "soc2-trust-services-criteria-mapping.v1.md"
ISO_MD_PATH = REPO_ROOT / "docs" / "compliance" / "iso-27001-controls-mapping.v1.md"


FRAMEWORK_TITLES = {
    "SOC2-TSC": "SOC2 Trust Service Categories — Control-Reference Mapping (V5 Epic 6 E-6-3)",
    "ISO-27001-Annex-A": "ISO 27001:2022 Annex A — Control-Reference Mapping (V5 Epic 6 E-6-3)",
}

FRAMEWORK_INTROS = {
    "SOC2-TSC": (
        "This document maps ao-kernel repo artifacts to SOC2 Trust Service "
        "Categories (Common Criteria CC1-CC9 plus the four TSC categories: "
        "Availability, Confidentiality, Processing Integrity, Privacy). "
        "It is a control-reference mapping, not an audit attestation."
    ),
    "ISO-27001-Annex-A": (
        "This document maps ao-kernel repo artifacts to ISO 27001:2022 "
        "Annex A control areas (A.5 through A.18). It is a control-reference "
        "mapping, not an audit attestation."
    ),
}


DISCLAIMER = """> **Not certified.** **Not audited.** **Documentation only.** This document is
> a control-reference mapping and evidence index, not an audit attestation,
> certification statement, or compliance claim. Operator owns audit engagement,
> certification scope, and regulatory determination. The three guard flags
> (`support_widening`, `production_platform_claim`, `live_adapter_execution`)
> remain `const false`. Generated from
> [`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json); do
> not edit this rendered document by hand. Regenerate via
> `python scripts/render_compliance_docs.py`.
>
> **Local/operator smoke is not production evidence.** Repo-owned control
> surface presence does not constitute control operation effectiveness; that
> determination is operator and auditor responsibility."""


def _render_evidence_refs(refs: list[dict[str, Any]]) -> str:
    """Render evidence_refs list as a compact Markdown sub-list."""
    if not refs:
        return "  - (no repo evidence ref; operator-owned)"
    lines = []
    for ref in refs:
        type_lbl = ref["type"].upper()
        ref_text = ref["ref"]
        desc = ref["description"]
        boundary = ref["claim_boundary"]
        lines.append(f"  - **{type_lbl}** `{ref_text}` — {desc} (_{boundary}_)")
    return "\n".join(lines)


def render_framework_markdown(framework: dict[str, Any]) -> str:
    fid = framework["id"]
    version = framework["framework_version"]
    title = FRAMEWORK_TITLES[fid]
    intro = FRAMEWORK_INTROS[fid]
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    lines.append(f"**Framework version:** `{version}`")
    lines.append("")
    lines.append(intro)
    lines.append("")
    lines.append("## Control-Reference Mapping")
    lines.append("")
    # Summary table
    lines.append("| Control | Name | Status | Operator Boundary |")
    lines.append("|---|---|---|---|")
    for control in framework["controls"]:
        status = control["ao_kernel_status"]
        # Keep operator_boundary short for table cell
        boundary = control["operator_boundary"].split(".")[0]
        if len(boundary) > 80:
            boundary = boundary[:77] + "..."
        lines.append(
            f"| `{control['control_id']}` | {control['name']} | `{status}` | {boundary} |"
        )
    lines.append("")
    lines.append("## Per-Control Details")
    lines.append("")
    for control in framework["controls"]:
        lines.append(f"### `{control['control_id']}` — {control['name']}")
        lines.append("")
        lines.append(f"- **Status:** `{control['ao_kernel_status']}`")
        lines.append(f"- **Rationale:** {control['status_rationale']}")
        lines.append(f"- **Operator boundary:** {control['operator_boundary']}")
        lines.append("- **Evidence refs:**")
        lines.append(_render_evidence_refs(control["evidence_refs"]))
        lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append("- Source catalog: [`control-evidence-catalog.v1.json`](control-evidence-catalog.v1.json)")
    lines.append("- Schema: [`../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json`](../../ao_kernel/defaults/schemas/control-evidence-catalog.schema.v1.json)")
    lines.append("- Compliance overview: [`README.md`](README.md)")
    lines.append("- Codex cross-AI plan-time AGREE: thread `019e83d1` (2 iters: REVISE → AGREE)")
    lines.append("")
    return "\n".join(lines)


def generate(catalog_path: Path, soc2_path: Path, iso_path: Path) -> tuple[str, str]:
    """Read catalog → render both Markdown files → write. Returns rendered (soc2, iso)."""
    catalog = json.loads(catalog_path.read_text())
    soc2_md = ""
    iso_md = ""
    for framework in catalog["frameworks"]:
        if framework["id"] == "SOC2-TSC":
            soc2_md = render_framework_markdown(framework)
            soc2_path.write_text(soc2_md)
        elif framework["id"] == "ISO-27001-Annex-A":
            iso_md = render_framework_markdown(framework)
            iso_path.write_text(iso_md)
    return soc2_md, iso_md


def main() -> int:
    generate(CATALOG_PATH, SOC2_MD_PATH, ISO_MD_PATH)
    print(f"generated {SOC2_MD_PATH.relative_to(REPO_ROOT)}")
    print(f"generated {ISO_MD_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
