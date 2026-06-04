"""V5 Epic 3 E-3-2 invariants: per-surface smoke harness + runtime kill-switch.

Per-surface coverage is parametrized (one case per surface class). The dominant
runtime kill-switch is the security core: every forbidden path (socket /
subprocess / shell / urllib / dynamic-import / secret-env) must fail closed inside
`live_call_killswitch()` and be restored on exit.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ao_kernel._internal.support_widening.evidence import parse_v1
from ao_kernel._internal.support_widening.harnesses.killswitch import (
    SupportWideningError,
    assert_no_live_capability,
    live_call_killswitch,
)
from ao_kernel._internal.support_widening.harnesses.runner import SURFACE_CLASSES, run_surface_smoke
from ao_kernel.config import load_default

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GEN_AT = "2026-06-04T10:00:00Z"


def _schema() -> dict:
    return load_default("schemas", "support-widening-evidence.schema.v1.json")


# ---- 1. per-surface harness (parametrized: one case per surface class) ---


@pytest.mark.parametrize("surface", SURFACE_CLASSES)
def test_surface_smoke_emits_valid_pinned_artifact(surface: str) -> None:
    payload = run_surface_smoke(surface, generated_at=_GEN_AT)
    # schema-valid (E-3-1) + correct discriminator
    assert not list(Draft202012Validator(_schema()).iter_errors(payload)), f"{surface} payload not schema-valid"
    assert payload["surface_class"] == surface
    # guard + simulation pins literal in every emit path
    assert payload["support_widening"] is False
    assert payload["production_platform_claim"] is False
    assert payload["live_adapter_execution"] is False
    assert payload["simulated_only"] is True
    assert payload["live_call_made"] is False
    # recompute-not-trust: evidence_dimensions mirrors raw_dimensions
    assert payload["evidence_dimensions"] == payload["recompute_inputs"]["raw_dimensions"]
    # and it passes the E-3-1 module parse (runtime pin re-assert)
    parse_v1(payload, schema=_schema())


def test_all_five_surface_classes_present() -> None:
    assert set(SURFACE_CLASSES) == {
        "provider",
        "python_version",
        "os_platform",
        "db_backend",
        "deployment_topology",
    }


def test_unknown_surface_rejected() -> None:
    with pytest.raises(SupportWideningError):
        run_surface_smoke("not_a_surface", generated_at=_GEN_AT)


def test_evidence_out_written_owner_only(tmp_path: Path) -> None:
    out = tmp_path / "ev.json"
    run_surface_smoke("python_version", generated_at=_GEN_AT, evidence_out=out)
    assert out.is_file()
    assert out.stat().st_mode & 0o777 == 0o600, "evidence artifact must be owner-only (0o600)"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["surface_class"] == "python_version"


# ---- 2. runtime kill-switch: network paths fail closed (1) ---------------


def test_killswitch_blocks_network() -> None:
    with live_call_killswitch():
        with pytest.raises(SupportWideningError):
            socket.socket()
        with pytest.raises(SupportWideningError):
            urllib.request.urlopen("http://example.invalid")  # noqa: S310


# ---- 3. runtime kill-switch: subprocess / shell fail closed (1) ----------


def test_killswitch_blocks_subprocess_and_shell() -> None:
    with live_call_killswitch():
        for call in (
            lambda: subprocess.run(["echo", "x"]),  # noqa: S603,S607
            lambda: subprocess.Popen(["echo", "x"]),  # noqa: S603,S607
            lambda: os.system("echo x"),  # noqa: S605
            lambda: os.popen("echo x"),
        ):
            with pytest.raises(SupportWideningError):
                call()


# ---- 4. runtime kill-switch: dynamic import fail closed (1) ---------------


def test_killswitch_blocks_forbidden_dynamic_import() -> None:
    import importlib

    with live_call_killswitch():
        with pytest.raises(SupportWideningError):
            importlib.import_module("requests")
        with pytest.raises(SupportWideningError):
            importlib.import_module("socket")


# ---- 5. runtime kill-switch: secret-env fail closed, every read path (1) --


def test_killswitch_blocks_secret_env_every_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "dummy-not-real")
    monkeypatch.setenv("SECRET_TOKEN", "dummy")
    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin"))
    with live_call_killswitch():
        # direct read paths must raise
        with pytest.raises(SupportWideningError):
            _ = os.environ["API_KEY"]
        with pytest.raises(SupportWideningError):
            os.getenv("SECRET_TOKEN")
        with pytest.raises(SupportWideningError):
            os.environ.get("API_KEY")
        with pytest.raises(SupportWideningError):
            _ = "API_KEY" in os.environ
        # sanitized view: snapshot/iteration never EXPOSE a secret key
        assert "API_KEY" not in dict(os.environ.copy())
        assert all("API_KEY" != k and "SECRET_TOKEN" != k for k in os.environ.keys())
        # an allowlisted key is still readable
        assert os.getenv("PATH") is not None


# ---- 6. kill-switch restores process state on exit (1) -------------------


def test_killswitch_restores_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "dummy-not-real")
    with live_call_killswitch():
        with pytest.raises(SupportWideningError):
            socket.socket()
    # after exit: socket works again and the secret env is visible again
    s = socket.socket()
    s.close()
    assert os.environ["API_KEY"] == "dummy-not-real"


# ---- 7. layer-3 live_capability assertion (1) ---------------------------


def test_live_capability_stub_rejected() -> None:
    class _Live:
        live_capability = True

    with pytest.raises(SupportWideningError):
        assert_no_live_capability(_Live())


# ---- 8. CLI smoke (1) ----------------------------------------------------


def test_cli_smoke_runs(tmp_path: Path) -> None:
    out = tmp_path / "cli_ev.json"
    # Run the script with the repo root on PYTHONPATH so the subprocess resolves
    # this checkout's ao_kernel (a script's sys.path[0] is its own dir, and an
    # editable install may point at a different worktree).
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, "scripts/run_support_smoke.py", "--surface", "db_backend", "--evidence-out", str(out)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "SMOKE OK" in proc.stdout
    assert out.is_file()


# ---- 9. governance: no workflow mutation (1) ----------------------------


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_run_support_smoke.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-3-2 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-3-2 must not touch .github/workflows/. Touched: {touched}"
