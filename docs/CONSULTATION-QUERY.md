# Consultation Query — Consumer Side (v3.6)

**Status:** v3.6 Memory Loop Closure — consumer-side surfaces for the opt-in consultation promotion pipeline that landed in v3.5.

v3.5 D1/D2a/D2b shipped the **producer** half: consultation paths canonicalized, resolution records archived under `.ao/evidence/consultations/<CNS-ID>/`, and eligible `AGREE`/`PARTIAL` records optionally promoted into `.ao/canonical_decisions.v1.json` with keys like `consultation.<CNS-ID>`.

v3.6 E1/E2/E3 close the loop on the **consumer** side:

- **E1** — `query_promoted_consultations()` typed reader facade
- **E2** — `compile_context` 4-lane integration (`## Consultations` section) with per-profile caps via `ProfileConfig.max_consultations`
- **E3** — `ao_memory_read` MCP pagination (`max_results`, `offset`, `total`, `next_offset`)

---

## 1. Policy setup

By default the MCP memory surface ships **fail-closed**: `policy_mcp_memory.v1.json` has `read.enabled: false`. To expose promoted consultations to external agents (or to run the CLI `memory_read` MCP tool manually), override at the workspace level:

```jsonc
// .ao/policies/policy_mcp_memory.v1.json  (workspace override)
{
  "version": "v1",
  "read": {
    "enabled": true,
    "allowed_patterns": ["consultation.*"]
  },
  "write": {
    "enabled": false,
    "allowed_key_prefixes": [],
    "max_value_bytes": 4096,
    "allowed_source_prefixes": ["mcp:"]
  },
  "rate_limit": {
    "reads_per_minute": 60,
    "writes_per_minute": 10
  }
}
```

The bundled `policy_scorecard`-style "enabled by default" is **not** applied here; memory read is opt-in. Tight `allowed_patterns` scope lets you expose only consultations without lifting the rest of the canonical store.

---

## 2. Python API (E1 reader facade)

```python
from pathlib import Path
from ao_kernel.consultation.promotion import query_promoted_consultations

records = query_promoted_consultations(Path("."))
for r in records:
    print(r.cns_id, r.final_verdict, r.confidence, r.topic)
```

Filters:

```python
# AGREE-only
agree = query_promoted_consultations(Path("."), verdict="AGREE")

# Topic substring (case-insensitive)
arch = query_promoted_consultations(Path("."), topic="architecture")

# Include temporally expired entries (default False)
all_time = query_promoted_consultations(Path("."), include_expired=True)
```

`PromotedConsultation` dataclass fields:

| Field | Type | Notes |
|---|---|---|
| `cns_id` | `str` | strict core — missing → row skipped |
| `final_verdict` | `str` | `AGREE` or `PARTIAL` |
| `promoted_at` | `str` | ISO-8601 UTC; strict core |
| `topic` | `str \| None` | producer backfills `"unknown"` |
| `from_agent` | `str \| None` | producer backfills `"unknown"` |
| `to_agent` | `str \| None` | producer backfills `"unknown"` |
| `resolved_at` | `str \| None` | source-derived |
| `record_digest` | `str \| None` | `"sha256:..."`; from provenance |
| `evidence_path` | `str \| None` | relative workspace path; from provenance |
| `confidence` | `float` | top-level or derived via `verdict_confidence` (AGREE=1.0, PARTIAL=0.7) |

Malformed rows (missing strict-core fields) are silently skipped — the reader never raises on store content.

---

## 3. MCP API (E3 pagination)

External agents query via the `ao_memory_read` MCP tool. Default page size is 50; hard-capped at 200.

```jsonc
// MCP call
{
  "tool": "ao_memory_read",
  "params": {
    "workspace_root": "/path/to/project",
    "pattern": "consultation.*",
    "max_results": 50,
    "offset": 0
  }
}
```

Response envelope:

```jsonc
{
  "api_version": "0.1.0",
  "tool": "ao_memory_read",
  "allowed": true,
  "decision": "executed",
  "reason_codes": [],
  "data": {
    "items": [ /* up to max_results canonical entries */ ],
    "count": 50,
    "total": 142,
    "next_offset": 50
  },
  "error": null
}
```

Paginate by looping while `data.next_offset` is non-null:

```python
next_offset = 0
while next_offset is not None:
    resp = mcp_call("ao_memory_read", {
        "pattern": "consultation.*",
        "max_results": 50,
        "offset": next_offset,
    })
    for item in resp["data"]["items"]:
        process(item)
    next_offset = resp["data"]["next_offset"]
```

---

## 4. Context pipeline integration (E2)

The context compiler renders up to `ProfileConfig.max_consultations` promoted consultations under a `## Consultations` section in the preamble. Profile defaults:

| Profile | `max_consultations` |
|---|---|
| `PLANNING` | 10 |
| `REVIEW` | 10 |
| `TASK_EXECUTION` | 3 |
| `STARTUP` | 3 |
| `ASSESSMENT` | 3 |
| `EMERGENCY` | 0 (lean-context invariant) |

Loading happens at the caller layer (`compile_context_sdk`); the compiler itself is pure and I/O-free. When consultations are present:

1. The SDK queries via `query_promoted_consultations(workspace_root)`.
2. Results are split AGREE-first, PARTIAL-second.
3. Sliced to `max_consultations` for the resolved profile.
4. Fed into the pure compiler, which accepts lines into the budget-aware `max_tokens * 4` char cap (tail-first drop on overflow).

Rendered line format:

```
- [CNS-ID] topic VERDICT (from_agent→to_agent, resolved_at)
```

Lenient edges render gracefully: `None` topic → `"(topic unknown)"`, `None` agents → `"(from)"` / `"(to)"`, `None` resolved_at → `"unresolved"`. Literal `"None"` never appears.

---

## 5. AGREE vs PARTIAL semantics

The producer confidence map (v3.5 D2b) ships:

- `AGREE` → confidence `1.0`
- `PARTIAL` → confidence `0.7`

Consumers should treat `PARTIAL` records as weaker signals (agent-to-agent agreement with caveats). The reader facade does NOT filter by confidence — callers decide policy. Typical pattern: `verdict="AGREE"` for hard gates, include PARTIAL for advisory lanes.

---

## 6. See also

- [`docs/EVIDENCE-TIMELINE.md`](EVIDENCE-TIMELINE.md) — producer-side consultation archive + integrity manifest (v3.5 D2a)
- [`ao_kernel/consultation/promotion.py`](../ao_kernel/consultation/promotion.py) — `promote_resolved_consultations` + `query_promoted_consultations`
- [`ao_kernel/context/context_compiler.py`](../ao_kernel/context/context_compiler.py) — 4-lane compile + `## Consultations` section
- [`ao_kernel/_internal/mcp/memory_tools.py`](../ao_kernel/_internal/mcp/memory_tools.py) — `handle_memory_read` handler (pagination lives here)
