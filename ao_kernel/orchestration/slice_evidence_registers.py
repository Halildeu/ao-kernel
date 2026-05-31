"""AO-MA-11F slice evidence registers: pure compiler for the per-slice evidence
artifacts (test report, AI suggestion register, update ledger, closeout) plus a
top-level SHA-bound, tamper-evident bundle manifest.

This is the AO-MA-11F-1 pure core. Like ``run_governor.decide`` and
``notifier.decide_notification`` it performs no I/O, no process spawning, no
network, no LLM, no GitHub read or write: it takes already-collected inputs
(per-suite test counts, objection records, update-ledger lines) and returns
schema-shaped dicts. The GitHub PR-review-thread harvest and the CI test
artifact read are a separate later slice (AO-MA-11F-2, side-effect).

Invariants (Codex CNS-20260531-002, thread 019e7fce, three review rounds):
  - canonical_bytes is the single pinned serialization (sort_keys, ensure_ascii
    False, compact separators, one trailing newline) so the sha256 is stable.
  - The closeout SHA-binds the three siblings; build_bundle_manifest then lists
    the four members (incl. the closeout) with their digests. The closeout does
    NOT reference the manifest (no circular hash). verify_* re-hash and re-check
    semantics (machine recompute, never self-attestation).
  - Fail-closed, recompute-not-trust:
      * test report all_passed is derived from totals (required tests present +
        zero failures/errors); a forged flag is rejected by _report_is_green.
      * closeout slice_passed=True requires the bound report green by its OWN
        totals AND the suggestion register closed (complete or no_objections
        with matching coverage) AND every sibling carrying the same slice_id.
      * a reject/partial objection requires a rationale; an accept requires an
        applied_ref or a no-op rationale.
      * an empty register is honest only with an EXPLICIT expected count of 0
        plus an explanatory harvest_mode (never an implicit "no records means no
        objections").
      * ledger seq is monotonic with one shared slice_id.
      * the bundle manifest's listed members must match the hashed set exactly
        in role, artifact_kind, schema_version, sha256 and line_count.
  - Secret-safe: every free-text field is machine-redacted (notifier-grade
    denylist) before it enters an artifact, and no_secret_payload is asserted
    only after the redaction verifies clean.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, cast

TEST_REPORT_KIND = "ao_ma_slice_test_report"
TEST_REPORT_VERSION = "ao-ma-slice-test-report.v1"
SUGGESTION_REGISTER_KIND = "ao_ma_ai_suggestion_register"
SUGGESTION_REGISTER_VERSION = "ao-ma-ai-suggestion-register.v1"
LEDGER_LINE_KIND = "ao_ma_slice_update_ledger_line"
LEDGER_LINE_VERSION = "ao-ma-slice-update-ledger-line.v1"
CLOSEOUT_KIND = "ao_ma_slice_closeout"
CLOSEOUT_VERSION = "ao-ma-slice-closeout.v1"
MANIFEST_KIND = "ao_ma_slice_evidence_bundle_manifest"
MANIFEST_VERSION = "ao-ma-slice-evidence-bundle-manifest.v1"

Disposition = Literal["accept", "reject", "partial"]
RegisterStatus = Literal["complete", "in_progress", "no_objections"]
ConsensusStatus = Literal["agreed", "not_agreed", "not_required"]
HarvestMode = Literal["provided", "gh_review_threads", "not_applicable"]

_PROVIDERS = frozenset({"anthropic", "openai", "minimax"})
_SOURCE_KINDS = frozenset({"codex_mcp", "claude_session", "mavis_session", "gh_review_thread"})
_EVENT_KINDS = frozenset(
    {"impl", "review_iteration", "fix", "doc_update", "schema_change", "test_change", "consensus", "closeout"}
)
_REDACTION_PLACEHOLDER = "[REDACTED]"

# Expected (artifact_kind, schema_version) per manifest member role.
_MANIFEST_MEMBER_SPEC: dict[str, tuple[str, str]] = {
    "test_report": (TEST_REPORT_KIND, TEST_REPORT_VERSION),
    "suggestion_register": (SUGGESTION_REGISTER_KIND, SUGGESTION_REGISTER_VERSION),
    "update_ledger": (LEDGER_LINE_KIND, LEDGER_LINE_VERSION),
    "closeout": (CLOSEOUT_KIND, CLOSEOUT_VERSION),
}

# Authority / guard pins shared by the artifacts this module emits.
_COMMON_PINS: dict[str, Any] = {
    "register_authority": "evidence_record_only",
    "github_write_authorized": False,
    "side_effect_authority": "none",
    "support_widening": False,
    "production_platform_claim": False,
    "live_adapter_execution": False,
    "secrets_recorded": False,
}

# Notifier-grade secret denylist (kept conceptually in sync with notifier.py).
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"gh[pos]_[A-Za-z0-9]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{12,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"https://hooks\.[A-Za-z0-9.-]+/\S+"),
    re.compile(r"https://discord(?:app)?\.com/api/webhooks/\S+"),
    re.compile(r"https://[A-Za-z0-9.-]*slack\.com/\S*"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)


class SliceEvidenceError(ValueError):
    """Raised on contract misuse of the compiler (bad inputs, broken invariants)."""


# ---------------------------------------------------------------------------
# Canonical serialization + hashing + redaction
# ---------------------------------------------------------------------------
def canonical_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return the single pinned canonical byte serialization of an artifact."""

    text = json.dumps(artifact, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def sha256_of(artifact: Mapping[str, Any]) -> str:
    """Return ``sha256:<64hex>`` of an artifact's canonical bytes."""

    return "sha256:" + hashlib.sha256(canonical_bytes(artifact)).hexdigest()


def _redact(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_REDACTION_PLACEHOLDER, out)
    return out


def _is_clean(text: str) -> bool:
    return not any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def _redacted_summary(text: str, *, max_len: int = 2000) -> str:
    """Redact + clamp a free-text field; fall back to a fixed safe string if the
    redacted form somehow still is not clean (so no secret can ride in)."""

    redacted = _redact(text).strip()[:max_len]
    if not redacted or not _is_clean(redacted):
        return "[redacted summary]"
    return redacted


def _digest_text(*parts: str) -> str:
    """sha256 over a canonical tuple of strings (stable objection identity)."""

    joined = "\x1f".join(parts)
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Test report
# ---------------------------------------------------------------------------
def build_test_report(
    *,
    slice_id: str,
    generated_at: str,
    suites: Sequence[Mapping[str, Any]],
    coverage_percent: float | None = None,
) -> dict[str, Any]:
    """Build a slice test report from per-suite counts.

    ``required_tests_present`` is true iff at least one non-skipped test ran;
    ``all_passed`` requires required_tests_present AND zero failures/errors (a
    slice with no executed required tests is NOT a pass)."""

    _require_nonempty_str("slice_id", slice_id)
    _require_nonempty_str("generated_at", generated_at)

    norm_suites: list[dict[str, Any]] = []
    total_tests = total_failed = total_errors = total_skipped = 0
    for suite in suites:
        name = suite.get("name")
        _require_nonempty_str("suite.name", name)
        tests = _require_nonneg_int("suite.tests", suite.get("tests"))
        failed = _require_nonneg_int("suite.failed", suite.get("failed", 0))
        errors = _require_nonneg_int("suite.errors", suite.get("errors", 0))
        skipped = _require_nonneg_int("suite.skipped", suite.get("skipped", 0))
        norm_suites.append(
            {
                "name": _redacted_summary(cast(str, name), max_len=200),
                "tests": tests,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
            }
        )
        total_tests += tests
        total_failed += failed
        total_errors += errors
        total_skipped += skipped

    total_passed = total_tests - total_failed - total_errors - total_skipped
    if total_passed < 0:
        raise SliceEvidenceError(f"test report totals inconsistent: tests={total_tests} < failed+errors+skipped")

    if coverage_percent is not None and not (0 <= coverage_percent <= 100):
        raise SliceEvidenceError("coverage_percent must be within [0, 100]")

    executed = total_tests - total_skipped
    required_tests_present = executed > 0

    return {
        "schema_version": TEST_REPORT_VERSION,
        "artifact_kind": TEST_REPORT_KIND,
        "slice_id": slice_id,
        "generated_at": generated_at,
        "required_tests_present": required_tests_present,
        "totals": {
            "tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "skipped": total_skipped,
        },
        "suites": norm_suites,
        "all_passed": required_tests_present and total_failed == 0 and total_errors == 0,
        "coverage_percent": coverage_percent,
        "ai_output_release_authority": False,
        **_COMMON_PINS,
    }


# ---------------------------------------------------------------------------
# Suggestion register
# ---------------------------------------------------------------------------
def build_suggestion_register(
    *,
    slice_id: str,
    generated_at: str,
    objections: Sequence[Mapping[str, Any]],
    harvest_mode: HarvestMode,
    expected_objections_count: int | None = None,
    register_status: RegisterStatus | None = None,
) -> dict[str, Any]:
    """Build the cross-AI suggestion register.

    - reject/partial requires a non-empty rationale; accept requires an
      applied_ref or a non-empty rationale (closing evidence).
    - free text is machine-redacted into ``summary_redacted``.
    - each objection gets a stable ``objection_digest`` over
      (provider, source_kind, source_id, iteration, raw_objection).
    - an EMPTY register requires an explicit ``expected_objections_count=0``
      (an implicit "no records means no objections" is rejected); coverage
      (actual == expected) is enforced for a complete register."""

    _require_nonempty_str("slice_id", slice_id)
    _require_nonempty_str("generated_at", generated_at)
    if harvest_mode not in ("provided", "gh_review_threads", "not_applicable"):
        raise SliceEvidenceError(f"harvest_mode invalid: {harvest_mode!r}")

    norm: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_digests: set[str] = set()
    for obj in objections:
        oid = obj.get("objection_id")
        _require_nonempty_str("objection.objection_id", oid)
        oid_s = cast(str, oid)
        if oid_s in seen_ids:
            raise SliceEvidenceError(f"duplicate objection_id {oid_s!r}")
        seen_ids.add(oid_s)

        provider = obj.get("provider")
        if provider not in _PROVIDERS:
            raise SliceEvidenceError(f"objection.provider must be one of {sorted(_PROVIDERS)}, got {provider!r}")
        source_kind = obj.get("source_kind")
        if source_kind not in _SOURCE_KINDS:
            raise SliceEvidenceError(f"objection.source_kind invalid: {source_kind!r}")
        source_id = obj.get("source_id")
        _require_nonempty_str("objection.source_id", source_id)
        iteration = obj.get("iteration")
        if not isinstance(iteration, int) or isinstance(iteration, bool) or iteration < 1:
            raise SliceEvidenceError("objection.iteration must be an integer >= 1")

        raw_objection = obj.get("objection") or obj.get("summary") or ""
        if not isinstance(raw_objection, str) or not raw_objection.strip():
            raise SliceEvidenceError(f"objection {oid_s!r} requires non-empty objection text")
        digest = _digest_text(
            cast(str, provider), cast(str, source_kind), cast(str, source_id), str(iteration), raw_objection
        )
        if digest in seen_digests:
            raise SliceEvidenceError(f"duplicate objection identity (digest) for {oid_s!r}")
        seen_digests.add(digest)

        disposition = obj.get("disposition")
        if disposition not in ("accept", "reject", "partial"):
            raise SliceEvidenceError(f"objection.disposition invalid: {disposition!r}")
        rationale = obj.get("rationale")
        rationale_ok = isinstance(rationale, str) and bool(rationale.strip())
        applied_ref = obj.get("applied_ref")
        applied_ok = applied_ref is not None
        if applied_ref is not None and not _is_short_sha(applied_ref):
            raise SliceEvidenceError("objection.applied_ref must be a 7-40 char lowercase hex or null")

        if disposition in ("reject", "partial") and not rationale_ok:
            raise SliceEvidenceError(f"objection {oid_s!r} disposition={disposition} requires a non-empty rationale")
        if disposition == "accept" and not applied_ok and not rationale_ok:
            raise SliceEvidenceError(
                f"objection {oid_s!r} disposition=accept requires an applied_ref or a no-op rationale"
            )

        norm.append(
            {
                "objection_id": oid_s,
                "provider": provider,
                "source_kind": source_kind,
                "source_id": source_id,
                "iteration": iteration,
                "objection_digest": digest,
                "summary_redacted": _redacted_summary(raw_objection),
                "disposition": disposition,
                "rationale": _redacted_summary(cast(str, rationale)) if rationale_ok else None,
                "applied_ref": applied_ref,
            }
        )

    # Empty register requires an explicit expected count of 0 (no implicit
    # "no records => no objections"). A non-empty register defaults expected to
    # the recorded count unless the caller pins a different one (coverage check).
    if not norm and expected_objections_count is None:
        raise SliceEvidenceError(
            "an empty suggestion register requires an explicit expected_objections_count=0 "
            "(implicit 'no records means no objections' is rejected)"
        )

    if expected_objections_count is None:
        expected = len(norm)
    else:
        expected = _require_nonneg_int("expected_objections_count", expected_objections_count)

    status: RegisterStatus
    if register_status is None:
        status = "no_objections" if not norm else "complete"
    else:
        status = register_status
    if status == "no_objections":
        if norm:
            raise SliceEvidenceError("register_status=no_objections but objections were provided")
        if expected != 0:
            raise SliceEvidenceError("register_status=no_objections requires expected_objections_count=0")
    if status == "complete":
        if not norm:
            raise SliceEvidenceError("register_status=complete requires at least one objection")
        if expected != len(norm):
            raise SliceEvidenceError(f"objection coverage mismatch: expected {expected}, recorded {len(norm)}")

    return {
        "schema_version": SUGGESTION_REGISTER_VERSION,
        "artifact_kind": SUGGESTION_REGISTER_KIND,
        "slice_id": slice_id,
        "generated_at": generated_at,
        "harvest_mode": harvest_mode,
        "register_status": status,
        "expected_objections_count": expected,
        "objections": norm,
        "ai_output_release_authority": False,
        "no_secret_payload": True,
        **_COMMON_PINS,
    }


# ---------------------------------------------------------------------------
# Update ledger
# ---------------------------------------------------------------------------
def build_update_ledger(*, slice_id: str, lines: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build the update ledger as a list of schema-valid lines (monotonic seq,
    single shared slice_id)."""

    _require_nonempty_str("slice_id", slice_id)
    out: list[dict[str, Any]] = []
    prev_seq = -1
    for line in lines:
        seq = line.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
            raise SliceEvidenceError("ledger line seq must be an integer >= 0")
        if seq < prev_seq:
            raise SliceEvidenceError(f"ledger seq not monotonic: {seq} < previous {prev_seq}")
        prev_seq = seq
        ts = line.get("ts")
        _require_nonempty_str("ledger.ts", ts)
        event_kind = line.get("event_kind")
        if event_kind not in _EVENT_KINDS:
            raise SliceEvidenceError(f"ledger.event_kind invalid: {event_kind!r}")
        summary = line.get("summary")
        _require_nonempty_str("ledger.summary", summary)
        ref_sha = line.get("ref_sha")
        if ref_sha is not None and not _is_short_sha(ref_sha):
            raise SliceEvidenceError("ledger.ref_sha must be a 7-40 char lowercase hex or null")
        out.append(
            {
                "schema_version": LEDGER_LINE_VERSION,
                "artifact_kind": LEDGER_LINE_KIND,
                "slice_id": slice_id,
                "seq": seq,
                "ts": ts,
                "event_kind": event_kind,
                "summary": _redacted_summary(cast(str, summary)),
                "ref_sha": ref_sha,
                "register_authority": "evidence_record_only",
                "github_write_authorized": False,
                "side_effect_authority": "none",
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
                "secrets_recorded": False,
            }
        )
    return out


def ledger_to_jsonl(lines: Sequence[Mapping[str, Any]]) -> str:
    """Render ledger lines as canonical JSONL text (one object per line)."""

    return "".join(canonical_bytes(line).decode("utf-8") for line in lines)


def _ledger_hash(lines: Sequence[Mapping[str, Any]]) -> str:
    return "sha256:" + hashlib.sha256(ledger_to_jsonl(lines).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Semantic recompute helpers (truth derived from the artifacts, not flags)
# ---------------------------------------------------------------------------
def _report_is_green(test_report: Mapping[str, Any]) -> bool:
    """Recompute green-ness from the report's OWN totals (never trust the
    all_passed flag): required tests present AND zero failures AND zero errors,
    AND the all_passed flag must agree with that recompute."""

    totals = test_report.get("totals")
    if not isinstance(totals, Mapping):
        return False
    failed = totals.get("failed")
    errors = totals.get("errors")
    if not isinstance(failed, int) or isinstance(failed, bool):
        return False
    if not isinstance(errors, int) or isinstance(errors, bool):
        return False
    required_present = test_report.get("required_tests_present") is True
    recomputed_green = required_present and failed == 0 and errors == 0
    if test_report.get("all_passed") is not recomputed_green:
        return False
    return bool(recomputed_green)


def _register_is_closed(suggestion_register: Mapping[str, Any]) -> bool:
    """Recompute whether the suggestion register is closed for a passing slice:
    status complete (with matching coverage) or no_objections (empty, expected
    0). An in_progress register cannot back slice_passed=True."""

    status = suggestion_register.get("register_status")
    objections = suggestion_register.get("objections")
    expected = suggestion_register.get("expected_objections_count")
    if not isinstance(objections, list):
        return False
    if status == "no_objections":
        return len(objections) == 0 and expected == 0
    if status == "complete":
        return len(objections) >= 1 and expected == len(objections)
    return False


def _siblings_share_slice_id(
    slice_id: str,
    test_report: Mapping[str, Any],
    suggestion_register: Mapping[str, Any],
    update_ledger: Sequence[Mapping[str, Any]],
) -> bool:
    """Every bound artifact (and every ledger line) must carry the closeout's
    slice_id, so the bundle is a single-slice chain."""

    if test_report.get("slice_id") != slice_id:
        return False
    if suggestion_register.get("slice_id") != slice_id:
        return False
    return all(line.get("slice_id") == slice_id for line in update_ledger)


# ---------------------------------------------------------------------------
# Closeout (SHA-binds the three siblings)
# ---------------------------------------------------------------------------
def build_closeout(
    *,
    slice_id: str,
    generated_at: str,
    test_report: Mapping[str, Any],
    suggestion_register: Mapping[str, Any],
    update_ledger: Sequence[Mapping[str, Any]],
    consensus_status: ConsensusStatus,
    slice_passed: bool,
) -> dict[str, Any]:
    """Build a closeout that SHA-binds the three siblings.

    Fail-closed for ``slice_passed=True`` (Codex CNS-20260531-002): the bound
    test report must be green by its own totals, the suggestion register must be
    closed (complete with coverage or no_objections), and every sibling must
    carry this closeout's slice_id."""

    _require_nonempty_str("slice_id", slice_id)
    _require_nonempty_str("generated_at", generated_at)
    if consensus_status not in ("agreed", "not_agreed", "not_required"):
        raise SliceEvidenceError(f"consensus_status invalid: {consensus_status!r}")

    if not _siblings_share_slice_id(slice_id, test_report, suggestion_register, update_ledger):
        raise SliceEvidenceError("bound artifacts must all carry the closeout's slice_id")

    if slice_passed:
        if not _report_is_green(test_report):
            raise SliceEvidenceError("slice_passed=True but the bound test report is not green by its own totals")
        if not _register_is_closed(suggestion_register):
            raise SliceEvidenceError(
                "slice_passed=True but the suggestion register is not closed "
                "(needs status complete with matching coverage, or no_objections)"
            )

    return {
        "schema_version": CLOSEOUT_VERSION,
        "artifact_kind": CLOSEOUT_KIND,
        "slice_id": slice_id,
        "generated_at": generated_at,
        "slice_passed": slice_passed,
        "bound_artifacts": {
            "test_report": {
                "artifact_kind": test_report.get("artifact_kind", TEST_REPORT_KIND),
                "schema_version": test_report.get("schema_version", TEST_REPORT_VERSION),
                "sha256": sha256_of(test_report),
                "line_count": None,
            },
            "suggestion_register": {
                "artifact_kind": suggestion_register.get("artifact_kind", SUGGESTION_REGISTER_KIND),
                "schema_version": suggestion_register.get("schema_version", SUGGESTION_REGISTER_VERSION),
                "sha256": sha256_of(suggestion_register),
                "line_count": None,
            },
            "update_ledger": {
                "artifact_kind": LEDGER_LINE_KIND,
                "schema_version": LEDGER_LINE_VERSION,
                "sha256": _ledger_hash(update_ledger),
                "line_count": len(update_ledger),
            },
        },
        "consensus_status": consensus_status,
        "ai_output_release_authority": False,
        "release_authority": "ao-release-gate+github-ruleset",
        **_COMMON_PINS,
    }


def verify_closeout_binding(
    closeout: Mapping[str, Any],
    *,
    test_report: Mapping[str, Any],
    suggestion_register: Mapping[str, Any],
    update_ledger: Sequence[Mapping[str, Any]],
) -> bool:
    """Re-hash AND re-check the semantics of the supplied siblings against the
    closeout (machine recompute, not self-attestation)."""

    bound = closeout.get("bound_artifacts", {})
    try:
        if bound["test_report"]["sha256"] != sha256_of(test_report):
            return False
        if bound["suggestion_register"]["sha256"] != sha256_of(suggestion_register):
            return False
        if bound["update_ledger"]["sha256"] != _ledger_hash(update_ledger):
            return False
        if bound["update_ledger"].get("line_count") != len(update_ledger):
            return False
    except (KeyError, TypeError):
        return False

    slice_id = closeout.get("slice_id")
    if not isinstance(slice_id, str) or not slice_id:
        return False
    if not _siblings_share_slice_id(slice_id, test_report, suggestion_register, update_ledger):
        return False

    if closeout.get("slice_passed") is True:
        if not _report_is_green(test_report):
            return False
        if not _register_is_closed(suggestion_register):
            return False
    return True


# ---------------------------------------------------------------------------
# Bundle manifest (lists the four members; references the closeout, not vice versa)
# ---------------------------------------------------------------------------
def build_bundle_manifest(
    *,
    slice_id: str,
    generated_at: str,
    test_report: Mapping[str, Any],
    suggestion_register: Mapping[str, Any],
    update_ledger: Sequence[Mapping[str, Any]],
    closeout: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the top-level bundle manifest listing exactly the four members with
    their digests. The listed set equals the hashed set by construction."""

    _require_nonempty_str("slice_id", slice_id)
    _require_nonempty_str("generated_at", generated_at)
    members = [
        {
            "member_role": "test_report",
            "artifact_kind": TEST_REPORT_KIND,
            "schema_version": TEST_REPORT_VERSION,
            "sha256": sha256_of(test_report),
            "line_count": None,
        },
        {
            "member_role": "suggestion_register",
            "artifact_kind": SUGGESTION_REGISTER_KIND,
            "schema_version": SUGGESTION_REGISTER_VERSION,
            "sha256": sha256_of(suggestion_register),
            "line_count": None,
        },
        {
            "member_role": "update_ledger",
            "artifact_kind": LEDGER_LINE_KIND,
            "schema_version": LEDGER_LINE_VERSION,
            "sha256": _ledger_hash(update_ledger),
            "line_count": len(update_ledger),
        },
        {
            "member_role": "closeout",
            "artifact_kind": CLOSEOUT_KIND,
            "schema_version": CLOSEOUT_VERSION,
            "sha256": sha256_of(closeout),
            "line_count": None,
        },
    ]
    return {
        "schema_version": MANIFEST_VERSION,
        "artifact_kind": MANIFEST_KIND,
        "slice_id": slice_id,
        "generated_at": generated_at,
        "members": members,
        "ai_output_release_authority": False,
        **_COMMON_PINS,
    }


def verify_bundle_manifest(
    manifest: Mapping[str, Any],
    *,
    test_report: Mapping[str, Any],
    suggestion_register: Mapping[str, Any],
    update_ledger: Sequence[Mapping[str, Any]],
    closeout: Mapping[str, Any],
) -> bool:
    """Re-hash all four members and confirm the manifest lists them exactly:
    role, artifact_kind, schema_version, sha256 and line_count must all match
    the recomputed values (no missing/extra/duplicate/wrong-kind/mismatch)."""

    expected: dict[str, dict[str, Any]] = {
        "test_report": {
            "artifact_kind": TEST_REPORT_KIND,
            "schema_version": TEST_REPORT_VERSION,
            "sha256": sha256_of(test_report),
            "line_count": None,
        },
        "suggestion_register": {
            "artifact_kind": SUGGESTION_REGISTER_KIND,
            "schema_version": SUGGESTION_REGISTER_VERSION,
            "sha256": sha256_of(suggestion_register),
            "line_count": None,
        },
        "update_ledger": {
            "artifact_kind": LEDGER_LINE_KIND,
            "schema_version": LEDGER_LINE_VERSION,
            "sha256": _ledger_hash(update_ledger),
            "line_count": len(update_ledger),
        },
        "closeout": {
            "artifact_kind": CLOSEOUT_KIND,
            "schema_version": CLOSEOUT_VERSION,
            "sha256": sha256_of(closeout),
            "line_count": None,
        },
    }
    members = manifest.get("members")
    if not isinstance(members, list) or len(members) != 4:
        return False
    seen_roles: set[str] = set()
    for member in members:
        if not isinstance(member, Mapping):
            return False
        role = member.get("member_role")
        if role not in expected or role in seen_roles:
            return False
        seen_roles.add(cast(str, role))
        spec = expected[cast(str, role)]
        if member.get("artifact_kind") != spec["artifact_kind"]:
            return False
        if member.get("schema_version") != spec["schema_version"]:
            return False
        if member.get("sha256") != spec["sha256"]:
            return False
        if member.get("line_count") != spec["line_count"]:
            return False
    return seen_roles == set(expected)


# ---------------------------------------------------------------------------
# Small validators (kept tiny + pure)
# ---------------------------------------------------------------------------
def _require_nonempty_str(field: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SliceEvidenceError(f"{field} must be a non-empty string")


def _require_nonneg_int(field: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SliceEvidenceError(f"{field} must be an integer >= 0")
    return value


def _is_short_sha(value: object) -> bool:
    if not isinstance(value, str) or not (7 <= len(value) <= 40):
        return False
    return all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class SliceEvidenceBundle:
    """Convenience container holding all five artifacts for one slice."""

    test_report: dict[str, Any]
    suggestion_register: dict[str, Any]
    update_ledger: list[dict[str, Any]]
    closeout: dict[str, Any]
    manifest: dict[str, Any]
