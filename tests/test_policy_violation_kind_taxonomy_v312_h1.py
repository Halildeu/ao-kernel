"""v3.12 H1 — ``PolicyViolation.kind`` closed-taxonomy pin.

Pre-H1 the taxonomy declared ``env_unknown`` + ``env_missing_required``
but no ``policy_enforcer`` path actually emitted them — ``build_sandbox``
silently filters unknown env keys rather than raising a violation.
Shipping dead taxonomy entries muddles the operator signal when they
write ``rollout.promote_to_block_on`` lists. H1 prunes the two dead
kinds from the Literal, updates the docstring, and removes references
from the bundled policy `_mode_note` + `docs/WORKTREE-PROFILE.md` +
`docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md`.

Future runtime PR may reintroduce emitters for env allowlist violations;
if that happens, the kinds get re-added in a dedicated PR.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args, get_type_hints

from ao_kernel.executor.errors import PolicyViolation


# Authoritative list — matches the updated Literal on PolicyViolation.kind.
# The runtime emit paths in `ao_kernel/executor/policy_enforcer.py` only
# construct PolicyViolation with these values (grep PolicyViolation(kind=
# inside that file to confirm).
EXPECTED_KINDS = frozenset(
    {
        "command_not_allowlisted",
        "command_path_outside_policy",
        "cwd_escape",
        "secret_exposure_denied",
        "secret_missing",
        "http_header_exposure_unauthorized",
    }
)


def _resolved_kind_literal_args() -> frozenset[str]:
    """Resolve the Literal args off ``PolicyViolation.kind`` through
    ``get_type_hints`` so ``from __future__ import annotations`` does
    not turn the annotation into an unresolvable string."""
    hints = get_type_hints(PolicyViolation)
    return frozenset(get_args(hints["kind"]))


class TestPolicyViolationKindTaxonomy:
    def test_literal_matches_expected_kinds(self) -> None:
        literal_args = _resolved_kind_literal_args()
        assert literal_args == EXPECTED_KINDS, (
            f"PolicyViolation.kind taxonomy drift; expected {sorted(EXPECTED_KINDS)}, got {sorted(literal_args)}"
        )

    def test_dead_kinds_removed(self) -> None:
        # Regression anchor: env_unknown + env_missing_required were
        # declared pre-H1 but never emitted. They must stay OUT.
        literal_args = _resolved_kind_literal_args()
        assert "env_unknown" not in literal_args
        assert "env_missing_required" not in literal_args


class TestBundledPolicyModeNoteTaxonomyReference:
    def test_mode_note_lists_only_live_kinds(self) -> None:
        # The bundled `_mode_note` inside policy_worktree_profile.v1.json
        # enumerates the closed taxonomy for operators. After H1 the
        # dead kinds are removed from that enumeration.
        bundled = Path("ao_kernel/defaults/policies/policy_worktree_profile.v1.json").read_text(encoding="utf-8")
        policy = json.loads(bundled)
        note = policy["rollout"]["_mode_note"]
        assert "env_unknown" not in note
        assert "env_missing_required" not in note
        # Live kinds still referenced.
        for live in (
            "command_not_allowlisted",
            "cwd_escape",
            "secret_exposure_denied",
            "secret_missing",
            "http_header_exposure_unauthorized",
        ):
            assert live in note, f"_mode_note should still reference {live}"

    def test_promote_to_block_on_has_no_dead_kinds(self) -> None:
        # Regression: P2 iter-2 already dropped env_unknown from the
        # bundled default. This pin stays green so a future edit can't
        # sneak it back in.
        bundled = Path("ao_kernel/defaults/policies/policy_worktree_profile.v1.json").read_text(encoding="utf-8")
        policy = json.loads(bundled)
        promote = set(policy["rollout"].get("promote_to_block_on", []))
        assert "env_unknown" not in promote
        assert "env_missing_required" not in promote


class TestDocTaxonomyAlignment:
    def test_worktree_profile_doc_has_no_dead_kinds(self) -> None:
        text = Path("docs/WORKTREE-PROFILE.md").read_text(encoding="utf-8")
        assert "env_unknown" not in text
        assert "env_missing_required" not in text

    def test_real_adapter_runbook_has_no_dead_kinds(self) -> None:
        text = Path("docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md").read_text(encoding="utf-8")
        assert "env_unknown" not in text
        assert "env_missing_required" not in text
