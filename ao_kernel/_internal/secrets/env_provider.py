from __future__ import annotations

import os
from collections.abc import Mapping

from ao_kernel._internal.secrets.provider import SecretsProvider

_SECRET_ID_TO_ENV: dict[str, str] = {
    "OPENAI_API_KEY": "OPENAI_API_KEY",
}


class EnvSecretsProvider(SecretsProvider):
    def __init__(self, *, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def get(self, secret_id: str) -> str | None:
        env_var = _SECRET_ID_TO_ENV.get(secret_id)
        if not env_var:
            return None
        raw = self._environ.get(env_var, "")
        value = raw.strip() if isinstance(raw, str) else ""
        return value or None

