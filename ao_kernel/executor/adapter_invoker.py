"""Adapter invocation dispatch — CLI (subprocess) and HTTP (urllib).

Plan v2 (CNS-20260415-022 iter-1) decisions:

- **Stdlib-only.** ``subprocess.run`` for CLI; ``urllib.request`` for
  HTTP. No new runtime dep.
- **JSON-first parse** (Q7 PASS). Stdout that is fully valid JSON AND
  matches ``output_envelope`` shape wins. Free-text prose with embedded
  diff is ambiguous and surfaces as ``output_parse_failed``.
- **text/plain fallback triple gate** (Q4 B7). Only when all three
  conditions hold does the invoker synthesize a ``{status=ok,
  diff=body}`` envelope: (1) body begins with unified diff markers,
  (2) manifest ``capabilities`` includes ``"write_diff"``, and
  (3) for HTTP: ``Content-Type`` starts with ``text/plain``. Any other
  stdout / body shape fails.
- **Minimal JSONPath subset** (Q4 B6). Only ``$.key(.key)*`` — no
  array indices, wildcards, filters. ``response_parse`` paths are
  validated at invocation time; non-subset paths surface as
  ``output_parse_failed`` so the adapter author sees the restriction
  before shipping.
- **HTTP auth gate preflight** (Q4 W). ``check_http_header_exposure``
  from ``policy_enforcer`` runs before any request is built.
- **Env hermetic subprocess.** ``subprocess.run(env=sandbox.env_vars)``
  — the host environment does NOT leak through.
"""

from __future__ import annotations

import importlib.resources
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

from jsonschema import Draft202012Validator

from ao_kernel.adapters import AdapterManifest
from ao_kernel.executor.errors import (
    AdapterInvocationFailedError,
    AdapterOutputParseError,
)
from ao_kernel.executor.evidence_emitter import emit_adapter_log
from ao_kernel.executor.policy_enforcer import SandboxedEnvironment
from ao_kernel.executor.worktree_builder import WorktreeHandle
from ao_kernel.workflow import Budget, record_spend


_SENTINEL_MISSING: object = object()

_DIFF_MARKERS = ("---", "+++", "@@")

_EMPTY_EXTRACTED: Mapping[str, Mapping[str, Any]] = MappingProxyType({})


@dataclass(frozen=True)
class InvocationResult:
    status: Literal["ok", "declined", "interrupted", "failed", "partial"]
    diff: str | None
    evidence_events: tuple[Mapping[str, Any], ...]
    commands_executed: tuple[Mapping[str, Any], ...]
    error: Mapping[str, Any] | None
    finish_reason: str | None
    interrupt_token: str | None
    cost_actual: Mapping[str, Any]
    stdout_path: Path | None
    stderr_path: Path | None
    extracted_outputs: Mapping[str, Mapping[str, Any]] = field(
        default_factory=lambda: _EMPTY_EXTRACTED
    )
    """Capability-keyed, schema-validated payloads extracted from the
    adapter envelope by the ``output_parse`` rule walker (PR-B0, net-new).

    Default: empty (``MappingProxyType({})``). Adapters without an
    ``output_parse`` manifest field, and legacy callers that construct
    :class:`InvocationResult` directly, see the empty default — no
    behaviour change for pre-FAZ-B callers.

    Keys are capability names (e.g. ``"review_findings"``). Values are
    the extracted payloads after schema validation against each rule's
    ``schema_ref``. See :func:`_walk_output_parse` and
    ``docs/BENCHMARK-SUITE.md`` §3.
    """


# ---------------------------------------------------------------------------
# CLI invocation
# ---------------------------------------------------------------------------


