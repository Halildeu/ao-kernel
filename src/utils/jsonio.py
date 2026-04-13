"""Legacy JSON I/O — delegates to src.shared.utils for atomic writes.

Prefer importing from ``src.shared.utils`` directly for new code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.shared.utils import write_json_atomic


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, obj: Any, *, indent: int = 2) -> None:
    # Delegates to canonical atomic writer (includes fsync).
    write_json_atomic(path, obj, indent=indent)


def to_canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
