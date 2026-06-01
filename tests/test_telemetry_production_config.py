"""Production telemetry config invariants (Epic 5 E-5-1)."""

from __future__ import annotations

import pytest

from ao_kernel.telemetry_config import (
    BATCH_SIZE_MAX,
    BATCH_SIZE_MIN,
    DEFAULT_BATCH_SIZE,
    DEFAULT_EXPORT_TIMEOUT_MS,
    DEFAULT_SAMPLING_RATE,
    DEFAULT_SERVICE_NAME,
    EXPORT_TIMEOUT_MS_MAX,
    EXPORT_TIMEOUT_MS_MIN,
    SAMPLING_RATE_MAX,
    SAMPLING_RATE_MIN,
    TelemetryConfigError,
    load_production_config,
)


# ---- Defaults (no env vars set) ----


def test_load_with_empty_env_returns_defaults():
    cfg = load_production_config(environ={})
    assert cfg.enabled is False
    assert cfg.exporter_otlp_endpoint is None
    assert cfg.sampling_rate == DEFAULT_SAMPLING_RATE
    assert cfg.batch_size == DEFAULT_BATCH_SIZE
    assert cfg.service_name == DEFAULT_SERVICE_NAME
    assert cfg.resource_attributes == {}
    assert cfg.insecure is False
    assert cfg.export_timeout_ms == DEFAULT_EXPORT_TIMEOUT_MS
    assert cfg.headers == {}


def test_load_default_disabled_is_zero_cost_path():
    """When enabled=False, no endpoint requirement; ready to be no-op."""
    cfg = load_production_config(environ={})
    assert not cfg.enabled
    assert cfg.exporter_otlp_endpoint is None


# ---- Enabled + endpoint ----


def test_enabled_requires_endpoint():
    with pytest.raises(TelemetryConfigError, match="endpoint"):
        load_production_config(environ={"AO_KERNEL_OTEL_ENABLED": "true"})


def test_enabled_with_endpoint_succeeds():
    cfg = load_production_config(
        environ={
            "AO_KERNEL_OTEL_ENABLED": "true",
            "AO_KERNEL_OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example.com:4317",
        }
    )
    assert cfg.enabled
    assert cfg.exporter_otlp_endpoint == "https://otel.example.com:4317"


# ---- Boolean parsing ----


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
    ],
)
def test_bool_parsing_accepted(value, expected):
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_INSECURE": value})
    assert cfg.insecure is expected


def test_bool_parsing_rejects_garbage():
    with pytest.raises(TelemetryConfigError, match="boolean"):
        load_production_config(environ={"AO_KERNEL_OTEL_INSECURE": "maybe"})


# ---- Sampling rate ----


def test_sampling_rate_default_is_full_capture():
    cfg = load_production_config(environ={})
    assert cfg.sampling_rate == 1.0


def test_sampling_rate_zero_disables():
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_SAMPLING_RATE": "0"})
    assert cfg.sampling_rate == 0.0


def test_sampling_rate_below_min_rejected():
    with pytest.raises(TelemetryConfigError, match="out of range"):
        load_production_config(environ={"AO_KERNEL_OTEL_SAMPLING_RATE": "-0.1"})


def test_sampling_rate_above_max_rejected():
    with pytest.raises(TelemetryConfigError, match="out of range"):
        load_production_config(environ={"AO_KERNEL_OTEL_SAMPLING_RATE": "1.5"})


def test_sampling_rate_non_numeric_rejected():
    with pytest.raises(TelemetryConfigError, match="float"):
        load_production_config(environ={"AO_KERNEL_OTEL_SAMPLING_RATE": "half"})


# ---- Batch size ----


def test_batch_size_in_range():
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_BATCH_SIZE": "1024"})
    assert cfg.batch_size == 1024


def test_batch_size_below_min_rejected():
    with pytest.raises(TelemetryConfigError, match="out of range"):
        load_production_config(environ={"AO_KERNEL_OTEL_BATCH_SIZE": "0"})


def test_batch_size_above_max_rejected():
    with pytest.raises(TelemetryConfigError, match="out of range"):
        load_production_config(environ={"AO_KERNEL_OTEL_BATCH_SIZE": str(BATCH_SIZE_MAX + 1)})


def test_batch_size_float_rejected():
    with pytest.raises(TelemetryConfigError, match="int"):
        load_production_config(environ={"AO_KERNEL_OTEL_BATCH_SIZE": "100.5"})


# ---- Export timeout ----


def test_export_timeout_in_range():
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS": "60000"})
    assert cfg.export_timeout_ms == 60000


def test_export_timeout_above_10min_rejected():
    """10 minutes hard upper bound (defense vs. runaway exporter waits)."""
    with pytest.raises(TelemetryConfigError, match="out of range"):
        load_production_config(environ={"AO_KERNEL_OTEL_EXPORT_TIMEOUT_MS": str(EXPORT_TIMEOUT_MS_MAX + 1)})


# ---- Service name ----


def test_service_name_defaults_to_ao_kernel():
    cfg = load_production_config(environ={})
    assert cfg.service_name == "ao-kernel"


def test_service_name_override():
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_SERVICE_NAME": "custom-service"})
    assert cfg.service_name == "custom-service"


