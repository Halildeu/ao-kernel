"""V5 Epic 8 E-8-1 invariants: production deployment guide presence + claim discipline.

Docs-only slice. The guide MUST:
- Exist at docs/PRODUCTION-DEPLOYMENT-GUIDE.md
- Cover three deployment patterns (standalone, Docker, k8s)
- Disclaim production-readiness explicitly (3 guard flags const false)
- Avoid positive production-platform / GA-release claim tokens (negation prose allowed)
- Not flip any guard flag
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = REPO_ROOT / "docs" / "PRODUCTION-DEPLOYMENT-GUIDE.md"
ROADMAP_PATH = REPO_ROOT / ".claude" / "plans" / "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md"
PLAN_PATH = REPO_ROOT / ".claude" / "plans" / "EPIC-8-1-PRODUCTION-DEPLOYMENT-GUIDE.md"

PROHIBITED_CLAIM_TOKENS = (
    "production ready",
    "production-ready",
    "ga release",
    "general availability",
    "fully supported",
    "we are production",
    "live in production",
)


def _strip_fenced_blocks(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append(line)
    return "\n".join(out)


def _guide_prose() -> str:
    return _strip_fenced_blocks(GUIDE_PATH.read_text())


# ---- 1. Presence + structure (5) -----------------------------------------


def test_guide_exists() -> None:
    assert GUIDE_PATH.exists(), f"deployment guide missing at {GUIDE_PATH}"


def test_guide_covers_standalone_pattern() -> None:
    text = GUIDE_PATH.read_text()
    assert "Standalone Python Package" in text
    assert "pip install ao-kernel" in text
    assert "ao-kernel init" in text


def test_guide_covers_docker_pattern() -> None:
    text = GUIDE_PATH.read_text()
    assert "Docker" in text
    assert "Dockerfile" in text
    assert "Compose" in text


def test_guide_covers_kubernetes_pattern() -> None:
    text = GUIDE_PATH.read_text()
    assert "Kubernetes" in text
    assert "PersistentVolumeClaim" in text or "PersistentVolume" in text
    assert "Helm" in text


def test_guide_lists_required_python_version() -> None:
    text = GUIDE_PATH.read_text()
    assert "3.11+" in text or "3.11+" in text.replace(" ", "")


# ---- 2. Claim discipline (4) ---------------------------------------------


def test_guide_three_guard_flags_const_false_disclaimer() -> None:
    text = GUIDE_PATH.read_text().lower()
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text
    assert "const false" in text or "`const false`" in text


def test_guide_no_production_ready_positive_claim() -> None:
    # Whitespace-flatten + drop Markdown emphasis/bullet chars so multi-line
    # blockquote prose like "no\n> production-ready" still registers the
    # "no production" negation cue.
    prose = re.sub(r"[\s>*]+", " ", _guide_prose().lower())
    for token in PROHIBITED_CLAIM_TOKENS:
        idx = 0
        while True:
            idx = prose.find(token, idx)
            if idx == -1:
                break
            # Include the token itself in the window so cues like
            # "no production" can match across the token boundary (e.g.
            # "no production-ready posture").
            window = prose[max(0, idx - 80) : idx + len(token) + 5]
            negated = any(
                cue in window
                for cue in (
                    "not a",
                    "not an",
                    "is not",
                    "no production",
                    "documentation only",
                )
            )
            assert negated, (
                f"deployment guide contains positive claim token {token!r}; "
                f"context: ...{prose[max(0, idx - 40) : idx + len(token) + 40]!r}"
            )
            idx += len(token)


def test_guide_references_operator_bound_final_supersession() -> None:
    """The disclaimer must point promotion authority at the final
    operator-bound supersession PR."""
    text = GUIDE_PATH.read_text().lower()
    assert "operator-bound supersession" in text
    assert "final" in text


def test_guide_does_not_flip_guard_flags_in_prose() -> None:
    prose = _guide_prose().lower()
    forbidden = (
        "support_widening = true",
        "support_widening: true",
        "production_platform_claim = true",
        "production_platform_claim: true",
        "live_adapter_execution = true",
        "live_adapter_execution: true",
    )
    for token in forbidden:
        assert token not in prose, f"deployment guide must not flip guard flag: {token!r}"


# ---- 3. Operator boundary + roadmap forward refs (3) ---------------------


def test_guide_lists_operator_owned_surfaces() -> None:
    text = GUIDE_PATH.read_text().lower()
    expected = (
        "authentication",
        "key management",
        "tls",
        "physical security",
        "bcp",
    )
    for surface in expected:
        assert surface in text, f"operator-owned surface missing from guide: {surface}"


def test_guide_links_v5_roadmap() -> None:
    text = GUIDE_PATH.read_text()
    assert "V5-FULL-PRODUCTION-PROMOTION-ROADMAP.md" in text
    assert ROADMAP_PATH.exists()


def test_guide_references_future_helm_chart_slice() -> None:
    text = GUIDE_PATH.read_text()
    assert "E-4-1" in text


# ---- 4. Governance ZERO TOUCH (1) ----------------------------------------


def test_plan_records_workflows_as_zero_touch_out_of_scope() -> None:
    text = PLAN_PATH.read_text()
    assert "**Out of scope (ZERO TOUCH):**" in text
    assert "- `.github/workflows/*`" in text
