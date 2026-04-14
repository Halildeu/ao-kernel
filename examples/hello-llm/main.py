"""hello-llm — one governed LLM call, end to end.

Run with:
    cp .env.example .env && $EDITOR .env  # set OPENAI_API_KEY
    pip install -r requirements.txt
    python main.py

See README.md for switching providers and troubleshooting.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ── Pick your provider here ──────────────────────────────────────────
# See README.md "Switching providers" for the full table.
PROVIDER_ID = "openai"
MODEL = "gpt-4o-mini"
API_KEY_ENV = "OPENAI_API_KEY"

# ── Load .env if present (keeps us dependency-free) ──────────────────

def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Do not override something the shell already set
        os.environ.setdefault(key, value)


def main() -> int:
    here = Path(__file__).resolve().parent
    _load_dotenv(here / ".env")

    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        print(
            f"✗ {API_KEY_ENV} is not set.\n"
            f"  Copy .env.example to .env and paste your key, or export {API_KEY_ENV} manually.",
            file=sys.stderr,
        )
        return 2

    # Import here so --help-style checks do not require ao-kernel installed yet.
    from ao_kernel import AoKernelClient

    # workspace_root="." means: create/use .ao/ in the current directory.
    with AoKernelClient(workspace_root=str(here)) as client:
        print(f"✓ Workspace initialized at: {here}")

        session_id = client.start_session()
        print(f"✓ Session started: {session_id}")

        result = client.llm_call(
            messages=[
                {"role": "system", "content": "Answer concisely, one sentence."},
                {"role": "user", "content": "What is the Python programming language?"},
            ],
            provider_id=PROVIDER_ID,
            model=MODEL,
            api_key=api_key,
            intent="FAST_TEXT",
        )

        print("✓ LLM call complete")
        print(f"  provider_id : {result.get('provider_id')}")
        print(f"  model       : {result.get('model')}")
        print(f"  status      : {result.get('status')}")

        # Some paths set 'text', others embed under 'response' — handle both.
        text = result.get("text") or result.get("response", "")
        if text:
            print(f"  text        : {text.strip()[:200]}")

        usage = result.get("usage") or {}
        if usage:
            print(f"  tokens_in   : {usage.get('prompt_tokens', usage.get('input_tokens', '?'))}")
            print(f"  tokens_out  : {usage.get('completion_tokens', usage.get('output_tokens', '?'))}")

        # Policy decision (shown when denied)
        decision = result.get("decision")
        if decision and decision not in ("allow", "executed"):
            print(f"  decision    : {decision}")
            print(f"  reasons     : {result.get('reason_codes', [])}")

        client.end_session()
        print("✓ Session ended cleanly")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
