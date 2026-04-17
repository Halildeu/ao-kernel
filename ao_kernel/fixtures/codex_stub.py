"""Deterministic in-process stub adapter for CI + demos.

Exercises the ``agent-adapter-contract.schema.v1.json`` CLI transport
without requiring an LLM provider. Reads the prompt (from ``--prompt-file``
or stdin depending on ``--stdin-mode``) and emits a canonical
``output_envelope`` JSON on stdout.

Invocation (matches ``codex-stub.manifest.v1.json`` fixture):

    python3 -m ao_kernel.fixtures.codex_stub --run-id <uuid>
                                              [--prompt-file <path>]
                                              [--stdin-mode none|prompt_only|multipart]

Output (stdout; single line JSON):

    {"status":"ok","diff":"--- a/x\\n+++ b/x\\n@@ -1 +1 @@\\n-old\\n+new\\n",
     "commands_executed":[],
     "evidence_events":[],
     "finish_reason":"normal",
     "cost_actual":{"tokens_input":0,"tokens_output":0,"time_seconds":0.0},
     "review_findings":{"schema_version":"1","findings":[],
                        "summary":"codex-stub: deterministic review (no issues)."}}

The bundled manifest ``ao_kernel/defaults/adapters/codex-stub.manifest.v1.json``
advertises the ``review_findings`` capability and pins an
``output_parse`` rule pointing at ``review-findings.schema.v1.json``.
The rule walker in ``adapter_invoker._walk_output_parse`` extracts
``$.review_findings`` on every invocation, so the stub always emits
a schema-valid (empty findings) payload — bundled-path invocations
never fail with ``output_parse_failed``. The payload is trivially
valid; the stub does not actually review anything.

Exit code ``0`` on success; non-zero reserved for simulated crashes
(test fixtures may configure alternate behaviour via env vars).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_CANNED_DIFF = (
    "--- a/hello.txt\n"
    "+++ b/hello.txt\n"
    "@@ -1 +1 @@\n"
    "-hello\n"
    "+hello world\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex_stub",
        description=(
            "Deterministic CLI adapter stub used by ao-kernel demos "
            "and integration tests."
        ),
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt-file", required=False)
    parser.add_argument(
        "--stdin-mode",
        choices=["none", "prompt_only", "multipart"],
        default="none",
    )
    args = parser.parse_args(argv)

    # Read prompt per stdin_mode (deterministic stub ignores content
    # but drains stdin to play nicely with subprocess pipes).
    if args.stdin_mode == "prompt_only":
        _ = sys.stdin.read()
    elif args.stdin_mode == "multipart":
        try:
            json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            pass
    elif args.prompt_file:
        try:
            _ = Path(args.prompt_file).read_text(encoding="utf-8")
        except OSError:
            pass

    # Deterministic: the stub ignores prompt content and always emits
    # the canned diff + an empty-findings review payload. The latter
    # keeps the bundled output_parse rule green end-to-end on every
    # invocation without the stub needing to do any actual reviewing.
    envelope = {
        "status": "ok",
        "diff": _CANNED_DIFF,
        "commands_executed": [],
        "evidence_events": [],
        "finish_reason": "normal",
        "cost_actual": {
            "tokens_input": 0,
            "tokens_output": 0,
            "time_seconds": 0.0,
        },
        "review_findings": {
            "schema_version": "1",
            "findings": [],
            "summary": "codex-stub: deterministic review (no issues).",
        },
        # PR-B6: commit_message capability — object-shape payload so
        # adapter_invoker._walk_output_parse Mapping check accepts the
        # value. Deterministic placeholder subject; operator downstream
        # applies the actual git commit (ao-kernel never runs git commit).
        "commit_message": {
            "schema_version": "1",
            "subject": "chore: codex-stub deterministic commit",
            "body": "",
            "breaking_change": False,
            "trailers": [],
        },
    }
    sys.stdout.write(json.dumps(envelope))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
