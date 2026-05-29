"""AO-MA-4.5 deterministic local worker fixture.

Promoted from the AO-MA-8 e2e smoke in-file surrogate
(``tests/test_ao_ma_8_e2e_smoke.py::_emit_mock_worker_result``) to a runtime
module so the AO-MA-4.5 worker invoker can drive a real ``worker_result.v1``
producer instead of a test-only helper.

This fixture is a DETERMINISTIC LOCAL worker. It does NOT call any LLM, does
NOT reach the network, and does NOT use a live adapter. It modifies one file
from the assignment's ``declared_write_set`` inside the already-prepared
worktree, commits it, derives ``head_sha`` + ``actual_changed_files`` from
real git state, and writes a schema-valid ``worker_result.v1.json`` to the
output path (the AO-MA-4 runner's ``expected_worker_result_path`` SSOT — the
worktree root, not an artifact-dir shortcut).

Invocation (matches the pinned ``WorkerInvoker`` command; no arbitrary adapter
selection is offered in v1):

    python3 -m ao_kernel.fixtures.ao_ma_worker_stub \
        --assignment <agent_assignment-*.v1.json> \
        --worktree <actual_worktree> \
        --output <expected_worker_result_path>

Identity: the emitted ``worker.provider`` is ``"local"`` — this fixture does
not impersonate a live provider. The assignment's planned ``agent.provider``
(AO-MA-3 metadata, default ``anthropic``) may differ; no AO-MA layer enforces
equality between assignment provider and worker_result provider.

Guard flags stay closed (``support_widening`` / ``production_platform_claim``
/ ``live_adapter_execution`` all ``False``). Real LLM worker execution
requires a separate operator-bound GPP supersession with
``live_adapter_execution=true`` and is out of scope for AO-MA-4.5 v1.

Lifecycle note: the emitted ``worker_result.v1.json`` lands in the worktree
root and stays untracked (it is written AFTER the implementation commit so it
never enters ``actual_changed_files``). Removing it / cleaning the worktree is
a separate operator step; this fixture makes no end-to-end lifecycle-clean
claim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

FIXTURE_ID = "ao-ma-worker-stub"
WORKER_PROVIDER = "local"

_GUARD_KEYS = ("support_widening", "production_platform_claim", "live_adapter_execution")
_CLOSED_GUARDS = {key: False for key in _GUARD_KEYS}


class WorkerStubError(RuntimeError):
    """Raised when the deterministic worker fixture cannot emit a worker_result."""


def _run_git(worktree: Path, args: list[str]) -> str:
    """Run ``git -C worktree <args>`` fail-closed and return stripped stdout."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(worktree), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerStubError(f"git {args!r} failed in {worktree!s}: {exc}") from exc
    return completed.stdout.strip()


