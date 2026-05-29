"""AO-MA-4.5 worker invoker.

Closes the AO-MA pipeline gap where AO-MA-4 prepared worktrees but no worker
ever wrote ``worker_result.v1``. The invoker reads the AO-MA-4
``runner_report.v1.json`` (the runner's truth) and, for each worker entry the
runner actually prepared, invokes a PINNED deterministic local worker fixture
inside that worktree. The fixture writes a schema-valid ``worker_result.v1.json``
to the runner's ``expected_worker_result_path`` SSOT. The invoker then emits an
``ao-ma-worker-invocation-report.v1.json``.

Design boundaries (Codex thread 019e74ef AGREE):

- It does NOT reuse ``executor.run_step``: that path owns its own worktree
  lifecycle (it would bypass the AO-MA-4 worktree truth) and has no native
  AO-MA ``live_adapter_execution`` gate.
- It does NOT offer arbitrary adapter selection. v1 pins the
  ``ao-ma-worker-stub`` deterministic local fixture; a live adapter (e.g.
  ``claude-code-cli``) or an open ``live_adapter_execution`` flag is rejected
  fail-closed. Real LLM worker execution requires a separate operator-bound
  GPP supersession with ``live_adapter_execution=true`` and is out of scope.

Eligible runner_report statuses: ``prepared`` and
``skipped_existing_idempotent``. Every other status is recorded as
``skipped_not_eligible`` (the runner already declined or skipped it).

No GitHub write. No branch-protection / ruleset / workflow mutation.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ao_kernel.fixtures.ao_ma_worker_stub import FIXTURE_ID as _STUB_FIXTURE_ID
from ao_kernel.orchestration.runner_report_writer import sha256_of
from ao_kernel.orchestration.worker_runner import WorkerRunnerError, _validate_manifest_envelope

# Package root that contains the ``ao_kernel`` package (…/worker_invoker.py ->
# orchestration -> ao_kernel -> <root>). Injected into the worker fixture
# subprocess PYTHONPATH so the child imports the SAME ao_kernel as this
# process — robust across installed, editable, and worktree layouts.
_PKG_ROOT = Path(__file__).resolve().parent.parent.parent

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "defaults" / "schemas"
_RUNNER_REPORT_SCHEMA = "ao-ma-runner-report.schema.v1.json"
_INVOCATION_REPORT_SCHEMA = "ao-ma-worker-invocation-report.schema.v1.json"
_WORKER_RESULT_SCHEMA = "ao-ma-worker-result.schema.v1.json"
_ASSIGNMENT_SCHEMA = "ao-ma-agent-assignment.schema.v1.json"

PINNED_FIXTURE_ID = _STUB_FIXTURE_ID  # "ao-ma-worker-stub"
_STUB_MODULE = "ao_kernel.fixtures.ao_ma_worker_stub"
_ELIGIBLE_STATUSES = ("prepared", "skipped_existing_idempotent")
_GUARD_KEYS = ("support_widening", "production_platform_claim", "live_adapter_execution")


class WorkerInvocationError(RuntimeError):
    """Raised when the worker invoker cannot run fail-closed."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise WorkerInvocationError(f"file not found: {path!s}")
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerInvocationError(f"failed to read {path!s}: {exc}") from exc


