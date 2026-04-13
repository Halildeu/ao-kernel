from __future__ import annotations

import abc


class SecretsProvider(abc.ABC):
    """Abstract base for secrets providers. Subclasses must implement get()."""

    @abc.abstractmethod
    def get(self, secret_id: str) -> str | None: ...

