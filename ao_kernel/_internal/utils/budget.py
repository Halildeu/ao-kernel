from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """
    Deterministic rough token estimate.

    WWV heuristic: ~4 characters per token => ceil(len(text) / 4).
    """
    if not isinstance(text, str) or not text:
        return 0
    return (len(text) + 3) // 4

