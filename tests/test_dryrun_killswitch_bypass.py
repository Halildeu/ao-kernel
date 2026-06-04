"""Runtime bypass tests for the E-2-4 dry-run kill-switch."""

from __future__ import annotations

import http.client
import os
import socket
import subprocess
import urllib.request
from typing import Callable

import pytest

from ao_kernel._internal.live_adapter_dryrun import DryRunKillSwitchError, install_dry_run_killswitches


def _assert_blocked(attempt: Callable[[], object]) -> None:
    with install_dry_run_killswitches(), pytest.raises(DryRunKillSwitchError, match="network call attempted"):
        attempt()


def test_blocks_socket_constructor_and_create_connection() -> None:
    _assert_blocked(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    _assert_blocked(lambda: socket.create_connection(("127.0.0.1", 9), timeout=0.01))


def test_blocks_precaptured_socket_connect_alias() -> None:
    socket_class = socket.socket

    def _attempt() -> object:
        sock = socket_class(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(("127.0.0.1", 9))
            return None
        finally:
            sock.close()

    _assert_blocked(_attempt)


@pytest.mark.parametrize(
    "attempt",
    [
        lambda: subprocess.Popen(["true"]),  # noqa: S603,S607 - bypass fixture
        lambda: subprocess.run(["true"], check=False),  # noqa: S603,S607
        lambda: subprocess.call(["true"]),  # noqa: S603,S607
        lambda: subprocess.check_output(["true"]),  # noqa: S603,S607
        lambda: subprocess.check_call(["true"]),  # noqa: S603,S607
    ],
)
def test_blocks_subprocess_full_family(attempt: Callable[[], object]) -> None:
    _assert_blocked(attempt)


@pytest.mark.parametrize(
    "attempt",
    [
        lambda: os.system("true"),
        lambda: os.popen("true"),
        lambda: os.spawnv(os.P_WAIT, "/bin/echo", ["echo", "x"]),
    ],
)
def test_blocks_os_shell_exec_family(attempt: Callable[[], object]) -> None:
    _assert_blocked(attempt)


def test_exec_family_is_patched_without_invoking_originals() -> None:
    names = ("execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe")
    originals = {name: getattr(os, name) for name in names if hasattr(os, name)}

    with install_dry_run_killswitches():
        for name, original in originals.items():
            assert getattr(os, name) is not original

    for name, original in originals.items():
        assert getattr(os, name) is original


def test_overlapping_killswitch_contexts_restore_after_last_exit() -> None:
    original_socket = socket.socket
    first = install_dry_run_killswitches()
    second = install_dry_run_killswitches()

    first.__enter__()
    try:
        second.__enter__()
        try:
            first.__exit__(None, None, None)
            with pytest.raises(DryRunKillSwitchError, match="network call attempted"):
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        finally:
            second.__exit__(None, None, None)

    finally:
        if socket.socket is not original_socket:
            first.__exit__(None, None, None)

    assert socket.socket is original_socket


def test_blocks_urllib_and_http_client() -> None:
    _assert_blocked(lambda: urllib.request.urlopen("https://example.com", timeout=1))
    _assert_blocked(lambda: http.client.HTTPConnection("example.com").request("GET", "/"))
    _assert_blocked(lambda: http.client.HTTPSConnection("example.com").request("GET", "/"))


def test_blocks_httpx_sync_async_and_stream_if_installed() -> None:
    httpx = pytest.importorskip("httpx")
    _assert_blocked(lambda: httpx.Client().send(httpx.Request("GET", "https://example.com")))
    _assert_blocked(lambda: httpx.stream("GET", "https://example.com"))
    _assert_blocked(lambda: httpx.AsyncClient().send(httpx.Request("GET", "https://example.com")))


def test_blocks_urllib3_if_installed() -> None:
    urllib3 = pytest.importorskip("urllib3")
    pool = urllib3.PoolManager()
    _assert_blocked(lambda: pool.request("GET", "https://example.com"))


def test_blocks_requests_if_installed() -> None:
    requests = pytest.importorskip("requests")
    _assert_blocked(lambda: requests.get("https://example.com", timeout=1))


def test_blocks_aiohttp_if_installed() -> None:
    aiohttp = pytest.importorskip("aiohttp")
    _assert_blocked(lambda: object.__new__(aiohttp.ClientSession)._request("GET", "https://example.com"))


def test_blocks_native_library_escape_hatches_if_installed() -> None:
    import ctypes

    _assert_blocked(lambda: ctypes.CDLL("libcurl"))
    cffi = pytest.importorskip("cffi")
    _assert_blocked(lambda: cffi.FFI())
