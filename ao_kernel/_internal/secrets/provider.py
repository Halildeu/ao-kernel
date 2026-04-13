from __future__ import annotations


class SecretsProvider:
    def get(self, secret_id: str) -> str | None:
        raise NotImplementedError

