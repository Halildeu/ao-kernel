"""AO-MA-4.6-1 native worker result importer (import-only, pure core).

Closes the AO-MA pipeline gap between the AO-MA-4.5 deterministic local
worker fixture and the real-AI worker output, WITHOUT violating the
control-plane model. The operator (or a native AI interface — claude-cli,
codex-cli, mavis-cli) produces ``worker_result.v1.json`` externally; this
module imports it: reads the file, schema-validates the artifact chain
(worker_result + runner_report + manifest envelope + task_graph +
agent_assignment), provenance-binds it to the AO-MA-4 runner truth, and
atomically copies the validated artifact into the canonical
``<artifact_dir>/workers/<task_id>/worker_result.v1.json`` location so
AO-MA-5/6/7 can consume it (those layers fail-closed on evidence outside
``base_dir`` / ``artifact_dir``).

Design boundaries (Codex thread 019e8000-e794-74c0-a47d-725b41da72a4,
CNS-20260601-001 plan iter-1..4 REVISE -> AGREE):

- Pure import-only. NO subprocess, NO socket, NO network, NO LLM, NO
  GitHub read/write. AST import-allowlist test pins the module's set
  of imports so a forbidden module (subprocess/socket/requests/httpx/
  urllib/asyncio.subprocess/os.popen/anthropic/openai/mavis client/MCP
  client) cannot be added without breaking the test.
- Two error classes (Codex iter-3/4 absorb):
  * Fatal trust-boundary error: ``NativeWorkerImportError`` raised
    before any import_report is written. Triggered by JSON parse fail,
    artifact schema-invalid (including guard/no_secret_attestation
    const violations — they live at the artifact's own schema
    boundary), manifest envelope invalid, manifest sha mismatch with
    ``runner_report.manifest_sha256``, ``task_graph`` / ``assignment``
    sha mismatch with the manifest entry or with the runner entry,
    runner entry missing for the requested ``task_id``, and cross-id
    mismatches (``task_graph_id`` / ``task_id`` / ``assignment_id``
    across the chain).
  * Reportable policy-invalid: a schema-valid import_report is emitted
    with ``valid=false``, ``integrated_worker_result_path=None``, and
    ``integrated_worker_result_sha256=None``. Triggered by
    ``source_interface`` not in allowlist, ``source_interface`` /
    ``worker_provider`` mismatch, ``runner_entry.status`` not in
    ``{prepared, skipped_existing_idempotent}``, declared write set
    mismatch across worker/assignment/task_graph, actual changed files
    not a subset of declared, empty actual changed files, non-empty
    ``known_gaps`` (4.6-1; downstream emits a finding in 4.6-2), and
    existing integrated file with a different hash (no overwrite).
- Manifest anchoring. The trusted source-of-truth for the AO-MA-4
  artifact set is the manifest envelope. ``artifact_dir`` is derived
  canonically as ``runner_report_path.parent.resolve()``; the
  ``--artifact-dir`` CLI flag is optional and, when provided, must
  equal that derived value (mismatch is fatal). ``manifest.v1.json``,
  ``task_graph.v1.json``, and the agent assignment referenced by the
  runner entry are loaded from ``artifact_dir`` and verified
  sha-bound: ``sha256(manifest) == runner_report.manifest_sha256``,
  ``sha256(task_graph) == manifest_entry_sha256``,
  ``sha256(assignment) == manifest_entry_sha256 ==
  runner_entry.assignment_sha256``.
- Recompute-not-trust. ``import_native_worker_result`` populates the
  report's ``valid`` field from ``all(checks[k].outcome == "pass")``,
  never from a caller-supplied flag. ``verify_import_binding``
  re-derives the same flag from the report's own ``checks`` and
  rejects forged ``valid=true`` with a non-pass check. All sha256
  values in the report are re-computed from disk during verify.
- Atomic copy. The integrated worker_result is written via temp file +
  fsync + ``Path.replace``. An existing integrated file with a
  different hash refuses the replace (reportable invalid). An
  existing integrated file with the same hash is idempotent OK.
- No release authority. The import report records audit evidence; it
  does NOT release AI output. Release authority remains with the
  ao-release-gate required check + branch ruleset + non-author
  approval. ``execution_performed_by_ao_kernel`` and
  ``ai_output_release_authority`` are schema const false; the module
  rejects any attempt to widen them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

from jsonschema import Draft202012Validator


# ---------------------------------------------------------------------------
# Constants / pinned regexes
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "ao-ma-native-worker-import-report.v1"
"""Pinned schema_version emitted by build_import_report."""

IMPORT_MODE = "import_only"
"""Hard-pinned: ao-kernel never spawns the worker."""

EXPECTED_MANIFEST_SCHEMA_VERSION = "ao-ma-orchestration-manifest.v1"
"""Mirror of worker_runner._EXPECTED_MANIFEST_SCHEMA_VERSION (copied per
Codex iter-4 plan: copy keeps AST allowlist narrow; refactor would have
to add ``ao_kernel.orchestration.worker_runner`` to the allowlist and
widen the import surface for a 4.6-1 slice that only needs one helper
mirror)."""

DEFAULT_SOURCE_INTERFACE_ALLOWLIST: tuple[str, ...] = (
    "claude-cli",
    "codex-cli",
    "mavis-cli",
    "local-file",
)
"""Canonical full allowlist. Caller may supply a narrower allowlist; the
effective allowlist is always recorded in the import report under
``effective_source_interface_allowlist`` for audit transparency."""

_SOURCE_INTERFACE_PROVIDER_MAP: dict[str, frozenset[str]] = {
    "claude-cli": frozenset({"anthropic"}),
    "codex-cli": frozenset({"openai"}),
    "mavis-cli": frozenset({"minimax"}),
    "local-file": frozenset({"local", "tool"}),
}
"""(source_interface, worker_provider) consistency map. Provenance
must not silently lie: an operator declaring ``claude-cli`` cannot
import a ``worker_provider=openai`` worker_result."""

_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_ARTIFACT_PATH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.v1\.json$")
_TASK_GRAPH_ID_PATTERN = re.compile(r"^ao-ma-[a-z0-9][a-z0-9-]{2,80}$")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,80}$")
_RFC3339_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]+$")

# Notifier-grade machine redaction. Free-text fields (currently only
# finding messages and check messages) are scrubbed defensively before
# entering an artifact. The list mirrors the notifier denylist in
# spirit; widening it does not weaken behavior.
_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ghp_[A-Za-z0-9]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_.\-]{16,}", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"https?://hooks\.[A-Za-z0-9.\-]+/[A-Za-z0-9_/\-]+"),
    re.compile(r"https?://outlook\.office\.com/webhook/[A-Za-z0-9./\-]+"),
)


class NativeWorkerImportError(Exception):
    """Fatal trust-boundary error in the native worker result importer.

    Raised BEFORE any import report is emitted and BEFORE any integrated
    copy is written. Triggered only by trust-boundary failures
    (artifact schema-invalid, JSON parse fail, manifest sha mismatch,
    cross-id mismatch, missing runner entry). Reportable policy-invalid
    inputs do NOT raise this error; they produce a schema-valid
    import_report with ``valid=false`` and no integrated copy.
    """


# ---------------------------------------------------------------------------
# Small helpers (pure)
# ---------------------------------------------------------------------------


def _redact(text: object) -> str:
    """Scrub secret-shaped substrings out of a free-text value."""

    if not isinstance(text, str):
        return ""
    scrubbed = text
    for pattern in _LEAK_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    return scrubbed


def _compute_sha256(path: Path) -> str:
    """Return ``sha256:<hex>`` for the file at ``path``."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _load_json_or_fatal(path: Path, label: str) -> Any:
    """Read+parse JSON; raise NativeWorkerImportError on any failure."""

    if not path.exists() or not path.is_file():
        raise NativeWorkerImportError(f"{label}: file not found at {path!s}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NativeWorkerImportError(f"{label}: read error at {path!s}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise NativeWorkerImportError(f"{label}: JSON parse error at {path!s}: {exc}") from exc


def _validate_or_fatal(data: Any, schema: Mapping[str, Any], label: str) -> None:
    """Draft 2020-12 validate; raise NativeWorkerImportError on first error."""

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.absolute_path)
    if errors:
        first = errors[0]
        # Path-only context (no value echo) to avoid leaking secrets.
        loc = "/".join(str(p) for p in first.absolute_path) or "<root>"
        raise NativeWorkerImportError(f"{label}: schema-invalid at {loc}: {first.message}")