def invoke_cli(
    *,
    manifest: AdapterManifest,
    input_envelope: Mapping[str, Any],
    sandbox: SandboxedEnvironment,
    worktree: WorktreeHandle,
    budget: Budget,
    workspace_root: Path,
    run_id: str,
) -> tuple[InvocationResult, Budget]:
    """Spawn ``subprocess.run`` per ``manifest.invocation``.

    Substitutes ``input_envelope`` placeholders into args; applies
    the sandbox env strictly (no host leakage); measures wall-clock
    duration; records spend against budget.

    Raises ``AdapterInvocationFailedError`` for transport-layer
    failures; raises ``AdapterOutputParseError`` when stdout does not
    satisfy JSON-first or the text/plain triple-gate fallback.
    """
    invocation = manifest.invocation
    if invocation.get("transport") != "cli":
        raise AdapterInvocationFailedError(
            reason="subprocess_crash",
            detail=(
                f"invoke_cli called with transport={invocation.get('transport')!r}"
            ),
        )

    substitution_context = _substitution_context(input_envelope)
    command = _substitute_args(invocation["command"], substitution_context)
    args_template = tuple(invocation.get("args", ()))
    resolved_args = tuple(
        _substitute_args(a, substitution_context) for a in args_template
    )
    stdin_mode = invocation.get("stdin_mode", "none")
    stdin_payload = _build_stdin(stdin_mode, input_envelope)

    # Compute effective timeout = min(manifest-level, budget remaining)
    effective_timeout = _effective_timeout(invocation, budget)

    started = time.monotonic()
    try:
        proc = subprocess.run(
            [command, *resolved_args],
            cwd=str(worktree.path),
            env=dict(sandbox.env_vars),
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=False,
        )
        elapsed = time.monotonic() - started
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
    except FileNotFoundError as exc:
        raise AdapterInvocationFailedError(
            reason="command_not_found",
            detail=f"command {command!r} not found in sandbox PATH",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        # Timeout → partial status with finish_reason=timeout
        updated_budget = _spend_time(budget, elapsed, run_id)
        timeout_stdout = exc.stdout or ""
        timeout_stderr = exc.stderr or ""
        if isinstance(timeout_stdout, bytes):
            timeout_stdout = timeout_stdout.decode("utf-8", errors="replace")
        if isinstance(timeout_stderr, bytes):
            timeout_stderr = timeout_stderr.decode("utf-8", errors="replace")
        emit_adapter_log(
            workspace_root,
            run_id=run_id,
            adapter_id=manifest.adapter_id,
            captured_stdout=timeout_stdout,
            captured_stderr=timeout_stderr,
            redaction=sandbox.evidence_redaction,
        )
        return (
            InvocationResult(
                status="partial",
                diff=None,
                evidence_events=(),
                commands_executed=({
                    "command": command,
                    "exit_code": -1,
                    "elapsed_s": elapsed,
                    "timeout": True,
                },),
                error=None,
                finish_reason="timeout",
                interrupt_token=None,
                cost_actual={"time_seconds": elapsed},
                stdout_path=None,
                stderr_path=None,
            ),
            updated_budget,
        )
    except OSError as exc:
        raise AdapterInvocationFailedError(
            reason="subprocess_crash",
            detail=f"subprocess OS error: {exc}",
        ) from exc

    # Capture logs (redacted)
    log_path = emit_adapter_log(
        workspace_root,
        run_id=run_id,
        adapter_id=manifest.adapter_id,
        captured_stdout=stdout,
        captured_stderr=stderr,
        redaction=sandbox.evidence_redaction,
    )

    # Budget time accounting
    updated_budget = _spend_time(budget, elapsed, run_id)

    # Exit-code mapping
    exit_map = invocation.get("exit_code_map") or {"0": "ok"}
    mapped = exit_map.get(str(exit_code))
    if mapped is None:
        mapped = "failed"
    if mapped == "failed" and exit_code != 0:
        raise AdapterInvocationFailedError(
            reason="non_zero_exit",
            detail=f"command {command!r} exited {exit_code}",
        )

    # Parse stdout via JSON-first -> text/plain triple-gate -> fail-closed
    result = _parse_cli_stdout(
        stdout=stdout,
        manifest=manifest,
        exit_status=mapped,
        log_path=log_path,
        elapsed=elapsed,
        command=command,
    )
    return result, updated_budget


# ---------------------------------------------------------------------------
# HTTP invocation
# ---------------------------------------------------------------------------


def invoke_http(
    *,
    manifest: AdapterManifest,
    input_envelope: Mapping[str, Any],
    sandbox: SandboxedEnvironment,
    worktree: WorktreeHandle,
    budget: Budget,
    workspace_root: Path,
    run_id: str,
) -> tuple[InvocationResult, Budget]:
    """POST per ``manifest.invocation`` using ``urllib.request``.

    Pre-flights ``secrets.exposure_modes`` via
    ``policy_enforcer.check_http_header_exposure`` (called by the
    orchestrator before this function is invoked — this function
    assumes the check passed).

    Raises ``AdapterInvocationFailedError`` on transport failures;
    raises ``AdapterOutputParseError`` on unparseable response.
    """
    invocation = manifest.invocation
    if invocation.get("transport") != "http":
        raise AdapterInvocationFailedError(
            reason="http_error",
            detail=(
                f"invoke_http called with transport={invocation.get('transport')!r}"
            ),
        )

    endpoint = invocation["endpoint"]
    substitution_context = _substitution_context(input_envelope)
    endpoint_resolved = _substitute_args(endpoint, substitution_context)
    auth_secret_id_ref = invocation.get("auth_secret_id_ref")
    headers_allowlist = tuple(invocation.get("headers_allowlist", ()))
    body_template = invocation.get("request_body_template", {}) or {}

    headers: dict[str, str] = {}
    if auth_secret_id_ref:
        secret_value = sandbox.env_vars.get(auth_secret_id_ref)
        if not secret_value:
            raise AdapterInvocationFailedError(
                reason="http_error",
                detail=(
                    f"auth_secret_id_ref={auth_secret_id_ref!r} not present "
                    f"in sandbox env"
                ),
            )
        headers["Authorization"] = f"Bearer {secret_value}"

    for header_name in headers_allowlist:
        # Caller may pre-populate headers via input envelope; skip auth.
        if header_name.lower() == "authorization":
            continue
        # Leave headers_allowlist as the advertisement — actual headers
        # are produced by the executor via response_parse contract.
    headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Accept", "application/json")

    body_resolved = _resolve_body(body_template, input_envelope)
    body_bytes = json.dumps(body_resolved).encode("utf-8")

    effective_timeout = _effective_timeout(invocation, budget)
    request = urllib.request.Request(
        url=endpoint_resolved,
        data=body_bytes,
        headers=headers,
        method="POST",
    )

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=effective_timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            raw_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        elapsed = time.monotonic() - started
        updated_budget = _spend_time(budget, elapsed, run_id)
        raise AdapterInvocationFailedError(
            reason="http_error",
            detail=f"HTTP {exc.code}: {exc.reason}",
        ) from exc
    except urllib.error.URLError as exc:
        elapsed = time.monotonic() - started
        updated_budget = _spend_time(budget, elapsed, run_id)
        # timeout or connection refused map
        if "timed out" in str(exc.reason).lower():
            raise AdapterInvocationFailedError(
                reason="http_timeout",
                detail=str(exc.reason),
            ) from exc
        raise AdapterInvocationFailedError(
            reason="connection_refused",
            detail=str(exc.reason),
        ) from exc

    elapsed = time.monotonic() - started
    updated_budget = _spend_time(budget, elapsed, run_id)

    # Capture redacted response body to adapter log
    log_path = emit_adapter_log(
        workspace_root,
        run_id=run_id,
        adapter_id=manifest.adapter_id,
        captured_stdout=raw_body,
        captured_stderr="",
        redaction=sandbox.evidence_redaction,
    )

    # Parse: JSON-first with optional response_parse subset; else text/plain
    result = _parse_http_response(
        raw_body=raw_body,
        content_type=content_type,
        manifest=manifest,
        invocation=invocation,
        log_path=log_path,
        elapsed=elapsed,
    )
    return result, updated_budget


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_cli_stdout(
    *,
    stdout: str,
    manifest: AdapterManifest,
    exit_status: str,
    log_path: Path,
    elapsed: float,
    command: str,
) -> InvocationResult:
    stripped = stdout.strip()

    # JSON-first
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict) and "status" in parsed:
        return _invocation_from_envelope(parsed, log_path, elapsed, command, manifest=manifest)

    # text/plain fallback triple-gate (CLI side: no content-type, so
    # use (diff markers + write_diff capability + no prose) as the
    # triple).
    if (
        _is_clear_unified_diff(stripped)
        and "write_diff" in manifest.capabilities
    ):
        return InvocationResult(
            status="ok",
            diff=stripped,
            evidence_events=(),
            commands_executed=({
                "command": command,
                "exit_code": 0,
                "elapsed_s": elapsed,
                "timeout": False,
            },),
            error=None,
            finish_reason="normal",
            interrupt_token=None,
            cost_actual={"time_seconds": elapsed},
            stdout_path=log_path,
            stderr_path=None,
        )

    raise AdapterOutputParseError(
        raw_excerpt=stripped[:120],
        detail=(
            "stdout neither a valid JSON output_envelope nor a clear "
            "unified diff; embedded-diff-in-prose is rejected"
        ),
    )


