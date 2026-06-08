#!/usr/bin/env python3
"""Probe hosted no-secret health endpoints for the internal GPP-2 gate host."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_POLICY_HEALTH_PATH = "/policy/healthz"
DEFAULT_RELEASE_GATE_HEALTH_PATH = "/release-gate/healthz"
EXPECTED_POLICY_PROGRAM_ID = "GPP-2q"
EXPECTED_RELEASE_GATE_PROGRAM_ID = "GPP-2w"
MAX_HEALTH_BODY_BYTES = 64 * 1024

LOCAL_HTTP_HOSTS = {"localhost", "127.0.0.1", "::1"}

HealthTransport = Callable[[str, float], tuple[int, bytes]]


def _safe_text(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _base_url_from_host(host: str) -> str:
    value = host.strip()
    if not value:
        raise ValueError("host must not be empty")
    if "://" not in value:
        value = f"https://{value}"
    return value.rstrip("/")


def _join_url(base_url: str, path: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    normalized_path = "/" + path.lstrip("/")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", "", ""))


def build_health_urls(host: str) -> tuple[str, str]:
    """Build the two public health URLs from an operator host name."""

    base_url = _base_url_from_host(host)
    return (
        _join_url(base_url, DEFAULT_POLICY_HEALTH_PATH),
        _join_url(base_url, DEFAULT_RELEASE_GATE_HEALTH_PATH),
    )


def _is_local_http_url(parsed: urllib.parse.ParseResult) -> bool:
    return parsed.scheme == "http" and parsed.hostname in LOCAL_HTTP_HOSTS


def _url_findings(url: str, *, allow_http_localhost: bool) -> list[dict[str, str]]:
    parsed = urllib.parse.urlparse(url)
    findings: list[dict[str, str]] = []

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return [
            {
                "code": "internal_gate_host_health_url_invalid",
                "detail": "Health URL must be absolute HTTP(S).",
            }
        ]

    if parsed.username or parsed.password:
        findings.append(
            {
                "code": "internal_gate_host_health_url_credentials_forbidden",
                "detail": "Health URL must not include userinfo or credentials.",
            }
        )

    if parsed.query or parsed.fragment:
        findings.append(
            {
                "code": "internal_gate_host_health_url_not_canonical",
                "detail": "Health URL must not include query strings or fragments.",
            }
        )

    if parsed.scheme != "https":
        if not (allow_http_localhost and _is_local_http_url(parsed)):
            findings.append(
                {
                    "code": "internal_gate_host_health_url_not_https",
                    "detail": "Hosted GPP-2 health evidence must use HTTPS.",
                }
            )

    return findings


def _sanitize_url(url: str) -> str:
    """Return ``url`` stripped of every secret-bearing component.

    Health URLs must be canonical and credential-free (``_url_findings``
    flags ``..._credentials_forbidden`` for userinfo and
    ``..._not_canonical`` for query/fragment), but the URL is still echoed
    into the evidence payload, the per-service ``service_results[].url``,
    the rendered text, the JSON output, and the persisted artifact. Any of
    userinfo (``user:password@``), the query string (``?token=...``), and
    the fragment (``#...``) can carry a secret, so all three are removed
    before the URL reaches any stored/emitted surface — a caller-supplied
    ``https://user:pw@host/p?token=SECRET#SECRET`` can never leak in clear
    text. Findings are computed from the raw URL upstream, so the
    forbidden-userinfo / not-canonical flags are preserved. A
    credential-free canonical URL is returned unchanged; non-parseable
    input is defensively stripped of userinfo, query, and fragment.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return url.split("@", 1)[-1].split("?", 1)[0].split("#", 1)[0]
    if not parsed.netloc:
        return url
    if not (parsed.username or parsed.password or parsed.query or parsed.fragment):
        return url
    host = parsed.hostname or ""
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urllib.parse.urlunparse(parsed._replace(netloc=host, query="", fragment=""))


def _is_public_https_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.hostname not in LOCAL_HTTP_HOSTS


def urllib_health_get(url: str, timeout_seconds: float) -> tuple[int, bytes]:
    """Perform one no-secret health GET request."""

    request = urllib.request.Request(url=url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), response.read(MAX_HEALTH_BODY_BYTES)
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(MAX_HEALTH_BODY_BYTES)


def _decode_json_object(body: bytes) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, {
            "code": "internal_gate_host_health_payload_invalid_json",
            "detail": f"Health response body was not JSON: {type(exc).__name__}.",
        }
    if not isinstance(payload, dict):
        return None, {
            "code": "internal_gate_host_health_payload_not_object",
            "detail": "Health response body was not a JSON object.",
        }
    return payload, None


def _probe_service(
    *,
    service: str,
    url: str,
    expected_program_id: str,
    timeout_seconds: float,
    allow_http_localhost: bool,
    transport: HealthTransport,
) -> dict[str, object]:
    findings = _url_findings(url, allow_http_localhost=allow_http_localhost)
    if findings:
        return {
            "service": service,
            "url": _sanitize_url(url),
            "status": "blocked",
            "http_status": None,
            "health_status": None,
            "program_id": None,
            "is_public_https": _is_public_https_url(url),
            "findings": findings,
        }

    try:
        status_code, body = transport(url, timeout_seconds)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        return {
            "service": service,
            "url": _sanitize_url(url),
            "status": "blocked",
            "http_status": None,
            "health_status": None,
            "program_id": None,
            "is_public_https": _is_public_https_url(url),
            "findings": [
                {
                    "code": "internal_gate_host_health_request_failed",
                    "detail": f"Health request failed: {type(exc).__name__}.",
                }
            ],
        }

    payload, decode_finding = _decode_json_object(body)
    if decode_finding is not None:
        findings.append(decode_finding)

    health_status = _safe_text(payload.get("status")) if payload is not None else None
    program_id = _safe_text(payload.get("program_id")) if payload is not None else None

    if status_code != 200:
        findings.append(
            {
                "code": "internal_gate_host_health_http_status_not_ok",
                "detail": f"Health endpoint returned HTTP {status_code}.",
            }
        )
    if health_status != "ok":
        findings.append(
            {
                "code": "internal_gate_host_health_status_not_ok",
                "detail": "Health payload did not report status=ok.",
            }
        )
    if program_id != expected_program_id:
        findings.append(
            {
                "code": "internal_gate_host_health_program_id_mismatch",
                "detail": f"Health payload did not report program_id={expected_program_id}.",
            }
        )

    return {
        "service": service,
        "url": url,
        "status": "pass" if not findings else "blocked",
        "http_status": status_code,
        "health_status": health_status,
        "program_id": program_id,
        "is_public_https": _is_public_https_url(url),
        "findings": findings,
    }


def build_evidence(
    *,
    policy_url: str,
    release_gate_url: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    allow_http_localhost: bool = False,
    transport: HealthTransport | None = None,
) -> dict[str, object]:
    """Build no-secret hosted health evidence for both internal gate services."""

    probe_transport = transport or urllib_health_get
    policy = _probe_service(
        service="live-adapter-gate-policy",
        url=policy_url,
        expected_program_id=EXPECTED_POLICY_PROGRAM_ID,
        timeout_seconds=timeout_seconds,
        allow_http_localhost=allow_http_localhost,
        transport=probe_transport,
    )
    release_gate = _probe_service(
        service="ao-release-gate",
        url=release_gate_url,
        expected_program_id=EXPECTED_RELEASE_GATE_PROGRAM_ID,
        timeout_seconds=timeout_seconds,
        allow_http_localhost=allow_http_localhost,
        transport=probe_transport,
    )

    policy_health_evidence = policy["status"] == "pass"
    release_gate_health_evidence = release_gate["status"] == "pass"
    public_https_hosting_evidence = (
        policy_health_evidence
        and release_gate_health_evidence
        and bool(policy["is_public_https"])
        and bool(release_gate["is_public_https"])
    )
    if public_https_hosting_evidence:
        status = "hosted_health_ready"
    elif policy_health_evidence and release_gate_health_evidence:
        status = "local_health_ready"
    else:
        status = "blocked"

    findings: list[dict[str, str]] = []
    for result in (policy, release_gate):
        for finding in result["findings"]:
            if isinstance(finding, dict):
                findings.append(
                    {
                        "service": str(result["service"]),
                        "code": str(finding.get("code")),
                        "detail": str(finding.get("detail")),
                    }
                )

    return {
        "schema_version": "1",
        "program_id": "GPP-2af",
        "status": status,
        "operator_owned_platform_infrastructure": True,
        "end_user_self_host_required": False,
        "policy_url": _sanitize_url(policy_url),
        "release_gate_url": _sanitize_url(release_gate_url),
        "policy_health_evidence": policy_health_evidence,
        "release_gate_health_evidence": release_gate_health_evidence,
        "public_https_hosting_evidence": public_https_hosting_evidence,
        "allow_http_localhost": allow_http_localhost,
        "secret_value_readback": False,
        "github_webhook_configured": False,
        "github_callback_post": False,
        "github_check_run_post": False,
        "branch_protection_cutover": False,
        "protected_workflow_dispatch": False,
        "live_adapter_execution": False,
        "support_widening": False,
        "production_platform_claim": False,
        "service_results": {
            "policy": policy,
            "release_gate": release_gate,
        },
        "findings": findings,
    }


def _render_text(payload: Mapping[str, object]) -> str:
    lines = [
        "Internal Gate Host Health Probe",
        f"status: {payload['status']}",
        f"policy_url: {payload['policy_url']}",
        f"release_gate_url: {payload['release_gate_url']}",
        f"policy_health_evidence: {str(payload['policy_health_evidence']).lower()}",
        f"release_gate_health_evidence: {str(payload['release_gate_health_evidence']).lower()}",
        f"public_https_hosting_evidence: {str(payload['public_https_hosting_evidence']).lower()}",
        f"secret_value_readback: {str(payload['secret_value_readback']).lower()}",
        f"github_webhook_configured: {str(payload['github_webhook_configured']).lower()}",
        f"github_callback_post: {str(payload['github_callback_post']).lower()}",
        f"github_check_run_post: {str(payload['github_check_run_post']).lower()}",
        f"branch_protection_cutover: {str(payload['branch_protection_cutover']).lower()}",
        f"protected_workflow_dispatch: {str(payload['protected_workflow_dispatch']).lower()}",
        f"live_adapter_execution: {str(payload['live_adapter_execution']).lower()}",
        f"support_widening: {str(payload['support_widening']).lower()}",
        f"production_platform_claim: {str(payload['production_platform_claim']).lower()}",
    ]
    findings = payload.get("findings", [])
    if findings:
        lines.append("findings:")
        for finding in findings:
            if isinstance(finding, dict):
                lines.append(f"- {finding.get('service')}: {finding.get('code')}: {finding.get('detail')}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--host", help="Operator gate host name or base URL.")
    source.add_argument("--policy-url", help="Hosted policy service health URL.")
    parser.add_argument("--release-gate-url", help="Hosted ao-release-gate health URL.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--artifact-path", type=Path, default=None)
    parser.add_argument("--output", choices=("json", "text"), default="json")
    parser.add_argument(
        "--allow-http-localhost",
        action="store_true",
        help="Allow http://localhost or 127.0.0.1 only for local rehearsal evidence.",
    )
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser


def _resolve_urls(args: argparse.Namespace) -> tuple[str, str]:
    if args.host:
        return build_health_urls(args.host)
    if not args.release_gate_url:
        raise ValueError("--release-gate-url is required when --policy-url is used")
    return str(args.policy_url), str(args.release_gate_url)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        policy_url, release_gate_url = _resolve_urls(args)
    except ValueError as exc:
        print(f"internal_gate_host_health_probe: {exc}", file=sys.stderr)
        return 2

    payload = build_evidence(
        policy_url=policy_url,
        release_gate_url=release_gate_url,
        timeout_seconds=args.timeout_seconds,
        allow_http_localhost=args.allow_http_localhost,
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.artifact_path is not None:
        args.artifact_path.write_text(rendered + "\n", encoding="utf-8")
    if args.output == "text":
        print(_render_text(payload))
    else:
        print(rendered)
    if args.fail_on_blocked and payload["status"] != "hosted_health_ready":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
