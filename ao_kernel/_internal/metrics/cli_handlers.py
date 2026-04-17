"""CLI handlers for ``ao-kernel metrics`` subcommands (PR-B5 C3).

Dispatched from :mod:`ao_kernel.cli`. Returns int exit code.

Exit code mapping (plan v4 §2.6):

- 0: success (textfile emitted to stdout/--output) or dormant-graceful
     (banner-only textfile; Grafana shows "No data" with explicit
     comment rationale).
- 1: user error (workspace resolve fail, --output path not writable,
     incompatible flags).
- 2: internal (corrupt evidence JSONL → :class:`EvidenceSourceCorruptedError`).
- 3: extra-missing informational (``pip install 'ao-kernel[metrics]'``
     prompt; textfile banner-only).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def cmd_metrics_export(args: Any) -> int:
    """Handle ``ao-kernel metrics export`` (cumulative Prometheus textfile).

    Full workspace scan → Prometheus exposition format. Plan v4 §2.6
    explicit invariants:

    - No ``--since`` or ``--run`` filtering (these break Prometheus
      counter semantics; debug-query is the debug surface for
      windowed queries).
    - Output is atomic when ``--output`` is supplied (tmp + fsync +
      rename via :func:`write_text_atomic`).
    - Dormant policy → exit 0 with banner comment (Grafana "No data").
    - Cost-dormant (cost tracking dormant) → LLM metric family absent;
      banner explains the cause.
    """
    from ao_kernel.metrics.derivation import derive_metrics_from_evidence
    from ao_kernel.metrics.errors import EvidenceSourceCorruptedError
    from ao_kernel.metrics.export import generate_textfile
    from ao_kernel.metrics.policy import load_metrics_policy
    from ao_kernel.metrics.registry import build_registry, is_metrics_available

    workspace = _resolve_workspace(args)

    # Load metrics policy (fail-closed on corrupt override).
    metrics_policy = load_metrics_policy(workspace)

    # Load cost policy to decide cost-disjunction gate. The policy
    # loader is imported lazily so the metrics export CLI does not
    # pull in the cost runtime when it is not needed (e.g., dormant
    # workspace). Cost policy absence or load failure is treated as
    # cost-dormant — the banner surfaces the condition to the
    # operator without failing the export.
    cost_dormant = _is_cost_dormant(workspace)

    # Build registry. LLM families skipped when cost-dormant so they
    # cannot appear in the textfile even as metadata (plan v4 §2
    # invariant).
    built = build_registry(
        metrics_policy,
        include_llm_metrics=not cost_dormant,
    )

    # Extra-missing branch: prometheus-client not installed.
    if built is None:
        if not is_metrics_available():
            payload = generate_textfile(
                built=None,
                metrics_dormant=not metrics_policy.enabled,
                cost_dormant=cost_dormant,
            )
            _emit_output(payload, args)
            return 3
        # Unexpected: is_metrics_available() returned False earlier
        # but build_registry returned None anyway — treat as internal.
        print(
            "error: metrics registry could not be constructed",
            file=sys.stderr,
        )
        return 2

    # Populate metrics families from evidence + run_store + coordination.
    try:
        derive_metrics_from_evidence(workspace, built, metrics_policy)
    except EvidenceSourceCorruptedError as exc:
        print(f"error: corrupt evidence JSONL — {exc}", file=sys.stderr)
        return 2

    # Serialize. Dormant / cost-dormant banners prepend naturally via
    # the export helper; callers rely on the resulting text being
    # Prometheus-parseable even with comments attached.
    payload = generate_textfile(
        built,
        metrics_dormant=not metrics_policy.enabled,
        cost_dormant=cost_dormant,
    )

    try:
        _emit_output(payload, args)
    except (OSError, PermissionError) as exc:
        print(f"error: output write failed — {exc}", file=sys.stderr)
        return 1

    return 0


def _emit_output(payload: str, args: Any) -> None:
    """Write ``payload`` to ``--output`` (atomic) or stdout."""
    output_path = getattr(args, "output", None)
    if output_path:
        from ao_kernel._internal.shared.utils import write_text_atomic

        write_text_atomic(Path(output_path), payload)
        return
    sys.stdout.write(payload)
    if not payload.endswith("\n"):
        sys.stdout.write("\n")


def _resolve_workspace(args: Any) -> Path:
    """Resolve workspace root from ``--workspace-root`` or CWD lookup.

    Mirrors :func:`ao_kernel._internal.evidence.cli_handlers._resolve_workspace`.
    """
    ws = getattr(args, "workspace_root", None)
    if ws:
        return Path(ws)
    from ao_kernel.config import workspace_root

    resolved = workspace_root()
    if resolved is None:
        print("error: no .ao/ workspace found", file=sys.stderr)
        sys.exit(1)
    return resolved


def _is_cost_dormant(workspace: Path) -> bool:
    """Return ``True`` when cost tracking is effectively off.

    A missing cost policy file or a load failure counts as dormant —
    the metrics CLI surfaces this via the cost-dormant banner rather
    than aborting the export.
    """
    try:
        from ao_kernel.cost.policy import load_cost_policy
    except ImportError:
        return True
    try:
        policy = load_cost_policy(workspace)
    except Exception:
        return True
    return not policy.enabled


__all__ = [
    "cmd_metrics_export",
]
