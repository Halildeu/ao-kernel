"""AO-MA-3 risk classifier.

Pure-Python deterministic path → risk class heuristic for the orchestrator.
Codex iter-1 absorb (thread 019e6645): the high-risk pattern list intentionally
covers governance, release-gate, live-adapter, GPP, schema, secret-wiring, and
GPP test surfaces so the orchestrator never silently scopes a high-impact
change as ``low``.

Risk classes (from ``ao-ma-task-graph.v1`` schema enum):

- ``low`` — purely additive change in test/docs/example/non-release paths
- ``normal`` — runtime code under ``ao_kernel/`` outside high-risk surfaces
- ``high`` — single high-risk surface touched
- ``critical`` — multiple distinct high-risk surfaces touched
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

RiskClass = Literal["low", "normal", "high", "critical"]


_HIGH_RISK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        # GitHub governance surface
        r"^\.github/.*$",
        r"^CODEOWNERS$",
        r"^AGENTS\.md$",
        r"^CLAUDE\.md$",
        # Program SSOT
        r"^\.claude/plans/GPP-.*$",
        r"^\.claude/plans/AO-GATE.*$",
        r"^\.claude/plans/.*STATUS.*\.md$",
        r"^\.claude/plans/gpp_status\.v1\.json$",
        # Release authority code
        r"^ao_kernel/ao_release_gate.*\.py$",
        r"^ao_kernel/live_adapter_gate.*\.py$",
        r"^scripts/ao_release_gate.*\.py$",
        r"^scripts/local_gpp_gate.*\.py$",
        r"^scripts/live_adapter_gate.*\.py$",
        # Policy / gate / AO-MA schema surface
        r"^ao_kernel/defaults/policies/.*$",
        r"^ao_kernel/defaults/schemas/.*gate.*\.json$",
        r"^ao_kernel/defaults/schemas/ao-ma-.*\.schema\.v1\.json$",
        # Deploy / secret wiring
        r"^deploy/.*$",
        # GPP / gate test surface
        r"^tests/test_.*gate.*\.py$",
        r"^tests/test_gpp_.*\.py$",
        r"^tests/test_ao_ma.*\.py$",
        r"^tests/test_orchestration_.*\.py$",
    )
)


@dataclass(frozen=True)
class RiskClassifier:
    """Heuristic path → risk class classifier."""

    @staticmethod
    def is_high_risk_path(path: str) -> bool:
        """Return True if ``path`` matches any high-risk pattern."""

        return any(p.match(path) for p in _HIGH_RISK_PATTERNS)

    @classmethod
    def classify(cls, paths: list[str]) -> RiskClass:
        """Classify a path list into a single risk class.

        - empty / falsy → ``low`` (no scope declared)
        - all paths low-risk → ``low`` for test/docs/examples surfaces;
          otherwise ``normal``
        - one high-risk surface touched → ``high``
        - two or more distinct high-risk surface "families" → ``critical``

        Families are coarse buckets (governance vs release-gate vs schema vs
        deploy vs tests) so a PR that edits both `.github/workflows/test.yml`
        and `ao_kernel/ao_release_gate.py` becomes ``critical``.
        """

        if not paths:
            return "low"
        high_paths = [p for p in paths if cls.is_high_risk_path(p)]
        if not high_paths:
            if all(_is_pure_test_or_docs(p) for p in paths):
                return "low"
            return "normal"
        families = {_high_risk_family(p) for p in high_paths}
        if len(families) >= 2:
            return "critical"
        return "high"


def _is_pure_test_or_docs(path: str) -> bool:
    """Return True for low-impact test/doc/example paths."""

    if path.startswith("tests/") and not path.startswith("tests/test_"):
        return True
    if path.startswith("tests/test_"):
        # Test files NOT touching gate/gpp/ao_ma/orchestration surfaces
        # already match the test high-risk pattern above; reaching here
        # means the path is genuinely low-impact test scaffolding.
        return True
    if path.startswith("docs/") or path.startswith("examples/"):
        return True
    if path.endswith(".md") and not path.startswith(".claude/"):
        return True
    return False


def _high_risk_family(path: str) -> str:
    """Return a coarse "family" label for a high-risk path.

    Used by ``classify`` to decide ``high`` vs ``critical`` (multi-family).
    """

    if path.startswith(".github/"):
        return "github"
    if path in ("CODEOWNERS", "AGENTS.md", "CLAUDE.md"):
        return "governance"
    if path.startswith(".claude/plans/"):
        return "program-ssot"
    if "release_gate" in path or "local_gpp_gate" in path:
        return "release-gate"
    if "live_adapter_gate" in path:
        return "live-adapter"
    if path.startswith("ao_kernel/defaults/policies/"):
        return "policies"
    if path.startswith("ao_kernel/defaults/schemas/"):
        return "schemas"
    if path.startswith("deploy/"):
        return "deploy"
    if path.startswith("tests/"):
        return "tests-gate"
    return "other"