def _load_assignment(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise WorkerStubError(f"assignment not found: {path!s}")
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerStubError(f"failed to read assignment {path!s}: {exc}") from exc


def emit_worker_result(*, assignment_path: Path, worktree: Path, output_path: Path) -> dict[str, Any]:
    """Modify one declared file, commit, and write a schema-valid worker_result.v1.

    Returns the worker_result dict written to ``output_path``. Fail-closed when
    the assignment guard flags are open, the declared write set is empty, or the
    worktree is missing.
    """

    assignment = _load_assignment(assignment_path)

    # Guard: never run a worker under an open live-adapter / widening flag.
    guard = assignment.get("guard_flags")
    if not isinstance(guard, dict):
        raise WorkerStubError("assignment guard_flags must be an object")
    for key in _GUARD_KEYS:
        if guard.get(key) is not False:
            raise WorkerStubError(
                f"assignment guard_flags.{key} must be the literal boolean False "
                f"(got {guard.get(key)!r}); deterministic worker refuses an open guard"
            )

    try:
        task_graph_id = assignment["task_graph_id"]
        task_id = assignment["task_id"]
        assignment_id = assignment["assignment_id"]
        base_ref = assignment["base_ref"]
        base_sha = assignment["base_sha"]
        branch = assignment["branch"]
    except KeyError as exc:
        raise WorkerStubError(f"assignment missing required field: {exc}") from exc

    declared = list(assignment.get("declared_write_set", []))
    if not declared:
        raise WorkerStubError("assignment declared_write_set is empty; nothing to implement")

    worktree = worktree.resolve()
    if not worktree.exists():
        raise WorkerStubError(f"worktree does not exist: {worktree!s}")

    # Defense-in-depth: the worktree must be the expected git checkout (on the
    # assignment branch at base_sha HEAD) BEFORE any write. Standalone callers
    # do not get the invoker's worktree gate, so the fixture self-verifies and
    # refuses to write into a plain directory or a wrong branch / base.
    head_before = _run_git(worktree, ["rev-parse", "HEAD"])
    if head_before != base_sha:
        raise WorkerStubError(f"worktree HEAD {head_before!r} != assignment base_sha {base_sha!r}; refusing write")
    branch_now = _run_git(worktree, ["symbolic-ref", "--short", "HEAD"])
    if branch_now != branch:
        raise WorkerStubError(f"worktree branch {branch_now!r} != assignment branch {branch!r}; refusing write")

    # 1. Modify the first declared file (create parent dirs / file if absent).
    #    Path containment fail-closed BEFORE any write: a tampered assignment
    #    must not drive an out-of-worktree write (e.g. '../outside.txt' or an
    #    absolute path). Defense in depth — the fixture can be run standalone,
    #    so it does not rely on the invoker's prior schema/containment checks.
    target_rel = declared[0]
    if target_rel.startswith("/") or ".." in Path(target_rel).parts or "\\" in target_rel:
        raise WorkerStubError(
            f"declared path {target_rel!r} is absolute or contains traversal components; refusing out-of-worktree write"
        )
    target_abs = (worktree / target_rel).resolve()
    try:
        target_abs.relative_to(worktree)
    except ValueError as exc:
        raise WorkerStubError(f"declared path {target_rel!r} escapes worktree {worktree!s}") from exc
    target_abs.parent.mkdir(parents=True, exist_ok=True)
    existing = target_abs.read_text(encoding="utf-8") if target_abs.exists() else ""
    target_abs.write_text(existing + "\n# ao-ma-worker-stub deterministic change\n", encoding="utf-8")

    # 2. Commit the implementation change (no --allow-empty).
    _run_git(worktree, ["add", target_rel])
    _run_git(worktree, ["commit", "-m", f"ao-ma-worker-stub: {task_id}"])

    # 3. Derive head_sha + actual_changed_files from real git state.
    head_sha = _run_git(worktree, ["rev-parse", "HEAD"])
    actual_changed = [
        line.strip()
        for line in _run_git(worktree, ["diff", "--name-only", f"{base_sha}..HEAD"]).splitlines()
        if line.strip()
    ]

    worker_result: dict[str, Any] = {
        "schema_version": "ao-ma-worker-result.v1",
        "task_graph_id": task_graph_id,
        "task_id": task_id,
        "assignment_id": assignment_id,
        "worker": {
            "agent_id": f"ao-ma-worker-stub-{task_id}"[:81],
            "agent_type": "implementer",
            "provider": WORKER_PROVIDER,
            "session_id": f"ao-ma-4-5-{task_graph_id}",
        },
        "base_ref": base_ref,
        "base_sha": base_sha,
        "head_ref": branch,
        "head_sha": head_sha,
        "declared_write_set": declared,
        "actual_changed_files": actual_changed,
        "summary": f"ao-ma-worker-stub deterministic implementer for {task_id}",
        "tests_run": [],
        "known_gaps": ["deterministic local worker fixture; no real implementation logic"],
        "no_secret_attestation": {"secrets_recorded": False},
        "guard_flags": dict(_CLOSED_GUARDS),
    }

    # 4. Write worker_result AFTER the commit so it stays untracked in the
    #    worktree root and never enters actual_changed_files. Atomic tmp+replace.
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.parent / (output_path.name + ".tmp")
    tmp.write_text(json.dumps(worker_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(output_path)
    return worker_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ao_ma_worker_stub",
        description=(
            "Deterministic local worker fixture for AO-MA-4.5 worker invocation. "
            "Modifies one declared file, commits, and emits a schema-valid "
            "worker_result.v1.json. No LLM call, no network, no live adapter."
        ),
    )
    parser.add_argument("--assignment", required=True, help="Path to agent_assignment-*.v1.json")
    parser.add_argument("--worktree", required=True, help="Prepared worktree path (actual_worktree)")
    parser.add_argument(
        "--output",
        required=True,
        help="Where to write worker_result.v1.json (the runner's expected_worker_result_path)",
    )
    args = parser.parse_args(argv)

    try:
        emit_worker_result(
            assignment_path=Path(args.assignment).resolve(),
            worktree=Path(args.worktree),
            output_path=Path(args.output),
        )
    except WorkerStubError as exc:
        print(f"ao-ma-worker-stub failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