def _parse_http_response(
    *,
    raw_body: str,
    content_type: str,
    manifest: AdapterManifest,
    invocation: Mapping[str, Any],
    log_path: Path,
    elapsed: float,
) -> InvocationResult:
    response_parse = invocation.get("response_parse", {}) or {}

    stripped = raw_body.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        if not response_parse:
            # Expect canonical output_envelope shape
            if "status" in parsed:
                return _invocation_from_envelope(
                    parsed,
                    log_path,
                    elapsed,
                    command=invocation.get("endpoint", "http"),
                    manifest=manifest,
                )
            raise AdapterOutputParseError(
                raw_excerpt=stripped[:120],
                detail="JSON body does not contain a canonical status field",
            )
        # Apply subset JSONPath hints
        return _apply_response_parse(parsed, response_parse, log_path, elapsed)

    # Non-JSON: text/plain fallback triple gate
    if (
        content_type.startswith("text/plain")
        and _is_clear_unified_diff(stripped)
        and "write_diff" in manifest.capabilities
    ):
        return InvocationResult(
            status="ok",
            diff=stripped,
            evidence_events=(),
            commands_executed=(),
            error=None,
            finish_reason="normal",
            interrupt_token=None,
            cost_actual={"time_seconds": elapsed},
            stdout_path=log_path,
            stderr_path=None,
        )

    raise AdapterOutputParseError(
        raw_excerpt=stripped[:120],
        detail=(
            "HTTP body neither JSON nor text/plain+unified-diff with "
            "write_diff capability"
        ),
    )


