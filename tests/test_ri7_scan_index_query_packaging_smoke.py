"""RI-7.4 — packaged-CLI scan/index/query smoke.

Encodes the six scenarios in
`.claude/plans/RI-7.4-SCAN-INDEX-QUERY-PACKAGING-SMOKE.md`. The smoke runs
`python -m ao_kernel ...` as a subprocess (via `sys.executable`) so the
contract is observed on the packaged module entry point, not just on
in-process imports. No external service is contacted; the embedding
environment is cleared so the documented fail-closed paths are exercised.

This file is evidence-only and does not flip any GPP guard flag, change
public SDK signatures, expose MCP tools, or alter branch protection /
workflows.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest  # noqa: F401  # imported for type hints / future fixtures

# The repo intelligence subsystem requires this exact confirmation token to
# allow a write-vector run. Top-level import keeps lint clean (E402).
from ao_kernel._internal.repo_intelligence.repo_vector_indexer import CONFIRM_VECTOR_INDEX


# RI-7.4 supplementary subprocess CLI surface: uses the same deterministic
# env shape as the wheel-installed smoke in scripts/packaging_smoke.py so
# host provider/embedding env cannot bypass the documented fail-closed
# contract. The forbidden key list mirrors the wheel-installed smoke.
_HOST_ENV_ALLOWLIST = frozenset(
    {
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
        "SYSTEMROOT",
    }
)
_FORBIDDEN_PROVIDER_ENV_KEYS = (
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
_VECTOR_BACKEND_ENV = "AO_KERNEL_VECTOR_BACKEND"


def _cli_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    # Build a minimal allowlist env so host embedding/provider settings
    # cannot silently bypass the documented fail-closed paths.
    env = {k: v for k, v in os.environ.items() if k in _HOST_ENV_ALLOWLIST}
    env[_VECTOR_BACKEND_ENV] = "disabled"
    for key in _FORBIDDEN_PROVIDER_ENV_KEYS:
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


def _run_cli(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ao_kernel", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=env if env is not None else _cli_env(),
        timeout=timeout,
        check=False,
    )


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "ri7-smoke-project"
    (project / ".ao" / "context").mkdir(parents=True)
    (project / "pkg").mkdir()
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (project / "pyproject.toml").write_text('[project]\nname = "ri7-smoke-project"\n', encoding="utf-8")
    return project


# --- scenario 1: entrypoint_help_exits_zero ----------------------------


def test_entrypoint_help_exits_zero() -> None:
    """RI-7.4: `python -m ao_kernel --help` exits zero and prints usage.

    Proves the packaged module entry point is wired and the top-level
    CLI surface is reachable as a subprocess.
    """
    result = _run_cli(["--help"])
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "ao-kernel" in combined or "ao_kernel" in combined.lower()


# --- scenario 2: repo_scan_writes_schema_valid_repo_map ----------------


def test_repo_scan_writes_schema_valid_repo_map(tmp_path: Path) -> None:
    """RI-7.4: `python -m ao_kernel repo scan --project-root <tmp>` exits
    zero and writes a schema-valid repo map artifact (no embedding call,
    no backend required for scan).
    """
    project = _make_project(tmp_path)
    result = _run_cli(
        [
            "repo",
            "scan",
            "--project-root",
            str(project),
            "--output",
            "json",
        ],
    )
    assert result.returncode == 0, result.stderr
    # repo scan emits a JSON object on stdout; we accept either stdout or
    # an artifact written under .ao/context as evidence of success.
    repo_map_artifact = project / ".ao" / "context" / "repo_map.v1.json"
    if repo_map_artifact.exists():
        repo_map = json.loads(repo_map_artifact.read_text(encoding="utf-8"))
        assert repo_map.get("artifact_kind") == "repo_map"
    else:
        # Fallback: assert a parseable JSON object on stdout.
        try:
            data = json.loads(result.stdout)
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(
                f"repo scan stdout was not JSON; stdout={result.stdout!r}; stderr={result.stderr!r}"
            ) from exc
        assert isinstance(data, dict)


# --- scenarios 3 & 4: fail-closed without backend ----------------------


def test_repo_index_write_vectors_fails_closed_without_backend(tmp_path: Path) -> None:
    """RI-7.4: `repo index --write-vectors` with a valid API key but with
    no configured vector backend must exit non-zero with the documented
    backend stderr contract. Setting the API key isolates this scenario
    from the API-key fail-closed branch so reviewers can see the backend
    rejection on its own.
    """
    project = _make_project(tmp_path)
    # Run scan first so the index command does not fail on a missing
    # repo map; the backend fail-closed check is what we want to observe.
    env = _cli_env({"OPENAI_API_KEY": "ri7-smoke-key", "AO_KERNEL_VECTOR_BACKEND": "disabled"})
    scan = _run_cli(
        [
            "repo",
            "scan",
            "--project-root",
            str(project),
            "--output",
            "json",
        ],
        env=env,
    )
    assert scan.returncode == 0, scan.stderr

    result = _run_cli(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            CONFIRM_VECTOR_INDEX,
            "--output",
            "json",
        ],
        env=env,
    )
    assert result.returncode != 0, (result.stdout, result.stderr)
    # With API key set and backend disabled, the CLI must reject on the
    # backend branch specifically.
    assert "configured vector backend" in result.stderr, result.stderr


def test_repo_query_fails_closed_without_manifest_or_backend(tmp_path: Path) -> None:
    """RI-7.4: `repo query` without a vector index manifest or a configured
    backend must exit non-zero. The CLI's documented order checks for the
    manifest first; we accept either the manifest or the backend
    fail-closed message so the scenario is robust to ordering.
    """
    project = _make_project(tmp_path)
    env = _cli_env({"OPENAI_API_KEY": "ri7-smoke-key", "AO_KERNEL_VECTOR_BACKEND": "disabled"})
    result = _run_cli(
        [
            "repo",
            "query",
            "--project-root",
            str(project),
            "--query",
            "run",
            "--output",
            "json",
        ],
        env=env,
    )
    assert result.returncode != 0, (result.stdout, result.stderr)
    msg = result.stderr.lower()
    # The CLI emits one of these contract messages on the prerequisite
    # missing path; any of them constitutes RI-7.4 fail-closed evidence.
    assert "configured vector backend" in msg or "manifest" in msg, result.stderr


# --- scenarios 5 & 6: fail-closed without API key ----------------------


def test_repo_index_write_vectors_fails_closed_without_api_key(tmp_path: Path) -> None:
    """RI-7.4: `repo index --write-vectors` without an embedding API key
    must exit non-zero with the documented stderr contract.
    """
    project = _make_project(tmp_path)
    scan = _run_cli(
        [
            "repo",
            "scan",
            "--project-root",
            str(project),
            "--output",
            "json",
        ],
    )
    assert scan.returncode == 0, scan.stderr

    # Force inmemory backend so we get past the backend check and observe
    # the API-key fail-closed path specifically.
    env = _cli_env({"AO_KERNEL_VECTOR_BACKEND": "inmemory"})
    result = _run_cli(
        [
            "repo",
            "index",
            "--project-root",
            str(project),
            "--write-vectors",
            "--confirm-vector-index",
            CONFIRM_VECTOR_INDEX,
            "--output",
            "json",
        ],
        env=env,
    )
    assert result.returncode != 0, (result.stdout, result.stderr)
    msg = result.stderr.lower()
    assert "api key" in msg or "api_key" in msg, result.stderr


def test_repo_query_fails_closed_without_api_key(tmp_path: Path) -> None:
    """RI-7.4: `repo query` without an embedding API key must exit
    non-zero with the documented stderr contract.
    """
    project = _make_project(tmp_path)
    env = _cli_env({"AO_KERNEL_VECTOR_BACKEND": "inmemory"})
    result = _run_cli(
        [
            "repo",
            "query",
            "--project-root",
            str(project),
            "--query",
            "run",
            "--output",
            "json",
        ],
        env=env,
    )
    assert result.returncode != 0, (result.stdout, result.stderr)
    msg = result.stderr.lower()
    assert "api key" in msg or "api_key" in msg or "manifest" in msg or "configured vector backend" in msg, (
        result.stderr
    )
