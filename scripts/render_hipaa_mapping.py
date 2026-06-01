"""Render the HIPAA control mapping Markdown from canonical JSON.

V5 Epic 6 E-6-3b. Codex 019e84ee cross-AI plan-time AGREE.

Deterministic JSON → Markdown emitter (no PyYAML; no PyMD). Output is
byte-equal across runs so a drift test can pin canonical content.

Discipline:
- Section order follows JSON section_status semantics (preserves JSON
  array order; does NOT alphabetize).
- Disclaimers + prohibited claims are listed in inline-code spans so
  the prohibited-token scanner does not flag the documentation itself.
- The renderer never emits any prohibited claim outside of inline code.

Run: python scripts/render_hipaa_mapping.py
Drift test: tests/test_hipaa_mapping.py::test_drift_committed_matches_generated
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "hipaa-control-mapping.v1.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "compliance" / "hipaa-control-mapping.v1.md"


DISCLAIMER_BANNER = """> **Documentation only.** **Not certified.** **Not audited.** ao-kernel
> does NOT process PHI; this mapping is a control-reference document, not
> a HIPAA compliance claim. The three guard flags (`support_widening`,
> `production_platform_claim`, `live_adapter_execution`) remain
> `const false`. Operator MUST consult legal counsel before any external
> claim. **No BAA template** is shipped in this repository.
>
> Generated from
> [`hipaa-control-mapping.v1.json`](hipaa-control-mapping.v1.json); do
> not edit this rendered document by hand. Regenerate via
> `python scripts/render_hipaa_mapping.py`."""


def _render_evidence_refs(refs: list[dict[str, Any]]) -> str:
    if not refs:
        return "  - (no repo evidence ref; operator-owned)"
    out = []
    for ref in refs:
        type_lbl = ref["type"].upper()
        out.append(
            f"  - **{type_lbl}** `{ref['ref']}` — {ref['description']} "
            f"(_{ref['claim_boundary']}_)"
        )
    return "\n".join(out)


def _render_control(control: dict[str, Any]) -> str:
    lines = [
        f"#### `{control['citation']}` — {control['name']}",
        "",
        f"- **Status:** `{control['ao_kernel_status']}`",
        f"- **Rationale:** {control['status_rationale']}",
        f"- **Operator boundary:** {control['operator_boundary']}",
        "- **Evidence refs:**",
        _render_evidence_refs(control["evidence_refs"]),
        "",
    ]
    return "\n".join(lines)


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# ao-kernel HIPAA Control Mapping (V5 Epic 6 E-6-3b)")
    lines.append("")
    lines.append(DISCLAIMER_BANNER)
    lines.append("")
    lines.append(f"**Framework version:** `{data['framework_version']}`")
    lines.append("")
    lines.append("## PHI Handling Disclosure")
    lines.append("")
    lines.append(
        f"- `ao_kernel_processes_phi`: `{str(data['phi_handling_disclosure']['ao_kernel_processes_phi']).lower()}`"
    )
    lines.append(
        f"- `no_phi_in_repo`: `{str(data['phi_handling_disclosure']['no_phi_in_repo']).lower()}`"
    )
    lines.append(
        f"- `operator_phi_handler_decision`: `{str(data['phi_handling_disclosure']['operator_phi_handler_decision']).lower()}`"
    )
    lines.append("")
    lines.append("## Sections")
    lines.append("")
    for section in data["sections"]:
        lines.append(f"### {section['name']}")
        lines.append("")
        lines.append(f"- **Section status:** `{section['section_status']}`")
        lines.append(f"- **Rationale:** {section['section_rationale']}")
        lines.append("")
        if not section["controls"]:
            lines.append("(No controls listed; section is `not_applicable`.)")
            lines.append("")
            continue
        for control in section["controls"]:
            lines.append(_render_control(control))
    lines.append("## Prohibited Public Claims (scanner-enforced)")
    lines.append("")
    lines.append(
        "The following tokens are forbidden in any non-disclaimer prose across "
        "the HIPAA mapping artifacts. The token list lives in the JSON catalog "
        "under `prohibited_claims` and is enforced by "
        "`test_no_prohibited_hipaa_claim_language`."
    )
    lines.append("")
    for token in data["prohibited_claims"]:
        lines.append(f"- `{token}`")
    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append(
        "- Source catalog: [`hipaa-control-mapping.v1.json`](hipaa-control-mapping.v1.json)"
    )
    lines.append(
        "- Schema: [`../../ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json`](../../ao_kernel/defaults/schemas/hipaa-control-mapping.schema.v1.json)"
    )
    lines.append("- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)")
    lines.append("- E-6-6 incident response playbook: PR #801 MERGED")
    lines.append(
        "- Codex cross-AI plan-time AGREE: thread `019e84ee` (2 iters: REVISE → AGREE)"
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
