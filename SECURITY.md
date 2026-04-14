# Security Policy

ao-kernel is a **governed AI orchestration runtime** — it sits between agent code and LLM providers, handles policy decisions, and writes audit trails. Security posture matters. This document covers how to report issues, how the project defends itself, and how you should configure it in production.

## Supported versions

| Version | Security fixes |
|---|---|
| `2.x` (current)  | ✅ active |
| `1.x` and older  | ❌ end of life — please upgrade |

Security fixes land on `main` first, then on the newest `2.x` patch release. Older minor lines receive fixes only if a regression was introduced there.

## Reporting a vulnerability

**Do not open a public GitHub issue** for anything that could be a security problem.

- Preferred channel: **GitHub private vulnerability reporting** — https://github.com/Halildeu/ao-kernel/security/advisories/new
- Backup channel: open a placeholder issue with no detail and request a private channel; a maintainer will reach out.

When you report, please include:
- ao-kernel version (`pip show ao-kernel`) and Python version
- Minimal reproducer (script, prompt, or MCP call sequence)
- Observed vs expected behavior
- Blast radius you estimate (who is affected, under what configuration)

**What to expect:**
- Acknowledgement within 5 business days
- Initial severity assessment within 10 business days
- Fix or mitigation plan communicated before any public disclosure
- Credit in the CHANGELOG and release notes unless you prefer otherwise

Coordinated disclosure is the default. If you need a specific timeline (e.g., you plan to present findings), say so in the initial report.

## Security model — what ao-kernel guarantees (and does not)

### What the runtime guarantees

- **Fail-closed policy evaluation.** A missing policy, a corrupt policy file, or an unknown action is a **deny**, not a silent allow. See CLAUDE.md §7.
- **Secrets are not logged and not sent to MCP.** API keys are resolved from environment variables (or a future `SecretsProvider`) inside the runtime and never appear in tool arguments or evidence JSONL files. The MCP tool `ao_llm_call` rejects `api_key` as a parameter on purpose (D11).
- **Atomic writes.** State files (session, canonical store, workspace facts) are written via `tmp + fsync + rename` so an interrupted write cannot leave a half-valid JSON behind.
- **Evidence is append-only.** JSONL evidence lines are never rewritten; the SHA256 manifest detects tampering.
- **Version-pinned bundled defaults.** Policy and schema JSON shipped inside the wheel is read via `importlib.resources`; it cannot be tampered with without a new install.

### What ao-kernel does NOT protect you from

- **Your own prompts and tool implementations.** Prompt injection that convinces your LLM to call a tool you registered is a policy question for *your* code. ao-kernel will enforce the policy you write (`policy_tool_calling.v1.json`), but it does not guess good intent for you.
- **Third-party MCP clients.** If you connect ao-kernel to an MCP client that you do not control, that client sees every tool response. Apply the **SDK vs MCP** boundary in the README accordingly — MCP is a thin executor, not a trust boundary for arbitrary callers.
- **Network-level adversaries.** TLS termination is handled by your Python runtime and provider SDKs; ao-kernel does not pin certificates.
- **Local file system access.** Workspace (`.ao/`) protection is OS-level. Anyone with read access to the workspace can read canonical decisions and evidence.

## Secrets handling — best practices

**Do:**
- Keep API keys in environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) or a secret manager.
- In multi-tenant deployments, launch a dedicated process per tenant with its own env.
- Rotate keys on a schedule that matches your provider's guidance; ao-kernel re-reads env every request.
- Keep `.ao/` and `.cache/` out of images pushed to public registries. They may contain tool outputs.

**Do NOT:**
- Do not pass API keys as MCP tool arguments. They will be rejected.
- Do not commit `.env` files. The bundled `.gitignore` covers common names; extend it for project-specific ones.
- Do not paste secrets into chat, prompt, or issue comments to "help Claude test something." The evidence writer will persist them.
- Do not disable the pre-commit hook (`.githooks/pre-commit`) that scans for common secret patterns.

## Operational hardening

Recommended production configuration:

- **Python 3.11+** with pinned dependencies in your app's `requirements.txt`.
- `pip install --require-hashes` when installing in CI.
- **Branch protection** on `main`: required PR review, required status checks (CI), no force pushes, no deletions — ao-kernel uses these on its own `main`; repo templates can replicate.
- **Tag ruleset** on `v*`: block deletion, block force-update. ao-kernel releases use trusted publishing (OIDC) to PyPI, so the tag-to-release provenance must stay intact.
- **Dependency scanning**: enable GitHub Dependabot on your app repo.
- **Observability**: enable the `ao-kernel[otel]` extra and export to your OTEL collector so policy denials and evidence skips are visible.

## Known non-secrets in the JSONL evidence trail

By design, the evidence writer captures:
- Request envelope (provider, model, token counts, prompt prefix up to `max_output_chars`)
- Response text (truncated)
- Tool call names and arguments (minus any field the policy marks as a secret)

If you operate in a regulated environment, treat the `.ao/evidence/` directory as **equivalent in sensitivity to your LLM conversation logs**. Rotate, redact, or retain per your policy.

## Reporting non-security bugs

Non-security bugs go to the normal GitHub issue tracker:
- https://github.com/Halildeu/ao-kernel/issues

Security-adjacent topics (e.g., fail-closed semantics) that are not actual vulnerabilities can go through issues — when in doubt, choose private reporting and we will reclassify together.
