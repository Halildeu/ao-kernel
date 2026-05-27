"""AO-MA-7 verifier (v1 — deterministic checks; NO LLM call).

Consumes the inputs supplied by the operator + AO-MA-3/4/5/6 artifacts
and produces a schema-valid ``verification_report.v1.json`` for the
AO-MA-5 integrator to consume.

**v1 scope (Codex iter-1 AGREE absorbed):**

- **GPP guard check** — manifest + task_graph + worker_result +
  optional review_verdict + gpp_status.v1.json guard flags
- **Secret scan (metadata-only)** — regex pattern set over AO-MA artifact
  JSON content; ``no_secret_attestation.secrets_recorded`` cross-check.
  **Changed source file contents are NOT scanned in v1** (explicit
  ``secret_scan.detail`` documents this).
- **Diff scope static check** — ``set(worker_result.actual_changed_files)
  ⊆ set(worker_result.declared_write_set)`` AND
  ``worker_result.declared_write_set == task_graph.tasks[task_id].declared_write_set``
  (inflation defense)
- **Artifact hashes** — ``{path, sha256}`` H1 format for inputs consulted

**HARD RULE pin (Codex iter-1 absorbed):**

- No LLM execution surface (static AST + text tests enforce no imports
  or call patterns)
- No ``subprocess`` import (all checks deterministic Python)
- No GitHub write, no PR/GitHub fetch
- No edits to AO-MA-5/6 modules
- ``release_authority`` not in ``verification_report.v1`` schema; verifier
  is not authority
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.orchestration.verification_report_writer import (
    VerificationReportWriter,
    VerificationReportWriterError,
)

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"

_TASK_GRAPH_SCHEMA_NAME = "ao-ma-task-graph.schema.v1.json"
_WORKER_RESULT_SCHEMA_NAME = "ao-ma-worker-result.schema.v1.json"
_REVIEW_VERDICT_SCHEMA_NAME = "ao-ma-review-verdict.schema.v1.json"

# Codex iter-1 must_close #5: deterministic check names recorded under
# ``commands[]`` so integrator's ``commands[].outcome == "fail"``
# predicate sees a meaningful name.
_CHECK_SCHEMA_VALIDATION = "schema_validation"
_CHECK_GPP_GUARD = "gpp_guard_check"
_CHECK_SECRET_SCAN = "metadata_secret_scan"
_CHECK_DIFF_SCOPE = "diff_scope_static_check"
_CHECK_ARTIFACT_HASH = "artifact_hashing"

# Codex iter-1 absorb (S1): regex pattern set scanned over AO-MA artifact
# JSON content (metadata only; NOT source file content in v1).
_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("aws_access_key_id", r"AKIA[0-9A-Z]{16}"),
    ("aws_secret_access_key", r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}"),
    ("github_classic_token", r"ghp_[A-Za-z0-9]{36,}"),
    ("github_oauth_token", r"gho_[A-Za-z0-9]{36,}"),
    ("github_pat", r"github_pat_[A-Za-z0-9_]{82}"),
    ("openai_or_anthropic_token", r"sk-[A-Za-z0-9_-]{32,}"),
    ("anthropic_token", r"sk-ant-[A-Za-z0-9_-]{40,}"),
    ("xai_token", r"xai-[A-Za-z0-9]{40,}"),
    ("google_api_key", r"AIza[0-9A-Za-z_-]{35}"),
    ("private_key_block", r"-----BEGIN (RSA|DSA|EC|OPENSSH|PRIVATE) ?(PRIVATE )?KEY-----"),
    ("pgp_private_key_block", r"-----BEGIN PGP PRIVATE KEY BLOCK-----"),
)

# Codex iter-1 must_close #1: regex set above explicitly avoids matching
# AO-MA artifact's own SHA256 / git SHA hex strings:
#   - sha256:[0-9a-f]{64}  (lowercase hex, prefix-anchored, 64 chars)
#   - 40-char hex git SHA  (no prefix, but length 40 ≠ AKIA/sk-/etc.)
# To rule out false positives at runtime, _check_secret_scan strips
# these patterns before regex matching.
_FALSE_POSITIVE_STRIP_PATTERNS: tuple[str, ...] = (
    r"sha256:[0-9a-f]{64}",
    r"\b[0-9a-f]{40}\b",  # git SHA
)

Provider = Literal["openai", "anthropic", "minimax", "google", "local", "tool"]
CheckOutcome = Literal["pass", "fail", "skipped"]


class VerifierError(RuntimeError):
    """Raised for I/O / schema-load / trust-boundary failures."""


@dataclass
class VerificationInputs:
    manifest_path: Path
    task_id: str
    worker_result_paths: dict[str, Path]
    verifier_agent_id: str
    verifier_provider: Provider
    verifier_session_id: str
    review_verdict_path: Path | None = None
    gpp_status_path: Path | None = None


@dataclass
class VerificationResult:
    overall_pass: bool
    report: dict[str, Any]
    diagnostics: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)


def _load_schema(name: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerifierError(f"failed to load bundled schema {name!r}: {exc}") from exc


def _validate_schema(payload: dict[str, Any], schema_name: str, source: Path) -> None:
    schema = _load_schema(schema_name)
    try:
        Draft202012Validator(schema).validate(payload)
    except ValidationError as exc:
        raise VerifierError(
            f"{source.name} failed schema {schema_name!r}: {exc.message} (at {list(exc.absolute_path)})"
        ) from exc


def _sha256_of(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _check_gpp_guards(
    *,
    manifest: dict[str, Any],
    task_graph: dict[str, Any],
    worker_result: dict[str, Any],
    review_verdict: dict[str, Any] | None,
    gpp_status: dict[str, Any] | None,
) -> tuple[CheckOutcome, list[str]]:
    """Codex iter-1 must_close #3: GPP guards read from all 5 sources.

    Returns ``(outcome, failed_checks_entries)``. Each violation gets
    its own ``failed_checks[]`` string so audit lists the exact source +
    flag.
    """

    violations: list[str] = []
    for required in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        if manifest.get("guard_flags", {}).get(required) is not False:
            violations.append(f"gpp_guard.manifest.{required}_not_false")
        if task_graph.get("guard_flags", {}).get(required) is not False:
            violations.append(f"gpp_guard.task_graph.{required}_not_false")
        if worker_result.get("guard_flags", {}).get(required) is not False:
            violations.append(f"gpp_guard.worker_result.{required}_not_false")
        if review_verdict is not None and review_verdict.get("guard_flags", {}).get(required) is not False:
            violations.append(f"gpp_guard.review_verdict.{required}_not_false")
    # gpp_status: check current_wp allowed flags AND root-level allowed flags
    if gpp_status is not None:
        # Common GPP guard names mapped from the gpp_status authority
        gpp_allowed_keys = {
            "support_widening_allowed": "support_widening",
            "production_platform_claim_allowed": "production_platform_claim",
            "live_adapter_execution_allowed": "live_adapter_execution",
        }
        # Check root + current_wp + any nested authority block
        roots: list[dict[str, Any]] = [gpp_status]
        if isinstance(gpp_status.get("current_wp"), dict):
            roots.append(gpp_status["current_wp"])
        for blob in roots:
            for allowed_key, guard_name in gpp_allowed_keys.items():
                value = blob.get(allowed_key)
                if value is True:  # Only True is a violation; missing/false OK
                    violations.append(f"gpp_guard.gpp_status.{allowed_key}_true")
    outcome: CheckOutcome = "fail" if violations else "pass"
    return outcome, violations


def _strip_false_positives(text: str) -> str:
    """Strip AO-MA's own sha256:/git SHA hex strings so the secret regex set
    does not flag them. Codex iter-1 must_close #1 defensive pattern.
    """

    cleaned = text
    for pat in _FALSE_POSITIVE_STRIP_PATTERNS:
        cleaned = re.sub(pat, "", cleaned)
    return cleaned


def _check_secret_scan(
    *,
    worker_result: dict[str, Any],
    review_verdict: dict[str, Any] | None,
    artifact_payloads: dict[str, dict[str, Any]],
) -> tuple[CheckOutcome, list[str], str]:
    """Metadata-only secret scan. Codex iter-1 must_close #1: scope statement explicit.

    Returns ``(outcome, failed_checks_entries, detail_text)``.
    """

    detail = (
        "AO-MA JSON artifacts / metadata scanned (manifest + task_graph + worker_result"
        " + optional review_verdict); changed source file contents were NOT scanned in v1"
    )
    violations: list[str] = []
    # 1. no_secret_attestation cross-check (worker_result + review_verdict)
    if worker_result.get("no_secret_attestation", {}).get("secrets_recorded") is True:
        violations.append("secret_scan.worker_result.secrets_recorded_true")
    if review_verdict is not None and review_verdict.get("no_secret_attestation", {}).get("secrets_recorded") is True:
        violations.append("secret_scan.review_verdict.secrets_recorded_true")
    # 2. Regex scan over each artifact's full JSON text
    for name, payload in artifact_payloads.items():
        text = json.dumps(payload, sort_keys=True)
        cleaned = _strip_false_positives(text)
        for pat_name, pattern in _SECRET_PATTERNS:
            if re.search(pattern, cleaned):
                violations.append(f"secret_scan.{name}.{pat_name}_match")
    outcome: CheckOutcome = "fail" if violations else "pass"
    return outcome, violations, detail


def _check_diff_scope(
    *,
    worker_result: dict[str, Any],
    task_graph: dict[str, Any],
    task_id: str,
) -> tuple[CheckOutcome, list[str]]:
    """Codex iter-1 must_close #2: subset + task_graph cross-ref (inflation defense)."""

    violations: list[str] = []
    task = next((t for t in task_graph.get("tasks", []) if t.get("task_id") == task_id), None)
    if task is None:
        violations.append(f"diff_scope.task_id_{task_id}_not_in_task_graph")
        outcome: CheckOutcome = "fail"
        return outcome, violations
    task_declared = set(task.get("declared_write_set", []))
    worker_declared = set(worker_result.get("declared_write_set", []))
    if task_declared != worker_declared:
        violations.append(
            f"diff_scope.worker_declared_set_mismatch_with_task_graph "
            f"(inflation_defense: worker={sorted(worker_declared)}, task={sorted(task_declared)})"
        )
    actual = set(worker_result.get("actual_changed_files", []))
    extras = actual - worker_declared
    if extras:
        violations.append(f"diff_scope.actual_outside_declared: {sorted(extras)}")
    outcome2: CheckOutcome = "fail" if violations else "pass"
    return outcome2, violations


