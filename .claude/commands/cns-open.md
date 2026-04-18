---
description: Scaffold a new Codex consultation request + open MCP thread
argument-hint: <short-topic> [:: question body]
allowed-tools: Bash(ls:*), Bash(git rev-parse:*), Bash(date:*), Bash(wc:*), Read, Write
---

You are opening a new **Codex consultation (CNS)**. The user invoked `/cns-open` with `$ARGUMENTS`.

Input parsing:
- If `$ARGUMENTS` contains `::`, split on first `::` — left = topic slug (snake_case), right = question body.
- Otherwise `$ARGUMENTS` is the topic; ask the user for the question body in one line.
- If `$ARGUMENTS` is empty, ask the user for both topic and body.

## Steps (execute in order, no extra user confirmation)

1. **Compute next CNS id** for today:
   ```bash
   ls .ao/consultations/requests/ 2>/dev/null | grep -E "^CNS-$(date +%Y%m%d)-[0-9]{3}" | sed -E 's/^CNS-[0-9]{8}-([0-9]{3}).*/\1/' | sort -u | tail -1
   ```
   If empty → `001`. Otherwise zero-pad increment (max+1).
2. **Git state**: `git rev-parse --abbrev-ref HEAD` (branch), `git rev-parse --short HEAD` (head_sha).
3. **Timestamp**: `date -u +"%Y-%m-%dT%H:%M:%S+03:00"` (Istanbul tz per project convention).
4. **Write** `.ao/consultations/requests/CNS-YYYYMMDD-NNN.request.v1.json` with the following shape (mirror the latest existing request for field order and style):
   ```json
   {
     "version": "v1",
     "consultation_id": "CNS-YYYYMMDD-NNN",
     "status": "OPEN",
     "iteration": 1,
     "from_agent": "claude",
     "to_agent": "codex",
     "transport": "mcp",
     "topic": "<topic_slug>",
     "mode": "adversarial_plan_review",
     "question": {
       "title": "<short topic human-readable>",
       "body": "<question body>"
     },
     "created_at": "<iso8601>",
     "branch": "<branch>",
     "head_sha": "<short-sha>"
   }
   ```
5. **Open Codex MCP thread** via `mcp__codex__codex`:
   - `prompt`: the question body (prepend 1-line context: "Consultation <id> — <topic>\n\n" then body)
   - `sandbox`: `"read-only"` (default plan-time istişare)
   - `approval-policy`: `"never"`
   - `model`: Codex default
6. **Capture `threadId`** from the Codex response and append `"mcp_thread_id": "<threadId>"` to the JSON file (use Edit, not full rewrite).
7. **Report to the user** (Türkçe, kısa):
   - CNS id
   - Topic
   - Branch + head_sha
   - Codex thread id
   - First Codex response (özet 2-3 cümle) or "clarify istedi: <soru>"

## Post-open behavior

- If Codex returns a clarifying question, decide based on global CLAUDE.md "MCP iterate" vs "yeni thread" heuristics. Default: `codex-reply` with the clarification answer if within current topic scope.
- Thread id SHOULD be saved to memory for later `codex-reply` continuity if the consultation is expected to span multiple sessions.

## Guardrails

- **Never overwrite** an existing request file. If the computed id already exists, increment until free (collision = concurrent CNS open, extremely rare).
- **Don't commit** the request JSON as part of this command — commits are explicit per `feedback_proactive_execution.md` / user preference.
- If the user explicitly types `exec` / `CLI` / `script` mode, fall back to the `codex exec -C . -o .../responses/<id>.codex.response.v1.json "..."` pattern per project CLAUDE.md §15.
