#!/usr/bin/env python3
"""Codex provider command for ``ao-kernel ai-review``."""

from __future__ import annotations

from ao_kernel.ai_review_provider_wrappers import main


if __name__ == "__main__":
    raise SystemExit(main(["codex"]))