def _compute_artifact_hashes(consulted_paths: dict[str, Path], *, base_dir: Path) -> list[dict[str, str]]:
    """Codex iter-1 must_close #4: H1 format {path, sha256} only. No role.

    Paths are recorded relative to ``base_dir`` so the schema's path
    constraint (``not pattern (^/|\\.\\.)``) is satisfied. Paths that
    would escape ``base_dir`` are dropped fail-closed (no leak of
    outside-tree paths into the verification report).
    """

    hashes: list[dict[str, str]] = []
    resolved_base = base_dir.resolve()
    for _label, path in consulted_paths.items():
        if not path.exists():
            continue
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(resolved_base)
        except ValueError:
            # Path escapes base_dir; fail-closed (skip this entry).
            continue
        rel_str = rel.as_posix()
        if not rel_str or rel_str.startswith("/") or ".." in rel_str.split("/"):
            continue
        hashes.append({"path": rel_str, "sha256": _sha256_of(resolved)})
    # Stable order by path
    hashes.sort(key=lambda d: d["path"])
    return hashes


@dataclass
class Verifier:
    """Pure-data verifier (Codex iter-1 L1 + A2): deterministic checks; no LLM."""

    repo_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.repo_root, Path):
            raise VerifierError("repo_root must be a Path instance")
        self.repo_root = self.repo_root.resolve()

    def verify(self, inputs: VerificationInputs, *, emit: bool = True) -> VerificationResult:
        """Read artifacts → 4 modular checks → emit report → return result."""

        # 1. Load + validate manifest
        manifest = self._load_json(inputs.manifest_path)
        task_graph_id = manifest.get("task_graph_id")
        if not isinstance(task_graph_id, str):
            raise VerifierError(f"{inputs.manifest_path.name}: task_graph_id missing or non-string")

        # 2. Load + validate task_graph
        task_graph_path = inputs.manifest_path.parent / "task_graph.v1.json"
        task_graph = self._load_json(task_graph_path)
        _validate_schema(task_graph, _TASK_GRAPH_SCHEMA_NAME, task_graph_path)
        if task_graph.get("task_graph_id") != task_graph_id:
            raise VerifierError("task_graph task_graph_id != manifest task_graph_id; split-brain artifact set")

        # 3. Load + validate worker_result
        wr_path = inputs.worker_result_paths.get(inputs.task_id)
        if wr_path is None:
            raise VerifierError(f"--worker-result mapping missing entry for task_id {inputs.task_id!r}")
        worker_result = self._load_json(wr_path)
        _validate_schema(worker_result, _WORKER_RESULT_SCHEMA_NAME, wr_path)
        if worker_result.get("task_graph_id") != task_graph_id:
            raise VerifierError(f"{wr_path.name} task_graph_id mismatch with manifest")
        if worker_result.get("task_id") != inputs.task_id:
            raise VerifierError(f"{wr_path.name} payload task_id mismatch with --task-id")

        # Cross-provider check (Codex iter-1 #6 — same-provider audit)
        implementer_provider = (worker_result.get("worker") or {}).get("provider")
        if implementer_provider == inputs.verifier_provider:
            raise VerifierError(
                f"verifier.provider {inputs.verifier_provider!r} matches worker_result implementer "
                f"provider {implementer_provider!r}; verifier audit requires distinct provider "
                f"(or set --verifier-provider tool for no-LLM verifier)"
            )

        # 4. Optional review_verdict
        review_verdict: dict[str, Any] | None = None
        if inputs.review_verdict_path is not None:
            review_verdict = self._load_json(inputs.review_verdict_path)
            _validate_schema(review_verdict, _REVIEW_VERDICT_SCHEMA_NAME, inputs.review_verdict_path)
            if review_verdict.get("task_graph_id") != task_graph_id:
                raise VerifierError("review_verdict task_graph_id mismatch")

        # 5. Optional gpp_status
        gpp_status: dict[str, Any] | None = None
        gpp_status_path: Path | None = inputs.gpp_status_path
        if gpp_status_path is None:
            default_path = self.repo_root / ".claude" / "plans" / "gpp_status.v1.json"
            if default_path.exists():
                gpp_status_path = default_path
        if gpp_status_path is not None and gpp_status_path.exists():
            gpp_status = self._load_json(gpp_status_path)

        # 6. Run 4 deterministic checks
        commands: list[dict[str, Any]] = []
        failed_checks: list[str] = []

        # schema_validation pass (we validated above; if we got here, it's pass)
        commands.append({"command": _CHECK_SCHEMA_VALIDATION, "outcome": "pass"})

        # gpp_guard_check
        gpp_outcome, gpp_violations = _check_gpp_guards(
            manifest=manifest,
            task_graph=task_graph,
            worker_result=worker_result,
            review_verdict=review_verdict,
            gpp_status=gpp_status,
        )
        commands.append({"command": _CHECK_GPP_GUARD, "outcome": gpp_outcome})
        failed_checks.extend(gpp_violations)

        # metadata_secret_scan
        artifact_payloads: dict[str, dict[str, Any]] = {
            "manifest": manifest,
            "task_graph": task_graph,
            "worker_result": worker_result,
        }
        if review_verdict is not None:
            artifact_payloads["review_verdict"] = review_verdict
        secret_outcome, secret_violations, secret_detail = _check_secret_scan(
            worker_result=worker_result,
            review_verdict=review_verdict,
            artifact_payloads=artifact_payloads,
        )
        commands.append({"command": _CHECK_SECRET_SCAN, "outcome": secret_outcome})
        failed_checks.extend(secret_violations)

        # diff_scope_static_check
        scope_outcome, scope_violations = _check_diff_scope(
            worker_result=worker_result,
            task_graph=task_graph,
            task_id=inputs.task_id,
        )
        commands.append({"command": _CHECK_DIFF_SCOPE, "outcome": scope_outcome})
        failed_checks.extend(scope_violations)

        # artifact_hashing — H1 format
        consulted = {
            "manifest": inputs.manifest_path,
            "task_graph": task_graph_path,
            "worker_result": wr_path,
        }
        if inputs.review_verdict_path is not None:
            consulted["review_verdict"] = inputs.review_verdict_path
        if gpp_status_path is not None:
            consulted["gpp_status"] = gpp_status_path
        artifact_hashes = _compute_artifact_hashes(consulted, base_dir=inputs.manifest_path.parent)
        commands.append({"command": _CHECK_ARTIFACT_HASH, "outcome": "pass"})

        # 7. Build report payload
        scope_check_passed = scope_outcome == "pass"
        secret_scan_passed = secret_outcome == "pass"
        verifier_block = {
            "agent_id": inputs.verifier_agent_id,
            "agent_type": "verifier",
            "provider": inputs.verifier_provider,
            "session_id": inputs.verifier_session_id,
        }
        report: dict[str, Any] = {
            "schema_version": "ao-ma-verification-report.v1",
            "task_graph_id": task_graph_id,
            "verified_task_ids": [inputs.task_id],
            "verifier": verifier_block,
            "commands": commands,
            "artifact_hashes": artifact_hashes,
            "failed_checks": failed_checks,
            "scope_check": {"passed": scope_check_passed},
            "secret_scan": {"passed": secret_scan_passed, "detail": secret_detail},
            "guard_flags": {
                "support_widening": False,
                "production_platform_claim": False,
                "live_adapter_execution": False,
            },
        }

        # 8. Emit
        if emit:
            output_dir = inputs.manifest_path.parent / "workers" / inputs.task_id
            writer = VerificationReportWriter(output_dir=output_dir)
            try:
                writer.emit(report)
            except VerificationReportWriterError as exc:
                raise VerifierError(f"verification_report write failed: {exc}") from exc

        diagnostics: list[str] = []
        if failed_checks:
            diagnostics.append(f"{len(failed_checks)} check failure(s); see failed_checks for detail")

        return VerificationResult(
            overall_pass=not failed_checks,
            report=report,
            diagnostics=diagnostics,
            failed_checks=failed_checks,
        )

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise VerifierError(f"file not found: {path!s}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VerifierError(f"failed to read {path!s}: {exc}") from exc
        if not isinstance(data, dict):
            raise VerifierError(f"{path.name}: expected a JSON object at top level")
        return cast(dict[str, Any], data)
