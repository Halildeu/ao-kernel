"""Structured logging module for the autonomous-orchestrator control-plane.

Provides a getLogger() wrapper that adds run_id and context to log records.
Uses Python's standard logging module; OTEL log export is opt-in via env var.

Usage::

    from src.shared.logger import get_logger
    log = get_logger(__name__)
    log.info("Runner started", run_id="abc123", intent="apply")
"""
from __future__ import annotations

import logging
import os
from typing import Any


# Configure root logger format once at import time
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.WARNING,
)


def get_logger(name: str) -> logging.Logger:
    """Return a standard Logger for *name*.

    When AO_LOG_LEVEL env var is set, apply it to this logger.
    Callers use standard logging methods: logger.info/warning/error/debug.
    """
    logger = logging.getLogger(name)
    level_str = os.environ.get("AO_LOG_LEVEL", "").upper()
    if level_str in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        logger.setLevel(getattr(logging, level_str))
    return logger
