"""PB-9.2 helper: deterministic truth inventory debt ratchet."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from ao_kernel.extensions.loader import (
    TRUTH_TIER_CONTRACT_ONLY,
    TRUTH_TIER_QUARANTINED,
    TRUTH_TIER_RUNTIME_BACKED,
    ExtensionManifest,
    ExtensionRegistry,
)


@dataclass(frozen=True)
class RatchetRow:
    extension_id: str
    truth_tier: str
    entrypoint_count: int
    ui_surfaces_count: int
    remap_candidate_refs: int
    missing_runtime_refs: int
    runtime_handler_registered: bool
    bucket: str
    priority_score: int | None


def entrypoint_count(manifest: ExtensionManifest) -> int:
    return sum(len(values) for values in manifest.entrypoints.values())


def classify_bucket(manifest: ExtensionManifest) -> str:
    missing = len(manifest.missing_runtime_refs)
    remap = len(manifest.remap_candidate_refs)
    entrypoints = entrypoint_count(manifest)
    ui = len(manifest.ui_surfaces)
    tier = manifest.truth_tier

    if tier == TRUTH_TIER_RUNTIME_BACKED:
        return "maintain_runtime_backed"
    if tier == TRUTH_TIER_CONTRACT_ONLY and missing == 0 and remap == 0:
        return "promotion_candidate"
    if tier == TRUTH_TIER_QUARANTINED and missing >= 9 and entrypoints == 0 and ui == 0:
        return "retire_candidate"
    if tier == TRUTH_TIER_QUARANTINED and missing <= 8 and remap >= 1:
        return "remap_priority"
    return "quarantine_keep"


def compute_priority_score(manifest: ExtensionManifest, bucket: str) -> int | None:
    if bucket != "remap_priority":
        return None
    entrypoints = entrypoint_count(manifest)
    ui = len(manifest.ui_surfaces)
    missing = len(manifest.missing_runtime_refs)
    remap = len(manifest.remap_candidate_refs)
    return (entrypoints * 2) + (ui * 3) - missing - remap


def build_report() -> dict[str, Any]:
    registry = ExtensionRegistry()
    registry.load_from_defaults()
    summary = registry.truth_summary()

    rows: list[RatchetRow] = []
    for manifest in registry.list_all():
        bucket = classify_bucket(manifest)
        rows.append(
            RatchetRow(
                extension_id=manifest.extension_id,
                truth_tier=manifest.truth_tier,
                entrypoint_count=entrypoint_count(manifest),
                ui_surfaces_count=len(manifest.ui_surfaces),
                remap_candidate_refs=len(manifest.remap_candidate_refs),
                missing_runtime_refs=len(manifest.missing_runtime_refs),
                runtime_handler_registered=manifest.runtime_handler_registered,
                bucket=bucket,
                priority_score=compute_priority_score(manifest, bucket),
            )
        )

    bucket_counts: dict[str, int] = {}
    for row in rows:
        bucket_counts[row.bucket] = bucket_counts.get(row.bucket, 0) + 1

    remap_queue = sorted(
        (row for row in rows if row.bucket == "remap_priority"),
        key=lambda row: (-(row.priority_score or -10_000), row.extension_id),
    )

    ordered_queue = {
        "promotion_candidate": [
            row.extension_id for row in rows if row.bucket == "promotion_candidate"
        ],
        "remap_priority": [row.extension_id for row in remap_queue],
        "quarantine_keep": sorted(
            row.extension_id for row in rows if row.bucket == "quarantine_keep"
        ),
        "retire_candidate": sorted(
            row.extension_id for row in rows if row.bucket == "retire_candidate"
        ),
    }

    return {
        "summary": {
            "total_extensions": summary.total_extensions,
            "runtime_backed": summary.runtime_backed,
            "contract_only": summary.contract_only,
            "quarantined": summary.quarantined,
            "remap_candidate_refs": summary.remap_candidate_refs,
            "missing_runtime_refs": summary.missing_runtime_refs,
        },
        "bucket_counts": bucket_counts,
        "ordered_queue": ordered_queue,
        "rows": [
            {
                "extension_id": row.extension_id,
                "truth_tier": row.truth_tier,
                "entrypoint_count": row.entrypoint_count,
                "ui_surfaces_count": row.ui_surfaces_count,
                "remap_candidate_refs": row.remap_candidate_refs,
                "missing_runtime_refs": row.missing_runtime_refs,
                "runtime_handler_registered": row.runtime_handler_registered,
                "bucket": row.bucket,
                "priority_score": row.priority_score,
            }
            for row in rows
        ],
    }


def render_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    bucket_counts = report["bucket_counts"]
    queue = report["ordered_queue"]
    lines: list[str] = []
    lines.append("truth_inventory_ratchet")
    lines.append(
        "summary:"
        f" total={summary['total_extensions']}"
        f" runtime_backed={summary['runtime_backed']}"
        f" contract_only={summary['contract_only']}"
        f" quarantined={summary['quarantined']}"
        f" remap_candidate_refs={summary['remap_candidate_refs']}"
        f" missing_runtime_refs={summary['missing_runtime_refs']}"
    )
    lines.append(
        "buckets:"
        f" maintain_runtime_backed={bucket_counts.get('maintain_runtime_backed', 0)}"
        f" promotion_candidate={bucket_counts.get('promotion_candidate', 0)}"
        f" remap_priority={bucket_counts.get('remap_priority', 0)}"
        f" quarantine_keep={bucket_counts.get('quarantine_keep', 0)}"
        f" retire_candidate={bucket_counts.get('retire_candidate', 0)}"
    )
    lines.append("queue.promotion_candidate: " + ", ".join(queue["promotion_candidate"]))
    lines.append("queue.remap_priority: " + ", ".join(queue["remap_priority"]))
    lines.append("queue.quarantine_keep: " + ", ".join(queue["quarantine_keep"]))
    lines.append("queue.retire_candidate: " + ", ".join(queue["retire_candidate"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit PB-9.2 truth inventory debt ratchet report.",
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    args = parser.parse_args(argv)
    report = build_report()
    if args.output == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0
