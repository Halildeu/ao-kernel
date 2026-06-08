"""Public context doc-bridge facade.

Bridges a repo's ``.md``-governed context (AGENTS.md, ADRs, current-state, ...)
into the ao-kernel governed store, and renders a short, provenance-tagged
markdown context packet for injection into any AI (Claude / Codex / Mavis).

Design: governed JSON store (query / freshness / provenance / tier) + a rendered
markdown packet (fresh + high-confidence only, NOT a full dump). The store stays
the single source of truth; the packet is derived and fail-closed.

    from ao_kernel.context.doc_bridge import ingest_docs, render_context_packet

    report = ingest_docs("/path/to/repo")            # root = repo = workspace
    packet = render_context_packet("/path/to/repo")  # short markdown packet

Both take the workspace root first; pass ``repo_root=`` to scan a different
tree (e.g. ingest an external repo read-only into a separate workspace).

The implementation lives in ``ao_kernel._internal.context_doc_bridge`` and may
change across versions; this facade is the stable surface.
"""

from __future__ import annotations

from ao_kernel._internal.context_doc_bridge.ingest import IngestReport, ingest_docs
from ao_kernel._internal.context_doc_bridge.renderer import render_context_packet

__all__ = ["ingest_docs", "render_context_packet", "IngestReport"]
