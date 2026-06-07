from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ao_kernel.extension_truth_ratchet import (
    build_report,
    classify_bucket,
    compute_priority_score,
    render_text,
)
from ao_kernel.extensions.loader import (
    TRUTH_TIER_CONTRACT_ONLY,
    TRUTH_TIER_QUARANTINED,
    TRUTH_TIER_RUNTIME_BACKED,
    ExtensionManifest,
)


def _row(report: dict[str, object], extension_id: str) -> dict[str, object]:
    rows = report["rows"]
    assert isinstance(rows, list)
    for candidate in rows:
        assert isinstance(candidate, dict)
        if candidate.get("extension_id") == extension_id:
            return candidate
    raise AssertionError(f"extension row not found: {extension_id}")


def _synth(
    *,
    tier: str,
    missing: int = 0,
    remap: int = 0,
    entrypoints: int = 0,
    ui: int = 0,
) -> ExtensionManifest:
    """Build a synthetic manifest exercising only the fields classify_bucket reads.

    Decouples bucket-classification behavior from the live bundled inventory so
    these tests stay valid even after retire_candidate extensions are removed.
    """
    return ExtensionManifest(
        version="extension.manifest.v1",
        extension_id="SYNTH-FIXTURE",
        semver="1.0.0",
        origin="test",
        owner="test",
        layer_contract={},
        entrypoints={"ops": ["op"] * entrypoints},
        policies=[],
        ui_surfaces=["ui"] * ui,
        compat={},
        truth_tier=tier,
        missing_runtime_refs=tuple(f"missing/{i}" for i in range(missing)),
        remap_candidate_refs=tuple(f"remap/{i}" for i in range(remap)),
    )


# ── classify_bucket: synthetic, behavior-level (no live-inventory dependency) ──


def test_classify_bucket_runtime_backed() -> None:
    manifest = _synth(tier=TRUTH_TIER_RUNTIME_BACKED, missing=3, remap=3, entrypoints=2, ui=1)
    assert classify_bucket(manifest) == "maintain_runtime_backed"


def test_classify_bucket_promotion_candidate() -> None:
    manifest = _synth(tier=TRUTH_TIER_CONTRACT_ONLY, missing=0, remap=0)
    assert classify_bucket(manifest) == "promotion_candidate"


def test_classify_bucket_retire_candidate() -> None:
    # quarantined + missing>=9 + no entrypoints + no ui = dead shell.
    manifest = _synth(tier=TRUTH_TIER_QUARANTINED, missing=9, remap=2, entrypoints=0, ui=0)
    assert classify_bucket(manifest) == "retire_candidate"


def test_classify_bucket_remap_priority() -> None:
    manifest = _synth(tier=TRUTH_TIER_QUARANTINED, missing=5, remap=2, entrypoints=3, ui=1)
    assert classify_bucket(manifest) == "remap_priority"


def test_classify_bucket_quarantine_keep_when_entrypoints_present() -> None:
    # quarantined + missing>=9 but has entrypoints -> not retire, not remap (missing>8).
    manifest = _synth(tier=TRUTH_TIER_QUARANTINED, missing=9, remap=0, entrypoints=4, ui=0)
    assert classify_bucket(manifest) == "quarantine_keep"


def test_classify_bucket_quarantine_keep_when_no_remap_refs() -> None:
    # quarantined + missing<=8 but no remap refs -> falls through to quarantine_keep.
    manifest = _synth(tier=TRUTH_TIER_QUARANTINED, missing=5, remap=0, entrypoints=0, ui=0)
    assert classify_bucket(manifest) == "quarantine_keep"


def test_compute_priority_score_only_for_remap_priority() -> None:
    remap = _synth(tier=TRUTH_TIER_QUARANTINED, missing=5, remap=2, entrypoints=3, ui=1)
    # (entrypoints*2) + (ui*3) - missing - remap = 6 + 3 - 5 - 2 = 2
    assert classify_bucket(remap) == "remap_priority"
    assert compute_priority_score(remap, "remap_priority") == 2

    not_remap = _synth(tier=TRUTH_TIER_CONTRACT_ONLY, missing=0, remap=0)
    assert compute_priority_score(not_remap, "promotion_candidate") is None


# ── build_report: live inventory, invariant-level (resilient to retirement) ──


def test_build_report_has_expected_buckets_and_queue() -> None:
    report = build_report()
    summary = report["summary"]
    assert summary["total_extensions"] >= 1
    assert summary["runtime_backed"] >= 2
    assert summary["contract_only"] >= 1
    assert summary["quarantined"] >= 1

    queue = report["ordered_queue"]
    # All bucket queues are always present, even when empty (e.g. retire_candidate
    # may be empty after dead inventory is retired).
    for bucket in ("promotion_candidate", "remap_priority", "quarantine_keep", "retire_candidate"):
        assert bucket in queue
        assert isinstance(queue[bucket], list)

    assert "PRJ-CONTEXT-ORCHESTRATION" in queue["promotion_candidate"]
    assert "PRJ-RELEASE-AUTOMATION" in queue["remap_priority"]


def test_known_extension_classifications_are_stable() -> None:
    report = build_report()

    context_orch = _row(report, "PRJ-CONTEXT-ORCHESTRATION")
    assert context_orch["bucket"] == "promotion_candidate"
    assert context_orch["priority_score"] is None

    cockpit = _row(report, "PRJ-UI-COCKPIT-LITE")
    assert cockpit["bucket"] == "quarantine_keep"
    assert cockpit["priority_score"] is None


def test_render_text_contains_key_sections() -> None:
    rendered = render_text(build_report())
    assert "truth_inventory_ratchet" in rendered
    assert "queue.promotion_candidate:" in rendered
    assert "queue.remap_priority:" in rendered
    # retire_candidate section renders cleanly even when the queue is empty.
    assert "queue.retire_candidate:" in rendered


def test_script_wrapper_executes_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/truth_inventory_ratchet.py", "--output", "json"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "summary" in payload
    assert "ordered_queue" in payload
