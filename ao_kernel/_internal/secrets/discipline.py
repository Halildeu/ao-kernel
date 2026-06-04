"""Secret resolution discipline for V5 Epic 2 E-2-5.

This module is the live-adapter infrastructure contract for secrets:

- resolution is environment-variable-only,
- every resolved value is added to a value-based taint set,
- every exported serialization helper redacts by taint before writing,
- regex redaction is defense-in-depth, not the primary control.

Legacy provider factory/vault helpers remain available elsewhere for older
surfaces. This module deliberately does not import or call them.
"""

from __future__ import annotations

import json
import os
import contextlib
from collections.abc import Mapping
from pathlib import Path

from ao_kernel._internal.secrets.api_key_resolver import env_names_for
from ao_kernel._internal.secrets.taint import Jsonish, SecretTaintSet


class SecretResolutionError(RuntimeError):
    """Raised when env-only secret resolution fails closed."""


class SecretSerializationError(RuntimeError):
    """Raised when a supposedly redacted payload still carries a taint."""


class SecretResolutionDiscipline:
    """Resolve secrets from env only and serialize through a taint set."""

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        taint_set: SecretTaintSet | None = None,
    ) -> None:
        self._environ = environ if environ is not None else os.environ
        self.taint_set = taint_set if taint_set is not None else SecretTaintSet()

    def resolve_env_secret(
        self,
        *,
        provider_id: str,
        env_var: str,
        required: bool = True,
    ) -> str | None:
        """Resolve exactly one env var and add its value to the taint set."""

        name = _validate_env_name(env_var)
        raw = self._environ.get(name, "")
        value = raw.strip() if isinstance(raw, str) else ""
        if not value:
            if required:
                raise SecretResolutionError(f"required env secret {name!r} is missing")
            return None
        self.taint_set.add(provider_id, value)
        return value

    def resolve_provider_api_key(self, provider_id: str, *, required: bool = True) -> str | None:
        """Resolve a provider API key from accepted env names only.

        Unlike ``resolve_api_key`` this function does not consult the secrets
        factory, vault stubs, MCP params, argv, stdin, files, or HTTP headers.
        """

        missing: list[str] = []
        for env_var in env_names_for(provider_id):
            try:
                return self.resolve_env_secret(provider_id=provider_id, env_var=env_var, required=True)
            except SecretResolutionError:
                missing.append(env_var)
        if required:
            joined = ", ".join(missing)
            raise SecretResolutionError(f"required env secret for provider {provider_id!r} is missing ({joined})")
        return None

    def invalidate(self, provider_id: str) -> None:
        """Clear taints for one provider after secret rotation."""

        self.taint_set.remove_provider(provider_id)

    def redact_payload(self, payload: Jsonish) -> Jsonish:
        """Return a deep-redacted copy of a JSON-like payload."""

        return self.taint_set.scan_and_redact(payload)

    def serialize_json(self, payload: Jsonish, *, indent: int | None = None) -> str:
        """Redact and serialize a JSON-like payload."""

        redacted = self.redact_payload(payload)
        encoded = json.dumps(
            redacted,
            ensure_ascii=False,
            sort_keys=True,
            separators=None if indent else (",", ":"),
            indent=indent,
        )
        self.assert_no_taint(encoded)
        return encoded

    def serialize_json_line(self, payload: Jsonish) -> str:
        """Redact and serialize one JSONL line."""

        return self.serialize_json(payload) + "\n"

    def safe_log_line(self, text: str) -> str:
        """Redact a free-text log line and fail closed if taint remains."""

        redacted = self.taint_set.redact_text(text)
        self.assert_no_taint(redacted)
        return redacted

    def write_json(self, path: Path, payload: Jsonish, *, indent: int = 2) -> None:
        """Redact, serialize, and write one JSON artifact with private mode."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.serialize_json(payload, indent=indent) + "\n", encoding="utf-8")
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)

    def append_jsonl(self, path: Path, payload: Jsonish) -> None:
        """Redact, serialize, and append one JSONL artifact with private mode."""

        path.parent.mkdir(parents=True, exist_ok=True)
        line = self.serialize_json_line(payload).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)

    def assert_no_taint(self, serialized: str) -> None:
        """Fail closed if a tracked secret remains in serialized output."""

        if self.taint_set.contains(serialized):
            raise SecretSerializationError("serialized output still contains a resolved secret value")


def _validate_env_name(env_var: str) -> str:
    name = str(env_var).strip()
    if not name or not name.replace("_", "").isalnum() or name[0].isdigit():
        raise ValueError(f"invalid env secret name: {env_var!r}")
    return name


def create_env_secret_discipline(
    *,
    environ: Mapping[str, str] | None = None,
    taint_set: SecretTaintSet | None = None,
) -> SecretResolutionDiscipline:
    """Factory for the env-only secret discipline."""

    return SecretResolutionDiscipline(environ=environ, taint_set=taint_set)


__all__ = [
    "SecretResolutionDiscipline",
    "SecretResolutionError",
    "SecretSerializationError",
    "create_env_secret_discipline",
]
