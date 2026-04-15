"""Tests for ``ao_kernel.workflow.primitives``.

Covers token minting (secrets.token_urlsafe), dataclass construction,
resume idempotency (same payload/decision → same object), and
mismatch rejection.
"""

from __future__ import annotations

import pytest

from ao_kernel.workflow import (
    Approval,
    InterruptRequest,
    WorkflowTokenInvalidError,
    create_approval,
    create_interrupt,
    mint_approval_token,
    mint_interrupt_token,
    resume_approval,
    resume_interrupt,
)


class TestTokenMint:
    def test_interrupt_token_length_at_least_48(self) -> None:
        t = mint_interrupt_token()
        # secrets.token_urlsafe(48) → ~64 base64url chars; allow some
        # tolerance but enforce a strong minimum.
        assert len(t) >= 48

    def test_approval_token_length_at_least_48(self) -> None:
        assert len(mint_approval_token()) >= 48

    def test_interrupt_tokens_unique(self) -> None:
        tokens = {mint_interrupt_token() for _ in range(500)}
        assert len(tokens) == 500

    def test_approval_tokens_unique(self) -> None:
        tokens = {mint_approval_token() for _ in range(500)}
        assert len(tokens) == 500

    def test_interrupt_and_approval_distinct_functions(self) -> None:
        """Distinct names even with identical impl — keeps audit domains separate."""
        assert mint_interrupt_token.__name__ == "mint_interrupt_token"
        assert mint_approval_token.__name__ == "mint_approval_token"


class TestCreateInterrupt:
    def test_fresh_interrupt_has_fields_populated(self) -> None:
        ir = create_interrupt(adapter_id="codex-stub", question_payload={"q": "ok?"})
        assert isinstance(ir, InterruptRequest)
        assert ir.adapter_id == "codex-stub"
        assert ir.question_payload == {"q": "ok?"}
        assert ir.interrupt_id
        assert ir.interrupt_token
        assert ir.emitted_at
        assert ir.resumed_at is None
        assert ir.response_payload is None


class TestResumeInterrupt:
    def test_happy_resume_sets_payload(self) -> None:
        ir = create_interrupt("codex-stub", {"q": "continue?"})
        ir2 = resume_interrupt(
            ir,
            token=ir.interrupt_token,
            response_payload={"a": "yes"},
        )
        assert ir2.resumed_at is not None
        assert ir2.response_payload == {"a": "yes"}

    def test_idempotent_resume_same_payload(self) -> None:
        """Re-submitting the same payload returns the same resumed record."""
        ir0 = create_interrupt("codex-stub", {"q": "x"})
        ir1 = resume_interrupt(ir0, token=ir0.interrupt_token, response_payload={"a": "y"})
        ir2 = resume_interrupt(ir1, token=ir0.interrupt_token, response_payload={"a": "y"})
        assert ir2 is ir1  # idempotent — same object returned

    def test_idempotent_resume_differently_ordered_payload(self) -> None:
        """Canonicalized hash means dict key order doesn't matter."""
        ir0 = create_interrupt("codex-stub", {"q": "x"})
        ir1 = resume_interrupt(
            ir0,
            token=ir0.interrupt_token,
            response_payload={"a": 1, "b": 2},
        )
        ir2 = resume_interrupt(
            ir1,
            token=ir0.interrupt_token,
            response_payload={"b": 2, "a": 1},
        )
        assert ir2 is ir1

    def test_resume_with_different_payload_raises(self) -> None:
        ir0 = create_interrupt("codex-stub", {"q": "x"})
        ir1 = resume_interrupt(ir0, token=ir0.interrupt_token, response_payload={"a": 1})
        with pytest.raises(WorkflowTokenInvalidError) as ei:
            resume_interrupt(
                ir1,
                token=ir0.interrupt_token,
                response_payload={"a": 2},
            )
        assert ei.value.reason == "resumed_with_different_payload"
        assert ei.value.token_kind == "interrupt"

    def test_resume_with_wrong_token_raises(self) -> None:
        ir = create_interrupt("codex-stub", {"q": "x"})
        with pytest.raises(WorkflowTokenInvalidError) as ei:
            resume_interrupt(
                ir,
                token="wrong-token",
                response_payload={"a": 1},
            )
        assert ei.value.reason == "token_mismatch"
        assert ei.value.token_kind == "interrupt"


class TestCreateApproval:
    def test_fresh_approval_fields(self) -> None:
        ap = create_approval(gate="pre_apply", actor="halildeu")
        assert isinstance(ap, Approval)
        assert ap.gate == "pre_apply"
        assert ap.actor == "halildeu"
        assert ap.decision is None
        assert ap.responded_at is None
        assert ap.payload == {}
        assert ap.approval_id
        assert ap.approval_token

    def test_unknown_gate_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown approval gate"):
            create_approval(gate="not_a_gate", actor="x")


class TestResumeApproval:
    def test_happy_resume_granted(self) -> None:
        ap = create_approval(gate="pre_apply", actor="h")
        ap2 = resume_approval(ap, token=ap.approval_token, decision="granted")
        assert ap2.decision == "granted"
        assert ap2.responded_at is not None

    def test_idempotent_resume_same_decision(self) -> None:
        ap = create_approval(gate="pre_apply", actor="h")
        ap1 = resume_approval(ap, token=ap.approval_token, decision="granted")
        ap2 = resume_approval(ap1, token=ap.approval_token, decision="granted")
        assert ap2 is ap1

    def test_resume_with_different_decision_raises(self) -> None:
        ap = create_approval(gate="pre_apply", actor="h")
        ap1 = resume_approval(ap, token=ap.approval_token, decision="granted")
        with pytest.raises(WorkflowTokenInvalidError) as ei:
            resume_approval(ap1, token=ap.approval_token, decision="denied")
        assert ei.value.reason == "resumed_with_different_payload"
        assert ei.value.token_kind == "approval"

    def test_resume_with_wrong_token_raises(self) -> None:
        ap = create_approval(gate="pre_apply", actor="h")
        with pytest.raises(WorkflowTokenInvalidError) as ei:
            resume_approval(ap, token="wrong", decision="granted")
        assert ei.value.reason == "token_mismatch"
        assert ei.value.token_kind == "approval"

    def test_unknown_decision_raises(self) -> None:
        ap = create_approval(gate="pre_apply", actor="h")
        with pytest.raises(ValueError, match="approval decision"):
            resume_approval(ap, token=ap.approval_token, decision="maybe")  # type: ignore[arg-type]
