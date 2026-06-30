"""Bounded async helpers for productized AO-MA local wrappers.

This module owns the concurrency primitive used by
``orchestration run-wrapper-async``. It is deliberately tiny: callers supply
already-validated, no-network, local callables; this helper only schedules them
through a bounded thread pool and returns results in input order.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar


T = TypeVar("T")


def invoke_callables_concurrently(calls: list[Callable[[], T]], *, max_workers: int) -> list[T]:
    """Run callables with bounded concurrency and preserve input order."""

    if max_workers <= 0:
        raise ValueError("max_workers must be a positive integer")
    if not calls:
        return []
    ordered: list[T | None] = [None] * len(calls)
    with ThreadPoolExecutor(max_workers=min(max_workers, len(calls))) as pool:
        futures = {pool.submit(call): index for index, call in enumerate(calls)}
        for future in as_completed(futures):
            ordered[futures[future]] = future.result()
    results: list[T] = []
    for item in ordered:
        if item is None:
            raise RuntimeError("concurrent invocation finished with a missing result")
        results.append(item)
    return results
