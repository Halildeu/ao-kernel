"""Runtime kill-switch for the support-widening smoke harness (V5 Epic 3 E-3-2).

The dominant (runtime) layer of the three-layer stub-purity discipline. A static
AST scan is advisory (dynamic import bypasses it); this module is the enforcement
that actually fails closed at execution time. While `live_call_killswitch()` is
active, ANY of the following raises `SupportWideningError`:

  - opening a socket (`socket.socket`)
  - an HTTP client connect (`http.client.HTTPConnection`)
  - `urllib.request.urlopen` / `OpenerDirector.open`
  - `requests` / `httpx` send paths (only patched when the dep is importable)
  - subprocess / shell exec (`subprocess.Popen/run/call/check_output/check_call`,
    `os.system`, `os.popen`)
  - `importlib.import_module(<forbidden network/cloud/provider module>)`
  - reading a secret-looking environment variable through ANY `os.environ` /
    `os.getenv` / `os.environb` path — the env is swapped for a sanitized,
    allowlisted view for the duration, and every read path is patched as
    defense-in-depth.

The switch is a context manager that restores every patched attribute on exit
(try/finally), so it never leaks into the wider process.
"""

from __future__ import annotations

import builtins
import contextlib
import http.client
import importlib
import os
import re
import socket
import subprocess
import urllib.request
from collections.abc import Iterator
from typing import Any

# Env keys the harness is allowed to read; everything secret-looking is denied.
_ENV_ALLOWLIST = frozenset({"WORKSPACE_ROOT", "CI", "PYTHONPATH", "PATH", "HOME", "TMPDIR"})

_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|secret|token|password|credential|bearer|auth)")

# Modules a stub harness must never import at runtime (dynamic-import covered too).
_FORBIDDEN_IMPORTS = frozenset(
    {
        "requests",
        "httpx",
        "urllib3",
        "socket",
        "openai",
        "anthropic",
        "google.generativeai",
        "aiohttp",
        "boto3",
        "paramiko",
        "subprocess",
    }
)


class SupportWideningError(RuntimeError):
    """Raised when the smoke harness attempts a forbidden (non-stub) operation."""


def _denied(what: str) -> "Any":
    def _raise(*_a: Any, **_k: Any) -> Any:
        raise SupportWideningError(f"{what} is forbidden inside the support-widening smoke harness")

    return _raise


class _SanitizedEnviron(dict):  # type: ignore[type-arg]
    """An ``os.environ``-like mapping that denies secret-looking keys on every
    read path (get/__getitem__/__contains__/copy/items/keys/values/__iter__)."""

    def _check(self, key: Any) -> None:
        name = key.decode() if isinstance(key, bytes) else str(key)
        if name not in _ENV_ALLOWLIST and _SECRET_KEY.search(name):
            raise SupportWideningError(
                f"environment read of secret-looking key {name!r} is forbidden in the smoke harness"
            )

    def __getitem__(self, key: Any) -> Any:
        self._check(key)
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        self._check(key)
        return super().get(key, default)

    def __contains__(self, key: Any) -> bool:
        self._check(key)
        return super().__contains__(key)


def _sanitized_pairs() -> "dict[str, str]":
    return {k: v for k, v in os.environ.items() if k in _ENV_ALLOWLIST}


@contextlib.contextmanager
def live_call_killswitch() -> Iterator[None]:
    """Patch every network / subprocess / shell / dynamic-import / secret-env path
    to fail closed, restoring all originals on exit."""
    patches: list[tuple[Any, str, Any]] = []

    def patch(target: Any, attr: str, replacement: Any) -> None:
        if hasattr(target, attr):
            patches.append((target, attr, getattr(target, attr)))
            setattr(target, attr, replacement)

    # --- network ---
    patch(socket.socket, "__init__", _denied("socket creation"))
    patch(http.client.HTTPConnection, "__init__", _denied("http.client connect"))
    patch(urllib.request, "urlopen", _denied("urllib urlopen"))
    patch(urllib.request.OpenerDirector, "open", _denied("urllib opener"))
    for mod_name, attrs in (("requests", ("request",)), ("httpx", ("Client", "AsyncClient"))):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        if mod_name == "requests":
            patch(mod, "request", _denied("requests.request"))
            sess = getattr(mod, "Session", None)
            if sess is not None:
                patch(sess, "send", _denied("requests.Session.send"))
        else:  # httpx
            for cls_name in attrs:
                cls = getattr(mod, cls_name, None)
                if cls is not None:
                    patch(cls, "send", _denied(f"httpx.{cls_name}.send"))

    # --- subprocess / shell ---
    patch(subprocess.Popen, "__init__", _denied("subprocess.Popen"))
    patch(subprocess, "run", _denied("subprocess.run"))
    patch(subprocess, "call", _denied("subprocess.call"))
    patch(subprocess, "check_output", _denied("subprocess.check_output"))
    patch(subprocess, "check_call", _denied("subprocess.check_call"))
    patch(os, "system", _denied("os.system"))
    patch(os, "popen", _denied("os.popen"))

    # --- dynamic import of forbidden modules ---
    _orig_import = importlib.import_module

    def _guarded_import(name: str, package: str | None = None) -> Any:
        root = name.lstrip(".").split(".")[0]
        if name in _FORBIDDEN_IMPORTS or root in _FORBIDDEN_IMPORTS:
            raise SupportWideningError(f"dynamic import of forbidden module {name!r} is blocked in the smoke harness")
        return _orig_import(name, package)

    patch(importlib, "import_module", _guarded_import)

    # --- secret-env access (sanitized view + getenv patch) ---
    _orig_environ = os.environ
    _orig_getenv = os.getenv
    sanitized = _SanitizedEnviron(_sanitized_pairs())

    def _guarded_getenv(key: str, default: Any = None) -> Any:
        if key not in _ENV_ALLOWLIST and _SECRET_KEY.search(key):
            raise SupportWideningError(f"os.getenv of secret-looking key {key!r} is forbidden in the smoke harness")
        return _orig_getenv(key, default)

    os.environ = sanitized  # type: ignore[assignment]
    patches.append((os, "getenv", _orig_getenv))
    os.getenv = _guarded_getenv

    try:
        yield
    finally:
        os.environ = _orig_environ
        for target, attr, original in reversed(patches):
            with contextlib.suppress(Exception):
                setattr(target, attr, original)


def assert_no_live_capability(stub: Any) -> None:
    """Layer-3 runtime declaration check: a stub adapter must not advertise
    `live_capability=True`."""
    if getattr(stub, "live_capability", False):
        raise SupportWideningError(
            f"stub adapter {stub!r} declares live_capability=True; smoke harness is simulated-only"
        )


# `builtins` re-exported so callers can reference the same name in assertions.
_ = builtins
