"""Render a short markdown context packet from doc-bridge-governed store items.

Fail-closed selection (Codex acceptance #3 + #5): an item is only rendered if
its source file still exists AND re-applying the same mapping rule reproduces
the same key + ``value_hash``. Stale / drifted / deleted sources, low-confidence
items, and unverified ``doc_claim`` facts (unless explicitly opted in) are
excluded. The packet is source-derived context, never release authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ao_kernel._internal.context_doc_bridge import ingest as _ingest
from ao_kernel._internal.context_doc_bridge import mapping as _mapping
from ao_kernel.context import canonical_store as cs

_SECTION_ORDER = [
    ("rule", "Rules (canonical — all AIs read)"),
    ("decision", "Decisions (ADR / decision records)"),
    ("fact", "Live State (doc-claim, unverified)"),
]

_AUTHORITY_HEADER = (
    "> AUTHORITY: source-derived context, NOT release authority. Cannot override "
    "support_widening / production_platform_claim / live_adapter_execution. "
    "Stale / low-confidence / unverified 'done' is excluded (fail-closed)."
)


@dataclass
class _Row:
    key: str
    value: str
    type: str
    tier: str
    status: str
    src: str
    confidence: float


def _verify_and_collect(
    ws: Path,
    repo: Path,
    rules_by_id: dict[str, Any],
    min_conf: float,
    include_doc_claims: bool,
) -> tuple[list[_Row], int]:
    rows: list[_Row] = []
    excluded = 0
    for item in cs.query(ws):
        prov = (item.get("provenance") or {}).get(_ingest.PROVENANCE_NS)
        if not prov:
            continue  # not doc-bridge managed
        conf = float(item.get("confidence", 0.0))
        if not item.get("_is_fresh", True) or conf < min_conf:
            excluded += 1
            continue
        tier = prov.get("tier", "")
        if tier == "doc_claim" and not include_doc_claims:
            excluded += 1
            continue
        rule = rules_by_id.get(prov.get("mapping_id", ""))
        if rule is None:  # mapping no longer defines this rule
            excluded += 1
            continue
        src_path = repo / prov.get("src", "")
        if not src_path.is_file():  # source deleted
            excluded += 1
            continue
        try:
            text = src_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            excluded += 1
            continue
        reproduced = {e.key: e for e in _ingest.extract_from_source(rule, prov["src"], text)}
        match = reproduced.get(item["key"])
        if match is None or match.value_hash != prov.get("value_hash"):
            excluded += 1  # source drifted away from what was ingested
            continue
        rows.append(
            _Row(
                key=item["key"],
                value=str(item.get("value", "")),
                type=prov.get("type", ""),
                tier=tier,
                status=prov.get("status", ""),
                src=prov.get("src", ""),
                confidence=conf,
            )
        )
    return rows, excluded


def render_context_packet(
    workspace_root: str | Path,
    *,
    repo_root: str | Path | None = None,
    mapping_path: str | None = None,
    profile: str | None = None,
    min_conf: float = 0.7,
    max_items: int = 20,
    include_doc_claims: bool = False,
) -> str:
    """Render the markdown context packet (see module docstring for the contract).

    ``max_items`` caps each section independently (top-N by confidence) so an
    ADR-heavy repo cannot crowd opted-in live-state facts out of the packet.
    """
    ws = Path(workspace_root)
    repo = Path(repo_root) if repo_root is not None else ws
    spec = _mapping.load_mapping(mapping_path)
    rules_by_id = {r["mapping_id"]: r for r in spec["rules"]}

    rows, excluded = _verify_and_collect(ws, repo, rules_by_id, min_conf, include_doc_claims)
    sections: list[tuple[str, list[_Row]]] = []
    shown = 0
    for type_, header in _SECTION_ORDER:
        group = sorted((r for r in rows if r.type == type_), key=lambda r: -r.confidence)[:max_items]
        if group:
            sections.append((header, group))
            shown += len(group)
    capped = len(rows) - shown

    lines = [
        f"# Context Packet — ao-kernel governed (fresh + conf>={min_conf})",
        f"> {shown} item shown · {excluded} excluded (stale/low-conf/unverified)"
        + (f" · {capped} over per-section cap" if capped else "")
        + (f" · profile {profile}" if profile else ""),
        _AUTHORITY_HEADER,
        "",
    ]
    for header, group in sections:
        lines.append(f"## {header}")
        for r in group:
            tag = f"<src: {r.src} | conf {r.confidence:.2f}"
            if r.status and r.status.lower() not in ("active", "accepted", "kabul"):
                tag += f" | {r.status}"
            if r.tier == "doc_claim":
                tag += " | UNVERIFIED"
            tag += ">"
            lines.append(f"- {r.value}  {tag}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
