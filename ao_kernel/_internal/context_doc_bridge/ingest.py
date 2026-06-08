"""Ingest repo ``.md`` sources into the canonical store with doc_bridge provenance.

Authoritative provenance lives inside each canonical item's ``provenance``
field under the ``doc_bridge`` namespace (no side-map — Codex acceptance #3).
The whole batch is written under a single CAS revision via
``canonical_store.promote_many`` (Codex acceptance #1: no partial state).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ao_kernel._internal.context_doc_bridge import keygen, mapping, parser
from ao_kernel.context import canonical_store as cs
from ao_kernel.errors import CanonicalRevisionConflict

PROVENANCE_NS = "doc_bridge"
PROVENANCE_SCHEMA_VERSION = "doc-bridge-provenance.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Extracted:
    """One deterministic entry extracted from a source under a rule."""

    key: str
    value: str
    confidence: float
    status: str
    doc_date: str
    value_hash: str


@dataclass
class IngestReport:
    ingested: int = 0
    revision: str = ""
    by_type: dict[str, int] = field(default_factory=dict)
    secrets_skipped: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)


def _confidence_for(rule: dict[str, Any], status: str) -> float:
    status_map = rule.get("status_map")
    if status_map:
        return float(status_map.get(status.lower(), status_map.get("unknown", 0.7)))
    return float(rule.get("confidence", 0.7))


def extract_from_source(rule: dict[str, Any], src_rel: str, text: str) -> list[Extracted]:
    """Deterministically extract entries from one source's text under a rule.

    Pure + shared by ingest (write) and renderer (re-verify): identical inputs
    always produce identical keys + value_hash, so the renderer can detect when
    a source drifted away from what was ingested.
    """
    strategy = rule["value_strategy"]
    template = rule["key_template"]
    fname = Path(src_rel).name
    stem = keygen.stem_of(fname)
    num = keygen.num_of(fname)
    out: list[Extracted] = []

    if strategy == "first_heading":
        value = parser.first_heading(text, stem)
        key = keygen.render_key(template, stem=stem, num=num)
        out.append(Extracted(key, value, _confidence_for(rule, "unknown"), "", "", parser.sha256_text(value)))
    elif strategy == "status_line":
        title = parser.first_heading(text, stem)
        status, date = parser.status_and_date(text)
        value = f"{title} [{status}{(' ' + date) if date else ''}]"
        key = keygen.render_key(template, stem=stem, num=num)
        out.append(Extracted(key, value, _confidence_for(rule, status), status, date, parser.sha256_text(value)))
    elif strategy == "section_headings":
        limit = int(rule.get("max_items", 8))
        for index, heading in enumerate(parser.section_headings(text, limit)):
            key = keygen.render_key(template, stem=stem, num=num, index=index)
            out.append(Extracted(key, heading, _confidence_for(rule, "unknown"), "", "", parser.sha256_text(heading)))
    return out


def _build_provenance(rule: dict[str, Any], src_rel: str, ex: Extracted, doc_hash: str) -> dict[str, Any]:
    return {
        PROVENANCE_NS: {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "src": src_rel,
            "mapping_id": rule["mapping_id"],
            "type": rule["type"],
            "tier": rule["tier"],
            "status": ex.status,
            "doc_date": ex.doc_date,
            "doc_hash": doc_hash,
            "value_hash": ex.value_hash,
            "observed_at": _now_iso(),
        }
    }


def ingest_docs(
    root: str | Path,
    *,
    repo_root: str | Path | None = None,
    mapping_path: str | None = None,
) -> IngestReport:
    """Parse repo ``.md`` sources per the mapping and write them to the store.

    ``root`` is the workspace root (where ``.ao`` lives). ``repo_root`` (where
    the ``.md`` sources are scanned) defaults to ``root`` — a single root in the
    common in-repo case (Codex acceptance #2). Same signature shape as
    :func:`render_context_packet` so the two never get transposed.
    """
    ws = Path(root)
    repo = Path(repo_root) if repo_root is not None else ws
    spec = mapping.load_mapping(mapping_path)
    max_files = int(spec.get("max_files_per_rule", mapping.DEFAULT_MAX_FILES))
    max_bytes = int(spec.get("max_file_bytes", mapping.DEFAULT_MAX_BYTES))

    report = IngestReport()
    items: list[dict[str, Any]] = []
    seen: dict[str, tuple[str, str]] = {}

    for rule in spec["rules"]:
        mid = rule["mapping_id"]
        policy = rule.get("collision_policy", "strict")
        for src in mapping.resolve_sources(repo, rule["glob"], max_files=max_files, max_bytes=max_bytes):
            src_rel = str(src.relative_to(repo))
            text = src.read_text(encoding="utf-8", errors="replace")
            doc_hash = parser.sha256_file(src)
            for ex in extract_from_source(rule, src_rel, text):
                if parser.looks_like_secret(ex.value):
                    report.secrets_skipped.append(f"{src_rel} ({ex.key})")
                    continue
                supersedes: str | None = None
                prev = seen.get(ex.key)
                if prev is not None and prev != (src_rel, mid):
                    if policy == "supersede":
                        supersedes = ex.key
                    else:  # strict | update_same_source: reject cross-source collision
                        report.collisions.append(f"{ex.key}: {prev[0]} vs {src_rel}")
                        continue
                seen[ex.key] = (src_rel, mid)
                category = "fact" if rule["type"] == "fact" else "architecture"
                items.append(
                    {
                        "key": ex.key,
                        "value": ex.value,
                        "category": category,
                        "source": "agent",
                        "confidence": ex.confidence,
                        "session_id": "doc-bridge",
                        "supersedes": supersedes,
                        "provenance": _build_provenance(rule, src_rel, ex, doc_hash),
                    }
                )
                report.by_type[rule["type"]] = report.by_type.get(rule["type"], 0) + 1

    if items:
        report.revision = _cas_write(ws, items)
        report.ingested = len(items)
    return report


def _cas_write(ws: Path, items: list[dict[str, Any]], retries: int = 1) -> str:
    """Single-revision batch write with read-revision-mutate-write retry.

    On conflict the loop re-loads a FRESH snapshot + revision (never re-writes
    the stale snapshot) — Codex acceptance #1.
    """
    attempt = 0
    while True:
        store = cs.load_store(ws)
        expected = cs.store_revision(store)
        try:
            return cs.promote_many(ws, items, expected_revision=expected, allow_overwrite=False)
        except CanonicalRevisionConflict:
            attempt += 1
            if attempt > retries:
                raise