def _validate_manifest_envelope_or_fatal(manifest: Any, source: Path) -> None:
    """Codex iter-4 absorb: copy of worker_runner._validate_manifest_envelope.

    Replicated rather than imported to keep this module's AST import
    allowlist narrow (stdlib + jsonschema only). The two copies are
    pinned by tests on both sides; if behavior diverges, tests fail
    fast.
    """

    if not isinstance(manifest, dict):
        raise NativeWorkerImportError(f"{source.name}: manifest must be a JSON object")

    schema_version = manifest.get("schema_version")
    if schema_version != EXPECTED_MANIFEST_SCHEMA_VERSION:
        raise NativeWorkerImportError(
            f"{source.name}: schema_version mismatch: expected "
            f"{EXPECTED_MANIFEST_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    task_graph_id = manifest.get("task_graph_id")
    if not isinstance(task_graph_id, str) or not _TASK_GRAPH_ID_PATTERN.match(task_graph_id):
        raise NativeWorkerImportError(f"{source.name}: task_graph_id {task_graph_id!r} does not match AO-MA-2 pattern")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise NativeWorkerImportError(f"{source.name}: artifacts must be a non-empty array")

    seen_paths: set[str] = set()
    task_graph_entries = 0
    for index, entry in enumerate(artifacts):
        if not isinstance(entry, dict):
            raise NativeWorkerImportError(f"{source.name}: artifacts[{index}] must be a JSON object")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise NativeWorkerImportError(f"{source.name}: artifacts[{index}].path must be a non-empty string")
        if path.startswith("/") or ".." in Path(path).parts or "\\" in path:
            raise NativeWorkerImportError(
                f"{source.name}: artifacts[{index}].path {path!r} contains traversal/absolute"
            )
        if not _ARTIFACT_PATH_PATTERN.match(path):
            raise NativeWorkerImportError(f"{source.name}: artifacts[{index}].path {path!r} does not match '*.v1.json'")
        if path in seen_paths:
            raise NativeWorkerImportError(f"{source.name}: duplicate artifact path {path!r}")
        seen_paths.add(path)
        if path == "task_graph.v1.json":
            task_graph_entries += 1
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not _SHA256_PATTERN.match(sha):
            raise NativeWorkerImportError(
                f"{source.name}: artifacts[{index}].sha256 must match 'sha256:[0-9a-f]{{64}}'"
            )
        size_bytes = entry.get("size_bytes")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise NativeWorkerImportError(f"{source.name}: artifacts[{index}].size_bytes must be a positive integer")

    if task_graph_entries != 1:
        raise NativeWorkerImportError(
            f"{source.name}: must declare exactly one task_graph.v1.json artifact entry (got {task_graph_entries})"
        )


def _find_manifest_entry(manifest: Mapping[str, Any], path: str) -> Mapping[str, Any] | None:
    """Locate a manifest artifact entry by path."""

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    for entry in artifacts:
        if not isinstance(entry, dict):
            continue
        if entry.get("path") == path:
            return entry
    return None


def _find_runner_entry(runner_report: Mapping[str, Any], task_id: str) -> Mapping[str, Any] | None:
    """Locate the runner_report.workers[] entry for ``task_id``."""

    workers = runner_report.get("workers")
    if not isinstance(workers, list):
        return None
    for entry in workers:
        if not isinstance(entry, dict):
            continue
        if entry.get("task_id") == task_id:
            return entry
    return None


def _canonical_integrated_path(artifact_dir: Path, task_id: str) -> Path:
    """Return ``<artifact_dir>/workers/<task_id>/worker_result.v1.json``."""

    return artifact_dir / "workers" / task_id / "worker_result.v1.json"


def _atomic_write_bytes(target: Path, payload: bytes) -> None:
    """Write ``payload`` atomically to ``target`` (tmp + fsync + replace)."""

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(target)


# ---------------------------------------------------------------------------
# Check/finding builders (pure)
# ---------------------------------------------------------------------------


def _check_pass(message: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"outcome": "pass"}
    if message is not None:
        out["message"] = _redact(message)
    return out


def _check_fail(message: str) -> dict[str, Any]:
    return {"outcome": "fail", "message": _redact(message)}


def _finding(code: str, severity: str, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": _redact(message)}


REQUIRED_CHECK_KEYS: tuple[str, ...] = (
    "source_json_readable",
    "worker_result_schema_valid",
    "runner_report_schema_valid",
    "manifest_envelope_valid",
    "manifest_sha_bound",
    "task_graph_binding_valid",
    "assignment_binding_valid",
    "runner_entry_eligible",
    "cross_id_consistent",
    "cross_ref_consistent",
    "declared_write_set_bound",
    "actual_subset_declared",
    "actual_non_empty",
    "known_gaps_empty",
    "no_secret_attestation",
    "guard_flags_closed",
    "source_interface_allowed",
    "source_interface_provider_consistent",
    "canonical_integrated_path",
    "source_integrated_hash_match",
)


def _recompute_valid(checks: Mapping[str, Any]) -> bool:
    for key in REQUIRED_CHECK_KEYS:
        entry = checks.get(key)
        if not isinstance(entry, Mapping):
            return False
        if entry.get("outcome") != "pass":
            return False
    return True


# ---------------------------------------------------------------------------
# Public API: import_native_worker_result
# ---------------------------------------------------------------------------


def import_native_worker_result(
    source_result_path: Path,
    runner_report_path: Path,
    source_interface: str,
    imported_at: str,
    *,
    artifact_dir: Path | None = None,
    source_interface_allowlist: Sequence[str] | None = None,
    worker_result_schema: Mapping[str, Any],
    runner_report_schema: Mapping[str, Any],
    task_graph_schema: Mapping[str, Any],
    assignment_schema: Mapping[str, Any],
    import_report_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Import a native AI worker_result.v1.json into the canonical artifact tree.

    Fatal trust-boundary errors (artifact schema-invalid, JSON parse
    fail, manifest sha mismatch, cross-id mismatch, missing runner
    entry, ``artifact_dir`` mismatch) raise ``NativeWorkerImportError``
    BEFORE any report is emitted and BEFORE any integrated copy is
    written.

    Reportable policy-invalid (source_interface allowlist mismatch,
    source_interface/provider mismatch, runner status not eligible,
    declared write set mismatch, actual not subset of declared, empty
    actual, known_gaps non-empty, existing integrated different hash)
    return a schema-valid import_report with ``valid=false``,
    ``integrated_worker_result_path=None``, and
    ``integrated_worker_result_sha256=None``.

    All checks must pass for a successful import: the integrated file
    is atomically written and the report carries ``valid=true``.
    """

    if not _RFC3339_PATTERN.match(imported_at):
        raise NativeWorkerImportError(f"imported_at {imported_at!r} is not RFC3339 UTC (YYYY-MM-DDTHH:MM:SSZ)")

    if source_interface not in DEFAULT_SOURCE_INTERFACE_ALLOWLIST:
        # schema would have caught this too, but fail fast and clearly
        raise NativeWorkerImportError(
            f"source_interface {source_interface!r} is not a known interface; "
            f"expected one of {list(DEFAULT_SOURCE_INTERFACE_ALLOWLIST)}"
        )

    # Codex iter-5 absorb (post-impl REVISE): validate the caller-supplied
    # allowlist BEFORE doing any work. Without this, a duplicate or unknown
    # entry would later make the emitted import_report schema-invalid; the
    # report-level _validate_or_fatal would raise fatal AFTER the atomic
    # copy had already been written — violating the "fatal -> NO copy"
    # contract. Caller wiring bug = fatal.
    if source_interface_allowlist is not None:
        seen: set[str] = set()
        for entry in source_interface_allowlist:
            if not isinstance(entry, str):
                raise NativeWorkerImportError(f"source_interface_allowlist contains non-string entry: {entry!r}")
            if entry not in DEFAULT_SOURCE_INTERFACE_ALLOWLIST:
                raise NativeWorkerImportError(
                    f"source_interface_allowlist contains unknown entry {entry!r}; "
                    f"expected subset of {list(DEFAULT_SOURCE_INTERFACE_ALLOWLIST)}"
                )
            if entry in seen:
                raise NativeWorkerImportError(f"source_interface_allowlist contains duplicate entry {entry!r}")
            seen.add(entry)
        if not seen:
            raise NativeWorkerImportError(
                "source_interface_allowlist must be non-empty (None means default canonical full allowlist)"
            )

    # --- artifact_dir derivation (Codex iter-2/3 absorb) -------------------
    canonical_artifact_dir = runner_report_path.parent.resolve()
    if artifact_dir is not None:
        if artifact_dir.resolve() != canonical_artifact_dir:
            raise NativeWorkerImportError(
                f"artifact_dir {artifact_dir!s} does not match runner_report parent "
                f"{canonical_artifact_dir!s}; canonical derivation must hold"
            )

    # --- fatal loads (Codex iter-4 absorb: artifact schema-invalid = fatal)
    worker_result = _load_json_or_fatal(source_result_path, "worker_result")
    _validate_or_fatal(worker_result, worker_result_schema, "worker_result")

    runner_report = _load_json_or_fatal(runner_report_path, "runner_report")
    _validate_or_fatal(runner_report, runner_report_schema, "runner_report")

    manifest_path = canonical_artifact_dir / "manifest.v1.json"
    manifest_raw = _load_json_or_fatal(manifest_path, "manifest")
    _validate_manifest_envelope_or_fatal(manifest_raw, manifest_path)
    if not isinstance(manifest_raw, dict):  # pragma: no cover - envelope guard above
        raise NativeWorkerImportError("manifest: must be JSON object after envelope validation")
    manifest = manifest_raw

    manifest_sha = _compute_sha256(manifest_path)
    runner_manifest_sha = runner_report.get("manifest_sha256")
    if manifest_sha != runner_manifest_sha:
        raise NativeWorkerImportError(
            f"manifest_sha_mismatch: on-disk {manifest_sha} vs runner_report manifest_sha256 {runner_manifest_sha!r}"
        )

    task_graph_path = canonical_artifact_dir / "task_graph.v1.json"
    task_graph_entry = _find_manifest_entry(manifest, "task_graph.v1.json")
    if task_graph_entry is None:
        raise NativeWorkerImportError("manifest: missing task_graph.v1.json entry")
    task_graph_sha = _compute_sha256(task_graph_path)
    if task_graph_sha != task_graph_entry.get("sha256"):
        raise NativeWorkerImportError(
            f"task_graph_sha_mismatch: on-disk {task_graph_sha} vs manifest entry {task_graph_entry.get('sha256')!r}"
        )
    task_graph = _load_json_or_fatal(task_graph_path, "task_graph")
    _validate_or_fatal(task_graph, task_graph_schema, "task_graph")

    task_id = worker_result.get("task_id")
    if not isinstance(task_id, str):
        raise NativeWorkerImportError("worker_result.task_id missing or not a string")

    runner_entry = _find_runner_entry(runner_report, task_id)
    if runner_entry is None:
        raise NativeWorkerImportError(f"runner_report.workers[] has no entry for task_id {task_id!r}")

    assignment_ref_rel = runner_entry.get("assignment_ref")
    if not isinstance(assignment_ref_rel, str) or not assignment_ref_rel:
        raise NativeWorkerImportError(f"runner_entry[{task_id!r}].assignment_ref must be a non-empty string")
    assignment_path = canonical_artifact_dir / assignment_ref_rel
    assignment_entry = _find_manifest_entry(manifest, assignment_ref_rel)
    if assignment_entry is None:
        raise NativeWorkerImportError(f"manifest: missing entry for {assignment_ref_rel!r}")
    assignment_sha = _compute_sha256(assignment_path)
    if assignment_sha != assignment_entry.get("sha256"):
        raise NativeWorkerImportError(
            f"assignment_sha_mismatch (manifest): on-disk {assignment_sha} vs entry {assignment_entry.get('sha256')!r}"
        )
    if assignment_sha != runner_entry.get("assignment_sha256"):
        raise NativeWorkerImportError(
            f"assignment_sha_mismatch (runner): on-disk {assignment_sha} vs runner "
            f"{runner_entry.get('assignment_sha256')!r}"
        )
    assignment = _load_json_or_fatal(assignment_path, "assignment")
    _validate_or_fatal(assignment, assignment_schema, "assignment")

    # --- cross-id consistency (FATAL) --------------------------------------
    wr_tg_id = worker_result.get("task_graph_id")
    rr_tg_id = runner_report.get("task_graph_id")
    mf_tg_id = manifest.get("task_graph_id")
    tg_tg_id = task_graph.get("task_graph_id")
    as_tg_id = assignment.get("task_graph_id")
    if not (wr_tg_id == rr_tg_id == mf_tg_id == tg_tg_id == as_tg_id):
        raise NativeWorkerImportError(
            "cross_id_mismatch: task_graph_id differs across worker_result / "
            f"runner_report / manifest / task_graph / assignment ({wr_tg_id!r} / "
            f"{rr_tg_id!r} / {mf_tg_id!r} / {tg_tg_id!r} / {as_tg_id!r})"
        )
    if worker_result.get("task_id") != runner_entry.get("task_id"):
        raise NativeWorkerImportError("cross_id_mismatch: worker_result.task_id != runner_entry.task_id")
    if worker_result.get("task_id") != assignment.get("task_id"):
        raise NativeWorkerImportError("cross_id_mismatch: worker_result.task_id != assignment.task_id")
    if worker_result.get("assignment_id") != assignment.get("assignment_id"):
        raise NativeWorkerImportError("cross_id_mismatch: worker_result.assignment_id != assignment.assignment_id")

    # All fatal checks passed; from here on we build a schema-valid report
    # and decide valid=true vs reportable invalid based on policy checks.

    # --- reportable policy checks ------------------------------------------
    checks: dict[str, Any] = {}
    findings: list[dict[str, Any]] = []

    checks["source_json_readable"] = _check_pass()
    checks["worker_result_schema_valid"] = _check_pass()
    checks["runner_report_schema_valid"] = _check_pass()
    checks["manifest_envelope_valid"] = _check_pass()
    checks["manifest_sha_bound"] = _check_pass()
    checks["task_graph_binding_valid"] = _check_pass()
    checks["assignment_binding_valid"] = _check_pass()
    checks["cross_id_consistent"] = _check_pass()
    checks["no_secret_attestation"] = _check_pass()
    checks["guard_flags_closed"] = _check_pass()

    # runner_entry status eligibility
    runner_status = runner_entry.get("status")
    eligible_statuses = {"prepared", "skipped_existing_idempotent"}
    if runner_status not in eligible_statuses:
        checks["runner_entry_eligible"] = _check_fail(
            f"runner_entry.status {runner_status!r} not in {sorted(eligible_statuses)}"
        )
        findings.append(
            _finding(
                "runner_entry_not_eligible",
                "error",
                f"runner status {runner_status!r} cannot back an import",
            )
        )
    else:
        checks["runner_entry_eligible"] = _check_pass()

    # cross-ref (string equality on base_ref/head_ref/base_sha)
    ref_mismatches: list[str] = []
    if worker_result.get("base_ref") != assignment.get("base_ref"):
        ref_mismatches.append("worker_result.base_ref != assignment.base_ref")
    if assignment.get("base_ref") != task_graph.get("base_ref"):
        ref_mismatches.append("assignment.base_ref != task_graph.base_ref")
    if worker_result.get("base_sha") != runner_report.get("base_sha"):
        ref_mismatches.append("worker_result.base_sha != runner_report.base_sha")
    if assignment.get("base_sha") != task_graph.get("base_sha"):
        ref_mismatches.append("assignment.base_sha != task_graph.base_sha")
    if worker_result.get("base_sha") != assignment.get("base_sha"):
        ref_mismatches.append("worker_result.base_sha != assignment.base_sha")
    wr_head_ref = worker_result.get("head_ref")
    re_branch = runner_entry.get("branch")
    as_branch = assignment.get("branch")
    if wr_head_ref != re_branch:
        ref_mismatches.append("worker_result.head_ref != runner_entry.branch")
    if re_branch != as_branch:
        ref_mismatches.append("runner_entry.branch != assignment.branch")
    if ref_mismatches:
        checks["cross_ref_consistent"] = _check_fail("; ".join(ref_mismatches))
        for msg in ref_mismatches:
            findings.append(_finding("cross_ref_mismatch", "error", msg))
    else:
        checks["cross_ref_consistent"] = _check_pass()

    # declared write set bound (worker_result == assignment == task_graph_tasks[task_id])
    wr_declared = worker_result.get("declared_write_set")
    as_declared = assignment.get("declared_write_set")
    tg_task_declared = None
    tg_tasks = task_graph.get("tasks")
    if isinstance(tg_tasks, list):
        for t in tg_tasks:
            if isinstance(t, dict) and t.get("task_id") == task_id:
                tg_task_declared = t.get("declared_write_set")
                break

    def _as_set(value: Any) -> frozenset[str] | None:
        if not isinstance(value, list):
            return None
        return frozenset(v for v in value if isinstance(v, str))

    wr_set = _as_set(wr_declared)
    as_set = _as_set(as_declared)
    tg_set = _as_set(tg_task_declared)
    if wr_set is None or as_set is None or tg_set is None or not (wr_set == as_set == tg_set):
        checks["declared_write_set_bound"] = _check_fail(
            "declared_write_set differs across worker_result / assignment / task_graph"
        )
        findings.append(
            _finding(
                "declared_write_set_mismatch",
                "error",
                "worker_result / assignment / task_graph declared_write_set must be set-equal",
            )
        )
    else:
        checks["declared_write_set_bound"] = _check_pass()

    # actual_subset_declared
    actual = worker_result.get("actual_changed_files")
    actual_set = _as_set(actual)
    if actual_set is None:
        checks["actual_subset_declared"] = _check_fail("actual_changed_files must be a list of strings")
        findings.append(
            _finding(
                "actual_changed_files_invalid",
                "error",
                "actual_changed_files must be a list of strings",
            )
        )
    elif wr_set is None or not actual_set.issubset(wr_set):
        checks["actual_subset_declared"] = _check_fail("actual_changed_files is not a subset of declared_write_set")
        findings.append(
            _finding(
                "actual_outside_declared",
                "error",
                "actual_changed_files contains paths outside declared_write_set",
            )
        )
    else:
        checks["actual_subset_declared"] = _check_pass()

    # actual_non_empty
    if actual_set is None or len(actual_set) == 0:
        checks["actual_non_empty"] = _check_fail(
            "actual_changed_files is empty; a real worker run must touch at least one file"
        )
        findings.append(
            _finding(
                "actual_changed_files_empty",
                "error",
                "empty actual_changed_files cannot back a real native worker output",
            )
        )
    else:
        checks["actual_non_empty"] = _check_pass()

    # known_gaps_empty
    known_gaps = worker_result.get("known_gaps")
    if isinstance(known_gaps, list) and len(known_gaps) > 0:
        checks["known_gaps_empty"] = _check_fail(
            f"known_gaps is non-empty ({len(known_gaps)} entr{'y' if len(known_gaps) == 1 else 'ies'})"
        )
        findings.append(
            _finding(
                "known_gaps_present",
                "error",
                "4.6-1 rejects non-empty known_gaps; downstream emits a finding in 4.6-2",
            )
        )
    else:
        checks["known_gaps_empty"] = _check_pass()

    # source_interface allowlist
    effective_allowlist: tuple[str, ...] = (
        tuple(source_interface_allowlist)
        if source_interface_allowlist is not None
        else DEFAULT_SOURCE_INTERFACE_ALLOWLIST
    )
    if source_interface not in effective_allowlist:
        checks["source_interface_allowed"] = _check_fail(
            f"source_interface {source_interface!r} not in effective allowlist {list(effective_allowlist)}"
        )
        findings.append(
            _finding(
                "source_interface_not_allowed",
                "error",
                "operator-configured allowlist excludes this source_interface",
            )
        )
    else:
        checks["source_interface_allowed"] = _check_pass()

    # source_interface ↔ worker_provider consistency
    worker = worker_result.get("worker")
    worker_provider = worker.get("provider") if isinstance(worker, dict) else None
    allowed_providers = _SOURCE_INTERFACE_PROVIDER_MAP.get(source_interface, frozenset())
    if not isinstance(worker_provider, str) or worker_provider not in allowed_providers:
        checks["source_interface_provider_consistent"] = _check_fail(
            f"source_interface {source_interface!r} expects worker_provider in "
            f"{sorted(allowed_providers)}, got {worker_provider!r}"
        )
        findings.append(
            _finding(
                "source_interface_provider_mismatch",
                "error",
                "operator-declared source_interface does not match worker.provider",
            )
        )
    else:
        checks["source_interface_provider_consistent"] = _check_pass()

    # canonical_integrated_path + source_integrated_hash_match
    integrated_path = _canonical_integrated_path(canonical_artifact_dir, task_id)
    integrated_resolved = integrated_path.resolve(strict=False)
    artifact_dir_resolved = canonical_artifact_dir.resolve(strict=False)
    try:
        integrated_resolved.relative_to(artifact_dir_resolved)
        canonical_under_artifact_dir = True
    except ValueError:
        canonical_under_artifact_dir = False
    if not canonical_under_artifact_dir:
        checks["canonical_integrated_path"] = _check_fail(
            f"canonical integrated path {integrated_resolved!s} escapes artifact_dir {artifact_dir_resolved!s}"
        )
        findings.append(
            _finding(
                "canonical_path_escape",
                "error",
                "canonical integrated path escapes the artifact tree",
            )
        )
    else:
        checks["canonical_integrated_path"] = _check_pass()

    source_sha = _compute_sha256(source_result_path)

    # decide whether we are valid (all pass) and only then atomically copy
    all_policy_pass = (
        checks["runner_entry_eligible"]["outcome"] == "pass"
        and checks["cross_ref_consistent"]["outcome"] == "pass"
        and checks["declared_write_set_bound"]["outcome"] == "pass"
        and checks["actual_subset_declared"]["outcome"] == "pass"
        and checks["actual_non_empty"]["outcome"] == "pass"
        and checks["known_gaps_empty"]["outcome"] == "pass"
        and checks["source_interface_allowed"]["outcome"] == "pass"
        and checks["source_interface_provider_consistent"]["outcome"] == "pass"
        and checks["canonical_integrated_path"]["outcome"] == "pass"
    )

    integrated_written_path: str | None = None
    integrated_sha: str | None = None
    hash_match_check_outcome = "pass"
    hash_match_message: str | None = None

    if not all_policy_pass:
        checks["source_integrated_hash_match"] = {
            "outcome": "skipped",
            "message": "no copy attempted because policy checks failed",
        }
    else:
        # Atomic copy with existing-different-hash refuse.
        if integrated_path.exists():
            existing_sha = _compute_sha256(integrated_path)
            if existing_sha != source_sha:
                checks["source_integrated_hash_match"] = _check_fail(
                    "existing integrated file has a different sha256; refusing overwrite"
                )
                findings.append(
                    _finding(
                        "existing_integrated_different_hash",
                        "error",
                        "an existing integrated worker_result.v1.json with a different "
                        "hash exists; atomic copy refused",
                    )
                )
                hash_match_check_outcome = "fail"
                hash_match_message = "existing different hash"
            else:
                # idempotent case: integrated matches source already
                integrated_written_path = str(integrated_path.resolve())
                integrated_sha = existing_sha
                checks["source_integrated_hash_match"] = _check_pass(
                    "idempotent: existing integrated file matches source sha256"
                )
        else:
            payload = source_result_path.read_bytes()
            _atomic_write_bytes(integrated_path, payload)
            integrated_sha = _compute_sha256(integrated_path)
            if integrated_sha != source_sha:
                # Tamper between read and write — extremely unlikely but
                # defensive: leave file but fail check.
                checks["source_integrated_hash_match"] = _check_fail("post-write integrated sha != source sha")
                findings.append(
                    _finding(
                        "post_write_hash_mismatch",
                        "error",
                        "integrated file hash does not equal source hash after atomic write",
                    )
                )
                hash_match_check_outcome = "fail"
                hash_match_message = "post-write hash mismatch"
            else:
                integrated_written_path = str(integrated_path.resolve())
                checks["source_integrated_hash_match"] = _check_pass("atomic copy succeeded, hashes match")

    # head_sha not git-recomputed: always a transparency warning
    findings.append(
        _finding(
            "head_sha_not_git_recomputed",
            "warning",
            "git object existence not verified in pure-import mode; verified only by cross-artifact declaration",
        )
    )

    # Recompute valid
    valid = _recompute_valid(checks)
    validation_status = "valid" if valid else "invalid"

    # Compose report. Codex iter-5 absorb: worker_status is OPTIONAL on
    # artifact_ref; for a non-eligible runner_status we OMIT the field
    # rather than synthesizing a misleading "prepared" placeholder. The
    # fail finding on runner_entry_eligible already records the truth.
    runner_report_ref: dict[str, Any] = {
        "path": str(runner_report_path.resolve()),
        "sha256": _compute_sha256(runner_report_path),
    }
    if isinstance(runner_status, str) and runner_status in {"prepared", "skipped_existing_idempotent"}:
        runner_report_ref["worker_status"] = runner_status

    manifest_ref = {
        "path": str(manifest_path.resolve()),
        "sha256": manifest_sha,
    }
    task_graph_ref = {
        "path": str(task_graph_path.resolve()),
        "sha256": task_graph_sha,
    }
    assignment_ref = {
        "path": str(assignment_path.resolve()),
        "sha256": assignment_sha,
    }

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "import_mode": IMPORT_MODE,
        "task_graph_id": wr_tg_id,
        "task_id": task_id,
        "assignment_id": worker_result.get("assignment_id"),
        "source_result_path": str(source_result_path),
        "source_result_sha256": source_sha,
        "source_interface": source_interface,
        "worker_provider": worker_provider if isinstance(worker_provider, str) else "local",
        "worker_agent_id": worker.get("agent_id") if isinstance(worker, dict) else "unknown",
        "worker_session_id": worker.get("session_id") if isinstance(worker, dict) else "unknown",
        "imported_at": imported_at,
        "validation_status": validation_status,
        "valid": valid,
        "checks": checks,
        "validation_findings": findings,
        "integrated_worker_result_path": integrated_written_path if valid else None,
        "integrated_worker_result_sha256": integrated_sha if valid else None,
        "runner_report_ref": runner_report_ref,
        "manifest_ref": manifest_ref,
        "task_graph_ref": task_graph_ref,
        "assignment_ref": assignment_ref,
        "effective_source_interface_allowlist": list(effective_allowlist),
        "guard_flags": {
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution": False,
        },
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
        "execution_performed_by_ao_kernel": False,
        "ai_output_release_authority": False,
    }

    # Suppress an unused-variable lint complaint about hash_match_*
    _ = (hash_match_check_outcome, hash_match_message)

    # Schema-validate the report itself before returning (Codex contract:
    # the importer always emits a schema-valid report).
    _validate_or_fatal(report, import_report_schema, "import_report")

    return report


# ---------------------------------------------------------------------------
# Public API: verify_import_binding
# ---------------------------------------------------------------------------


def verify_import_binding(
    import_report: Mapping[str, Any],
    *,
    import_report_schema: Mapping[str, Any],
    worker_result_schema: Mapping[str, Any] | None = None,
    runner_report_schema: Mapping[str, Any] | None = None,
    task_graph_schema: Mapping[str, Any] | None = None,
    assignment_schema: Mapping[str, Any] | None = None,
) -> None:
    """Re-verify a previously emitted import_report against on-disk state.

    Codex iter-5 absorb (post-impl REVISE): when the four artifact
    schemas are provided, this function replays the full build-side
    binding chain — manifest envelope, manifest/task_graph/assignment
    sha equality with the report's refs AND with each other, runner
    entry status, and the cross-id chain — from on-disk files. The
    valid flag is always recomputed; source/integrated sha equality is
    enforced; guard/authority pins are re-checked. Backward-compatible:
    callers that pass only ``import_report_schema`` get the legacy
    surface (schema + valid recompute + source/integrated sha +
    canonical-under-artifact-dir + guard/authority).
    """

    _validate_or_fatal(import_report, import_report_schema, "import_report")

    checks = import_report.get("checks")
    if not isinstance(checks, Mapping):  # pragma: no cover - schema covers this
        raise NativeWorkerImportError("verify: checks must be an object")
    recomputed = _recompute_valid(checks)
    declared_valid = import_report.get("valid")
    if declared_valid is not recomputed:
        raise NativeWorkerImportError(
            f"verify: forged valid flag (declared {declared_valid!r}, recomputed {recomputed!r})"
        )

    # source sha re-compute (when file still on disk)
    source_path = Path(cast(str, import_report.get("source_result_path", "")))
    if source_path.exists():
        recomputed_source_sha = _compute_sha256(source_path)
        if recomputed_source_sha != import_report.get("source_result_sha256"):
            raise NativeWorkerImportError(
                "verify: source_result file has changed since import "
                f"(recomputed {recomputed_source_sha} != reported "
                f"{import_report.get('source_result_sha256')!r})"
            )

    # integrated sha re-compute (only when valid)
    if recomputed:
        integrated_str = import_report.get("integrated_worker_result_path")
        if not isinstance(integrated_str, str) or not integrated_str:
            raise NativeWorkerImportError("verify: valid=true requires integrated_worker_result_path")
        integrated_path = Path(integrated_str)
        if not integrated_path.exists():
            raise NativeWorkerImportError(f"verify: integrated file missing at {integrated_path!s}")
        recomputed_integrated_sha = _compute_sha256(integrated_path)
        if recomputed_integrated_sha != import_report.get("integrated_worker_result_sha256"):
            raise NativeWorkerImportError(
                "verify: integrated file has changed since import "
                f"(recomputed {recomputed_integrated_sha} != reported "
                f"{import_report.get('integrated_worker_result_sha256')!r})"
            )
        # Codex iter-5: source/integrated sha MUST be equal when valid.
        if import_report.get("source_result_sha256") != import_report.get("integrated_worker_result_sha256"):
            raise NativeWorkerImportError(
                "verify: source/integrated sha mismatch in a valid report (integrated copy must byte-equal source)"
            )
        # canonical path inside artifact tree
        manifest_ref = import_report.get("manifest_ref")
        if not isinstance(manifest_ref, Mapping):  # pragma: no cover - schema covers this
            raise NativeWorkerImportError("verify: manifest_ref missing")
        manifest_path_str = manifest_ref.get("path")
        if not isinstance(manifest_path_str, str):  # pragma: no cover - schema covers this
            raise NativeWorkerImportError("verify: manifest_ref.path missing")
        artifact_dir = Path(manifest_path_str).parent.resolve()
        try:
            integrated_path.resolve(strict=False).relative_to(artifact_dir)
        except ValueError as exc:
            raise NativeWorkerImportError(f"verify: integrated path escapes artifact tree {artifact_dir!s}") from exc

    # guard flags + authority pins
    guard_flags = import_report.get("guard_flags")
    if not isinstance(guard_flags, Mapping):  # pragma: no cover - schema covers this
        raise NativeWorkerImportError("verify: guard_flags missing")
    for flag_name in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        if guard_flags.get(flag_name) is not False:
            raise NativeWorkerImportError(f"verify: guard_flags.{flag_name} must be const false")
    if import_report.get("register_authority") != "evidence_record_only":
        raise NativeWorkerImportError("verify: register_authority drift")
    if import_report.get("github_write_authorized") is not False:
        raise NativeWorkerImportError("verify: github_write_authorized drift")
    if import_report.get("execution_performed_by_ao_kernel") is not False:
        raise NativeWorkerImportError("verify: execution_performed_by_ao_kernel drift")
    if import_report.get("ai_output_release_authority") is not False:
        raise NativeWorkerImportError("verify: ai_output_release_authority drift")

    # Codex iter-5 absorb: full cross-bind replay from disk.
    # Only run when callers supplied the four artifact schemas — keeps
    # the legacy surface backward-compatible for the tests that exercise
    # only the lightweight (schema + sha + guard) path.
    if (
        worker_result_schema is None
        or runner_report_schema is None
        or task_graph_schema is None
        or assignment_schema is None
    ):
        return

    runner_ref = import_report.get("runner_report_ref")
    manifest_ref = import_report.get("manifest_ref")
    task_graph_ref = import_report.get("task_graph_ref")
    assignment_ref = import_report.get("assignment_ref")
    if not (
        isinstance(runner_ref, Mapping)
        and isinstance(manifest_ref, Mapping)
        and isinstance(task_graph_ref, Mapping)
        and isinstance(assignment_ref, Mapping)
    ):  # pragma: no cover - schema covers this
        raise NativeWorkerImportError("verify: artifact refs missing or malformed")

    # 1. runner_report
    runner_report_disk_path = Path(cast(str, runner_ref.get("path", "")))
    if not runner_report_disk_path.exists():
        raise NativeWorkerImportError(f"verify: runner_report file missing at {runner_report_disk_path!s}")
    runner_sha = _compute_sha256(runner_report_disk_path)
    if runner_sha != runner_ref.get("sha256"):
        raise NativeWorkerImportError(
            f"verify: runner_report sha drift (disk {runner_sha} != ref {runner_ref.get('sha256')!r})"
        )
    runner_disk = _load_json_or_fatal(runner_report_disk_path, "verify.runner_report")
    _validate_or_fatal(runner_disk, runner_report_schema, "verify.runner_report")

    # 2. manifest
    manifest_disk_path = Path(cast(str, manifest_ref.get("path", "")))
    if not manifest_disk_path.exists():
        raise NativeWorkerImportError(f"verify: manifest file missing at {manifest_disk_path!s}")
    manifest_sha = _compute_sha256(manifest_disk_path)
    if manifest_sha != manifest_ref.get("sha256"):
        raise NativeWorkerImportError(
            f"verify: manifest sha drift (disk {manifest_sha} != ref {manifest_ref.get('sha256')!r})"
        )
    if manifest_sha != runner_disk.get("manifest_sha256"):
        raise NativeWorkerImportError(
            "verify: manifest sha != runner_report.manifest_sha256 "
            f"(disk {manifest_sha} != runner {runner_disk.get('manifest_sha256')!r})"
        )
    manifest_disk = _load_json_or_fatal(manifest_disk_path, "verify.manifest")
    _validate_manifest_envelope_or_fatal(manifest_disk, manifest_disk_path)

    # 3. task_graph
    task_graph_disk_path = Path(cast(str, task_graph_ref.get("path", "")))
    if not task_graph_disk_path.exists():
        raise NativeWorkerImportError(f"verify: task_graph file missing at {task_graph_disk_path!s}")
    task_graph_sha = _compute_sha256(task_graph_disk_path)
    if task_graph_sha != task_graph_ref.get("sha256"):
        raise NativeWorkerImportError(
            f"verify: task_graph sha drift (disk {task_graph_sha} != ref {task_graph_ref.get('sha256')!r})"
        )
    tg_manifest_entry = _find_manifest_entry(manifest_disk, "task_graph.v1.json")
    if tg_manifest_entry is None or tg_manifest_entry.get("sha256") != task_graph_sha:
        raise NativeWorkerImportError("verify: task_graph sha != manifest entry")
    task_graph_disk = _load_json_or_fatal(task_graph_disk_path, "verify.task_graph")
    _validate_or_fatal(task_graph_disk, task_graph_schema, "verify.task_graph")

    # 4. assignment
    assignment_disk_path = Path(cast(str, assignment_ref.get("path", "")))
    if not assignment_disk_path.exists():
        raise NativeWorkerImportError(f"verify: assignment file missing at {assignment_disk_path!s}")
    assignment_sha = _compute_sha256(assignment_disk_path)
    if assignment_sha != assignment_ref.get("sha256"):
        raise NativeWorkerImportError(
            f"verify: assignment sha drift (disk {assignment_sha} != ref {assignment_ref.get('sha256')!r})"
        )
    # manifest entry by basename
    assignment_basename = assignment_disk_path.name
    asg_manifest_entry = _find_manifest_entry(manifest_disk, assignment_basename)
    if asg_manifest_entry is None or asg_manifest_entry.get("sha256") != assignment_sha:
        raise NativeWorkerImportError("verify: assignment sha != manifest entry")
    assignment_disk = _load_json_or_fatal(assignment_disk_path, "verify.assignment")
    _validate_or_fatal(assignment_disk, assignment_schema, "verify.assignment")

    # 5. runner entry binding to task_id + assignment sha
    report_task_id = import_report.get("task_id")
    if not isinstance(report_task_id, str):  # pragma: no cover - schema covers this
        raise NativeWorkerImportError("verify: import_report.task_id missing")
    runner_entry = _find_runner_entry(runner_disk, report_task_id)
    if runner_entry is None:
        raise NativeWorkerImportError(f"verify: runner_report.workers[] has no entry for task_id {report_task_id!r}")
    if runner_entry.get("assignment_sha256") != assignment_sha:
        raise NativeWorkerImportError("verify: runner_entry.assignment_sha256 != on-disk assignment sha")

    # 6. cross-id chain (replay of the build-side fatal check)
    report_task_graph_id = import_report.get("task_graph_id")
    if not (
        report_task_graph_id
        == runner_disk.get("task_graph_id")
        == manifest_disk.get("task_graph_id")
        == task_graph_disk.get("task_graph_id")
        == assignment_disk.get("task_graph_id")
    ):
        raise NativeWorkerImportError("verify: cross_id_mismatch on task_graph_id across the artifact chain")
    if report_task_id != assignment_disk.get("task_id"):
        raise NativeWorkerImportError("verify: cross_id_mismatch on task_id between report and assignment")
    if import_report.get("assignment_id") != assignment_disk.get("assignment_id"):
        raise NativeWorkerImportError("verify: cross_id_mismatch on assignment_id between report and assignment")

    # 7. Codex iter-6 absorb: replay the build-side worker_result semantic
    # chain from the integrated copy. Only relevant when valid=true (an
    # invalid report has no integrated copy by contract).
    if not recomputed:
        return

    integrated_str = cast(str, import_report["integrated_worker_result_path"])
    integrated_disk_path = Path(integrated_str)
    worker_result_disk = _load_json_or_fatal(integrated_disk_path, "verify.worker_result")
    _validate_or_fatal(worker_result_disk, worker_result_schema, "verify.worker_result")

    # 8. Integrated path MUST equal the canonical exact path (not merely
    # "under artifact_dir"). An attacker who can drop a file under the
    # tree but at a different sub-path must not pass verification.
    artifact_dir_disk = manifest_disk_path.parent.resolve()
    canonical = _canonical_integrated_path(artifact_dir_disk, report_task_id).resolve(strict=False)
    if integrated_disk_path.resolve(strict=False) != canonical:
        raise NativeWorkerImportError(f"verify: integrated path {integrated_disk_path!s} != canonical {canonical!s}")

    # 9. cross-id replay across worker_result content
    if worker_result_disk.get("task_graph_id") != report_task_graph_id:
        raise NativeWorkerImportError("verify: worker_result.task_graph_id != report.task_graph_id")
    if worker_result_disk.get("task_id") != report_task_id:
        raise NativeWorkerImportError("verify: worker_result.task_id != report.task_id")
    if worker_result_disk.get("assignment_id") != import_report.get("assignment_id"):
        raise NativeWorkerImportError("verify: worker_result.assignment_id != report.assignment_id")

    # 10. cross-ref replay (base_ref/base_sha/head_ref/branch chain)
    if not (worker_result_disk.get("base_ref") == assignment_disk.get("base_ref") == task_graph_disk.get("base_ref")):
        raise NativeWorkerImportError("verify: base_ref differs across worker_result / assignment / task_graph")
    if not (
        worker_result_disk.get("base_sha")
        == runner_disk.get("base_sha")
        == assignment_disk.get("base_sha")
        == task_graph_disk.get("base_sha")
    ):
        raise NativeWorkerImportError(
            "verify: base_sha differs across worker_result / runner_report / assignment / task_graph"
        )
    if not (worker_result_disk.get("head_ref") == runner_entry.get("branch") == assignment_disk.get("branch")):
        raise NativeWorkerImportError(
            "verify: head_ref/branch differs across worker_result / runner_entry / assignment"
        )

    # 11. declared_write_set set-equality replay
    def _as_set_verify(value: Any) -> frozenset[str] | None:
        if not isinstance(value, list):
            return None
        return frozenset(v for v in value if isinstance(v, str))

    wr_set = _as_set_verify(worker_result_disk.get("declared_write_set"))
    as_set = _as_set_verify(assignment_disk.get("declared_write_set"))
    tg_task_declared: Any = None
    tg_tasks_disk = task_graph_disk.get("tasks")
    if isinstance(tg_tasks_disk, list):
        for t in tg_tasks_disk:
            if isinstance(t, dict) and t.get("task_id") == report_task_id:
                tg_task_declared = t.get("declared_write_set")
                break
    tg_set = _as_set_verify(tg_task_declared)
    if wr_set is None or as_set is None or tg_set is None or not (wr_set == as_set == tg_set):
        raise NativeWorkerImportError(
            "verify: declared_write_set differs across worker_result / assignment / task_graph"
        )

    # 12. actual_changed_files subset + non-empty + known_gaps empty
    actual_set = _as_set_verify(worker_result_disk.get("actual_changed_files"))
    if actual_set is None or not actual_set.issubset(wr_set):
        raise NativeWorkerImportError("verify: actual_changed_files is not a subset of declared_write_set")
    if len(actual_set) == 0:
        raise NativeWorkerImportError("verify: actual_changed_files is empty")
    known_gaps = worker_result_disk.get("known_gaps")
    if isinstance(known_gaps, list) and len(known_gaps) > 0:
        raise NativeWorkerImportError("verify: worker_result.known_gaps is non-empty (4.6-1 invariant)")

    # 13. Codex iter-7 absorb: replay the three remaining policy invariants
    # that build enforces (runner status eligibility, source_interface in
    # effective allowlist, source_interface ↔ worker_provider). A forged
    # all-pass report whose disk artifacts are coherent but whose policy
    # context drifted must NOT pass verify.
    eligible_statuses = {"prepared", "skipped_existing_idempotent"}
    disk_runner_status = runner_entry.get("status")
    if disk_runner_status not in eligible_statuses:
        raise NativeWorkerImportError(
            f"verify: runner_entry.status {disk_runner_status!r} is not in {sorted(eligible_statuses)}"
        )
    runner_ref_status = runner_ref.get("worker_status")
    if runner_ref_status is not None and runner_ref_status != disk_runner_status:
        raise NativeWorkerImportError(
            f"verify: runner_report_ref.worker_status {runner_ref_status!r} "
            f"!= on-disk runner_entry.status {disk_runner_status!r}"
        )

    effective = import_report.get("effective_source_interface_allowlist")
    if not isinstance(effective, list) or not effective:  # pragma: no cover - schema covers this
        raise NativeWorkerImportError("verify: effective_source_interface_allowlist missing")
    report_source_interface = import_report.get("source_interface")
    if report_source_interface not in effective:
        raise NativeWorkerImportError(
            f"verify: source_interface {report_source_interface!r} not in "
            f"effective_source_interface_allowlist {list(effective)}"
        )

    if not isinstance(report_source_interface, str):  # pragma: no cover - schema covers this
        raise NativeWorkerImportError("verify: source_interface missing")
    allowed_providers = _SOURCE_INTERFACE_PROVIDER_MAP.get(report_source_interface, frozenset())
    report_worker_provider = import_report.get("worker_provider")
    if report_worker_provider not in allowed_providers:
        raise NativeWorkerImportError(
            f"verify: source_interface {report_source_interface!r} expects worker_provider "
            f"in {sorted(allowed_providers)}, got {report_worker_provider!r}"
        )
    disk_worker = worker_result_disk.get("worker")
    disk_worker_provider = disk_worker.get("provider") if isinstance(disk_worker, dict) else None
    if disk_worker_provider != report_worker_provider:
        raise NativeWorkerImportError(
            f"verify: import_report.worker_provider {report_worker_provider!r} "
            f"!= on-disk worker_result.worker.provider {disk_worker_provider!r}"
        )
