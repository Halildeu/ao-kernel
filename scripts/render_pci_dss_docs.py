"""Render the PCI-DSS control reference mapping Markdown from canonical JSON.

V5 Epic 6 E-6-3d. Codex 019e850a cross-AI plan-time AGREE.

Deterministic JSON -> Markdown emitter (no PyYAML; no PyMD). Output is
byte-equal across runs so a drift test can pin canonical content.

Discipline:
- Requirements are emitted in numeric req_id order (1..12).
- Disclaimers + prohibited claim tokens are listed in inline-code spans
  so the public-claim scanner does not flag the documentation itself.
- The renderer never emits any prohibited claim outside of inline code.
- No PAN/SAD/Track sample is ever emitted; the renderer copies field
  values verbatim from the JSON SSOT (which is itself scanner-protected).

Run: python scripts/render_pci_dss_docs.py
Drift test: tests/test_pci_dss_mapping.py::test_drift_committed_matches_generated
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "pci-dss-control-mapping.v1.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "compliance" / "pci-dss-control-mapping.v1.md"


DISCLAIMER_BANNER = """> **Documentation only.** **Not certified.** **No AOC.** **No ROC.**
> **No SAQ filed.** **No ASV scan.** ao-kernel does NOT process cardholder
> data (CHD), does NOT process sensitive authentication data (SAD), has
> NO PAN in this repo, and has NO CDE (Cardholder Data Environment). The
> three V5 guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`, and three PCI-scoped
> guard flags (`cde_claim_allowed`, `qsa_assessment_claim_allowed`,
> `saq_filing_claim_allowed`) also remain `const false`. Operator MUST
> engage a Qualified Security Assessor (QSA) before any external PCI
> claim.
>
> This document is a control-reference mapping only; it is NOT an
> Attestation of Compliance, NOT a Report on Compliance, NOT a
> Self-Assessment Questionnaire, NOT an ASV scan report, and NOT a
> penetration test report. Operator owns CDE scoping, QSA engagement,
> SAQ selection, ASV vendor selection, and any PCI control operation.
>
> Generated from
> [`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json);
> do not edit this rendered document by hand. Regenerate via
> `python scripts/render_pci_dss_docs.py`."""


def _render_evidence_refs(refs: list[dict[str, Any]]) -> str:
    if not refs:
        return "  - (no repo evidence ref; operator-owned)"
    out = []
    for ref in refs:
        type_lbl = ref["type"].upper()
        out.append(f"  - **{type_lbl}** `{ref['ref']}` - {ref['description']}")
    return "\n".join(out)


def _render_requirement(req: dict[str, Any]) -> str:
    lines = [
        f"### Req {req['req_id']} - {req['req_title']}",
        "",
        f"- **Status:** `{req['req_status']}`",
        f"- **Rationale:** {req['req_rationale']}",
        f"- **Operator boundary:** {req['operator_boundary']}",
        "- **Evidence refs:**",
        _render_evidence_refs(req["evidence_refs"]),
        "",
    ]
    return "\n".join(lines)


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# ao-kernel PCI-DSS Control Reference Mapping (V5 Epic 6 E-6-3d)")
    lines.append("")
    lines.append(DISCLAIMER_BANNER)
    lines.append("")
    lines.append(f"**Framework version:** `{data['framework_version']}`")
    lines.append("")
    lines.append("## Cardholder Data Handling Disclosure")
    lines.append("")
    for key, value in data["chd_handling_disclosure"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.append("")
    lines.append("## SAQ Applicability")
    lines.append("")
    saq = data["saq_applicability"]
    lines.append(f"- `repo_baseline_saq`: `{saq['repo_baseline_saq']}`")
    lines.append(f"- `operator_determines`: `{str(saq['operator_determines']).lower()}`")
    lines.append("- `available_saq_types` (machine slug + display label):")
    for saq_t in saq["available_saq_types"]:
        lines.append(f"  - `{saq_t['type_slug']}` - {saq_t['display_label']}")
    lines.append("")
    lines.append("## Requirements (Req 1-12)")
    lines.append("")
    # Sort by numeric req_id (handles 1..12 order even if JSON were ever
    # written out of order)
    sorted_reqs = sorted(data["requirements"], key=lambda r: int(r["req_id"]))
    for req in sorted_reqs:
        lines.append(_render_requirement(req))
    lines.append("## Prohibited Public Claims (scanner-enforced)")
    lines.append("")
    lines.append(
        "The following tokens are forbidden in any non-disclaimer prose "
        "across the PCI-DSS mapping artifacts. The token list lives in "
        "the JSON catalog under `prohibited_claims` and is enforced by "
        "`test_no_prohibited_pci_claim_language`."
    )
    lines.append("")
    for token in data["prohibited_claims"]:
        lines.append(f"- `{token}`")
    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append(
        "- Source catalog: "
        "[`pci-dss-control-mapping.v1.json`](pci-dss-control-mapping.v1.json)"
    )
    lines.append(
        "- Schema: "
        "[`../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json`]"
        "(../../ao_kernel/defaults/schemas/pci-dss-control-mapping.schema.v1.json)"
    )
    lines.append(
        "- Operator runbook: "
        "[`pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md`]"
        "(pci-dss-operator-scope-and-qsa-engagement-runbook.v1.md)"
    )
    lines.append("- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)")
    lines.append("- E-6-3b HIPAA mapping reference: PR #809")
    lines.append("- E-6-3c GDPR DPIA operator template: PR #810")
    lines.append(
        "- Codex cross-AI plan-time AGREE: thread `019e850a` (2 iters: REVISE -> AGREE)"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    data = json.loads(JSON_PATH.read_text())
    OUTPUT_PATH.write_text(render_markdown(data))
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
