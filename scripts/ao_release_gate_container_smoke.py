#!/usr/bin/env python3
"""Build and health-check the ao-release-gate check-run service container."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_DOCKERFILE = Path("deploy/ao-release-gate-service/Dockerfile")
DEFAULT_IMAGE = "ao-kernel-ao-release-gate-service:smoke"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_BUILD_TIMEOUT_SECONDS = 300.0
DEFAULT_RUN_TIMEOUT_SECONDS = 30.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/healthz"


def _wait_for_health(url: str, *, timeout_seconds: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict):
                    return payload
        except Exception as exc:  # noqa: BLE001 - report final health failure compactly
            last_error = exc
        time.sleep(1)
    detail = f": {last_error}" if last_error else ""
    raise RuntimeError(f"container health endpoint did not become ready{detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="Container image tag to build.")
    parser.add_argument(
        "--dockerfile",
        type=Path,
        default=DEFAULT_DOCKERFILE,
        help="Path to the ao-release-gate service Dockerfile.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Health wait timeout.")
    parser.add_argument(
        "--build-timeout-seconds",
        type=float,
        default=DEFAULT_BUILD_TIMEOUT_SECONDS,
        help="Docker build timeout.",
    )
    parser.add_argument(
        "--run-timeout-seconds",
        type=float,
        default=DEFAULT_RUN_TIMEOUT_SECONDS,
        help="Docker run command timeout.",
    )
    parser.add_argument("--skip-build", action="store_true", help="Run an already-built image.")
    return parser


def _print_process_output(stdout: str | bytes | None, stderr: str | bytes | None) -> None:
    for output in (stdout, stderr):
        if not output:
            continue
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        print(output, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = _repo_root()
    port = _free_port()
    container_id: str | None = None
    try:
        if not args.skip_build:
            _run(
                [
                    "docker",
                    "build",
                    "-f",
                    str(args.dockerfile),
                    "-t",
                    args.image,
                    ".",
                ],
                cwd=repo_root,
                timeout_seconds=args.build_timeout_seconds,
            )
        run = _run(
            [
                "docker",
                "run",
                "--rm",
                "--detach",
                "--publish",
                f"127.0.0.1:{port}:8000",
                args.image,
            ],
            cwd=repo_root,
            timeout_seconds=args.run_timeout_seconds,
        )
        container_id = run.stdout.strip()
        payload = _wait_for_health(_health_url(port), timeout_seconds=args.timeout_seconds)
        print(
            json.dumps(
                {
                    "status": "pass",
                    "image": args.image,
                    "health_url": _health_url(port),
                    "health_payload": payload,
                    "secret_value_readback": False,
                    "live_adapter_execution": False,
                    "github_check_run_post": False,
                    "merge_authority_enabled": False,
                    "branch_protection_cutover": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"release_gate_container_smoke: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            _print_process_output(exc.stdout, exc.stderr)
        if isinstance(exc, subprocess.TimeoutExpired):
            _print_process_output(exc.stdout, exc.stderr)
        return 2
    finally:
        if container_id:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", container_id],
                    cwd=repo_root,
                    check=False,
                    capture_output=True,
                    timeout=15,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