def _load_schema(name: str) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads((_SCHEMAS_DIR / name).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerInvocationError(f"bundled schema {name!r} could not be loaded: {exc}") from exc


def _assert_closed_guards(guard_flags: Any, source: str) -> None:
    """Fail-closed unless all three promotion guard flags are the literal False."""

    if not isinstance(guard_flags, dict):
        raise WorkerInvocationError(f"{source} guard_flags must be an object")
    for key in _GUARD_KEYS:
        if guard_flags.get(key) is not False:
            raise WorkerInvocationError(
                f"{source} guard_flags.{key} must be the literal boolean False "
                f"(got {guard_flags.get(key)!r}); AO-MA-4.5 refuses an open guard "
                f"(live adapter execution needs an operator-bound GPP supersession)"
            )


def _check_emitted_binding(
    *,
    emitted: dict[str, Any],
    task_graph_id: str,
    task_id: str,
    base_sha: str,
    branch: str,
) -> str | None:
    """Return an error string when the emitted worker_result does not bind to
    THIS task graph / task / base / branch, else None. Prevents a schema-valid
    but wrong-provenance payload from being reported as a successful invocation.
    """

    if emitted.get("task_graph_id") != task_graph_id:
        return f"emitted worker_result task_graph_id {emitted.get('task_graph_id')!r} != {task_graph_id!r}"
    if emitted.get("task_id") != task_id:
        return f"emitted worker_result task_id {emitted.get('task_id')!r} != {task_id!r}"
    if emitted.get("base_sha") != base_sha:
        return f"emitted worker_result base_sha {emitted.get('base_sha')!r} != {base_sha!r}"
    if emitted.get("head_ref") != branch:
        return f"emitted worker_result head_ref {emitted.get('head_ref')!r} != assignment branch {branch!r}"
    declared = set(emitted.get("declared_write_set", []))
    actual = set(emitted.get("actual_changed_files", []))
    if not actual.issubset(declared):
        return (
            f"emitted worker_result actual_changed_files {sorted(actual - declared)} not subset of declared_write_set"
        )
    return None


@dataclass
class WorkerInvoker:
    """Invoke a pinned deterministic local worker fixture per prepared worktree."""

    repo_root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.repo_root, Path):
            raise WorkerInvocationError("repo_root must be a Path instance")
        self.repo_root = self.repo_root.resolve()

    def invoke(self, manifest_path: Path, *, fixture_id: str = PINNED_FIXTURE_ID) -> dict[str, Any]:
        """Run the pinned worker fixture for each eligible runner_report entry.

        Returns the emitted invocation report dict. Fail-closed when an
        arbitrary adapter is requested, the manifest guard flags are open, the
        runner_report is missing/invalid, or an emitted worker_result fails its
        schema.
        """

        # 1. Pinned fixture only — v1 offers no arbitrary adapter selection.
        if fixture_id != PINNED_FIXTURE_ID:
            raise WorkerInvocationError(
                f"AO-MA-4.5 v1 only invokes the pinned deterministic local worker fixture "
                f"{PINNED_FIXTURE_ID!r}; arbitrary adapter {fixture_id!r} (e.g. a live "
                f"claude-code-cli) is rejected fail-closed. Live adapter execution needs an "
                f"operator-bound GPP supersession with live_adapter_execution=true."
            )

        manifest_path = manifest_path.resolve()
        manifest = _load_json(manifest_path)

        # 2. Manifest guard flags must be closed (defense in depth; this is the
        #    fail-closed point for a live_adapter_execution=true manifest).
        _assert_closed_guards(manifest.get("guard_flags"), manifest_path.name)

        # 3. Manifest envelope integrity — mirror the AO-MA-4 runner trust gate
        #    (schema_version, task_graph_id pattern, artifact sha256/size, single
        #    task_graph entry, no traversal in artifact paths). The invoker drives
        #    filesystem writes via the fixture, so it must not trust an unvalidated
        #    manifest.
        try:
            _validate_manifest_envelope(manifest, manifest_path)
        except WorkerRunnerError as exc:
            raise WorkerInvocationError(f"manifest envelope invalid: {exc}") from exc

        task_graph_id = manifest["task_graph_id"]
        manifest_dir = manifest_path.parent

        # 4. Load + schema-validate the AO-MA-4 runner_report (runner's truth).
        runner_report_path = manifest_dir / "runner_report.v1.json"
        runner_report = _load_json(runner_report_path)
        try:
            Draft202012Validator(_load_schema(_RUNNER_REPORT_SCHEMA)).validate(runner_report)
        except ValidationError as exc:
            raise WorkerInvocationError(f"{runner_report_path.name} fails runner-report schema: {exc.message}") from exc
        if runner_report.get("task_graph_id") != task_graph_id:
            raise WorkerInvocationError(
                f"runner_report task_graph_id {runner_report.get('task_graph_id')!r} != "
                f"manifest task_graph_id {task_graph_id!r}"
            )

        # 5. The runner_report must describe THIS manifest (no stale/tampered
        #    report pointed at a different manifest's worktrees).
        report_manifest_sha = runner_report.get("manifest_sha256")
        actual_manifest_sha = sha256_of(manifest_path)
        if report_manifest_sha != actual_manifest_sha:
            raise WorkerInvocationError(
                f"runner_report manifest_sha256 {report_manifest_sha!r} != on-disk manifest sha256 "
                f"{actual_manifest_sha!r}; re-run AO-MA-4 spawn before invoke"
            )
        workers = runner_report.get("workers", [])
        if not workers:
            raise WorkerInvocationError("runner_report has no workers; nothing to invoke")
        base_sha = runner_report["base_sha"]

        worker_result_validator = Draft202012Validator(_load_schema(_WORKER_RESULT_SCHEMA))
        assignment_validator = Draft202012Validator(_load_schema(_ASSIGNMENT_SCHEMA))
        manifest_artifacts = {entry["path"]: entry for entry in manifest["artifacts"]}

        # 6. Invoke the pinned fixture for each eligible worker entry.
        invoked: list[dict[str, Any]] = []
        for worker in workers:
            invoked.append(
                self._invoke_one(
                    worker=worker,
                    manifest_dir=manifest_dir,
                    manifest_artifacts=manifest_artifacts,
                    task_graph_id=task_graph_id,
                    base_sha=base_sha,
                    worker_result_validator=worker_result_validator,
                    assignment_validator=assignment_validator,
                )
            )

        # 5. Emit the schema-valid invocation report.
        return self._emit_report(
            manifest_dir=manifest_dir,
            manifest_path=manifest_path,
            task_graph_id=task_graph_id,
            invoked=invoked,
        )

    def _invoke_one(
        self,
        *,
        worker: dict[str, Any],
        manifest_dir: Path,
        manifest_artifacts: dict[str, Any],
        task_graph_id: str,
        base_sha: str,
        worker_result_validator: Draft202012Validator,
        assignment_validator: Draft202012Validator,
    ) -> dict[str, Any]:
        task_id = worker["task_id"]
        status = worker["status"]
        expected_path = Path(worker["expected_worker_result_path"])
        base_entry = {
            "task_id": task_id,
            "worker_result_path": str(expected_path),
            "integrated_worker_result_path": None,
        }

        if status not in _ELIGIBLE_STATUSES:
            return {
                **base_entry,
                "status": "skipped_not_eligible",
                "reason": f"runner_report status {status!r} is not prepared/skipped_existing_idempotent",
            }

        # Worker entry integrity BEFORE any subprocess / filesystem write: the
        # assignment artifact must be inside the manifest dir, sha256-pinned by
        # the runner report, schema-valid, cross-ref'd to this task graph / task /
        # base, and the expected output path must be the worktree-root SSOT. A
        # tampered runner_report / assignment must not drive an out-of-scope write.
        try:
            assignment = self._load_verified_assignment(
                worker=worker,
                manifest_dir=manifest_dir,
                manifest_artifacts=manifest_artifacts,
                task_graph_id=task_graph_id,
                base_sha=base_sha,
                expected_path=expected_path,
                assignment_validator=assignment_validator,
            )
            # The worktree itself must be the AO-MA-4-prepared git checkout
            # (same repo, expected branch + base HEAD) before any write — a
            # tampered runner_report pointing actual_worktree at an arbitrary
            # directory must not drive an out-of-scope write.
            self._verify_worktree(
                actual_worktree=Path(worker["actual_worktree"]),
                base_sha=base_sha,
                branch=worker["branch"],
            )
        except WorkerInvocationError as exc:
            return {**base_entry, "status": "failed", "reason": f"worker entry integrity failed: {exc}"}

        assignment_path = manifest_dir / worker["assignment_ref"]
        actual_worktree = Path(worker["actual_worktree"])
        cmd = [
            sys.executable,
            "-m",
            _STUB_MODULE,
            "--assignment",
            str(assignment_path),
            "--worktree",
            str(actual_worktree),
            "--output",
            str(expected_path),
        ]
        env = dict(os.environ)
        _existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(_PKG_ROOT) + (os.pathsep + _existing_pp if _existing_pp else "")
        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(self.repo_root),
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {**base_entry, "status": "failed", "reason": f"fixture invocation error: {exc}"}

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
            return {**base_entry, "status": "failed", "reason": f"fixture exited non-zero: {detail}"}

        # Validate the emitted worker_result.v1.json fail-closed.
        if not expected_path.exists():
            return {
                **base_entry,
                "status": "failed",
                "reason": "fixture exited 0 but no worker_result.v1.json at expected path",
            }
        try:
            emitted = _load_json(expected_path)
            worker_result_validator.validate(emitted)
        except WorkerInvocationError as exc:
            return {**base_entry, "status": "failed", "reason": f"emitted worker_result unreadable: {exc}"}
        except ValidationError as exc:
            return {**base_entry, "status": "failed", "reason": f"emitted worker_result fails schema: {exc.message}"}

        # Emitted worker_result binding BEFORE bridge: schema-valid bytes from a
        # DIFFERENT graph / task / base / branch must not be reported as a
        # successful invocation for THIS task (false provenance). On mismatch ->
        # failed, and the result is NOT bridged into the consumption point.
        binding_error = _check_emitted_binding(
            emitted=emitted,
            task_graph_id=task_graph_id,
            task_id=task_id,
            base_sha=base_sha,
            branch=assignment["branch"],
        )
        if binding_error:
            return {**base_entry, "status": "failed", "reason": binding_error}

        # Bridge: the worker fixture wrote worker_result.v1.json at the worktree
        # root (AO-MA-4 producer SSOT), but AO-MA-5/6/7 consume evidence under
        # the manifest base_dir and fail-closed on paths outside it (audit
        # provenance). Copy the validated worker_result to the canonical
        # consumption point so the downstream chain can integrate it regardless
        # of where the worktree lives.
        integrated_path = manifest_dir / "workers" / task_id / "worker_result.v1.json"
        try:
            integrated_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = integrated_path.parent / ".worker_result.v1.json.tmp"
            tmp.write_text(json.dumps(emitted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(integrated_path)
        except OSError as exc:
            return {
                **base_entry,
                "status": "failed",
                "reason": f"failed to bridge worker_result into base_dir consumption point: {exc}",
            }

        return {
            **base_entry,
            "integrated_worker_result_path": str(integrated_path),
            "status": "invoked",
            "reason": (
                "pinned deterministic local worker fixture invoked; worker_result.v1.json "
                "schema-valid and bridged to base_dir consumption point"
            ),
        }

    def _load_verified_assignment(
        self,
        *,
        worker: dict[str, Any],
        manifest_dir: Path,
        manifest_artifacts: dict[str, Any],
        task_graph_id: str,
        base_sha: str,
        expected_path: Path,
        assignment_validator: Draft202012Validator,
    ) -> dict[str, Any]:
        """Load + fully verify one worker's assignment, fail-closed.

        Containment (assignment_ref inside manifest dir) + sha256 pin (matches
        the runner_report) + schema + cross-ref (task_graph_id / task_id /
        base_sha / branch) + worktree-root expected output path. Raises
        WorkerInvocationError on any mismatch so a tampered runner_report /
        assignment cannot drive an out-of-scope write.
        """

        assignment_ref = worker["assignment_ref"]
        resolved_manifest_dir = manifest_dir.resolve()
        assignment_path = (manifest_dir / assignment_ref).resolve()
        try:
            assignment_path.relative_to(resolved_manifest_dir)
        except ValueError as exc:
            raise WorkerInvocationError(
                f"assignment_ref {assignment_ref!r} escapes manifest dir {resolved_manifest_dir!s}"
            ) from exc
        if not assignment_path.exists():
            raise WorkerInvocationError(f"assignment not found: {assignment_path!s}")

        # The assignment must be a DECLARED manifest artifact, and its sha256 must
        # agree across the manifest, the runner_report, and the on-disk bytes. The
        # runner_report is a tamperable on-disk artifact, so its assignment_sha256
        # alone is not trusted — the manifest (envelope-validated above) anchors it.
        manifest_entry = manifest_artifacts.get(assignment_ref)
        if manifest_entry is None:
            raise WorkerInvocationError(f"assignment_ref {assignment_ref!r} is not a declared manifest artifact")
        actual_sha = sha256_of(assignment_path)
        manifest_sha = manifest_entry.get("sha256")
        runner_sha = worker.get("assignment_sha256")
        if not (actual_sha == manifest_sha == runner_sha):
            raise WorkerInvocationError(
                f"assignment_sha256 mismatch for {assignment_ref!r}: on-disk {actual_sha!r}, "
                f"manifest {manifest_sha!r}, runner_report {runner_sha!r}"
            )

        assignment = _load_json(assignment_path)
        try:
            assignment_validator.validate(assignment)
        except ValidationError as exc:
            raise WorkerInvocationError(f"assignment fails schema: {exc.message}") from exc

        if assignment.get("task_graph_id") != task_graph_id:
            raise WorkerInvocationError(
                f"assignment task_graph_id {assignment.get('task_graph_id')!r} != {task_graph_id!r}"
            )
        if assignment.get("task_id") != worker["task_id"]:
            raise WorkerInvocationError(
                f"assignment task_id {assignment.get('task_id')!r} != runner task_id {worker['task_id']!r}"
            )
        if assignment.get("base_sha") != base_sha:
            raise WorkerInvocationError(
                f"assignment base_sha {assignment.get('base_sha')!r} != runner base_sha {base_sha!r}"
            )
        if assignment.get("branch") != worker["branch"]:
            raise WorkerInvocationError(
                f"assignment branch {assignment.get('branch')!r} != runner branch {worker['branch']!r}"
            )

        canonical_expected = (Path(worker["actual_worktree"]) / "worker_result.v1.json").resolve()
        if expected_path.resolve() != canonical_expected:
            raise WorkerInvocationError(
                f"expected_worker_result_path {expected_path!s} is not the worktree-root SSOT {canonical_expected!s}"
            )
        return assignment

    def _git_capture(self, worktree: Path, args: list[str]) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                ["git", "-C", str(worktree), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkerInvocationError(f"git {args!r} failed in {worktree!s}: {exc}") from exc
        return completed.returncode, completed.stdout.strip()

    def _verify_worktree(self, *, actual_worktree: Path, base_sha: str, branch: str) -> None:
        """Fail-closed unless ``actual_worktree`` is the AO-MA-4-prepared git
        worktree: a real worktree root, on the expected branch at ``base_sha``
        HEAD, attached to the same repo as ``repo_root``. Prevents a tampered
        runner_report from aiming the fixture's write at an arbitrary directory
        or a foreign repository.
        """

        if not actual_worktree.exists():
            raise WorkerInvocationError(f"actual_worktree does not exist: {actual_worktree!s}")
        rc, toplevel = self._git_capture(actual_worktree, ["rev-parse", "--show-toplevel"])
        if rc != 0:
            raise WorkerInvocationError(f"actual_worktree {actual_worktree!s} is not a git worktree")
        if Path(toplevel).resolve() != actual_worktree.resolve():
            raise WorkerInvocationError(
                f"actual_worktree {actual_worktree!s} is not a worktree root (toplevel={toplevel!r})"
            )
        rc, head = self._git_capture(actual_worktree, ["rev-parse", "HEAD"])
        if rc != 0 or head != base_sha:
            raise WorkerInvocationError(f"actual_worktree HEAD {head!r} != base_sha {base_sha!r}")
        rc, observed_branch = self._git_capture(actual_worktree, ["symbolic-ref", "--short", "HEAD"])
        if rc != 0 or observed_branch != branch:
            raise WorkerInvocationError(f"actual_worktree branch {observed_branch!r} != expected {branch!r}")
        # Same repo: the worktree's git-common-dir must match repo_root's.
        rc, wt_common = self._git_capture(actual_worktree, ["rev-parse", "--git-common-dir"])
        rc2, repo_common = self._git_capture(self.repo_root, ["rev-parse", "--git-common-dir"])
        if rc != 0 or rc2 != 0:
            raise WorkerInvocationError("failed to resolve git-common-dir for worktree containment")
        wt_common_abs = Path(wt_common) if Path(wt_common).is_absolute() else (actual_worktree / wt_common)
        repo_common_abs = Path(repo_common) if Path(repo_common).is_absolute() else (self.repo_root / repo_common)
        if wt_common_abs.resolve() != repo_common_abs.resolve():
            raise WorkerInvocationError(
                f"actual_worktree git-common-dir {wt_common_abs!s} is not the same repo as repo_root "
                f"{repo_common_abs!s}"
            )

    def _emit_report(
        self,
        *,
        manifest_dir: Path,
        manifest_path: Path,
        task_graph_id: str,
        invoked: list[dict[str, Any]],
    ) -> dict[str, Any]:
        report = {
            "schema_version": "ao-ma-worker-invocation-report.v1",
            "task_graph_id": task_graph_id,
            "manifest_sha256": sha256_of(manifest_path),
            "generated_at": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fixture_id": PINNED_FIXTURE_ID,
            "invoked": invoked,
            "guard_flags": {key: False for key in _GUARD_KEYS},
        }
        try:
            Draft202012Validator(_load_schema(_INVOCATION_REPORT_SCHEMA)).validate(report)
        except ValidationError as exc:
            raise WorkerInvocationError(f"worker invocation report fails schema validation: {exc.message}") from exc

        out_path = manifest_dir / "worker_invocation_report.v1.json"
        tmp = manifest_dir / ".worker_invocation_report.v1.json.tmp"
        tmp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(out_path)
        return report
