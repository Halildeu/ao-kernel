from __future__ import annotations

import os
from collections.abc import Mapping

from ao_kernel._internal.secrets.provider import SecretsProvider

# Canonical secret IDs are the env variable names themselves. Callers pass
# ``OPENAI_API_KEY`` and the provider returns ``os.environ["OPENAI_API_KEY"]``.
# Keeping the map explicit (rather than identity) lets future providers route
# through alternative env names without breaking existing callers.
_SECRET_ID_TO_ENV: dict[str, str] = {
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY": "CLAUDE_API_KEY",
    "GOOGLE_API_KEY": "GOOGLE_API_KEY",
    "GEMINI_API_KEY": "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY": "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY": "DASHSCOPE_API_KEY",
    "QWEN_API_KEY": "QWEN_API_KEY",
    "XAI_API_KEY": "XAI_API_KEY",
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