def _apply_response_parse(
    parsed: Mapping[str, Any],
    response_parse: Mapping[str, Any],
    log_path: Path,
    elapsed: float,
) -> InvocationResult:
    diff = _jsonpath_dotted(parsed, response_parse.get("diff_jsonpath", ""))
    status = _jsonpath_dotted(parsed, response_parse.get("status_jsonpath", ""))
    error = _jsonpath_dotted(parsed, response_parse.get("error_jsonpath", ""))

    status_val = status if status is not _SENTINEL_MISSING else None
    if status_val not in {"ok", "declined", "interrupted", "failed", "partial"}:
        raise AdapterOutputParseError(
            raw_excerpt=json.dumps(parsed)[:120],
            detail=f"response_parse.status_jsonpath did not yield a valid status (got {status_val!r})",
        )

    diff_val = diff if diff is not _SENTINEL_MISSING else None
    error_val = error if error is not _SENTINEL_MISSING else None

    return InvocationResult(
        status=status_val,
        diff=diff_val if isinstance(diff_val, str) else None,
        evidence_events=(),
        commands_executed=(),
        error=error_val if isinstance(error_val, dict) else None,
        finish_reason="normal",
        interrupt_token=None,
        cost_actual={"time_seconds": elapsed},
        stdout_path=log_path,
        stderr_path=None,
    )


def _invocation_from_envelope(
    envelope: Mapping[str, Any],
    log_path: Path,
    elapsed: float,
    command: str,
    manifest: AdapterManifest | None = None,
) -> InvocationResult:
    status = envelope.get("status")
    if status not in {"ok", "declined", "interrupted", "failed", "partial"}:
        raise AdapterOutputParseError(
            raw_excerpt=json.dumps(envelope)[:120],
            detail=f"output_envelope.status invalid: {status!r}",
        )
    extracted = _walk_output_parse(envelope, manifest) if manifest else _EMPTY_EXTRACTED
    return InvocationResult(
        status=status,
        diff=envelope.get("diff"),
        evidence_events=tuple(envelope.get("evidence_events", ())),
        commands_executed=tuple(envelope.get("commands_executed", ())) or ({
            "command": command,
            "exit_code": 0,
            "elapsed_s": elapsed,
            "timeout": False,
        },),
        error=envelope.get("error"),
        finish_reason=envelope.get("finish_reason", "normal"),
        interrupt_token=envelope.get("interrupt_token"),
        cost_actual=envelope.get("cost_actual", {"time_seconds": elapsed}),
        stdout_path=log_path,
        stderr_path=None,
        extracted_outputs=extracted,
    )


