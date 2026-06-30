#!/usr/bin/env python3
"""Build-and-install smoke for the packaged Public Beta surface.

The smoke is intentionally wheel-first:

1. Build sdist + wheel from the checkout.
2. Create a fresh virtualenv.
3. Install the built wheel only.
4. Run all supported CLI entry points.
5. Run ``examples/demo_review.py --cleanup`` from a temp cwd outside
   the repository.
6. (RI-7.4) Drive ``repo scan / repo index / repo query`` against a
   throwaway project from the same outside-cwd to prove the
   wheel-installed scan/index/query surface is reachable and emits the
   documented fail-closed contract for missing backend / missing API
   key. Writes a schema-valid JSON evidence artifact next to the smoke
   output.
7. Drive the productized local workflow commands added after v4.3.1
   prep: ``repo onboarding``, ``pr-metadata``, ``orchestration
   run-wrapper``, ``orchestration run-wrapper-async``, and the packaged
   ``ai-review`` command surface. Evidence is written under
   ``build/packaging-smoke/`` so ``dist/`` remains distribution-only.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"

    shutil.rmtree(dist_dir, ignore_errors=True)
    shutil.rmtree(build_dir, ignore_errors=True)

    with tempfile.TemporaryDirectory(prefix="ao-kernel-packaging-smoke-") as tmp_dir:
        temp_root = Path(tmp_dir)
        venv_dir = temp_root / "venv"
        smoke_cwd = temp_root / "cwd"
        smoke_cwd.mkdir()

        _run([sys.executable, "-m", "build"], cwd=repo_root)
        _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=repo_root)

        venv_bin = _venv_bin_dir(venv_dir)
        venv_python = venv_bin / ("python.exe" if os.name == "nt" else "python")
        venv_pip = venv_bin / ("pip.exe" if os.name == "nt" else "pip")
        console_script = venv_bin / ("ao-kernel.exe" if os.name == "nt" else "ao-kernel")

        wheel_path = _single_wheel(dist_dir)
        _run([str(venv_pip), "install", str(wheel_path)], cwd=smoke_cwd)

        _run([str(console_script), "version"], cwd=smoke_cwd)
        _run([str(venv_python), "-m", "ao_kernel", "version"], cwd=smoke_cwd)
        _run([str(venv_python), "-m", "ao_kernel.cli", "version"], cwd=smoke_cwd)
        _run(
            [
                str(venv_python),
                str(repo_root / "examples" / "demo_review.py"),
                "--cleanup",
            ],
            cwd=smoke_cwd,
        )

        # RI-7.4: wheel-installed scan/index/query fail-closed evidence.
        # P0-GATE-1 (V5-PR #783, AO-MA-11G-2c-PUBLISH-FIX): evidence path moved
        # `dist/` → `build/packaging-smoke/` so PyPI publish workflow's twine
        # check + pypa/gh-action-pypi-publish never see non-distribution files
        # in dist/. Distribution dir reserved for `.whl` + `.tar.gz` ONLY.
        _smoke_repo_intelligence_cli(
            venv_python=venv_python,
            outside_cwd=smoke_cwd,
            evidence_out=repo_root / "build" / "packaging-smoke" / "ri7-packaging-smoke-evidence.v1.json",
        )
        _smoke_productized_local_workflows(
            venv_python=venv_python,
            console_script=console_script,
            outside_cwd=smoke_cwd,
            evidence_out=repo_root / "build" / "packaging-smoke" / "productized-local-workflows-smoke.v1.json",
        )

    return 0


def _smoke_productized_local_workflows(
    *,
    venv_python: Path,
    console_script: Path,
    outside_cwd: Path,
    evidence_out: Path,
) -> None:
    """Smoke productized local workflows from the wheel-installed CLI."""

    project = outside_cwd / "productized-workflows-project"
    base_sha = _init_productized_smoke_project(project)
    commands: list[dict[str, object]] = []

    def _scenario(scenario_id: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            args,
            cwd=str(outside_cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        commands.append(
            {
                "id": scenario_id,
                "returncode": result.returncode,
                "stdout_excerpt": result.stdout.strip()[:500],
                "stderr_excerpt": result.stderr.strip()[:300],
            }
        )
        if result.returncode != 0:
            raise SystemExit(
                f"productized workflow smoke {scenario_id} failed with exit "
                f"{result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    _scenario("repo_onboarding_template", [str(console_script), "repo", "onboarding", "template", "--output", "json"])
    _scenario(
        "repo_onboarding_init_config",
        [
            str(console_script),
            "repo",
            "onboarding",
            "init-config",
            "--project-root",
            str(project),
            "--output",
            "json",
        ],
    )
    doctor = _scenario(
        "repo_onboarding_doctor",
        [str(console_script), "repo", "onboarding", "doctor", "--project-root", str(project), "--output", "json"],
    )
    if json.loads(doctor.stdout).get("status") != "ready":
        raise SystemExit("productized workflow smoke repo onboarding doctor did not report ready")

    body_path = outside_cwd / "product-pr-body.md"
    body_path.write_text("## Summary\n\nPackaging smoke.\n", encoding="utf-8")
    generated = _scenario(
        "pr_metadata_generate",
        [
            str(console_script),
            "pr-metadata",
            "generate",
            "--work-package",
            "PRODUCT-SMOKE",
            "--issue",
            "#123",
        ],
    )
    body_path.write_text(body_path.read_text(encoding="utf-8") + "\n" + generated.stdout, encoding="utf-8")
    _scenario(
        "pr_metadata_fix",
        [
            str(console_script),
            "pr-metadata",
            "fix",
            "--body-file",
            str(body_path),
            "--write",
            "--output",
            "json",
            "--work-package",
            "PRODUCT-SMOKE",
            "--issue",
            "#123",
        ],
    )
    _scenario(
        "pr_metadata_validate",
        [str(console_script), "pr-metadata", "validate", "--body-file", str(body_path), "--output", "json"],
    )

    _scenario(
        "orchestration_run_wrapper_dry_run",
        [
            str(console_script),
            "orchestration",
            "run-wrapper",
            "--goal",
            "packaging smoke run wrapper",
            "--repo-root",
            str(project),
            "--base-sha",
            base_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--declared-spec",
            "task-001:src/a.py:packaging smoke dry run",
            "--dry-run",
            "--format",
            "json",
        ],
    )
    async_result = _scenario(
        "orchestration_run_wrapper_async_execute",
        [
            str(console_script),
            "orchestration",
            "run-wrapper-async",
            "--goal",
            "packaging smoke async wrapper",
            "--repo-root",
            str(project),
            "--worktree-base",
            str(outside_cwd / "product-worktrees"),
            "--base-sha",
            base_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--declared-spec",
            "task-001:src/a.py:packaging smoke async one",
            "--declared-spec",
            "task-002:src/b.py:packaging smoke async two",
            "--execute-local-fixture",
            "--max-workers",
            "2",
            "--format",
            "json",
        ],
    )
    async_payload = json.loads(async_result.stdout)
    if async_payload.get("status") != "ok":
        raise SystemExit("productized workflow smoke async wrapper did not report ok")

    _scenario("ai_review_help", [str(console_script), "ai-review", "--help"])

    artifact = {
        "schema_version": "productized-local-workflows-smoke.v1",
        "artifact_kind": "productized_local_workflows_smoke",
        "decision": "productized_local_workflows_packaging_smoke_ready",
        "entrypoint": {
            "console_script": str(console_script),
            "module": str(venv_python),
        },
        "scenarios": [
            {"id": item["id"], "status": "pass", "returncode": item["returncode"]} for item in commands
        ],
        "async_wrapper_version": async_payload.get("async_wrapper_version"),
        "ai_review_cli_surface": "present",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    evidence_out.parent.mkdir(parents=True, exist_ok=True)
    evidence_out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"+ wrote productized workflow smoke evidence -> {evidence_out}")


def _init_productized_smoke_project(project: Path) -> str:
    project.mkdir(parents=True)
    _run(["git", "init", "--initial-branch=main", str(project)], cwd=project.parent)
    _run(["git", "-C", str(project), "config", "user.email", "test@example.com"], cwd=project)
    _run(["git", "-C", str(project), "config", "user.name", "test"], cwd=project)
    (project / "AGENTS.md").write_text("# AGENTS\nProductized workflow packaging smoke.\n", encoding="utf-8")
    plans = project / ".claude" / "plans"
    plans.mkdir(parents=True)
    (project / "src").mkdir()
    (project / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (project / "src" / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    (plans / "gpp_status.v1.json").write_text(
        json.dumps(
            {
                "schema_version": "gpp_status.v1",
                "current_wp": {"id": "productized-workflow-packaging-smoke"},
                "support_widening_allowed": False,
                "production_platform_claim_allowed": False,
                "live_adapter_execution_allowed": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _run(["git", "-C", str(project), "add", "."], cwd=project)
    _run(["git", "-C", str(project), "commit", "-m", "initial"], cwd=project)
    sha = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "HEAD"],
        cwd=str(project),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    _run(["git", "-C", str(project), "update-ref", "refs/remotes/origin/main", sha], cwd=project)
    return sha


def _smoke_repo_intelligence_cli(
    *,
    venv_python: Path,
    outside_cwd: Path,
    evidence_out: Path,
) -> None:
    """Drive repo scan/index/query against a temp project from outside-cwd.

    Uses the wheel-installed Python interpreter (not the source-checkout
    interpreter) so the smoke proves the packaged scan/index/query surface
    is reachable and emits the documented fail-closed contract for missing
    backend and missing embedding API key.
    """
    project = outside_cwd / "ri7-smoke-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[project]\nname = "ri7-smoke-project"\n', encoding="utf-8"
    )

    scenarios: list[dict[str, object]] = []

    def _scenario(
        scenario_id: str,
        args: list[str],
        env: dict[str, str],
        expect_returncode_zero: bool,
        expected_stderr_any: tuple[str, ...] = (),
    ) -> None:
        result = subprocess.run(
            [str(venv_python), "-m", "ao_kernel", *args],
            cwd=str(outside_cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120.0,
        )
        if expect_returncode_zero:
            if result.returncode != 0:
                raise SystemExit(
                    f"RI-7.4 scenario {scenario_id} expected exit 0 but got "
                    f"{result.returncode}; stderr={result.stderr!r}"
                )
        else:
            if result.returncode == 0:
                raise SystemExit(
                    f"RI-7.4 scenario {scenario_id} expected non-zero exit; "
                    f"stdout={result.stdout!r}"
                )
            if expected_stderr_any:
                stderr_lc = result.stderr.lower()
                if not any(s.lower() in stderr_lc for s in expected_stderr_any):
                    raise SystemExit(
                        f"RI-7.4 scenario {scenario_id} stderr did not match any of "
                        f"{expected_stderr_any!r}; got {result.stderr!r}"
                    )
        scenarios.append(
            {
                "id": scenario_id,
                "status": "pass",
                "returncode": result.returncode,
                "stderr_excerpt": result.stderr.strip()[:240],
            }
        )

    def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
        # RI-7.4 fail-closed smoke must not silently pick up a host
        # embedding/provider key from the parent shell. We build a
        # deterministic minimal env from a host allowlist and explicitly
        # exclude every known provider/embedding key so the smoke cannot
        # accidentally contact an external service.
        allowed_host_keys = {
            "PATH",
            "HOME",
            "TMPDIR",
            "TMP",
            "TEMP",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "USER",
            "LOGNAME",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONUTF8",
            "SYSTEMROOT",  # required on Windows for subprocess
        }
        base = {k: v for k, v in os.environ.items() if k in allowed_host_keys}
        # Disable vector backend by default for the fail-closed scenarios.
        base["AO_KERNEL_VECTOR_BACKEND"] = "disabled"
        # Defensively scrub anything the caller could have set in extras
        # that we do not want to leak through (caller can re-set explicitly).
        forbidden_keys = (
            "OPENAI_API_KEY",
            "AO_KERNEL_OPENAI_API_KEY",
            "AO_KERNEL_EMBEDDING_API_KEY",
            "AO_KERNEL_EMBEDDING_PROVIDER",
            "AO_KERNEL_EMBEDDING_MODEL",
            "AO_KERNEL_EMBEDDING_BASE_URL",
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
            "XAI_API_KEY",
            "QWEN_API_KEY",
        )
        for k in forbidden_keys:
            base.pop(k, None)
        if extra:
            base.update(extra)
        return base

    _scenario(
        "entrypoint_help_exits_zero",
        ["--help"],
        env=_env(),
        expect_returncode_zero=True,
    )
    _scenario(
        "repo_scan_writes_schema_valid_repo_map",
        ["repo", "scan", "--project-root", str(project), "--output", "json"],
        env=_env(),
        expect_returncode_zero=True,
    )
    _scenario(
        "repo_index_write_vectors_fails_closed_without_backend",
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            _confirm_token(venv_python, outside_cwd),
            "--output",
            "json",
        ],
        env=_env({"OPENAI_API_KEY": "ri7-wheel-smoke-key", "AO_KERNEL_VECTOR_BACKEND": "disabled"}),
        expect_returncode_zero=False,
        expected_stderr_any=("configured vector backend",),
    )
    _scenario(
        "repo_query_fails_closed_without_manifest_or_backend",
        ["repo", "query", "--project-root", str(project), "--query", "run", "--output", "json"],
        env=_env({"OPENAI_API_KEY": "ri7-wheel-smoke-key", "AO_KERNEL_VECTOR_BACKEND": "disabled"}),
        expect_returncode_zero=False,
        expected_stderr_any=("configured vector backend", "manifest"),
    )
    _scenario(
        "repo_index_write_vectors_fails_closed_without_api_key",
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            _confirm_token(venv_python, outside_cwd),
            "--output",
            "json",
        ],
        env=_env({"AO_KERNEL_VECTOR_BACKEND": "inmemory"}),
        expect_returncode_zero=False,
        expected_stderr_any=("api key", "api_key"),
    )
    _scenario(
        "repo_query_fails_closed_without_api_key",
        ["repo", "query", "--project-root", str(project), "--query", "run", "--output", "json"],
        env=_env({"AO_KERNEL_VECTOR_BACKEND": "inmemory"}),
        expect_returncode_zero=False,
        expected_stderr_any=("api key", "api_key", "manifest", "configured vector backend"),
    )

    artifact = {
        "schema_version": "ri7-scan-index-query-packaging-smoke-evidence.v1",
        "artifact_kind": "ri7_scan_index_query_packaging_smoke_evidence",
        "decision": "ri7_scan_index_query_packaging_smoke_ready",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "entrypoint": {
            "module": "ao_kernel",
            "invocation": "python -m ao_kernel (wheel-installed venv)",
        },
        "scenarios": [
            {"id": s["id"], "status": s["status"], "evidence_ref": "scripts/packaging_smoke.py::_smoke_repo_intelligence_cli"}
            for s in scenarios
        ],
        "build_install_layer_ref": "scripts/packaging_smoke.py",
        "notes": [
            "Subprocess smoke uses the wheel-installed venv Python, outside the source checkout cwd.",
            "Fail-closed scenarios run with cleared embedding API key envs and a disabled or inmemory vector backend so the documented contract is observed without contacting any external service.",
        ],
    }
    evidence_out.parent.mkdir(parents=True, exist_ok=True)
    evidence_out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"+ wrote RI-7.4 evidence -> {evidence_out}")


def _confirm_token(venv_python: Path, outside_cwd: Path) -> str:
    """Resolve the CONFIRM_VECTOR_INDEX token from the wheel-installed package.

    Runs from ``outside_cwd`` with a minimal env so the resolved token comes
    from the wheel-installed package, not a source-checkout import path.
    """
    minimal_env = {
        k: v
        for k, v in os.environ.items()
        if k in {"PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "SYSTEMROOT"}
    }
    proc = subprocess.run(
        [
            str(venv_python),
            "-c",
            "from ao_kernel._internal.repo_intelligence.repo_vector_indexer import CONFIRM_VECTOR_INDEX; print(CONFIRM_VECTOR_INDEX)",
        ],
        cwd=str(outside_cwd),
        env=minimal_env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30.0,
    )
    return proc.stdout.strip()


def _single_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("ao_kernel-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(
            f"expected exactly one ao-kernel wheel in {dist_dir}, found {len(wheels)}"
        )
    return wheels[0]


def _venv_bin_dir(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts"
    return venv_dir / "bin"


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"+ {shlex.join(command)}")
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode == 0:
        return
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    if proc.stdout.strip():
        print(proc.stdout.strip(), file=sys.stderr)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
