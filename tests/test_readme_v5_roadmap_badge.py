"""V5 Epic P0 E-P0-4 invariants: README v5 roadmap badge + link discipline.

The README MUST surface the v5 promotion roadmap as a transparent program
plan link AND must NOT claim production-readiness, production-platform,
support widening, live adapter execution, or any flag flip. The three
guard flags must be explicitly characterized as still `const false`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
ROADMAP_PATH = REPO_ROOT / ".claude" / "plans" / "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md"
GPP_STATUS_PATH = REPO_ROOT / ".claude" / "plans" / "GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md"

# Tokens that MUST NOT appear as positive claims in README prose
PRODUCTION_CLAIM_TOKENS = (
    "production ready",
    "production-ready",
    "production platform",
    "production-platform",
    "fully supported",
    "ga release",
    "general availability",
)


def _strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]*`", "", line)


def _strip_fenced_blocks(text: str) -> str:
    lines = text.splitlines()
    out = []
    in_fence = False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append(line)
    return "\n".join(out)


def _readme_prose() -> str:
    return _strip_fenced_blocks(README_PATH.read_text())


def test_readme_has_v5_promotion_roadmap_badge() -> None:
    text = README_PATH.read_text()
    assert "v5-promotion%20roadmap" in text, "v5 promotion roadmap badge missing"
    assert "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md" in text


def test_readme_has_gpp_badge() -> None:
    text = README_PATH.read_text()
    assert "GPP" in text
    assert "GENERAL-PURPOSE-PRODUCTION-PROMOTION-STATUS.md" in text


def test_readme_has_guard_flags_badge() -> None:
    text = README_PATH.read_text()
    assert "guard_flags" in text
    assert "const%20false" in text


def test_readme_roadmap_link_target_exists() -> None:
    assert ROADMAP_PATH.exists(), f"V5 roadmap missing at {ROADMAP_PATH}"


def test_readme_gpp_status_link_target_exists() -> None:
    assert GPP_STATUS_PATH.exists(), f"GPP status missing at {GPP_STATUS_PATH}"


def test_readme_disclaimer_mentions_three_guard_flags_const_false() -> None:
    """README banner MUST disclose the three guard flags + const false state."""
    prose = _readme_prose().lower()
    # Roadmap block must mention the three flags explicitly
    assert "support_widening" in prose
    assert "production_platform_claim" in prose
    assert "live_adapter_execution" in prose
    # And declare them const false
    assert "const false" in prose or "`const false`" in prose


def test_readme_no_production_ready_claim() -> None:
    """No positive production-ready / production-platform claim in prose."""
    prose = _readme_prose().lower()
    for token in PRODUCTION_CLAIM_TOKENS:
        # Allow only in negation prose (e.g. "not a ... production-platform claim")
        # Substring presence is OK only if a negation cue immediately precedes it
        idx = 0
        while True:
            idx = prose.find(token, idx)
            if idx == -1:
                break
            window = prose[max(0, idx - 60) : idx]
            negated = any(
                cue in window for cue in ("not a ", "not an ", "blanket ", '"not ', "**not**", "no production")
            )
            assert negated, (
                f"README contains positive production-claim token {token!r}; "
                f"context: ...{prose[max(0, idx - 30) : idx + len(token) + 30]!r}"
            )
            idx += len(token)


def test_readme_roadmap_status_banner_uses_qualified_language() -> None:
    """The Roadmap status banner must describe promotion as transparent
    program plan, NOT as accomplished promotion."""
    prose = _readme_prose().lower()
    assert "transparent program plan" in prose
    assert "operator-bound supersession" in prose
    assert "final" in prose


def test_readme_does_not_flip_guard_flags_in_prose() -> None:
    """No README sentence may claim a guard flag flipped to true."""
    prose = _readme_prose().lower()
    forbidden = (
        "support_widening = true",
        "support_widening: true",
        "production_platform_claim = true",
        "production_platform_claim: true",
        "live_adapter_execution = true",
        "live_adapter_execution: true",
    )
    for token in forbidden:
        assert token not in prose, f"README must not flip guard flag in prose: {token!r}"
