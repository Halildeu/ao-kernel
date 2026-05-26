"""AO-MA-3 orchestrator façade.

High-level entrypoint that:

1. Reads the SSOT paths (``AGENTS.md`` + ``.claude/plans/gpp_status.v1.json``)
   to confirm the program is in a state where orchestration is allowed.
2. Resolves a 40-char ``base_sha`` (default: ``origin/main`` if available).
3. Builds a deterministic task graph + agent assignments via
   :func:`task_graph_builder.build_task_graph`.
4. Emits the artifact set + SHA256 manifest via :class:`ArtifactWriter`.

Hard constraints:

- No LLM call, no subprocess spawn for workers, no GitHub write.
- No mutation of any SSOT, policy, schema, workflow, or branch protection.
- Guard flags (``support_widening``, ``production_platform_claim``,
  ``live_adapter_execution``) are forced to ``false`` in every emitted
  artifact regardless of input.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ao_kernel.orchestration.artifact_writer import ArtifactWriter
from ao_kernel.orchestration.task_graph_builder import (
    BuildResult,
    TaskGraphBuilderError,
    TaskSpec,
    build_task_graph,
)


class OrchestrationError(RuntimeError):
    """Raised when the orchestrator cannot fail-closed produce artifacts."""


@dataclass(frozen=True)
class SSOTPaths:
    """Filesystem paths the orchestrator reads (read-only) before emitting."""

    agents_md: Path = Path("AGENTS.md")
    gpp_status: Path = Path(".claude/plans/gpp_status.v1.json")

    @classmethod
    def default(cls, repo_root: Path | None = None) -> "SSOTPaths":
        """Return SSOT paths anchored at ``repo_root`` or the cwd."""

        root = (repo_root or Path.cwd()).resolve()
        return cls(
            agents_md=root / "AGENTS.md",
            gpp_status=root / ".claude/plans/gpp_status.v1.json",
        )


@dataclass
class Orchestrator:
    """High-level orchestrator façade.

    Construct with ``repo_root`` pointing at the repository working tree
    plus optional ``ssot`` override. Then call :meth:`plan` with the
    operator goal + optional declared task specs.
    """

    repo_root: Path
    ssot: SSOTPaths = field(default_factory=SSOTPaths.default)
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.repo_root, Path):
            raise OrchestrationError("repo_root must be a Path instance")
        self.repo_root = self.repo_root.resolve()

    def plan(
        self,
        goal: str,
        *,
        declared_specs: list[TaskSpec] | None = None,
        base_sha: str | None = None,
        base_ref: str = "refs/heads/main",
        utc_now: _dt.datetime | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """Build and emit the task graph + assignments + manifest.

        Returns the manifest dict. Raises :class:`OrchestrationError` for any
        fail-closed precondition: missing SSOT, open guard flags in
        ``gpp_status``, unresolvable ``base_sha``, or builder failures.
        """

        self._assert_ssot_present()
        self._assert_guard_flags_closed()
        resolved_repo = repo or self._infer_repo_full()
        resolved_base_sha = base_sha or self._resolve_origin_main_sha()

        try:
            result: BuildResult = build_task_graph(
                goal,
                resolved_base_sha,
                repo=resolved_repo,
                base_ref=base_ref,
                declared_specs=declared_specs,
                utc_now=utc_now,
            )
        except TaskGraphBuilderError as exc:
            raise OrchestrationError(f"task graph build failed: {exc}") from exc

        out_dir = self.output_dir or (self.repo_root / ".ao" / "orchestration")
        writer = ArtifactWriter(base_dir=out_dir)
        manifest = writer.emit(
            result.task_graph,
            result.assignments,
            utc_now=utc_now,
        )
        return manifest

    # ------------------------------------------------------------------
    # SSOT guard helpers
    # ------------------------------------------------------------------
    def _assert_ssot_present(self) -> None:
        if not self.ssot.agents_md.exists():
            raise OrchestrationError(
                f"SSOT missing: {self.ssot.agents_md!s} not found; "
                "orchestrator requires AGENTS.md before emitting a task graph"
            )
        if not self.ssot.gpp_status.exists():
            raise OrchestrationError(
                f"SSOT missing: {self.ssot.gpp_status!s} not found; "
                "orchestrator requires gpp_status.v1.json before emitting a task graph"
            )

    def _assert_guard_flags_closed(self) -> None:
        try:
            data = json.loads(self.ssot.gpp_status.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OrchestrationError(f"failed to read gpp_status.v1.json: {exc}") from exc

        flags = (
            "support_widening_allowed",
            "production_platform_claim_allowed",
            "live_adapter_execution_allowed",
        )
        for flag in flags:
            value = data.get(flag, False)
            if value is not False:
                raise OrchestrationError(
                    f"gpp_status guard flag {flag!r} is {value!r}; "
                    "orchestration may not run while a promotion flag is open"
                )

    # ------------------------------------------------------------------
    # base SHA + repo discovery
    # ------------------------------------------------------------------
    def _resolve_origin_main_sha(self) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.repo_root), "rev-parse", "origin/main"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            raise OrchestrationError(
                "failed to resolve origin/main SHA; ensure the repo has an "
                f"origin remote and the branch is fetched: {exc}"
            ) from exc
        sha = completed.stdout.strip()
        if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
            raise OrchestrationError(f"git rev-parse returned unexpected SHA shape: {sha!r}")
        return sha

    def _infer_repo_full(self) -> str:
        """Infer ``owner/repo`` from the origin remote URL.

        Falls back to a placeholder so the orchestrator can still emit
        artifacts when the remote is missing; downstream consumers will
        notice the placeholder and fail closed if they require a real repo.
        """

        try:
            completed = subprocess.run(
                ["git", "-C", str(self.repo_root), "remote", "get-url", "origin"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
            return "unknown/unknown"
        url = completed.stdout.strip()
        # https://github.com/owner/repo[.git] or git@github.com:owner/repo[.git]
        for separator in ("github.com/", "github.com:"):
            if separator in url:
                tail = url.split(separator, 1)[1]
                tail = tail.removesuffix(".git")
                if "/" in tail:
                    return tail
        return "unknown/unknown"
