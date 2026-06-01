"""Render the GDPR DPIA operator template Markdown from canonical JSON.

V5 Epic 6 E-6-3c. Codex 019e84fb cross-AI plan-time AGREE.

Deterministic JSON -> Markdown emitter (no PyYAML; no PyMD). Output is
byte-equal across runs so a drift test can pin canonical content.

Discipline:
- Section order follows JSON array order (preserves prefixItems contract).
- Disclaimers + prohibited claim tokens are listed in inline-code spans so
  the prohibited-token scanner does not flag the documentation itself.
- The renderer never emits any prohibited claim outside of inline code.
- Non-data placeholders propagate verbatim; no email/name/phone/IP added.

Run: python scripts/render_gdpr_dpia_template.py
Drift test: tests/test_gdpr_dpia_template.py::test_drift_committed_matches_generated
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "docs" / "compliance" / "gdpr-dpia-template.v1.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "compliance" / "gdpr-dpia-template.v1.md"


DISCLAIMER_BANNER = """> **Documentation only.** **Not a GDPR certification.** **Not a regulatory
> approval.** **Not an actual DPIA filing.** **Not legal advice.** ao-kernel
> does NOT process personal data; this template is an operator-owned
> structure, not a public claim. The three V5 guard flags
> (`support_widening`, `production_platform_claim`, `live_adapter_execution`)
> remain `const false`, and three GDPR-scoped flags
> (`regulatory_filing_claim_allowed`, `legal_advice_claim_allowed`,
> `contract_template_allowed`) also remain `const false`. Operator MUST
> consult legal counsel before any external claim. **No DPA contract
> template** is shipped in this repository.
>
> This template does not determine lawful basis, controller/processor
> role, transfer mechanism, DPA filing need, or data subject notice
> content. Article 36 prior consultation determination remains operator
> and DPO/counsel responsibility.
>
> Generated from
> [`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json); do not edit
> this rendered document by hand. Regenerate via
> `python scripts/render_gdpr_dpia_template.py`."""


def _render_fields(fields: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in fields.items():
        lines.append(f"- `{key}`: `{value}`")
    return lines


def _render_trigger(trigger: dict[str, Any]) -> list[str]:
    lines = ["", "#### DPIA Trigger Assessment", ""]
    for key, value in trigger.items():
        if isinstance(value, bool):
            lines.append(f"- `{key}`: `{str(value).lower()}`")
        else:
            lines.append(f"- `{key}`: {value}")
    return lines


def _render_risks(risks: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for risk in risks:
        lines.append(f"#### `{risk['risk_id']}` — {risk['risk_name']}")
        lines.append("")
        lines.append(f"- **Status:** `{risk['risk_status']}`")
        for fld in ("likelihood", "severity", "risk_score", "mitigation"):
            raw = risk[fld]
            display = "`null`" if raw is None else f"`{raw}`"
            lines.append(f"- **{fld.replace('_', ' ').title()}:** {display}")
        lines.append("")
    return lines


def _render_section(section: dict[str, Any]) -> list[str]:
    lines = [f"### {section['title']}", ""]
    if "fields" in section:
        lines.extend(_render_fields(section["fields"]))
        lines.append("")
    if "risks" in section:
        lines.extend(_render_risks(section["risks"]))
    if "dpia_trigger_assessment" in section:
        lines.extend(_render_trigger(section["dpia_trigger_assessment"]))
        lines.append("")
    return lines


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# ao-kernel GDPR DPIA Operator Template (V5 Epic 6 E-6-3c)")
    lines.append("")
    lines.append(DISCLAIMER_BANNER)
    lines.append("")
    lines.append(f"**Framework version:** `{data['framework_version']}`")
    lines.append("")
    lines.append("## Personal Data Disclosure")
    lines.append("")
    for key, value in data["personal_data_disclosure"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.append("")
    lines.append("## Sections")
    lines.append("")
    for section in data["sections"]:
        lines.extend(_render_section(section))
    lines.append("## Prohibited Public Claims (scanner-enforced)")
    lines.append("")
    lines.append(
        "The following tokens are forbidden in any non-disclaimer prose "
        "across the GDPR DPIA template artifacts. The token list lives in "
        "the JSON catalog under `prohibited_claims` and is enforced by "
        "`test_no_prohibited_gdpr_claim_language`."
    )
    lines.append("")
    for token in data["prohibited_claims"]:
        lines.append(f"- `{token}`")
    lines.append("")
    lines.append("## References")
    lines.append("")
    lines.append(
        "- Source catalog: "
        "[`gdpr-dpia-template.v1.json`](gdpr-dpia-template.v1.json)"
    )
    lines.append(
        "- Schema: "
        "[`../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json`]"
        "(../../ao_kernel/defaults/schemas/gdpr-dpia-template.schema.v1.json)"
    )
    lines.append(
        "- Operator runbook: "
        "[`gdpr-dpia-operator-runbook.v1.md`](gdpr-dpia-operator-runbook.v1.md)"
    )
    lines.append("- E-6-3 SOC2/ISO compliance overview: [`README.md`](README.md)")
    lines.append("- E-6-3b HIPAA mapping reference: [`hipaa-control-mapping.v1.md`](hipaa-control-mapping.v1.md)")
    lines.append(
        "- Codex cross-AI plan-time AGREE: thread `019e84fb` (2 iters: REVISE -> AGREE)"
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
