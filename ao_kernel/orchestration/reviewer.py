"""AO-MA-6 reviewer (v1 — artifact intake + verdict emit; **NO LLM call**).

Consumes the operator-supplied verdict + findings + evidence paths
and emits a schema-valid ``review_verdict.v1.json`` artifact that the
AO-MA-5 integrator can consume. The actual review judgement comes from
an EXTERNAL reviewer (human, or an external LLM driver in a future
slice); this module is the **artifact intake + validation + writer**.

**HARD RULE pin (Codex iter-1/2/3 absorbed):**

- **No LLM execution surface** — this module does not call any LLM client
  API. AST + text-static tests enforce no relevant imports or method
  invocations. No driver flag (``llm-driven`` style) exists.
- **No ``subprocess`` import** — AST-static test enforced
- **No GitHub write** — no shell-out to push or PR-creation tooling
- **No PR/GitHub fetch** — explicit local file paths only; no URL-based input
- **No AO-MA-5 module edits** — this slice adds NEW files only
- ``release_authority`` not in ``review_verdict.v1`` schema; reviewer is not authority

**Accept gate (Codex iter-1/2 Crit-D + Crit-E equivalent):**

1. ``--worker-result`` REQUIRED + ``ao-ma-worker-result.schema.v1.json`` validates
2. ``worker_result.task_graph_id == manifest.task_graph_id`` cross-ref
3. ``worker_result.task_id == --task-id`` cross-ref
4. CLI mapping key (``<task_id>=<path>``) equals payload ``task_id``
5. ``reviewer.provider != worker_result.worker.provider`` (cross-provider HARD RULE)
6. ``--findings-json`` items conform to ``ao-ma-review-verdict.schema.v1.json::$defs.finding``
   (severity + title + body required; additionalProperties=false)
7. ``--prior-review-verdict`` files validate against full review-verdict schema
   AND ``task_graph_id == manifest.task_graph_id`` AND
   ``reviewed_task_id == --task-id``
8. Bounded REVISE: if prior REVISE count ``>= max_revise_rounds`` AND
   ``--verdict == "REVISE"`` → emitted verdict is FORCED to ``BLOCK``
   (only REVISE is overridden; AGREE / BLOCK pass through)

``Reviewer.review(...)`` returns a ``ReviewDecision`` dataclass; the CLI
maps it to exit codes. ``ReviewerError`` is raised only for I/O / schema
failures (not for normal verdict outcomes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.orchestration.review_verdict_writer import (
    ReviewVerdictWriter,
    ReviewVerdictWriterError,
)

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"

_TASK_GRAPH_SCHEMA_NAME = "ao-ma-task-graph.schema.v1.json"
_WORKER_RESULT_SCHEMA_NAME = "ao-ma-worker-result.schema.v1.json"
_REVIEW_VERDICT_SCHEMA_NAME = "ao-ma-review-verdict.schema.v1.json"

Verdict = Literal["AGREE", "REVISE", "BLOCK"]
Provider = Literal["openai", "anthropic", "minimax", "google", "local", "tool"]


class ReviewerError(RuntimeError):
    """Raised for I/O / schema-load failures (NOT for normal verdict outcomes)."""


@dataclass
class ReviewInputs:
    """Inputs to a single review call (Codex iter-2 absorb: dataclass-shaped).

    All paths are explicit local files. PR URL fetching is OUT of v1 scope
    (Codex iter-1 must_close #5). AO-MA-6.5 may add a context collector.
    """

    manifest_path: Path
    task_id: str
    worker_result_paths: dict[str, Path]
    reviewer_agent_id: str
    reviewer_provider: Provider
    reviewer_session_id: str
    verdict: Verdict
    findings_path: Path
    diff_path: Path | None = None
    acceptance_criteria_path: Path | None = None
    repo_ssot_path: Path | None = None
    ci_results_path: Path | None = None
    artifact_chain_path: Path | None = None
    prior_review_verdict_paths: list[Path] = field(default_factory=list)


@dataclass
class ReviewDecision:
    """Codex iter-2 absorb: dataclass return; CLI maps to exit code.

    ``emitted_verdict`` may differ from ``requested_verdict`` when bounded
    REVISE budget forces ``BLOCK``. Diagnostics include the budget shape
    (Codex iter-3 nice-to-have: stable diagnostic contract).
    """

    requested_verdict: Verdict
    emitted_verdict: Verdict
    report: dict[str, Any]
    diagnostics: list[str] = field(default_factory=list)
    prior_revise_count: int = 0
    max_revise_rounds: int = 0
    budget_forced_block: bool = False


def _load_schema(name: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewerError(f"failed to load bundled schema {name!r}: {exc}") from exc


def _validate_schema(payload: dict[str, Any], schema_name: str, source: Path) -> None:
    schema = _load_schema(schema_name)
    try:
        Draft202012Validator(schema).validate(payload)
    except ValidationError as exc:
        raise ReviewerError(
            f"{source.name} failed schema {schema_name!r}: {exc.message} (at {list(exc.absolute_path)})"
        ) from exc


def _finding_validator() -> Draft202012Validator:
    """Codex iter-3 nice-to-have absorb: derive finding validator from bundled
    review-verdict schema's $defs/finding so any future schema drift is
    automatically picked up. No hand-written duplicate validator.
    """

    review_schema = _load_schema(_REVIEW_VERDICT_SCHEMA_NAME)
    finding_def = review_schema.get("$defs", {}).get("finding")
    if not finding_def:
        raise ReviewerError(
            f"bundled {_REVIEW_VERDICT_SCHEMA_NAME!r} missing '$defs/finding'; cannot validate --findings-json"
        )
    # Build a standalone schema that references the embedded $defs so
    # `$ref: #/$defs/path` still resolves.
    standalone = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": review_schema.get("$defs", {}),
        "$ref": "#/$defs/finding",
    }
    return Draft202012Validator(standalone)


@dataclass
class Reviewer:
    """Pure-data reviewer (Codex iter-1 L1): no LLM, no GitHub, no shell-out."""

    repo_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.repo_root, Path):
            raise ReviewerError("repo_root must be a Path instance")
        self.repo_root = self.repo_root.resolve()

    def review(self, inputs: ReviewInputs, *, emit: bool = True) -> ReviewDecision:
        """Read inputs → validate + cross-ref → enforce bounded REVISE → emit + return.

        Trust boundary (cumulative iter-1/2 absorb):
        1. manifest envelope + task_graph load + cross-ref task_graph_id
        2. worker_result.v1 schema + cross-ref (task_graph_id, task_id, mapping key)
        3. reviewer.provider != worker_result.worker.provider (cross-provider HARD RULE)
        4. findings-json items conform to $defs/finding
        5. prior review_verdict.v1 entries validate + cross-ref (task_graph_id, reviewed_task_id)
        6. REVISE budget check (force BLOCK only when requested REVISE)
        7. allowed_sources derived from provided optional paths (NOT user-input)

        Does NOT raise for the normal AGREE/REVISE/BLOCK verdict path;
        only raises ReviewerError for I/O / schema-load / trust-boundary
        failures.
        """

        # 1. Manifest + task_graph
        manifest = self._load_json(inputs.manifest_path)
        task_graph_id = manifest.get("task_graph_id")
        if not isinstance(task_graph_id, str):
            raise ReviewerError(f"{inputs.manifest_path.name}: task_graph_id missing or non-string")
        task_graph_path = inputs.manifest_path.parent / "task_graph.v1.json"
        task_graph = self._load_json(task_graph_path)
        _validate_schema(task_graph, _TASK_GRAPH_SCHEMA_NAME, task_graph_path)
        if task_graph.get("task_graph_id") != task_graph_id:
            raise ReviewerError(
                f"task_graph.v1.json task_graph_id {task_graph.get('task_graph_id')!r} != "
                f"manifest task_graph_id {task_graph_id!r}; split-brain artifact set"
            )

        # 2. worker_result (mapping key + payload cross-ref)
        wr_path = inputs.worker_result_paths.get(inputs.task_id)
        if wr_path is None:
            raise ReviewerError(
                f"--worker-result mapping missing entry for task_id {inputs.task_id!r} "
                f"(supplied keys: {sorted(inputs.worker_result_paths)})"
            )
        wr_payload = self._load_json(wr_path)
        _validate_schema(wr_payload, _WORKER_RESULT_SCHEMA_NAME, wr_path)
        if wr_payload.get("task_graph_id") != task_graph_id:
            raise ReviewerError(
                f"{wr_path.name} task_graph_id {wr_payload.get('task_graph_id')!r} != "
                f"manifest task_graph_id {task_graph_id!r}"
            )
        if wr_payload.get("task_id") != inputs.task_id:
            raise ReviewerError(
                f"{wr_path.name} payload task_id {wr_payload.get('task_id')!r} != "
                f"--task-id {inputs.task_id!r}; CLI mapping mismatch with payload"
            )

        # 3. Cross-provider HARD RULE
        implementer_provider = (wr_payload.get("worker") or {}).get("provider")
        if implementer_provider == inputs.reviewer_provider:
            raise ReviewerError(
                f"reviewer.provider {inputs.reviewer_provider!r} matches worker_result implementer "
                f"provider {implementer_provider!r}; cross-AI peer review HARD RULE requires different providers"
            )
        if not isinstance(implementer_provider, str):
            raise ReviewerError(
                f"{wr_path.name} worker.provider is missing or non-string; cannot verify cross-provider"
            )

        # 4. findings-json schema validation (Codex iter-3 derive from bundled $defs/finding)
        findings_payload = self._load_json_or_list(inputs.findings_path)
        if not isinstance(findings_payload, list):
            raise ReviewerError(
                f"{inputs.findings_path.name} must be a JSON array of finding objects; got {type(findings_payload).__name__}"
            )
        finding_validator = _finding_validator()
        for index, item in enumerate(findings_payload):
            try:
                finding_validator.validate(item)
            except ValidationError as exc:
                raise ReviewerError(
                    f"{inputs.findings_path.name} item {index}: {exc.message} (at {list(exc.absolute_path)})"
                ) from exc

        # 5. Prior review verdicts (validate + cross-ref)
        prior_revise_count = 0
        for prior_path in inputs.prior_review_verdict_paths:
            prior_payload = self._load_json(prior_path)
            _validate_schema(prior_payload, _REVIEW_VERDICT_SCHEMA_NAME, prior_path)
            if prior_payload.get("task_graph_id") != task_graph_id:
                # Defensive: skip prior verdicts that bind to a different graph
                continue
            if prior_payload.get("reviewed_task_id") != inputs.task_id:
                # Defensive: skip prior verdicts for a different task
                continue
            if prior_payload.get("verdict") == "REVISE":
                prior_revise_count += 1

        # 6. Bounded REVISE enforcement (Codex iter-2 must_close #1: only REVISE → BLOCK)
        max_rounds_raw = (task_graph.get("review_policy") or {}).get("max_revise_rounds", 0)
        try:
            max_revise_rounds = int(max_rounds_raw)
        except (TypeError, ValueError):
            max_revise_rounds = 0
        budget_forced_block = False
        emitted_verdict: Verdict = inputs.verdict
        if inputs.verdict == "REVISE" and max_revise_rounds > 0 and prior_revise_count >= max_revise_rounds:
            emitted_verdict = "BLOCK"
            budget_forced_block = True

        # 7. allowed_sources derived from provided optional paths
        # Codex iter-4 must_fix absorb: NO default fallback to ``["pr_diff"]``;
        # an empty allowed_sources set means the reviewer has no evidence
        # at all — that is operator misuse, fail-closed exit 2 (no fabrication
        # of source claims that don't correspond to actual reviewed artifacts).
        # Each optional path's existence is also checked here (defense in
        # depth) so a typo'd CLI arg cannot survive into a schema-valid
        # artifact that claims evidence the reviewer never read.
        allowed_sources_set: set[str] = set()
        for path_attr, source_label in (
            ("diff_path", "pr_diff"),
            ("acceptance_criteria_path", "issue_acceptance"),
            ("repo_ssot_path", "repo_ssot"),
            ("ci_results_path", "ci_results"),
            ("artifact_chain_path", "artifact_chain"),
        ):
            evidence_path = getattr(inputs, path_attr)
            if evidence_path is None:
                continue
            if not evidence_path.exists():
                raise ReviewerError(
                    f"--{path_attr.replace('_', '-')} {evidence_path!s} does not exist; "
                    f"refusing to claim {source_label!r} in allowed_sources for an unread artifact"
                )
            allowed_sources_set.add(source_label)
        if inputs.prior_review_verdict_paths:
            allowed_sources_set.add("finding_context")
        if not allowed_sources_set:
            raise ReviewerError(
                "no review evidence supplied (--diff-path / --acceptance-criteria-path / "
                "--repo-ssot / --ci-results / --artifact-chain / --prior-review-verdict); "
                "reviewer cannot produce a meaningful verdict without at least one source. "
                "Operator: supply the actual artifacts the external reviewer consulted."
            )
        allowed_sources = sorted(allowed_sources_set)

        # reviewed_artifacts derived from --worker-result + evidence paths +
        # --prior-review-verdict
        reviewed_artifacts_set: set[str] = set()
        reviewed_artifacts_set.add(self._relativize(wr_path))
        for opt_path in (
            inputs.diff_path,
            inputs.acceptance_criteria_path,
            inputs.repo_ssot_path,
            inputs.ci_results_path,
            inputs.artifact_chain_path,
        ):
            if opt_path is not None:
                reviewed_artifacts_set.add(self._relativize(opt_path))
        for prior_path in inputs.prior_review_verdict_paths:
            reviewed_artifacts_set.add(self._relativize(prior_path))
        reviewed_artifacts = sorted(reviewed_artifacts_set)

        # Build review_verdict.v1.json payload
        reviewer_block = {
            "agent_id": inputs.reviewer_agent_id,
            "agent_type": "reviewer",
            "provider": inputs.reviewer_provider,
            "session_id": inputs.reviewer_session_id,
        }
        implementer_block = {
            "agent_id": (wr_payload.get("worker") or {}).get("agent_id", inputs.task_id),
            "agent_type": "implementer",
            "provider": implementer_provider,
            "session_id": (wr_payload.get("worker") or {}).get("session_id", "unknown"),
        }
        report = {
            "schema_version": "ao-ma-review-verdict.v1",
            "task_graph_id": task_graph_id,
            "reviewed_task_id": inputs.task_id,
            "reviewer": reviewer_block,
            "implementer": implementer_block,
            "independent_review": True,
            "cross_provider_verified": True,
            "allowed_sources": allowed_sources,
            "prohibited_sources_absent": True,
            "verdict": emitted_verdict,
            "findings": findings_payload,
            "reviewed_artifacts": reviewed_artifacts,
            "no_secret_attestation": {"secrets_recorded": False},
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }

        diagnostics: list[str] = []
        if budget_forced_block:
            diagnostics.append(
                f"REVISE budget exhausted (prior={prior_revise_count}, max={max_revise_rounds}); "
                f"verdict forced from REVISE to BLOCK"
            )
        # (Codex iter-4 absorb: empty allowed_sources is now a fail-closed
        # ReviewerError above, not a diagnostic — execution can't reach here
        # without at least one evidence source.)

        if emit:
            output_dir = inputs.manifest_path.parent / "workers" / inputs.task_id
            writer = ReviewVerdictWriter(output_dir=output_dir)
            try:
                writer.emit(report)
            except ReviewVerdictWriterError as exc:
                raise ReviewerError(f"review_verdict write failed: {exc}") from exc

        return ReviewDecision(
            requested_verdict=inputs.verdict,
            emitted_verdict=emitted_verdict,
            report=report,
            diagnostics=diagnostics,
            prior_revise_count=prior_revise_count,
            max_revise_rounds=max_revise_rounds,
            budget_forced_block=budget_forced_block,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ReviewerError(f"file not found: {path!s}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReviewerError(f"failed to read {path!s}: {exc}") from exc
        if not isinstance(data, dict):
            raise ReviewerError(f"{path.name}: expected a JSON object at top level")
        return cast(dict[str, Any], data)

    def _load_json_or_list(self, path: Path) -> Any:
        """Like _load_json but allows top-level array (for --findings-json)."""

        if not path.exists():
            raise ReviewerError(f"file not found: {path!s}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReviewerError(f"failed to read {path!s}: {exc}") from exc

    def _relativize(self, path: Path) -> str:
        """Relativize a path to ``repo_root`` for schema-valid artifact paths.

        Mirrors AO-MA-5 ``_relativize`` semantics: outside-root paths are
        fail-closed (no bare-naming). Caller raises ReviewerError indirectly
        via the schema validator if this returns a path containing ``..``.
        """

        resolved = path.resolve()
        try:
            rel = resolved.relative_to(self.repo_root)
        except ValueError as exc:
            raise ReviewerError(
                f"Evidence path is outside the repo_root {self.repo_root!s}: {resolved!s}. "
                f"Refusing to bare-name it (audit provenance lost). "
                f"Pass the artifact under the repo or run from a worktree that contains it."
            ) from exc
        return str(rel)
