from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ao_kernel._internal.roadmap.step_templates import VirtualFS


@dataclass
class ChangeCounter:
    paths_touched: set[str]
    diff_lines: int

    def touch(self, path: str, diff_lines: int) -> None:
        self.paths_touched.add(path)
        self.diff_lines += diff_lines


@dataclass
class _ExecutionState:
    virtual_fs: VirtualFS
    counters_by_milestone: dict[str, ChangeCounter]
    write_allowlist: list[str] | None
    dlq: dict[str, Any] | None


@dataclass(frozen=True)
class _CoreImmutabilityPolicy:
    enabled: bool
    default_mode: str
    allow_env_var: str
    allow_env_value: str
    core_write_mode: str
    ssot_write_allowlist: tuple[str, ...]
    require_unlock_reason: bool
    evidence_required_when_unlocked: bool
    blocked_write_error_code: str
    core_git_required: bool
