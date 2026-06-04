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
from typing import Any, cast

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


def _schema() -> dict[str, Any]:
    return cast(dict[str, Any], load_default("schemas", "support-widening-evidence.schema.v1.json"))


# ---- 1. per-surface harness (parametrized: one case per surface class) ---


@pytest.mark.parametrize("surface", SURFACE_CLASSES)  # type: ignore[untyped-decorator]
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


def test_killswitch_blocks_forbidden_import_every_path() -> None:
    import importlib

    with live_call_killswitch():
        # importlib.import_module
        with pytest.raises(SupportWideningError):
            importlib.import_module("requests")
        with pytest.raises(SupportWideningError):
            importlib.import_module("socket")
        # submodule of a forbidden package (prefix match, not just root)
        with pytest.raises(SupportWideningError):
            importlib.import_module("google.generativeai")
        # builtins.__import__ (covers `import X`)
        with pytest.raises(SupportWideningError):
            __import__("socket")
        # exec("import …") routes through the patched __import__
        with pytest.raises(SupportWideningError):
            exec("import socket")  # noqa: S102
        # eval of an __import__ call
        with pytest.raises(SupportWideningError):
            eval("__import__('socket')")  # noqa: S307


# ---- 5. runtime kill-switch: secret-env fail closed, every read path (1) --


def test_killswitch_blocks_secret_env_every_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "dummy-not-real")
    monkeypatch.setenv("SECRET_TOKEN", "dummy")
    # credential-class keys a "secret-looking" regex MISSES — allowlist-only catches them
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "dummy-aws-access-key-id")
    monkeypatch.setenv("OPENAI_ORGANIZATION", "org_test")
    monkeypatch.setenv("PATH", os.environ.get("PATH", "/usr/bin"))
    with live_call_killswitch():
        # direct + membership read paths must raise (incl. non-regex credential keys)
        for key in ("API_KEY", "SECRET_TOKEN", "AWS_ACCESS_KEY_ID", "OPENAI_ORGANIZATION"):
            with pytest.raises(SupportWideningError):
                _ = os.environ[key]
            with pytest.raises(SupportWideningError):
                os.getenv(key)
            with pytest.raises(SupportWideningError):
                os.environ.get(key)
            with pytest.raises(SupportWideningError):
                _ = key in os.environ
        # bulk read paths must ALSO fail closed when a secret key is present —
        # including `dict(os.environ)`, which routes through the keys() override.
        for bulk in (
            lambda: os.environ.copy(),
            lambda: dict(os.environ),
            lambda: list(os.environ.keys()),
            lambda: list(os.environ.items()),
            lambda: list(os.environ.values()),
            lambda: [k for k in os.environ],
        ):
            with pytest.raises(SupportWideningError):
                bulk()
        # os.environb byte paths must fail closed too (where supported)
        if hasattr(os, "environb"):
            with pytest.raises(SupportWideningError):
                _ = os.environb[b"API_KEY"]
            with pytest.raises(SupportWideningError):
                os.environb.get(b"SECRET_TOKEN")
        # an allowlisted key is still readable
        assert os.getenv("PATH") == os.environ["PATH"]


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


# ---- 7b. evidence write hardening: overwrite mode + .ao reject (2) -------


def test_evidence_overwrite_tightens_mode(tmp_path: Path) -> None:
    out = tmp_path / "ev.json"
    out.write_text("{}", encoding="utf-8")
    out.chmod(0o644)  # pre-existing wide-mode artifact
    run_surface_smoke("python_version", generated_at=_GEN_AT, evidence_out=out)
    assert out.stat().st_mode & 0o777 == 0o600, "overwrite must tighten mode to 0o600 (fchmod)"


def test_evidence_out_under_dot_ao_rejected(tmp_path: Path) -> None:
    out = tmp_path / ".ao" / "ev.json"
    with pytest.raises(SupportWideningError):
        run_surface_smoke("python_version", generated_at=_GEN_AT, evidence_out=out)
    assert not out.exists(), "no .ao/ artifact may be written (read-only workspace contract)"


def test_malicious_stub_through_runner_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stub builder that attempts a forbidden op must fail closed because
    run_surface_smoke executes the stub inside the kill-switch."""
    from ao_kernel._internal.support_widening.harnesses import runner as _runner

    def _evil() -> dict[str, Any]:
        socket.socket()  # forbidden inside the harness
        return {"matrix": ["3.11"], "pytest_passed": True}

    monkeypatch.setitem(_runner._SURFACE_STUBS, "python_version", _evil)
    with pytest.raises(SupportWideningError):
        run_surface_smoke("python_version", generated_at=_GEN_AT)


# ---- 8. CLI smoke (1) ----------------------------------------------------


def test_cli_smoke_runs(tmp_path: Path) -> None:
    out = tmp_path / "cli_ev.json"
    # Run the script directly. The script itself is responsible for resolving
    # this checkout's repo root so an editable install cannot silently point at a
    # different worktree.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
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
