from __future__ import annotations

import json
from pathlib import Path

from ao_kernel._internal.secrets.provider import SecretsProvider


class VaultStubSecretsProvider(SecretsProvider):
    def __init__(self, *, secrets_path: Path) -> None:
        self._secrets_path = secrets_path

    def get(self, secret_id: str) -> str | None:
        if not self._secrets_path.exists():
            return None
        try:
            raw = json.loads(self._secrets_path.read_text(encoding="utf-8"))
        except Exception as exc:
            import logging
            logging.getLogger("ao_kernel").error(
                "secret retrieval failed for path=%s: %s", self._secrets_path, exc
            )
            return None
        if not isinstance(raw, dict):
            return None
        v = raw.get(secret_id)
        if not isinstance(v, str):
            return None
        value = v.strip()
        return value or None

