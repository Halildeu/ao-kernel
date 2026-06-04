"""Runtime kill-switch for the support-widening smoke harness (V5 Epic 3 E-3-2).

The dominant (runtime) layer of the three-layer stub-purity discipline. A static
AST scan is advisory (dynamic import bypasses it); this module is the enforcement
that actually fails closed at execution time. While `live_call_killswitch()` is
active, ANY of the following raises `SupportWideningError`:

  - opening a socket (`socket.socket`)
  - an HTTP client connect (`http.client.HTTPConnection`)
  - `urllib.request.urlopen` / `OpenerDirector.open`
  - `requests` (`request` / `Session.send` / `adapters.HTTPAdapter.send`) and
    `httpx` (`Client.send` / `AsyncClient.send`) — patched only when importable
  - subprocess / shell exec (`subprocess.Popen/run/call/check_output/check_call`,
    `os.system`, `os.popen`)
  - importing a forbidden network/cloud/provider module through ANY path —
    `import`, `__import__`, `importlib.import_module`, or `exec("import …")`
    (all route through the patched `builtins.__import__`)
  - reading a secret-looking environment variable through ANY `os.environ` /
    `os.getenv` / `os.environb` path — `os.environ`/`os.environb` are swapped for
    sanitized views and EVERY read path (direct, membership, and bulk
    copy/items/keys/values/iter) fails closed when a secret-looking key is present.

Setup is rollback-safe (a failure mid-setup restores already-applied patches) and
every patch is restored on exit (reverse order). The switch never leaks past the
context.
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
_ENV_ALLOWLIST_B = frozenset(k.encode() for k in _ENV_ALLOWLIST)

_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|secret|token|password|credential|bearer|auth)")

# Modules a stub harness must never import at runtime (any import path).
_FORBIDDEN_IMPORTS = (
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
)


class SupportWideningError(RuntimeError):
    """Raised when the smoke harness attempts a forbidden (non-stub) operation."""


def _denied(what: str) -> "Any":
    def _raise(*_a: Any, **_k: Any) -> Any:
        raise SupportWideningError(f"{what} is forbidden inside the support-widening smoke harness")

    return _raise


def _is_forbidden_module(name: str) -> bool:
    return any(name == b or name.startswith(b + ".") for b in _FORBIDDEN_IMPORTS)


def _secret_str(key: str) -> bool:
    return key not in _ENV_ALLOWLIST and bool(_SECRET_KEY.search(key))


def _secret_bytes(key: bytes) -> bool:
    return key not in _ENV_ALLOWLIST_B and bool(_SECRET_KEY.search(key.decode("latin-1")))


class _SanitizedEnviron(dict):  # type: ignore[type-arg]
    """An ``os.environ``-like mapping that fails closed on every read path when a
    secret-looking key is involved. Direct/membership reads check the requested
    key; bulk reads (copy/items/keys/values/iter/len) raise if the *original*
    environment contains any secret-looking key."""

    def __init__(self, original: Any) -> None:
        super().__init__({k: v for k, v in original.items() if k in _ENV_ALLOWLIST})
        self._original = original

    def _guard_bulk(self) -> None:
        for k in self._original.keys():
            if _secret_str(str(k)):
                raise SupportWideningError(
                    "bulk environment read is forbidden in the smoke harness (secret key present)"
                )

    def __getitem__(self, key: Any) -> Any:
        if _secret_str(str(key)):
            raise SupportWideningError(f"environment read of secret-looking key {key!r} is forbidden")
        return self._original[key]

    def get(self, key: Any, default: Any = None) -> Any:
        if _secret_str(str(key)):
            raise SupportWideningError(f"environment read of secret-looking key {key!r} is forbidden")
        return self._original.get(key, default)

    def __contains__(self, key: Any) -> bool:
        if _secret_str(str(key)):
            raise SupportWideningError(f"environment membership test of secret-looking key {key!r} is forbidden")
        return key in self._original

    def copy(self) -> Any:
        self._guard_bulk()
        return dict(self._original)

    def keys(self) -> Any:
        self._guard_bulk()
        return self._original.keys()

    def values(self) -> Any:
        self._guard_bulk()
        return self._original.values()

    def items(self) -> Any:
        self._guard_bulk()
        return self._original.items()

    def __iter__(self) -> Any:
        self._guard_bulk()
        return iter(self._original)

    def __len__(self) -> int:
        self._guard_bulk()
        return len(self._original)


class _SanitizedEnvironb(dict):  # type: ignore[type-arg]
    """Bytes counterpart of `_SanitizedEnviron` for `os.environb`."""

    def __init__(self, original: Any) -> None:
        super().__init__({k: v for k, v in original.items() if k in _ENV_ALLOWLIST_B})
        self._original = original

    def _guard_bulk(self) -> None:
        for k in self._original.keys():
            if _secret_bytes(bytes(k)):
                raise SupportWideningError("bulk environb read is forbidden in the smoke harness (secret key present)")

    def __getitem__(self, key: Any) -> Any:
        if _secret_bytes(bytes(key)):
            raise SupportWideningError(f"environb read of secret-looking key {key!r} is forbidden")
        return self._original[key]

    def get(self, key: Any, default: Any = None) -> Any:
        if _secret_bytes(bytes(key)):
            raise SupportWideningError(f"environb read of secret-looking key {key!r} is forbidden")
        return self._original.get(key, default)

    def __contains__(self, key: Any) -> bool:
        if _secret_bytes(bytes(key)):
            raise SupportWideningError(f"environb membership of secret-looking key {key!r} is forbidden")
        return key in self._original

    def copy(self) -> Any:
        self._guard_bulk()
        return dict(self._original)

    def keys(self) -> Any:
        self._guard_bulk()
        return self._original.keys()

    def items(self) -> Any:
        self._guard_bulk()
        return self._original.items()

    def __iter__(self) -> Any:
        self._guard_bulk()
        return iter(self._original)


@contextlib.contextmanager
def live_call_killswitch() -> Iterator[None]:
    """Patch every network / subprocess / shell / import / secret-env path to fail
    closed, with rollback-safe setup and full restore on exit."""
    applied: list[tuple[Any, str, Any]] = []

    def patch(target: Any, attr: str, replacement: Any) -> None:
        if hasattr(target, attr):
            applied.append((target, attr, getattr(target, attr)))
            setattr(target, attr, replacement)

    def _restore() -> None:
        for target, attr, original in reversed(applied):
            with contextlib.suppress(Exception):
                setattr(target, attr, original)

    try:
        # --- network ---
        patch(socket.socket, "__init__", _denied("socket creation"))
        patch(http.client.HTTPConnection, "__init__", _denied("http.client connect"))
        patch(urllib.request, "urlopen", _denied("urllib urlopen"))
        patch(urllib.request.OpenerDirector, "open", _denied("urllib opener"))
        with contextlib.suppress(ImportError):
            requests = importlib.import_module("requests")
            patch(requests, "request", _denied("requests.request"))
            if hasattr(requests, "Session"):
                patch(requests.Session, "send", _denied("requests.Session.send"))
            adapters = importlib.import_module("requests.adapters")
            if hasattr(adapters, "HTTPAdapter"):
                patch(adapters.HTTPAdapter, "send", _denied("requests.adapters.HTTPAdapter.send"))
        with contextlib.suppress(ImportError):
            httpx = importlib.import_module("httpx")
            for cls_name in ("Client", "AsyncClient"):
                cls = getattr(httpx, cls_name, None)
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

        # --- import guard (covers import / __import__ / importlib / exec("import …")) ---
        _orig_builtin_import = builtins.__import__

        def _guarded_builtin_import(name: str, *a: Any, **k: Any) -> Any:
            if _is_forbidden_module(name):
                raise SupportWideningError(f"import of forbidden module {name!r} is blocked in the smoke harness")
            return _orig_builtin_import(name, *a, **k)

        patch(builtins, "__import__", _guarded_builtin_import)

        _orig_import_module = importlib.import_module

        def _guarded_import_module(name: str, package: str | None = None) -> Any:
            target = name
            if name.startswith(".") and package:
                target = f"{package}{name}" if name.startswith(".") else name
            if _is_forbidden_module(name.lstrip(".")) or _is_forbidden_module(target.lstrip(".")):
                raise SupportWideningError(f"importlib of forbidden module {name!r} is blocked in the smoke harness")
            return _orig_import_module(name, package)

        patch(importlib, "import_module", _guarded_import_module)

        # --- secret-env access (sanitized views, all read paths fail closed) ---
        _orig_getenv = os.getenv

        def _guarded_getenv(key: str, default: Any = None) -> Any:
            if _secret_str(key):
                raise SupportWideningError(f"os.getenv of secret-looking key {key!r} is forbidden")
            return _orig_getenv(key, default)

        patch(os, "getenv", _guarded_getenv)
        patch(os, "environ", _SanitizedEnviron(os.environ))
        if hasattr(os, "environb"):
            patch(os, "environb", _SanitizedEnvironb(os.environb))
        if hasattr(os, "getenvb"):
            _orig_getenvb = os.getenvb

            def _guarded_getenvb(key: bytes, default: Any = None) -> Any:
                if _secret_bytes(key):
                    raise SupportWideningError(f"os.getenvb of secret-looking key {key!r} is forbidden")
                return _orig_getenvb(key, default)

            patch(os, "getenvb", _guarded_getenvb)
    except BaseException:
        _restore()
        raise

    try:
        yield
    finally:
        _restore()


def assert_no_live_capability(stub: Any) -> None:
    """Layer-3 runtime declaration check: a stub adapter must not advertise
    `live_capability=True`."""
    if getattr(stub, "live_capability", False):
        raise SupportWideningError(
            f"stub adapter {stub!r} declares live_capability=True; smoke harness is simulated-only"
        )
