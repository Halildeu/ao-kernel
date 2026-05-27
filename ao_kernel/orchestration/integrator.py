"""AO-MA-5 integrator policy (v1).

Consumes an AO-MA-3 manifest + AO-MA-4 runner_report + per-worker
``worker_result.v1`` (AO-MA-4.5 producer) + optional
``review_verdict.v1`` (AO-MA-6) + optional ``verification_report.v1``
(AO-MA-7), and emits an ``integration_report.v1`` with per-worker
accept/reject/not_integratable decisions, a CF3 conflict report, and
an operator-runnable assembly_plan in argv form.

**HARD RULE pin (Codex iter-2/3/4 absorbed):**

- **No agent execution, no LLM call** — Integrator is pure deterministic policy
- **No GitHub write** — no ``git push``, no ``gh pr create``, no ``gh api``
- **No local merge / branch create / worktree mutation** —
  ``assembly_plan`` items are operator-runnable data, never executed by integrator
- **No `subprocess` import** in this module — static-test enforced
- ``release_authority`` schema const ``"ao-release-gate+github-ruleset"``
  pins that Integrator is NOT release authority

**Accept gate (Crit-D + Crit-E):**

A worker is `accept`ed iff ALL hold:
1. worker_result.v1.json present + Draft202012Validator passes
2. worker_result.guard_flags all literal False
3. worker_result.no_secret_attestation.secrets_recorded is False
4. worker_result.actual_changed_files ⊆ worker_result.declared_write_set (subset)
5. review_verdict.v1 present + verdict == "AGREE"
6. verification_report.v1 present + verification_passed predicate True
7. no actual_changed_files overlap with another accept candidate (CF3 escalate)

If any of (5) or (6) is MISSING (not present on disk), the worker is
``not_integratable`` (Codex iter-1 Crit-E: pending evidence ≠ reject).

If (5) is REVISE/BLOCK or (6) fails the predicate, the worker is
``reject``ed with the corresponding reason_code.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.orchestration.integration_report_writer import (
    IntegrationReportWriter,
    IntegrationReportWriterError,
)

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"

_TASK_GRAPH_SCHEMA_NAME = "ao-ma-task-graph.schema.v1.json"
_ASSIGNMENT_SCHEMA_NAME = "ao-ma-agent-assignment.schema.v1.json"
_RUNNER_REPORT_SCHEMA_NAME = "ao-ma-runner-report.schema.v1.json"
_WORKER_RESULT_SCHEMA_NAME = "ao-ma-worker-result.schema.v1.json"
_REVIEW_VERDICT_SCHEMA_NAME = "ao-ma-review-verdict.schema.v1.json"
_VERIFICATION_REPORT_SCHEMA_NAME = "ao-ma-verification-report.schema.v1.json"

_TASK_GRAPH_ID_PATTERN = re.compile(r"^ao-ma-[0-9]{8}-[a-z0-9]{7}$")
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARTIFACT_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.v1\.json$")
_EXPECTED_MANIFEST_SCHEMA_VERSION = "ao-ma-orchestration-manifest.v1"

ReasonCode = Literal[
    "accepted_full_evidence",
    "missing_worker_result",
    "missing_review_verdict",
    "missing_verification_report",
    "review_revise",
    "review_block",
    "verification_failed",
    "actual_write_set_overlap",
    "guard_flag_violation",
    "schema_invalid",
]

Decision = Literal["accept", "reject", "not_integratable"]


class IntegratorError(RuntimeError):
    """Raised for true I/O / schema-load failures (NOT for normal policy outcomes)."""


@dataclass
class IntegrationDecision:
    """Codex iter-2 absorb: API/CLI split — decision object, not exceptions for policy outcomes.

    ``Integrator.integrate(...)`` returns this dataclass. CLI handler
    maps it to exit code per the §5 exit semantics matrix in
    ``.claude/plans/AO-MA-5-INTEGRATOR-POLICY.md``.
    """

    overall_status: Literal["all_accepted", "partial", "all_blocked"]
    report: dict[str, Any]
    assembly_plan: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    has_conflicts: bool = False
    has_rejections: bool = False
    has_pending: bool = False


def _load_schema(name: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegratorError(f"failed to load bundled schema {name!r}: {exc}") from exc


def _validate_schema(payload: dict[str, Any], schema_name: str, source: Path) -> None:
    schema = _load_schema(schema_name)
    try:
        Draft202012Validator(schema).validate(payload)
    except ValidationError as exc:
        raise IntegratorError(
            f"{source.name} failed schema {schema_name!r}: {exc.message} (at {list(exc.absolute_path)})"
        ) from exc


def _validate_manifest_envelope(manifest: dict[str, Any], source: Path) -> None:
    """Mirror AO-MA-4 manifest envelope check (Codex iter-4/5 absorbed there)."""

    if not isinstance(manifest, dict):
        raise IntegratorError(f"{source.name} manifest must be a JSON object")
    schema_version = manifest.get("schema_version")
    if schema_version != _EXPECTED_MANIFEST_SCHEMA_VERSION:
        raise IntegratorError(
            f"{source.name} schema_version mismatch: expected "
            f"{_EXPECTED_MANIFEST_SCHEMA_VERSION!r}, got {schema_version!r}"
        )
    task_graph_id = manifest.get("task_graph_id")
    if not isinstance(task_graph_id, str) or not _TASK_GRAPH_ID_PATTERN.match(task_graph_id):
        raise IntegratorError(f"{source.name} task_graph_id {task_graph_id!r} does not match AO-MA-2 pattern")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise IntegratorError(f"{source.name} artifacts must be a non-empty array")
    seen: set[str] = set()
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, dict):
            raise IntegratorError(f"{source.name} artifacts[{index}] must be a JSON object")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise IntegratorError(f"{source.name} artifacts[{index}].path must be a non-empty string")
        if path.startswith("/") or ".." in Path(path).parts or "\\" in path:
            raise IntegratorError(
                f"{source.name} artifacts[{index}].path {path!r} contains traversal/absolute components"
            )
        if not _ARTIFACT_PATH_PATTERN.match(path):
            raise IntegratorError(
                f"{source.name} artifacts[{index}].path {path!r} does not match AO-MA artifact suffix '*.v1.json'"
            )
        if path in seen:
            raise IntegratorError(f"{source.name} duplicate artifact path: {path!r}")
        seen.add(path)
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not _SHA256_PATTERN.match(sha):
            raise IntegratorError(f"{source.name} artifacts[{index}].sha256 {sha!r} must match 'sha256:[0-9a-f]{{64}}'")
        size_bytes = entry.get("size_bytes")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise IntegratorError(
                f"{source.name} artifacts[{index}].size_bytes {size_bytes!r} must be a positive integer"
            )
    guard_flags = manifest.get("guard_flags")
    if not isinstance(guard_flags, dict):
        raise IntegratorError(f"{source.name} guard_flags must be an object")
    for required in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        if guard_flags.get(required) is not False:
            raise IntegratorError(
                f"{source.name} guard_flags.{required} must be the literal boolean False; AO-MA no-widening contract"
            )


def sha256_of(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relativize(path_str: str | None, base_dir: Path) -> str | None:
    """Convert an absolute filesystem path to base_dir-relative for the
    integration_report.v1 schema (path $def rejects absolute paths).

    Codex iter-5 HIGH-2 absorb: paths OUTSIDE ``base_dir`` are NOT
    silently basenamed (audit trail leak: ``/tmp/a/worker_result.v1.json``
    and ``/other/b/worker_result.v1.json`` would both become
    ``worker_result.v1.json``). Fail-closed via ``IntegratorError`` —
    the integrator does not invent provenance.

    Preserves None (worker_result_ref null sentinel).
    """

    if path_str is None:
        return None
    p = Path(path_str)
    if not p.is_absolute():
        return str(p)
    try:
        return str(p.resolve().relative_to(base_dir.resolve()))
    except ValueError as exc:
        raise IntegratorError(
            f"evidence path {p!s} is outside base_dir {base_dir!s}; "
            f"refusing to bare-name it (audit provenance lost). "
            f"Pass --repo-root or move evidence under <manifest_dir>/.."
        ) from exc


def verification_passed(report: dict[str, Any]) -> bool:
    """Codex iter-3 absorb: verification pass predicate grounded in AO-MA-2 schema fields.

    Pass iff:
    - ``failed_checks`` is empty
    - ``scope_check.passed`` is True
    - ``secret_scan.passed`` is True
    - no ``commands[].outcome == "fail"`` (skipped allowed; non-failing but
      not sufficient on its own — the other gates carry the proof)
    - ``guard_flags`` all literal False
    """

    if report.get("failed_checks", []) != []:
        return False
    scope_check = report.get("scope_check") or {}
    if scope_check.get("passed") is not True:
        return False
    secret_scan = report.get("secret_scan") or {}
    if secret_scan.get("passed") is not True:
        return False
    for cmd in report.get("commands", []):
        if cmd.get("outcome") == "fail":
            return False
    guard_flags = report.get("guard_flags") or {}
    for required in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        if guard_flags.get(required) is not False:
            return False
    return True


@dataclass
class Integrator:
    """Pure-data integrator policy. No shell-out, no LLM, no GitHub write."""

    repo_root: Path
    integrator_agent_id: str = "claude-integrator"
    integrator_provider: str = "anthropic"
    integrator_session_id: str = "ao-ma-5-default-session"

    def __post_init__(self) -> None:
        if not isinstance(self.repo_root, Path):
            raise IntegratorError("repo_root must be a Path instance")
        self.repo_root = self.repo_root.resolve()

    def integrate(
        self,
        *,
        manifest_path: Path,
        runner_report_path: Path | None = None,
        worker_result_paths: dict[str, Path] | None = None,
        review_verdict_paths: dict[str, Path] | None = None,
        verification_report_paths: dict[str, Path] | None = None,
        emit: bool = True,
    ) -> IntegrationDecision:
        """Read artifacts → policy decide → emit + return IntegrationDecision.

        Trust boundary (Codex iter-2/3 absorb):
        1. manifest envelope validation BEFORE reading task_graph_id
        2. runner_report schema validation on disk-read
        3. manifest_sha256 cross-check NOT REQUIRED here (AO-MA-4 owns spawn-time
           binding; AO-MA-5 may run independently of spawn freshness)
        4. emit only when trust boundary valid; emit=False supports dry-run for tests

        Does NOT raise for not_integratable / rejected / conflict outcomes —
        returns IntegrationDecision with the corresponding decision states.
        Raises IntegratorError only for true I/O / schema-load failures.
        """

        manifest_path = manifest_path.resolve()
        manifest = self._load_json(manifest_path)
        _validate_manifest_envelope(manifest, manifest_path)
        task_graph_id = manifest["task_graph_id"]
        base_dir = manifest_path.parent.parent
        manifest_sha = sha256_of(manifest_path)

        # Codex iter-5 HIGH-1 absorb: load task_graph EARLY for cross-ref
        # checks (was loaded later for base_ref/base_sha only).
        task_graph_path = manifest_path.parent / "task_graph.v1.json"
        task_graph = self._load_json(task_graph_path)
        _validate_schema(task_graph, _TASK_GRAPH_SCHEMA_NAME, task_graph_path)

        # Cross-ref: task_graph.task_graph_id must match manifest.task_graph_id
        if task_graph.get("task_graph_id") != task_graph_id:
            raise IntegratorError(
                f"task_graph.v1.json task_graph_id {task_graph.get('task_graph_id')!r} != "
                f"manifest task_graph_id {task_graph_id!r}; split-brain artifact set"
            )

        if runner_report_path is None:
            runner_report_path = manifest_path.parent / "runner_report.v1.json"
        runner_report = self._load_json(runner_report_path)
        _validate_schema(runner_report, _RUNNER_REPORT_SCHEMA_NAME, runner_report_path)

        # Cross-ref: runner_report binds to same manifest + task_graph
        if runner_report.get("task_graph_id") != task_graph_id:
            raise IntegratorError(
                f"runner_report.v1.json task_graph_id {runner_report.get('task_graph_id')!r} != "
                f"manifest task_graph_id {task_graph_id!r}; split-brain artifact set"
            )
        if runner_report.get("manifest_sha256") != manifest_sha:
            raise IntegratorError(
                f"runner_report.v1.json manifest_sha256 {runner_report.get('manifest_sha256')!r} != "
                f"sha256_of(manifest_path) {manifest_sha!r}; manifest was modified after spawn"
            )
        if runner_report.get("base_sha") != task_graph.get("base_sha"):
            raise IntegratorError(
                f"runner_report.v1.json base_sha {runner_report.get('base_sha')!r} != "
                f"task_graph base_sha {task_graph.get('base_sha')!r}; base mismatch"
            )

        # Codex iter-5 MEDIUM absorb: empty workers → trust-boundary failure
        # (was emitting empty integration_report which contradicts the
        # "at least one worker decision" emit invariant from iter-4).
        task_ids = [w["task_id"] for w in runner_report.get("workers", [])]
        if not task_ids:
            raise IntegratorError(
                "runner_report.v1.json has no worker entries; trust boundary requires "
                "at least one worker decision to emit a meaningful integration_report"
            )

        worker_result_paths = worker_result_paths or {}
        review_verdict_paths = review_verdict_paths or {}
        verification_report_paths = verification_report_paths or {}

        # Per-worker decision pass
        decisions: list[dict[str, Any]] = []
        accepted_refs: list[str] = []
        rejected_refs: list[str] = []
        pending_refs: list[str] = []
        review_refs: list[str] = []
        verification_refs: list[str] = []
        accept_candidate_changes: dict[str, list[str]] = {}  # task_id -> actual_changed_files

        for worker in runner_report.get("workers", []):
            task_id = worker["task_id"]
            decision_record = self._decide_worker(
                task_id=task_id,
                task_graph_id=task_graph_id,
                worker_entry=worker,
                base_dir=base_dir,
                worker_result_paths=worker_result_paths,
                review_verdict_paths=review_verdict_paths,
                verification_report_paths=verification_report_paths,
            )
            decisions.append(decision_record["decision_record"])
            wr_ref = decision_record["worker_result_ref"]
            rv_ref = decision_record["review_verdict_ref"]
            vr_ref = decision_record["verification_report_ref"]
            if rv_ref:
                review_refs.append(rv_ref)
            if vr_ref:
                verification_refs.append(vr_ref)

            d = decision_record["decision_record"]["decision"]
            if d == "accept":
                if wr_ref:
                    accepted_refs.append(wr_ref)
                accept_candidate_changes[task_id] = decision_record["actual_changed_files"]
            elif d == "reject":
                if wr_ref:
                    rejected_refs.append(wr_ref)
            elif d == "not_integratable":
                if wr_ref:
                    pending_refs.append(wr_ref)

        # CF3 conflict pass: any overlap between accepted workers' actual_changed_files
        conflicts, conflict_task_ids = self._detect_conflicts(accept_candidate_changes)
        if conflict_task_ids:
            # Move conflicting workers from accepted → not_integratable with reason_code
            for decision_record in decisions:
                if decision_record["task_id"] in conflict_task_ids and decision_record["decision"] == "accept":
                    decision_record["decision"] = "not_integratable"
                    decision_record["reason_code"] = "actual_write_set_overlap"
                    wr_ref = decision_record["worker_result_ref"]
                    if wr_ref:
                        if wr_ref in accepted_refs:
                            accepted_refs.remove(wr_ref)
                        if wr_ref not in pending_refs:
                            pending_refs.append(wr_ref)
            # Recompute accept_candidate_changes (only true accepts remain)
            accept_candidate_changes = {
                tid: chs for tid, chs in accept_candidate_changes.items() if tid not in conflict_task_ids
            }

        # final_changed_files = union of accepted workers' actual_changed_files
        final_changed_set: set[str] = set()
        for changes in accept_candidate_changes.values():
            final_changed_set.update(changes)
        final_changed_files = sorted(final_changed_set)

        # Assembly plan: operator-runnable command list (argv form, data not shell strings)
        assembly_plan = self._build_assembly_plan(
            task_graph_id=task_graph_id,
            accepted_task_ids=list(accept_candidate_changes.keys()),
            runner_report=runner_report,
        )

        # Emit report
        integrator_identity = {
            "agent_id": self.integrator_agent_id,
            "agent_type": "integrator",
            "provider": self.integrator_provider,
            "session_id": self.integrator_session_id,
        }
        # task_graph already loaded + schema-validated + cross-ref'd earlier
        # (Codex iter-5 HIGH-1); no need to reload here.
        base_ref = task_graph.get("base_ref", "refs/heads/main")
        base_sha = task_graph["base_sha"]

        # Relativize all path refs to base_dir (integration_report.v1 path
        # $def rejects absolute paths). Decisions get their worker_result_ref
        # relativized in-place; ref lists are recomputed from the relativized
        # decisions so accepted/rejected/pending lists agree with decisions.
        for dec in decisions:
            dec["worker_result_ref"] = _relativize(dec.get("worker_result_ref"), base_dir)
            if "evidence_refs" in dec:
                dec["evidence_refs"] = [_relativize(e, base_dir) for e in dec["evidence_refs"] if e is not None]
        # _relativize returns str when input is non-None — the `if p is not None`
        # filter narrows the set, but mypy can't infer that the relativize
        # call only sees non-None values, so we cast the resulting set to set[str].
        rel_accepted = sorted(cast(set[str], {_relativize(p, base_dir) for p in accepted_refs if p is not None}))
        rel_rejected = sorted(cast(set[str], {_relativize(p, base_dir) for p in rejected_refs if p is not None}))
        rel_pending = sorted(cast(set[str], {_relativize(p, base_dir) for p in pending_refs if p is not None}))
        rel_reviews = sorted(cast(set[str], {_relativize(p, base_dir) for p in review_refs if p is not None}))
        rel_verifications = sorted(
            cast(set[str], {_relativize(p, base_dir) for p in verification_refs if p is not None})
        )

        report: dict[str, Any] = {}
        if emit:
            writer = IntegrationReportWriter(base_dir=base_dir)
            try:
                report = writer.emit(
                    task_graph_id=task_graph_id,
                    integrator=integrator_identity,
                    base_ref=base_ref,
                    base_sha=base_sha,
                    head_ref=base_ref,  # AO-MA-5 v1: no integrator branch yet; head = base
                    head_sha=base_sha,  # ditto
                    accepted_worker_results=rel_accepted,
                    rejected_worker_results=rel_rejected,
                    final_changed_files=final_changed_files,
                    conflicts=conflicts,
                    review_verdict_refs=rel_reviews,
                    verification_report_refs=rel_verifications,
                    pending_worker_results=rel_pending,
                    worker_decisions=decisions,
                    assembly_plan=assembly_plan,
                )
            except IntegrationReportWriterError as exc:
                raise IntegratorError(f"integration report write failed: {exc}") from exc

        # Overall status — derive from decisions, NOT ref-list emptiness
        # (a not_integratable worker with worker_result_ref=null still
        # counts as pending; ref lists only carry paths that exist).
        decision_kinds = [d["decision"] for d in decisions]
        has_pending = any(k == "not_integratable" for k in decision_kinds)
        has_rejections = any(k == "reject" for k in decision_kinds)
        has_conflicts = bool(conflicts)
        if accepted_refs and not (has_pending or has_rejections or has_conflicts):
            overall_status: Literal["all_accepted", "partial", "all_blocked"] = "all_accepted"
        elif accepted_refs:
            overall_status = "partial"
        else:
            overall_status = "all_blocked"

        diagnostics: list[str] = []
        for dec in decisions:
            if dec["decision"] != "accept":
                diagnostics.append(f"{dec['task_id']}: {dec['decision']} ({dec['reason_code']})")
        if conflicts:
            diagnostics.append(
                f"conflicts detected on {len(conflicts)} paths; conflicting workers moved to not_integratable"
            )

        return IntegrationDecision(
            overall_status=overall_status,
            report=report,
            assembly_plan=assembly_plan,
            diagnostics=diagnostics,
            has_conflicts=has_conflicts,
            has_rejections=has_rejections,
            has_pending=has_pending,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise IntegratorError(f"file not found: {path!s}")
        try:
            return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegratorError(f"failed to read {path!s}: {exc}") from exc

    def _decide_worker(
        self,
        *,
        task_id: str,
        task_graph_id: str,
        worker_entry: dict[str, Any],
        base_dir: Path,
        worker_result_paths: dict[str, Path],
        review_verdict_paths: dict[str, Path],
        verification_report_paths: dict[str, Path],
    ) -> dict[str, Any]:
        """Decide accept / reject / not_integratable for one worker.

        Codex iter-5 HIGH-1 absorb: cross-ref each worker artifact's
        task_graph_id + task_id (or reviewed_task_id / verified_task_ids)
        against the manifest's task_graph_id + the runner_report worker
        entry's task_id. Schema-valid bytes from a DIFFERENT graph/task
        must not satisfy THIS task's accept gate. Mismatches surface as
        ``schema_invalid`` (closest existing reason_code; ``cross_ref_mismatch``
        enum extension is nice-to-have for AO-MA-5 v1.1+).

        Returns dict with decision_record (matches worker_decision schema)
        + worker_result_ref / review_verdict_ref / verification_report_ref
        + actual_changed_files (for CF3 conflict pass).
        """

        # Worker result lookup
        wr_path = worker_result_paths.get(task_id)
        if wr_path is None:
            # Convention: <expected_worker_result_path> from runner_report worker entry
            expected = worker_entry.get("expected_worker_result_path")
            if expected:
                candidate = Path(expected)
                if candidate.exists():
                    wr_path = candidate

        if wr_path is None or not wr_path.exists():
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": None,
                    "decision": "not_integratable",
                    "reason_code": "missing_worker_result",
                },
                "worker_result_ref": None,
                "review_verdict_ref": None,
                "verification_report_ref": None,
                "actual_changed_files": [],
            }

        # Worker result schema validation
        try:
            wr_payload = self._load_json(wr_path)
            _validate_schema(wr_payload, _WORKER_RESULT_SCHEMA_NAME, wr_path)
        except IntegratorError:
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "schema_invalid",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": None,
                "verification_report_ref": None,
                "actual_changed_files": [],
            }

        # Codex iter-5 HIGH-1 absorb: worker_result task_graph_id + task_id cross-ref
        if wr_payload.get("task_graph_id") != task_graph_id or wr_payload.get("task_id") != task_id:
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "schema_invalid",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": None,
                "verification_report_ref": None,
                "actual_changed_files": [],
            }

        # Worker guard flag check
        guard_flags = wr_payload.get("guard_flags") or {}
        for required in ("support_widening", "production_platform_claim", "live_adapter_execution"):
            if guard_flags.get(required) is not False:
                return {
                    "decision_record": {
                        "task_id": task_id,
                        "worker_result_ref": str(wr_path),
                        "decision": "reject",
                        "reason_code": "guard_flag_violation",
                    },
                    "worker_result_ref": str(wr_path),
                    "review_verdict_ref": None,
                    "verification_report_ref": None,
                    "actual_changed_files": [],
                }

        # Worker no_secret_attestation check (treat secrets_recorded=True as guard_flag_violation)
        nsa = wr_payload.get("no_secret_attestation") or {}
        if nsa.get("secrets_recorded") is True:
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "guard_flag_violation",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": None,
                "verification_report_ref": None,
                "actual_changed_files": [],
            }

        # Worker actual_changed_files ⊆ declared_write_set
        declared = set(wr_payload.get("declared_write_set", []))
        actual = list(wr_payload.get("actual_changed_files", []))
        if not set(actual).issubset(declared):
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "actual_write_set_overlap",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": None,
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }

        # Review verdict lookup
        rv_path = review_verdict_paths.get(task_id)
        if rv_path is None or not rv_path.exists():
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "not_integratable",
                    "reason_code": "missing_review_verdict",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": None,
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }

        rv_payload = self._load_json(rv_path)
        try:
            _validate_schema(rv_payload, _REVIEW_VERDICT_SCHEMA_NAME, rv_path)
        except IntegratorError:
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "schema_invalid",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }

        # Codex iter-5 HIGH-1 absorb: review_verdict cross-ref
        if rv_payload.get("task_graph_id") != task_graph_id or rv_payload.get("reviewed_task_id") != task_id:
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "schema_invalid",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }

        verdict = rv_payload.get("verdict")
        if verdict == "REVISE":
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "review_revise",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }
        if verdict == "BLOCK":
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "review_block",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }
        # verdict == "AGREE" path continues

        # Verification report lookup
        vr_path = verification_report_paths.get(task_id)
        if vr_path is None or not vr_path.exists():
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "not_integratable",
                    "reason_code": "missing_verification_report",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": None,
                "actual_changed_files": actual,
            }

        vr_payload = self._load_json(vr_path)
        try:
            _validate_schema(vr_payload, _VERIFICATION_REPORT_SCHEMA_NAME, vr_path)
        except IntegratorError:
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "schema_invalid",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": str(vr_path),
                "actual_changed_files": actual,
            }

        # Codex iter-5 HIGH-1 absorb: verification_report cross-ref
        # (task_graph_id + task_id MUST be in verified_task_ids)
        if vr_payload.get("task_graph_id") != task_graph_id or task_id not in vr_payload.get("verified_task_ids", []):
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "schema_invalid",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": str(vr_path),
                "actual_changed_files": actual,
            }

        if not verification_passed(vr_payload):
            return {
                "decision_record": {
                    "task_id": task_id,
                    "worker_result_ref": str(wr_path),
                    "decision": "reject",
                    "reason_code": "verification_failed",
                },
                "worker_result_ref": str(wr_path),
                "review_verdict_ref": str(rv_path),
                "verification_report_ref": str(vr_path),
                "actual_changed_files": actual,
            }

        # All gates passed
        return {
            "decision_record": {
                "task_id": task_id,
                "worker_result_ref": str(wr_path),
                "decision": "accept",
                "reason_code": "accepted_full_evidence",
                "evidence_refs": [str(wr_path), str(rv_path), str(vr_path)],
            },
            "worker_result_ref": str(wr_path),
            "review_verdict_ref": str(rv_path),
            "verification_report_ref": str(vr_path),
            "actual_changed_files": actual,
        }

    def _detect_conflicts(
        self,
        accept_candidate_changes: dict[str, list[str]],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """CF3 conflict detection: same path in two accept-candidates → conflict.

        Returns (conflicts list for schema, set of task_ids touched by any conflict).
        """

        path_owners: dict[str, list[str]] = {}
        for task_id, changes in accept_candidate_changes.items():
            for path in changes:
                path_owners.setdefault(path, []).append(task_id)
        conflicts: list[dict[str, Any]] = []
        conflict_task_ids: set[str] = set()
        for path, owners in sorted(path_owners.items()):
            if len(owners) > 1:
                conflicts.append(
                    {
                        "path": path,
                        "resolution": f"operator_escalate: owners={sorted(owners)} both moved to not_integratable",
                    }
                )
                conflict_task_ids.update(owners)
        return conflicts, conflict_task_ids

    def _build_assembly_plan(
        self,
        *,
        task_graph_id: str,
        accepted_task_ids: list[str],
        runner_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build operator-runnable assembly plan in argv form.

        Each step is data, NOT executed by integrator. Operator-only=True
        const enforced by schema. Branch names come from runner_report
        worker entries (schema-validated).
        """

        if not accepted_task_ids:
            return []
        steps: list[dict[str, Any]] = []
        integrator_branch = f"codex/ao-ma-{task_graph_id}/integration"

        # Step 1: operator creates integrator branch from base
        steps.append(
            {
                "argv": ["git", "checkout", "-b", integrator_branch, "origin/main"],
                "operator_only": True,
                "side_effect": "local_branch_create",
                "requires_clean_worktree": True,
                "note": "Create integrator branch from origin/main",
            }
        )

        # Step 2+: for each accepted worker, merge its branch
        branch_by_task: dict[str, str] = {w["task_id"]: w["branch"] for w in runner_report.get("workers", [])}
        for task_id in sorted(accepted_task_ids):
            branch = branch_by_task.get(task_id)
            if not branch:
                continue
            steps.append(
                {
                    "argv": ["git", "merge", "--no-ff", branch],
                    "operator_only": True,
                    "side_effect": "local_git_merge",
                    "requires_clean_worktree": True,
                    "note": f"Merge accepted worker {task_id} branch",
                }
            )

        # Final step: operator opens PR (data only; integrator does not call gh)
        steps.append(
            {
                "argv": ["gh", "pr", "create", "--base", "main", "--head", integrator_branch, "--draft"],
                "operator_only": True,
                "side_effect": "remote_pr_create",
                "note": (
                    "Open draft PR with assembled integrator branch. "
                    "Integrator does NOT execute this command; operator runs it explicitly."
                ),
            }
        )
        return steps


def render_assembly_plan_text(assembly_plan: Iterable[dict[str, Any]]) -> str:
    """Render assembly_plan as human-readable text for CLI text format.

    Codex iter-3 absorb: JSON canonical (data); text is a renderer.
    """

    lines: list[str] = []
    lines.append("assembly_plan (operator-runnable; integrator does NOT execute):")
    for i, step in enumerate(assembly_plan, 1):
        argv = step.get("argv", [])
        side = step.get("side_effect", "?")
        note = step.get("note", "")
        cmd = " ".join(argv)
        lines.append(f"  {i}. [{side}] {cmd}")
        if note:
            lines.append(f"      # {note}")
    if not list(assembly_plan):
        lines.append("  (no accepted workers; no assembly steps)")
    return "\n".join(lines)
