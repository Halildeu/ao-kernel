"""Production telemetry tunables (Epic 5 E-5-1).

Environment-driven configuration for OTEL exporter, sampling rate, batch size,
service name, and resource attributes. Pure-stdlib (no `opentelemetry` import
at module level; lazy validation only). All knobs opt-in via env vars; default
behavior is identical to v4.x (lazy import + no-op fallback per ADR D12).

Public API:
    load_production_config() -> ProductionTelemetryConfig
    ProductionTelemetryConfig (dataclass)
    SAMPLING_RATE_MIN / SAMPLING_RATE_MAX constants
    BATCH_SIZE_MIN / BATCH_SIZE_MAX constants

Environment variables (all optional):
    AO_KERNEL_OTEL_ENABLED              — "true"/"false" (default false)
    AO_KERNEL_OTEL_EXPORTER_OTLP_ENDPOINT — OTLP collector URL (required if enabled)
    AO_KERNEL_OTEL_SAMPLING_RATE        — float 0.0-1.0 (default 1.0)
    AO_KERNEL_OTEL_BATCH_SIZE           — int 1-10000 (default 512)
    AO_KERNEL_OTEL_SERVICE_NAME         — string (default "ao-kernel")
    AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES  — "k1=v1,k2=v2" CSV (default empty)
    AO_KERNEL_OTEL_INSECURE             — "true"/"false" (default false, TLS required)
    AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS    — int milliseconds (default 30000)
    AO_KERNEL_OTEL_HEADERS              — "k1=v1,k2=v2" CSV (default empty; e.g. auth tokens)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional


# Bounds (Codex iter-1 hardening: explicit min/max enforce fail-closed range)
SAMPLING_RATE_MIN = 0.0
SAMPLING_RATE_MAX = 1.0
BATCH_SIZE_MIN = 1
BATCH_SIZE_MAX = 10000
EXPORT_TIMEOUT_MS_MIN = 100
EXPORT_TIMEOUT_MS_MAX = 600_000  # 10 min hard upper bound

DEFAULT_SERVICE_NAME = "ao-kernel"
DEFAULT_SAMPLING_RATE = 1.0
DEFAULT_BATCH_SIZE = 512
DEFAULT_EXPORT_TIMEOUT_MS = 30_000


class TelemetryConfigError(ValueError):
    """Raised when an env-var value is malformed or out of range."""


@dataclass(frozen=True)
class ProductionTelemetryConfig:
    """Frozen production telemetry configuration."""

    enabled: bool = False
    exporter_otlp_endpoint: Optional[str] = None
    sampling_rate: float = DEFAULT_SAMPLING_RATE
    batch_size: int = DEFAULT_BATCH_SIZE
    service_name: str = DEFAULT_SERVICE_NAME
    # Codex iter-1 absorb: frozen=True is shallow. Wrap dict fields in
    # MappingProxyType so the public surface is a read-only view (mutating
    # cfg.resource_attributes["k"] = "v" raises TypeError).
    resource_attributes: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    insecure: bool = False
    export_timeout_ms: int = DEFAULT_EXPORT_TIMEOUT_MS
    headers: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "exporter_otlp_endpoint": self.exporter_otlp_endpoint,
            "sampling_rate": self.sampling_rate,
            "batch_size": self.batch_size,
            "service_name": self.service_name,
            "resource_attributes": dict(self.resource_attributes),
            "insecure": self.insecure,
            "export_timeout_ms": self.export_timeout_ms,
            # Redact header values for audit safety (Codex would catch this otherwise).
            "headers": {k: "<redacted>" for k in self.headers},
        }


def _parse_bool(value: str, *, env_name: str) -> bool:
    v = value.strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off", ""):
        return False
    raise TelemetryConfigError(f"{env_name}: invalid boolean {value!r}; expected true/false/1/0/yes/no")


def _parse_float_in_range(value: str, *, env_name: str, lo: float, hi: float) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise TelemetryConfigError(f"{env_name}: cannot parse {value!r} as float") from exc
    if parsed < lo or parsed > hi:
        raise TelemetryConfigError(f"{env_name}: {parsed} out of range [{lo}, {hi}]")
    return parsed


def _parse_int_in_range(value: str, *, env_name: str, lo: int, hi: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise TelemetryConfigError(f"{env_name}: cannot parse {value!r} as int") from exc
    if parsed < lo or parsed > hi:
        raise TelemetryConfigError(f"{env_name}: {parsed} out of range [{lo}, {hi}]")
    return parsed


def _redact_pair_for_error(pair: str, *, sensitive: bool) -> str:
    """Codex iter-1 absorb: when env_name suggests sensitive content
    (headers/tokens), the raw value half of a malformed CSV pair MUST NOT
    appear in error messages — even malformed entries may carry auth tokens.
    """
    if not sensitive:
        return repr(pair)
    if "=" in pair:
        k, _ = pair.split("=", 1)
        return repr(f"{k}=<redacted>")
    return repr("<redacted>")


def _parse_csv_kv(value: str, *, env_name: str) -> dict[str, str]:
    """Parse `k1=v1,k2=v2` CSV. Empty value → empty dict.

    Codex iter-1 absorb: HEADERS env-var values may contain auth tokens.
    Malformed entries are redacted in exception messages so a stack trace
    cannot leak the raw token.
    """
    if not value.strip():
        return {}
    sensitive = "HEADERS" in env_name.upper()
    result: dict[str, str] = {}
    for pair in value.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise TelemetryConfigError(
                f"{env_name}: malformed entry {_redact_pair_for_error(pair, sensitive=sensitive)}; expected key=value"
            )
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise TelemetryConfigError(
                f"{env_name}: empty key in entry {_redact_pair_for_error(pair, sensitive=sensitive)}"
            )
        result[k] = v
    return result


def load_production_config(*, environ: Optional[dict[str, str]] = None) -> ProductionTelemetryConfig:
    """Build ProductionTelemetryConfig from environment.

    Args:
        environ: dict mapping env-var name → value (default: os.environ).
                 Useful for deterministic tests.

    Raises:
        TelemetryConfigError: when a knob's value is malformed or out of range,
            or when enabled=True but exporter endpoint is missing/empty.
    """
    env = environ if environ is not None else os.environ

    enabled = _parse_bool(env.get("AO_KERNEL_OTEL_ENABLED", "false"), env_name="AO_KERNEL_OTEL_ENABLED")
    endpoint = env.get("AO_KERNEL_OTEL_EXPORTER_OTLP_ENDPOINT", "").strip() or None
    sampling_rate = _parse_float_in_range(
        env.get("AO_KERNEL_OTEL_SAMPLING_RATE", str(DEFAULT_SAMPLING_RATE)),
        env_name="AO_KERNEL_OTEL_SAMPLING_RATE",
        lo=SAMPLING_RATE_MIN,
        hi=SAMPLING_RATE_MAX,
    )
    batch_size = _parse_int_in_range(
        env.get("AO_KERNEL_OTEL_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)),
        env_name="AO_KERNEL_OTEL_BATCH_SIZE",
        lo=BATCH_SIZE_MIN,
        hi=BATCH_SIZE_MAX,
    )
    service_name = env.get("AO_KERNEL_OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME).strip()
    if not service_name:
        service_name = DEFAULT_SERVICE_NAME
    resource_attributes = _parse_csv_kv(
        env.get("AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES", ""),
        env_name="AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES",
    )
    insecure = _parse_bool(
        env.get("AO_KERNEL_OTEL_INSECURE", "false"),
        env_name="AO_KERNEL_OTEL_INSECURE",
    )
    export_timeout_ms = _parse_int_in_range(
        env.get("AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS", str(DEFAULT_EXPORT_TIMEOUT_MS)),
        env_name="AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS",
        lo=EXPORT_TIMEOUT_MS_MIN,
        hi=EXPORT_TIMEOUT_MS_MAX,
    )
    headers = _parse_csv_kv(
        env.get("AO_KERNEL_OTEL_HEADERS", ""),
        env_name="AO_KERNEL_OTEL_HEADERS",
    )

    # Enabled but no endpoint → fail-closed.
    if enabled and not endpoint:
        raise TelemetryConfigError(
            "AO_KERNEL_OTEL_ENABLED=true but AO_KERNEL_OTEL_EXPORTER_OTLP_ENDPOINT empty; "
            "production telemetry requires explicit OTLP endpoint"
        )

    # Insecure transport sanity: in production, endpoint should start with `https://`
    # unless insecure=True was explicitly set. We do not block here (CI/dev may
    # use http://localhost:4317), but document the contract; downstream OTEL
    # exporter SDK enforces actual TLS.

    return ProductionTelemetryConfig(
        enabled=enabled,
        exporter_otlp_endpoint=endpoint,
        sampling_rate=sampling_rate,
        batch_size=batch_size,
        service_name=service_name,
        resource_attributes=MappingProxyType(dict(resource_attributes)),
        insecure=insecure,
        export_timeout_ms=export_timeout_ms,
        headers=MappingProxyType(dict(headers)),
    )
