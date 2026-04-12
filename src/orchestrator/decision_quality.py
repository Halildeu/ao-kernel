"""Continuous decision quality monitoring.

Records every AI decision's quality metrics and computes rolling scores.
Enables trend alerting and PDCA triggers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log_path(workspace_root: Path) -> Path:
    return workspace_root / ".cache" / "index" / "decision_quality_log.v1.jsonl"


def record_decision_quality(
    *,
    workspace_root: Path,
    run_id: str,
    decision_boundary_used: str,
    quality_gate_results: list[dict[str, Any]],
    provider: str = "",
    model: str = "",
    outcome: str = "SUCCESS",
    latency_ms: int = 0,
) -> None:
    """Append decision quality entry to JSONL log."""
    gates_passed = sum(1 for r in quality_gate_results if r.get("passed", True))
    gates_failed = sum(1 for r in quality_gate_results if not r.get("passed", True))

    entry = {
        "timestamp": _now_iso(),
        "run_id": run_id,
        "boundary": decision_boundary_used,
        "gates_passed": gates_passed,
        "gates_failed": gates_failed,
        "provider": provider,
        "model": model,
        "outcome": outcome,
        "latency_ms": latency_ms,
    }

    log = _log_path(workspace_root)
    log.parent.mkdir(parents=True, exist_ok=True)

    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")


def compute_decision_quality_score(
    *,
    workspace_root: Path,
    window_days: int = 7,
) -> dict[str, Any]:
    """Compute rolling decision quality score from log."""
    log = _log_path(workspace_root)
    if not log.exists():
        return {"status": "NO_DATA", "score": 0.0, "entries": 0}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    entries: list[dict[str, Any]] = []

    for line in log.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if str(entry.get("timestamp", "")) >= cutoff:
                entries.append(entry)
        except Exception:
            continue

    if not entries:
        return {"status": "NO_DATA", "score": 0.0, "entries": 0}

    total = len(entries)
    successes = sum(1 for e in entries if e.get("outcome") == "SUCCESS")
    gate_pass_total = sum(int(e.get("gates_passed", 0)) for e in entries)
    gate_fail_total = sum(int(e.get("gates_failed", 0)) for e in entries)
    gate_total = gate_pass_total + gate_fail_total

    outcome_rate = successes / max(total, 1)
    gate_pass_rate = gate_pass_total / max(gate_total, 1)
    quality_score = round((outcome_rate * 0.6 + gate_pass_rate * 0.4), 4)

    # Trend detection
    if total >= 10:
        recent = entries[-5:]
        recent_success = sum(1 for e in recent if e.get("outcome") == "SUCCESS")
        recent_rate = recent_success / len(recent)
        if recent_rate < outcome_rate - 0.15:
            trend = "degrading"
        elif recent_rate > outcome_rate + 0.1:
            trend = "improving"
        else:
            trend = "stable"
    else:
        trend = "insufficient_data"

    return {
        "status": "OK",
        "score": quality_score,
        "entries": total,
        "window_days": window_days,
        "outcome_rate": round(outcome_rate, 4),
        "gate_pass_rate": round(gate_pass_rate, 4),
        "trend": trend,
        "alert": quality_score < 0.7,
    }