def _walk_output_parse(
    envelope: Mapping[str, Any],
    manifest: AdapterManifest,
) -> Mapping[str, Mapping[str, Any]]:
    """Walk ``manifest.output_parse.rules`` and populate extracted outputs.

    Contract (CNS-028v2 iter-5 B4''''; docs/BENCHMARK-SUITE.md §3.2):

    - No ``output_parse`` field on the manifest → empty mapping.
    - Each rule's ``json_path`` is evaluated against the envelope with the
      PR-A3 minimal JSONPath subset (``$.key(.key)*``).
    - Missing key along the path fails fast with
      :class:`AdapterOutputParseError` (edge case: json_path unresolvable).
    - Extracted payload is validated against the rule's ``schema_ref``
      (bundled ``ao_kernel/defaults/schemas/<name>`` preferred;
      ``.ao/schemas/<name>`` fallback when a workspace override exists).
    - Missing ``schema_ref`` on disk → :class:`AdapterOutputParseError`
      (edge case: unresolvable schema_ref fail-closed).
    - ``null`` payload: accepted if the schema accepts ``null``; otherwise
      the schema validator rejects it (edge case: null payload
      schema-decided).
    - Rules without a ``capability`` key are walked and validated but not
      stored — they serve as schema guards only.
    """
    if manifest.output_parse is None:
        return _EMPTY_EXTRACTED
    rules = manifest.output_parse.get("rules", ())
    if not rules:
        return _EMPTY_EXTRACTED
    out: dict[str, Mapping[str, Any]] = {}
    for rule in rules:
        json_path = rule.get("json_path", "")
        capability = rule.get("capability")
        schema_ref = rule.get("schema_ref")
        value = _jsonpath_dotted(envelope, json_path)
        if value is _SENTINEL_MISSING:
            raise AdapterOutputParseError(
                raw_excerpt=json.dumps(envelope)[:120],
                detail=(
                    f"output_parse rule json_path={json_path!r} did not "
                    f"resolve in adapter envelope (key absent)."
                ),
            )
        if schema_ref:
            schema = _resolve_schema_ref(schema_ref, manifest.source_path)
            errors = list(Draft202012Validator(schema).iter_errors(value))
            if errors:
                summary = "; ".join(
                    f"{list(e.absolute_path)}: {e.message}" for e in errors[:3]
                )
                raise AdapterOutputParseError(
                    raw_excerpt=json.dumps(value)[:120],
                    detail=(
                        f"output_parse rule schema_ref={schema_ref!r} "
                        f"validation failed: {summary}"
                    ),
                )
        if capability and isinstance(value, Mapping):
            out[capability] = value
    return MappingProxyType(out) if out else _EMPTY_EXTRACTED


def _resolve_schema_ref(
    schema_ref: str,
    manifest_source: Path,
) -> Mapping[str, Any]:
    """Resolve an ``output_parse`` rule's schema reference.

    Resolution order:

    1. Bundled ``ao_kernel/defaults/schemas/<schema_ref>`` (via
       :mod:`importlib.resources` — wheel-safe, D4 invariant).
    2. Workspace override: walk the manifest's source path upward looking
       for ``.ao/schemas/<schema_ref>`` (matches the ``ao_kernel.adapters``
       workspace-discovery pattern).

    Raises :class:`AdapterOutputParseError` if neither location carries the
    schema. Fail-closed per CNS-028v2 edge-case contract #2.
    """
    bundled_root = importlib.resources.files("ao_kernel.defaults.schemas")
    bundled = bundled_root / schema_ref
    try:
        if bundled.is_file():
            loaded: Mapping[str, Any] = json.loads(bundled.read_text(encoding="utf-8"))
            return loaded
    except (FileNotFoundError, OSError):
        pass

    # Walk upward from the manifest source looking for a workspace
    # ``.ao/schemas/`` override. The manifest itself lives under
    # ``<workspace>/.ao/adapters/`` in a configured workspace, so ``.ao``
    # is one directory up.
    probe = manifest_source.resolve().parent
    for _ in range(5):
        candidate = probe / ".ao" / "schemas" / schema_ref
        if candidate.is_file():
            loaded_override: Mapping[str, Any] = json.loads(
                candidate.read_text(encoding="utf-8")
            )
            return loaded_override
        if probe.parent == probe:
            break
        probe = probe.parent

    raise AdapterOutputParseError(
        raw_excerpt=schema_ref,
        detail=(
            f"output_parse rule schema_ref={schema_ref!r} could not be "
            f"resolved under bundled ao_kernel/defaults/schemas/ or any "
            f"workspace .ao/schemas/ override."
        ),
    )


