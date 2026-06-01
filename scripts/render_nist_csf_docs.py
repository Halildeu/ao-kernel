"""Render NIST CSF 2.0 Function/Category reference mapping Markdown.

V5 Epic 6 E-6-3e. Codex 019e8516 cross-AI plan-time AGREE.

Deterministic JSON -> Markdown emitter (no PyYAML; no PyMD). Output is
byte-equal across runs so a drift test can pin canonical content.

Discipline:
- Functions are emitted in canonical NIST CSF 2.0 order:
  GV, ID, PR, DE, RS, RC.
- Disclaimers + prohibited claim tokens + Tier/Profile disclosure tables
  are emitted in inline-code spans so the public-claim scanner does not
  flag the documentation itself.
- The renderer never emits any prohibited claim outside of inline code.

Run: python scripts/render_nist_csf_docs.py
Drift test: tests/test_nist_csf_mapping.py::test_drift_committed_matches_generated
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "nist-csf-control-mapping.v1.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "compliance" / "nist-csf-control-mapping.v1.md"

FUNCTION_ORDER = ("GV", "ID", "PR", "DE", "RS", "RC")


DISCLAIMER_BANNER = """> **Documentation only.** **NIST CSF is a voluntary risk management
> framework.** **NIST does NOT operate a CSF certification program.** No
> AOC, no audit report, no CISA attestation. ao-kernel claims no
> Implementation Tier and ships no organizational CSF Profile. The
> three V5 guard flags (`support_widening`, `production_platform_claim`,
> `live_adapter_execution`) remain `const false`, and three CSF-scoped
> guard flags (`csf_certification_claim_allowed`,
> `csf_tier_claim_allowed`, `csf_profile_claim_allowed`) also remain
> `const false`.
>
> This document is a Function/Category reference mapping only; it is
> NOT a 106-Subcategory deep-dive, NOT a Profile (Current/Target), NOT
> an Implementation Tier assessment, and NOT an implementation plan.
> Operator owns risk management strategy, organizational context,
> Profile creation, and any external claim.
>
> Generated from
> [`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json);
> do not edit this rendered document by hand. Regenerate via
> `python scripts/render_nist_csf_docs.py`."""


def _render_evidence_refs(refs: list[dict[str, Any]]) -> str:
    if not refs:
        return "  - (no repo evidence ref; operator-owned)"
    out = []
    for ref in refs:
        type_lbl = ref["type"].upper()
        out.append(
            f"  - **{type_lbl}** `{ref['ref']}` - {ref['description']} "
            f"(_{ref['claim_boundary']}_)"
        )
    return "\n".join(out)


def _render_category(cat: dict[str, Any]) -> str:
    lines = [
        f"#### `{cat['category_id']}` - {cat['category_title']}",
        "",
        f"- **Status:** `{cat['category_status']}`",
        f"- **Rationale:** {cat['rationale']}",
        f"- **Operator boundary:** {cat['operator_boundary']}",
        "- **Evidence refs:**",
        _render_evidence_refs(cat["evidence_refs"]),
        "",
    ]
    return "\n".join(lines)


def _render_function(func: dict[str, Any]) -> str:
    lines = [
        f"### `{func['function_id']}` - {func['function_title']}",
        "",
        f"- **Function status:** `{func['function_status']}`",
        "",
    ]
    for cat in func["categories"]:
        lines.append(_render_category(cat))
    return "\n".join(lines)


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# ao-kernel NIST CSF Function / Category Reference Mapping (V5 Epic 6 E-6-3e)")
    lines.append("")
    lines.append(DISCLAIMER_BANNER)
    lines.append("")
    lines.append(f"**Framework version:** `{data['framework_version']}`")
    lines.append("")
    lines.append("## CSF Tier Disclosure")
    lines.append("")
    tier = data["csf_tier_disclosure"]
    lines.append(f"- `ao_kernel_claims_tier`: `{tier['ao_kernel_claims_tier']}`")
    lines.append(
        f"- `tier_assessment_operator_owned`: `{str(tier['tier_assessment_operator_owned']).lower()}`"
    )
    lines.append("- `available_tiers` (disclosure only; not claimed):")
    for t in tier["available_tiers"]:
        lines.append(f"  - `{t}`")
    lines.append("")
    lines.append("## CSF Profile Disclosure")
    lines.append("")
    prof = data["csf_profile_disclosure"]
    for key, value in prof.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.append("")
    lines.append("## Functions (GV / ID / PR / DE / RS / RC)")
    lines.append("")
    funcs_by_id = {f["function_id"]: f for f in data["functions"]}
    for fid in FUNCTION_ORDER:
        lines.append(_render_function(funcs_by_id[fid]))
    lines.append("## Prohibited Public Claims (scanner-enforced)")
    lines.append("")
    lines.append(
        "The following tokens are forbidden in any non-disclaimer prose "
        "across the NIST CSF mapping artifacts. The token list lives in "
        "the JSON catalog under `prohibited_claims` and is enforced by "
        "`test_no_prohibited_csf_claim_language`."
    )
    lines.append("")
    for token in data["prohibited_claims"]:
        lines.append(f"- `{token}`")
    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append(
        "- Source catalog: "
        "[`nist-csf-control-mapping.v1.json`](nist-csf-control-mapping.v1.json)"
    )
    lines.append(
        "- Schema: "
        "[`../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json`]"
        "(../../ao_kernel/defaults/schemas/nist-csf-control-mapping.schema.v1.json)"
    )
    lines.append(
        "- Operator runbook: "
        "[`nist-csf-operator-usage-runbook.v1.md`](nist-csf-operator-usage-runbook.v1.md)"
    )
    lines.append("- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)")
    lines.append("- E-6-3b HIPAA mapping reference: PR #809")
    lines.append("- E-6-3c GDPR DPIA operator template: PR #810")
    lines.append("- E-6-3d PCI-DSS control reference mapping: PR #811")
    lines.append(
        "- Codex cross-AI plan-time AGREE: thread `019e8516` (2 iters: REVISE -> AGREE)"
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
