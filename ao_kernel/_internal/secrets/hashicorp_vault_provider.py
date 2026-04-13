"""HashiCorp Vault secrets provider — KV v2 HTTP API integration.

Reads secrets from HashiCorp Vault via HTTP. Requires:
    VAULT_ADDR: Vault server address (e.g., https://vault.example.com)
    VAULT_TOKEN: Authentication token

secret_id format: "path/to/secret/key_name"
    e.g., "openai/api-key" → GET /v1/secret/data/openai → data.data["api-key"]
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError

from ao_kernel._internal.secrets.provider import SecretsProvider


class HashiCorpVaultProvider(SecretsProvider):
    """HashiCorp Vault KV v2 secrets provider."""

    def __init__(
        self,
        *,
        vault_addr: str = "",
        vault_token: str = "",
        secret_mount: str = "secret",
        timeout_seconds: float = 5.0,
    ) -> None:
        self._vault_addr = (vault_addr or os.environ.get("VAULT_ADDR", "")).strip().rstrip("/")
        self._vault_token = (vault_token or os.environ.get("VAULT_TOKEN", "")).strip()
        self._secret_mount = secret_mount or os.environ.get("VAULT_SECRET_MOUNT", "secret")
        self._timeout = timeout_seconds

    def get(self, secret_id: str) -> str | None:
        """Retrieve secret from Vault KV v2.

        secret_id format: "path/key_name" where path is the secret path
        and key_name is the JSON key within the secret data.
        Returns None if not found, misconfigured, or on any error.
        """
        if not secret_id or "/" not in secret_id:
            return None
        if not self._vault_addr or not self._vault_token:
            return None

        path, key_name = secret_id.rsplit("/", 1)
        if not path or not key_name:
            return None

        url = f"{self._vault_addr}/v1/{self._secret_mount}/data/{path}"
        req = Request(url, method="GET")
        req.add_header("X-Vault-Token", self._vault_token)
        req.add_header("Accept", "application/json")

        try:
            with urlopen(req, timeout=self._timeout) as resp:
                body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except (URLError, json.JSONDecodeError, OSError):
            return None

        secret_data = body.get("data", {})
        if isinstance(secret_data, dict):
            secret_data = secret_data.get("data", secret_data)

        if not isinstance(secret_data, dict):
            return None

        value = secret_data.get(key_name)
        if isinstance(value, str):
            return value.strip() or None
        return None
