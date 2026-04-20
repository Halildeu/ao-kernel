# hello-llm — ao-kernel quickstart

A minimal, runnable example that takes you from zero to a governed LLM call in under five minutes.

## What this shows

- Creating an ao-kernel workspace (`.ao/`)
- Constructing an `AoKernelClient`
- Making a single governed LLM call (route → policy → context → execute → extract decisions)
- Reading the response, token usage, and policy decision from the result dict

Everything the main README describes happens behind one `client.llm_call(...)` call here. Open `main.py` to see the full shape.

## Prerequisites

- Python 3.11+
- An OpenAI API key (other providers work too — see *Switching providers* below)

## Run it

```bash
cd examples/hello-llm

# 1. Install the minimum needed for a governed LLM call
pip install -r requirements.txt

# 2. Put your API key in a .env-style file (or export it yourself)
cp .env.example .env
$EDITOR .env   # paste your OPENAI_API_KEY

# 3. Go
python main.py
```

Expected output (abbreviated):

```
✓ Workspace initialized at: .
✓ Session started: hello-llm-<uuid>
✓ LLM call complete
  provider_id : openai
  model       : gpt-4o-mini
  status      : OK
  text        : Python is a high-level programming language...
  tokens_in   : 17
  tokens_out  : 58
✓ Session ended cleanly
```

If you see a policy decision instead of a response, that is working as intended — the policy engine blocked the call. Check `.ao/evidence/` for the audit trail.

## Switching providers

`main.py` uses `OPENAI_API_KEY` by default. To try a different provider, edit the two `provider_id` / `model` values at the top of the file:

| Provider  | `provider_id` | Example model        | Env var             |
|-----------|---------------|----------------------|---------------------|
| OpenAI    | `openai`      | `gpt-4o-mini`        | `OPENAI_API_KEY`    |
| Anthropic | `claude`      | `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| Google    | `google`      | `gemini-1.5-pro`     | `GOOGLE_API_KEY`    |
| DeepSeek  | `deepseek`    | `deepseek-chat`      | `DEEPSEEK_API_KEY`  |

Capability details (which providers expose tool use, streaming, structured output) live in the bundled registry — see the main README *Supported providers* table.

## What was created on disk

After a successful run you will have:

```
.
├── .ao/                          # workspace root (created by client)
│   ├── workspace.json            # version + ID
│   ├── canonical_decisions.v1.json   # (empty after one turn)
│   └── evidence/                 # JSONL audit trail
├── .env                          # your secrets (gitignored)
├── main.py                       # the example
├── README.md                     # you are here
└── requirements.txt
```

`.ao/` is the governed state directory. Delete it to start fresh. Do not commit it.

## Troubleshooting

- **`WorkspaceNotFoundError`** — the `.ao/` workspace is missing. The example passes `auto_init=True` to `AoKernelClient` so the first run will bootstrap `.ao/` in the example folder automatically. If you deleted the directory mid-run, re-run cleanly from the example folder — the next invocation will scaffold it again. (If you want the stricter "fail closed when `.ao/` is absent" behavior in your own code, omit `auto_init=True` — the default is `False`.)
- **`401 Unauthorized` from provider** — your API key is wrong, expired, or missing. Double-check `.env` (or `echo $OPENAI_API_KEY`).
- **`Policy violation`** — the bundled `policy_llm_routing.v1.json` denied the call. That is the fail-closed behavior; inspect the `decision` and `reason_codes` in the result dict.
- **Silent hang** — a provider may be throttling you. Ctrl-C is safe; no partial state is persisted mid-call.

## Next step

Once you have this running, the next example to build is a **tool-use loop** (policy-gated). That will land in `examples/tool-use/` in a later release — follow the CHANGELOG.