def test_service_name_empty_falls_back_to_default():
    """Empty env var → DEFAULT (not empty string)."""
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_SERVICE_NAME": ""})
    assert cfg.service_name == DEFAULT_SERVICE_NAME


# ---- Resource attributes (CSV k=v) ----


def test_resource_attributes_csv_parse():
    cfg = load_production_config(
        environ={"AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": "deployment=prod,region=eu-west,team=core"}
    )
    assert cfg.resource_attributes == {
        "deployment": "prod",
        "region": "eu-west",
        "team": "core",
    }


def test_resource_attributes_empty_returns_empty_dict():
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": ""})
    assert cfg.resource_attributes == {}


def test_resource_attributes_malformed_pair_rejected():
    """Malformed `k=v` pair → fail-closed."""
    with pytest.raises(TelemetryConfigError, match="key=value"):
        load_production_config(environ={"AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": "deployment=prod,malformed"})


def test_resource_attributes_empty_key_rejected():
    with pytest.raises(TelemetryConfigError, match="empty key"):
        load_production_config(environ={"AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": "=value"})


# ---- Headers (sensitive — redaction) ----


def test_headers_parse():
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_HEADERS": "X-Custom-Header=value-one,X-API-Key=other"})
    assert cfg.headers == {
        "X-Custom-Header": "value-one",
        "X-API-Key": "other",
    }


def test_to_dict_redacts_header_values():
    """Codex-style review: header values may carry tokens — redact in serialization."""
    sentinel_value = "FIXTURE-VALUE-XYZ-789"
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_HEADERS": f"X-Sentinel={sentinel_value}"})
    serialized = cfg.to_dict()
    assert serialized["headers"] == {"X-Sentinel": "<redacted>"}
    # Field still present (key name) but value redacted
    assert sentinel_value not in str(serialized)


# ---- Dataclass immutability ----


def test_config_is_frozen():
    cfg = load_production_config(environ={})
    with pytest.raises((AttributeError, Exception)):
        cfg.enabled = True  # type: ignore[misc]


def test_config_dict_fields_are_truly_immutable():
    """Codex iter-1 absorb: frozen=True is shallow; MUST also prevent dict
    mutation on resource_attributes + headers.
    """
    cfg = load_production_config(
        environ={
            "AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": "k=v",
            "AO_KERNEL_OTEL_HEADERS": "Authorization=X-Custom-Scheme value-two",
        }
    )
    with pytest.raises(TypeError):
        cfg.resource_attributes["mutated"] = "yes"  # type: ignore[index]
    with pytest.raises(TypeError):
        cfg.headers["mutated"] = "yes"  # type: ignore[index]


def test_headers_malformed_entry_does_not_leak_value_in_error():
    """Codex iter-1 absorb: malformed AO_KERNEL_OTEL_HEADERS error message
    MUST redact the raw value half — even malformed entries can carry tokens.
    """
    leaked_token = "REDACT_TEST_FIXTURE_VALUE_001"
    with pytest.raises(TelemetryConfigError) as exc_info:
        load_production_config(environ={"AO_KERNEL_OTEL_HEADERS": f"k=v,{leaked_token}"})
    assert leaked_token not in str(exc_info.value)


def test_headers_empty_key_does_not_leak_value_in_error():
    """Empty-key path also redacts."""
    leaked_token = "REDACT_TEST_FIXTURE_VALUE_002"
    with pytest.raises(TelemetryConfigError) as exc_info:
        load_production_config(environ={"AO_KERNEL_OTEL_HEADERS": f"={leaked_token}"})
    assert leaked_token not in str(exc_info.value)


def test_resource_attributes_malformed_entry_still_shows_value():
    """Resource attributes are NOT sensitive; error keeps raw entry for
    operator debugging. Codex iter-1: redaction is HEADERS-only.
    """
    with pytest.raises(TelemetryConfigError) as exc_info:
        load_production_config(environ={"AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": "deployment=prod,malformed"})
    assert "malformed" in str(exc_info.value)


# ---- to_dict integrity ----


def test_to_dict_includes_all_fields():
    cfg = load_production_config(environ={})
    d = cfg.to_dict()
    for key in (
        "enabled",
        "exporter_otlp_endpoint",
        "sampling_rate",
        "batch_size",
        "service_name",
        "resource_attributes",
        "insecure",
        "export_timeout_ms",
        "headers",
    ):
        assert key in d


def test_to_dict_does_not_leak_environ_reference():
    """Defensive: to_dict copies resource_attributes (mutation of return doesn't
    affect internal state).
    """
    cfg = load_production_config(environ={"AO_KERNEL_OTEL_RESOURCE_ATTRIBUTES": "k=v"})
    d = cfg.to_dict()
    d["resource_attributes"]["mutated"] = "yes"
    # Internal state still has only original k
    assert cfg.resource_attributes == {"k": "v"}


# ---- Bound constants surface ----


def test_bounds_are_documented():
    assert SAMPLING_RATE_MIN == 0.0
    assert SAMPLING_RATE_MAX == 1.0
    assert BATCH_SIZE_MIN >= 1
    assert BATCH_SIZE_MAX >= 1000
    assert EXPORT_TIMEOUT_MS_MIN >= 1
    assert EXPORT_TIMEOUT_MS_MAX <= 600_000  # 10 min cap
