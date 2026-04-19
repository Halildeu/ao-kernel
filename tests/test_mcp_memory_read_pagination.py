"""v3.6 E3: ao_memory_read pagination tests (5 pins).

Covers:
- Default max_results=50 honoured when store has many entries
- Explicit offset returns later page
- max_results > 200 clamped to 200
- total reflects post-policy-filtered count (distinct from page count)
- next_offset=null when the last page is reached
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ao_kernel._internal.mcp.memory_tools import handle_memory_read


def _write_policy(ws: Path, *, reads_per_minute: int = 6000) -> None:
    """High rate-limit so pagination tests can hit multiple reads."""
    policies_dir = ws / ".ao" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "version": "v1",
        "read": {"enabled": True, "allowed_patterns": ["*"]},
        "write": {
            "enabled": False,
            "allowed_key_prefixes": [],
            "max_value_bytes": 4096,
            "allowed_source_prefixes": ["mcp:"],
        },
        "rate_limit": {
            "reads_per_minute": reads_per_minute,
            "writes_per_minute": 10,
        },
    }
    (policies_dir / "policy_mcp_memory.v1.json").write_text(
        json.dumps(doc),
        encoding="utf-8",
    )


def _seed_store(ws: Path, *, count: int) -> None:
    """Write `count` canonical decisions under distinct keys."""
    ao = ws / ".ao"
    ao.mkdir(parents=True, exist_ok=True)
    decisions: dict[str, dict[str, Any]] = {}
    for i in range(count):
        key = f"runtime.test.k{i:04d}"
        decisions[key] = {
            "key": key,
            "value": f"v{i}",
            "category": "runtime",
            "source": "test",
            "confidence": 0.8,
            "provenance": {},
            "promoted_at": f"2026-04-19T{i % 24:02d}:00:00Z",
            "expires_at": "",
        }
    (ao / "canonical_decisions.v1.json").write_text(
        json.dumps(
            {
                "version": "v1",
                "decisions": decisions,
                "facts": {},
                "updated_at": "2026-04-19T00:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.fixture
def ws_populated(tmp_path: Path) -> Path:
    """Workspace with enabled policy + 100 seeded decisions."""
    _write_policy(tmp_path)
    _seed_store(tmp_path, count=100)
    return tmp_path


class TestPagination:
    def test_default_max_results_caps_at_50(self, ws_populated: Path) -> None:
        """Default max_results=50 honoured when store has 100 entries."""
        result = handle_memory_read(
            {"workspace_root": str(ws_populated), "pattern": "*"},
        )
        assert result["decision"] == "executed"
        data = result["data"]
        assert data["count"] == 50
        assert len(data["items"]) == 50
        assert data["total"] == 100
        assert data["next_offset"] == 50

    def test_explicit_offset_returns_second_page(
        self,
        ws_populated: Path,
    ) -> None:
        """offset=50 + default max_results=50 returns the rest."""
        result = handle_memory_read(
            {
                "workspace_root": str(ws_populated),
                "pattern": "*",
                "offset": 50,
            },
        )
        assert result["decision"] == "executed"
        data = result["data"]
        assert data["count"] == 50
        assert data["total"] == 100
        # Last page exhausted → no further cursor.
        assert data["next_offset"] is None

    def test_max_results_over_cap_clamped_to_200(
        self,
        tmp_path: Path,
    ) -> None:
        """max_results > 200 silently clamped to 200 — MCP payload limit."""
        _write_policy(tmp_path)
        _seed_store(tmp_path, count=250)
        result = handle_memory_read(
            {
                "workspace_root": str(tmp_path),
                "pattern": "*",
                "max_results": 500,
            },
        )
        assert result["decision"] == "executed"
        data = result["data"]
        assert data["count"] == 200
        assert data["total"] == 250
        assert data["next_offset"] == 200

    def test_total_distinct_from_count_when_paginating(
        self,
        ws_populated: Path,
    ) -> None:
        """`count` = page size, `total` = post-policy-filter total."""
        result = handle_memory_read(
            {
                "workspace_root": str(ws_populated),
                "pattern": "*",
                "max_results": 10,
                "offset": 20,
            },
        )
        data = result["data"]
        assert data["count"] == 10  # this page
        assert data["total"] == 100  # full store
        assert data["count"] != data["total"]
        assert data["next_offset"] == 30

    def test_next_offset_null_at_exhaustion(
        self,
        ws_populated: Path,
    ) -> None:
        """next_offset is null when the current page reaches total."""
        result = handle_memory_read(
            {
                "workspace_root": str(ws_populated),
                "pattern": "*",
                "max_results": 100,
            },
        )
        data = result["data"]
        assert data["count"] == 100
        assert data["total"] == 100
        assert data["next_offset"] is None


class TestInputValidation:
    def test_invalid_max_results_zero_rejected(
        self,
        ws_populated: Path,
    ) -> None:
        """max_results < 1 → deny with invalid_max_results reason."""
        result = handle_memory_read(
            {
                "workspace_root": str(ws_populated),
                "pattern": "*",
                "max_results": 0,
            },
        )
        assert result["decision"] == "deny"
        assert "invalid_max_results" in result["reason_codes"]

    def test_invalid_offset_negative_rejected(
        self,
        ws_populated: Path,
    ) -> None:
        """offset < 0 → deny with invalid_offset reason."""
        result = handle_memory_read(
            {
                "workspace_root": str(ws_populated),
                "pattern": "*",
                "offset": -5,
            },
        )
        assert result["decision"] == "deny"
        assert "invalid_offset" in result["reason_codes"]


class TestBackwardCompat:
    def test_no_pagination_params_still_returns_items_and_count(
        self,
        ws_populated: Path,
    ) -> None:
        """Pre-E3 callers that only read `data.items`/`data.count`
        still work; the new `total`/`next_offset` fields are additive."""
        result = handle_memory_read(
            {"workspace_root": str(ws_populated), "pattern": "*"},
        )
        data = result["data"]
        assert "items" in data
        assert "count" in data
        # New fields additive — present but callers may ignore.
        assert "total" in data
        assert "next_offset" in data
