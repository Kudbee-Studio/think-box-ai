# Run a real Think Box on your laptop

This guide gets `thinkbox run` calling a real model, through governance, with a
tamper-evident ledger — and proves it with one command. Nothing here is simulated.

## 1. Requirements

- Python 3.10+ (stdlib only for this path; no `pip install` needed)
- One model provider:
  - **Local (free, offline):** [Ollama](https://ollama.com/download)
  - **Hosted:** Inception Mercury-2, OpenAI, Groq, or any OpenAI-compatible server (vLLM, LM Studio)

## 2. Pick a provider

### Option A — Ollama (local)

```bash
ollama serve &                 # if the desktop app is not already running
ollama pull qwen2.5:1.5b       # ~1 GB, runs on CPU; use llama3.1:8b if you have the RAM
export THINKBOX_DEFAULT_PROVIDER=ollama
export THINKBOX_DEFAULT_MODEL=qwen2.5:1.5b
```

### Option B — Inception Mercury-2

```bash
export THINKBOX_DEFAULT_PROVIDER=inception
export INCEPTION_API_KEY=...          # from the Inception dashboard
# model defaults to mercury-2; max_tokens defaults to 3500 (reasoning model)
```

### Option C — any OpenAI-compatible API

```bash
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.groq.com/openai/v1
export THINKBOX_OPENAI_COMPAT_API_KEY=gsk_...
export THINKBOX_DEFAULT_MODEL=llama-3.1-8b-instant
```

Flags override env: `--provider`, `--model`, `--base-url`, `--max-tokens`.

## 3. Check the model (one real call)

```bash
python3 -m thinkbox.cli model check
```

`OK (0.4s): OK` means a real reply came back. `FAIL` prints the real reason
(connection refused, HTTP 401, empty content) and exits `1`.

## 4. Run a goal

```bash
python3 -m thinkbox.cli run --goal "What is 17 * 23? Reply with only the number."
```

- Runs through `GovernedEngine`: a governance token is minted for `--agent-id`
  (default `cli-operator`), checked by `AdmissionGate`, and recorded in the
  `ActionLedger` at `$THINKBOX_CLI_DB_DIR/run_ledger.db`
  (default `data/thinkboxmd/db/run_ledger.db`).
- Prints each task's real output, or its real error.
- Exit code `0` only if every task succeeded; `--json` prints the full result.

## 5. Prove it

```bash
python3 scripts/prove_think_box_local.py
```

Six checks, each of which can fail: model reachable, a random multiplication
answered correctly through the governed engine, no-token denied, forged token
denied, ledger chain verifies, tampering detected. Writes
`data/proofs/local_proof_<timestamp>.json` (git-ignored) and exits `0` only if
all six pass.

## What this does and does not prove

| Proven by the script | Not proven by the script |
|----------------------|--------------------------|
| A real model answered through the engine | Answer quality beyond one arithmetic check |
| Governance denies missing/forged tokens | Upstash Vector memory (needs `UPSTASH_VECTOR_REST_*` + an embedding key) |
| The ledger is hash-chained and tamper-evident | Upstash Box remote execution, UpCloud |
| Failures are reported as failures | Multi-agent swarm at scale |

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `unreachable at http://localhost:11434` | Ollama not running — `ollama serve` |
| `error: model 'x' not found` | `ollama pull <model>` |
| `HTTP 401` | Missing/wrong API key for the selected provider |
| `returned empty content (finish_reason=length)` | Reasoning model ran out of tokens — raise `--max-tokens` |