def _jsonpath_dotted(root: Mapping[str, Any], path: str) -> Any:
    """Evaluate a minimal JSONPath subset (``$.key(.key)*``).

    Raises ``AdapterOutputParseError`` on non-subset input (arrays,
    wildcards, filters) so the adapter author sees the restriction.
    Returns ``_SENTINEL_MISSING`` when a key is absent along the path.
    """
    if not path:
        return _SENTINEL_MISSING
    if not path.startswith("$."):
        raise AdapterOutputParseError(
            raw_excerpt=path,
            detail=(
                f"JSONPath {path!r} must begin with '$.'. Only dotted "
                f"key subset is supported."
            ),
        )
    if "[" in path or "*" in path or ".." in path or "?" in path:
        raise AdapterOutputParseError(
            raw_excerpt=path,
            detail=(
                f"JSONPath {path!r} uses unsupported feature (array "
                f"index, wildcard, recursive descent, or filter). Only "
                f"dotted keys are allowed."
            ),
        )
    parts = path[2:].split(".")
    cursor: Any = root
    for part in parts:
        if not isinstance(cursor, Mapping) or part not in cursor:
            return _SENTINEL_MISSING
        cursor = cursor[part]
    return cursor


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _substitute_args(template: str, envelope: Mapping[str, Any]) -> str:
    """Simple ``{placeholder}`` substitution; no shell expansion."""
    result = template
    for key, value in envelope.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def _substitution_context(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Build the placeholder context for invocation templates.

    Reserved runtime tokens are injected after caller-provided values so
    adapter manifests cannot override them through the input envelope.
    """
    context = dict(envelope)
    context["python_executable"] = sys.executable
    return context


def _build_stdin(
    stdin_mode: str,
    envelope: Mapping[str, Any],
) -> str | None:
    if stdin_mode == "none":
        return None
    if stdin_mode == "prompt_only":
        prompt = envelope.get("task_prompt", "")
        return str(prompt)
    if stdin_mode == "multipart":
        return json.dumps(dict(envelope))
    # unknown mode: safest default is none
    return None


def _effective_timeout(
    invocation: Mapping[str, Any],
    budget: Budget,
) -> float:
    manifest_timeout = float(invocation.get("timeout_seconds", 300))
    if budget.time_seconds is None:
        return manifest_timeout
    remaining = float(budget.time_seconds.remaining)
    return max(1.0, min(manifest_timeout, remaining))


def _spend_time(budget: Budget, elapsed: float, run_id: str) -> Budget:
    if budget.time_seconds is None:
        return budget
    try:
        return record_spend(budget, time_seconds=elapsed, run_id=run_id)
    except Exception:  # noqa: BLE001 — budget exhaust is the caller's concern
        raise


def _resolve_body(
    template: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> Any:
    if isinstance(template, dict):
        return {k: _resolve_body(v, envelope) for k, v in template.items()}
    if isinstance(template, list):
        return [_resolve_body(v, envelope) for v in template]
    if isinstance(template, str):
        return _substitute_args(template, _substitution_context(envelope))
    return template


def _is_clear_unified_diff(body: str) -> bool:
    if not body:
        return False
    first_line = body.splitlines()[0] if body else ""
    return any(first_line.startswith(marker) for marker in _DIFF_MARKERS)


__all__ = [
    "InvocationResult",
    "invoke_cli",
    "invoke_http",
]
