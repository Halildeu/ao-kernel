#!/usr/bin/env python3
"""Fresh-install smoke for the productized local workflow surface.

Builds the current checkout, installs the wheel and sdist into separate clean
virtualenvs, and runs the user-facing product workflow commands from a temp cwd
outside the source checkout:

- ``repo onboarding`` template/init/doctor
- ``pr-metadata`` generate/fix/validate
- ``orchestration run-wrapper`` dry-run
- ``orchestration run-wrapper-async`` local fixture execution
- ``ai-review`` packaged command surface help

No GitHub, Vault, webhook, branch-protection, live adapter, support widening,
or production-platform claim is touched. Evidence is written under
``build/fresh-install-product-smoke/`` so ``dist/`` remains distribution-only.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["wheel", "sdist", "both"],
        default="both",
        help="Distribution artifact(s) to install and smoke (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        default="build/fresh-install-product-smoke",
        help="Evidence output directory (default: build/fresh-install-product-smoke)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    dist_dir = repo_root / "dist"

    shutil.rmtree(dist_dir, ignore_errors=True)
    # Keep the parent build dir but reset only this script's evidence subdir.
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    _run([sys.executable, "-m", "build"], cwd=repo_root)
    wheel = _single(dist_dir, "ao_kernel-*.whl", "wheel")
    sdist = _single(dist_dir, "ao_kernel-*.tar.gz", "sdist")
    artifacts: list[tuple[str, Path]] = []
    if args.mode in ("wheel", "both"):
        artifacts.append(("wheel", wheel))
    if args.mode in ("sdist", "both"):
        artifacts.append(("sdist", sdist))

    scenario_results = []
    with tempfile.TemporaryDirectory(prefix="ao-kernel-fresh-install-smoke-") as tmp:
        tmp_root = Path(tmp)
        for artifact_kind, artifact_path in artifacts:
            scenario_results.append(
                _smoke_one_distribution(
                    artifact_kind=artifact_kind,
                    artifact_path=artifact_path,
                    tmp_root=tmp_root,
                    output_dir=output_dir,
                )
            )

    evidence = {
        "schema_version": "fresh-install-product-smoke.v1",
        "artifact_kind": "fresh_install_product_smoke",
        "decision": "productized_local_workflows_fresh_install_ready",
        "package_version": _package_version(repo_root),
        "distribution_modes": [kind for kind, _ in artifacts],
        "scenarios": scenario_results,
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "notes": [
            "Each scenario installs a built distribution into a clean virtualenv.",
            "Smoke commands run from a temp cwd outside the source checkout.",
            "No network or external service calls are required by the product workflow smoke.",
        ],
    }
    evidence_path = output_dir / "fresh-install-product-smoke.v1.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"+ wrote fresh-install product smoke evidence -> {evidence_path}")
    return 0


def _smoke_one_distribution(
    *,
    artifact_kind: str,
    artifact_path: Path,
    tmp_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    scenario_root = tmp_root / artifact_kind
    scenario_root.mkdir()
    venv_dir = scenario_root / "venv"
    smoke_cwd = scenario_root / "cwd"
    smoke_cwd.mkdir()

    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=scenario_root)
    bin_dir = _venv_bin_dir(venv_dir)
    venv_pip = bin_dir / ("pip.exe" if os.name == "nt" else "pip")
    console = bin_dir / ("ao-kernel.exe" if os.name == "nt" else "ao-kernel")
    _run([str(venv_pip), "install", str(artifact_path)], cwd=smoke_cwd)

    project_root = smoke_cwd / "product-project"
    base_sha = _init_product_project(project_root)
    scenario_evidence = output_dir / f"{artifact_kind}-productized-local-workflows.v1.json"

    commands: list[dict[str, Any]] = []

    def run_step(step_id: str, command: list[str], *, cwd: Path = smoke_cwd) -> subprocess.CompletedProcess[str]:
        result = _run_capture(command, cwd=cwd)
        commands.append(
            {
                "id": step_id,
                "returncode": result.returncode,
                "stdout_excerpt": result.stdout.strip()[:500],
                "stderr_excerpt": result.stderr.strip()[:300],
            }
        )
        if result.returncode != 0:
            raise SystemExit(f"{artifact_kind} smoke step {step_id} failed with exit {result.returncode}")
        return result

    run_step("console_version", [str(console), "version"])
    run_step(
        "repo_onboarding_template",
        [str(console), "repo", "onboarding", "template", "--output", "json"],
    )
    run_step(
        "repo_onboarding_init_config",
        [
            str(console),
            "repo",
            "onboarding",
            "init-config",
            "--project-root",
            str(project_root),
            "--output",
            "json",
        ],
    )
    doctor = run_step(
        "repo_onboarding_doctor",
        [str(console), "repo", "onboarding", "doctor", "--project-root", str(project_root), "--output", "json"],
    )
    doctor_payload = json.loads(doctor.stdout)
    if doctor_payload.get("status") != "ready":
        raise SystemExit(f"{artifact_kind} repo onboarding doctor did not report ready")

    pr_body = smoke_cwd / "pr-body.md"
    pr_body.write_text("## Summary\n\nFresh install smoke.\n", encoding="utf-8")
    metadata = run_step(
        "pr_metadata_generate",
        [
            str(console),
            "pr-metadata",
            "generate",
            "--work-package",
            "PRODUCT-SMOKE",
            "--issue",
            "#123",
            "--reviewer-provider",
            "anthropic",
        ],
    )
    pr_body.write_text("## Summary\n\nFresh install smoke.\n\n" + metadata.stdout, encoding="utf-8")
    run_step(
        "pr_metadata_fix",
        [
            str(console),
            "pr-metadata",
            "fix",
            "--body-file",
            str(pr_body),
            "--write",
            "--output",
            "json",
            "--work-package",
            "PRODUCT-SMOKE",
            "--issue",
            "#123",
            "--reviewer-provider",
            "anthropic",
        ],
    )
    run_step(
        "pr_metadata_validate",
        [str(console), "pr-metadata", "validate", "--body-file", str(pr_body), "--output", "json"],
    )

    run_step(
        "orchestration_run_wrapper_dry_run",
        [
            str(console),
            "orchestration",
            "run-wrapper",
            "--goal",
            "fresh install dry-run wrapper smoke",
            "--repo-root",
            str(project_root),
            "--base-sha",
            base_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--declared-spec",
            "task-001:src/a.py:fresh install dry run",
            "--dry-run",
            "--format",
            "json",
        ],
    )
    async_result = run_step(
        "orchestration_run_wrapper_async_execute",
        [
            str(console),
            "orchestration",
            "run-wrapper-async",
            "--goal",
            "fresh install async wrapper smoke",
            "--repo-root",
            str(project_root),
            "--worktree-base",
            str(smoke_cwd / "worktrees"),
            "--base-sha",
            base_sha,
            "--repo",
            "Halildeu/ao-kernel",
            "--declared-spec",
            "task-001:src/a.py:fresh install async worker one",
            "--declared-spec",
            "task-002:src/b.py:fresh install async worker two",
            "--execute-local-fixture",
            "--max-workers",
            "2",
            "--format",
            "json",
        ],
    )
    async_payload = json.loads(async_result.stdout)
    if async_payload.get("status") != "ok":
        raise SystemExit(f"{artifact_kind} async wrapper did not report ok")

    run_step("ai_review_help", [str(console), "ai-review", "--help"])

    payload = {
        "schema_version": "productized-local-workflows-smoke.v1",
        "artifact_kind": "productized_local_workflows_smoke",
        "distribution_mode": artifact_kind,
        "artifact_name": artifact_path.name,
        "decision": "productized_local_workflows_ready",
        "commands": commands,
        "async_wrapper_status": async_payload.get("status"),
        "async_invocation_report_path": async_payload.get("invocation_report_path"),
        "ai_review_cli_surface": "present",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
    scenario_evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "distribution_mode": artifact_kind,
        "artifact_name": artifact_path.name,
        "status": "pass",
        "evidence_path": str(scenario_evidence),
        "command_count": len(commands),
    }


def _init_product_project(project_root: Path) -> str:
    project_root.mkdir(parents=True)
    _run(["git", "init", "--initial-branch=main", str(project_root)], cwd=project_root.parent)
    _run(["git", "-C", str(project_root), "config", "user.email", "test@example.com"], cwd=project_root)
    _run(["git", "-C", str(project_root), "config", "user.name", "test"], cwd=project_root)
    (project_root / "AGENTS.md").write_text("# AGENTS\nFresh install product smoke.\n", encoding="utf-8")
    plans_dir = project_root / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "src").mkdir()
    (project_root / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (project_root / "src" / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")
    (plans_dir / "gpp_status.v1.json").write_text(
        json.dumps(
            {
                "schema_version": "gpp_status.v1",
                "current_wp": {"id": "fresh-install-product-smoke"},
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
    _run(["git", "-C", str(project_root), "add", "."], cwd=project_root)
    _run(["git", "-C", str(project_root), "commit", "-m", "initial"], cwd=project_root)
    sha = _run_capture(["git", "-C", str(project_root), "rev-parse", "HEAD"], cwd=project_root).stdout.strip()
    _run(["git", "-C", str(project_root), "update-ref", "refs/remotes/origin/main", sha], cwd=project_root)
    return sha


def _single(dist_dir: Path, pattern: str, label: str) -> Path:
    matches = sorted(dist_dir.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {label} matching {pattern} in {dist_dir}, found {len(matches)}")
    return matches[0]


def _package_version(repo_root: Path) -> str:
    import tomllib

    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = data.get("project", {})
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise SystemExit("pyproject.toml project.version missing")
    return str(project["version"])


def _venv_bin_dir(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts"
    return venv_dir / "bin"


def _run(command: list[str], *, cwd: Path) -> None:
    result = _run_capture(command, cwd=cwd)
    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(result.returncode)


def _run_capture(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    print(f"+ {shlex.join(command)}")
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip() and result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
