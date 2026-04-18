#!/usr/bin/env bash
# PostToolUse hook — auto-format Python files after Write/Edit.
#
# Reads the tool-event JSON from stdin, extracts tool_input.file_path,
# and if it is a .py file inside ao_kernel/ or tests/, runs
#   ruff check --fix --quiet   (apply fixable lint)
#   ruff format --quiet         (canonicalise formatting)
#
# Exit 0 always — this hook never blocks Claude's subsequent actions.
# Ruff failures are logged via stderr but not surfaced as hook errors.

set +e

INPUT="$(cat)"

# Extract file_path (Write + Edit both expose tool_input.file_path).
FILE_PATH="$(
  python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)
path = (d.get("tool_input") or {}).get("file_path") or ""
print(path)
' <<<"$INPUT" 2>/dev/null
)"

[ -z "$FILE_PATH" ] && exit 0
[[ "$FILE_PATH" != *.py ]] && exit 0

# Only touch project code: ao_kernel/ or tests/. Skip scripts/, docs/, etc.
case "$FILE_PATH" in
  */ao_kernel/*|*/tests/*) ;;
  *) exit 0 ;;
esac

# Require ruff on PATH — silently no-op if missing (e.g. devcontainer mismatch).
command -v ruff >/dev/null 2>&1 || exit 0

ruff check --fix --quiet "$FILE_PATH" >/dev/null 2>&1
ruff format --quiet "$FILE_PATH" >/dev/null 2>&1

exit 0
