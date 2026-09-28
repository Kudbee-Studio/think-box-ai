# HERMES — Algorand Read-Only Research Agent

## What it is

HERMES is a named, tool-scoped agent lane inside kudbEE Agent OS (`apps/web/agent.ts`,
`AGENT_PROFILES.hermes`). It runs on the same worker-agent loop as every other goal, but
with a restricted tool allowlist and a role-specific system prompt addendum.

**Tools:** `algorand`, `recall`, `remember` — nothing else. No `write_file`, `read_file`,
`fetch_url`, `read_rss`, `list_files`.

**Forbidden, by design, not by convention:** wallet import, mnemonic handling, signing,
send/pay, rekey, or any application call that mutates chain state. HERMES's system prompt
tells the model to refuse these and explain that wallet/signing support is a separate,
deliberately deferred capability pending an explicit decision on wallet strategy. The tool
allowlist backs this up at the code level (see "Enforcement" below) — the prompt isn't the
only thing stopping it.

## The existing Algorand read-only surface

`apps/web/algorand.ts` — public AlgoNode endpoints, no API key, no SDK, no wallet. Six
query actions, all pure functions taking validated input and returning JSON:

| Action | Input | Notes |
|---|---|---|
| `status` | — | Network round/catchup status |
| `account` | `address` | Balance, min balance, asset holdings (top 20) |
| `asset` | `id` | ASA params: name, unit, decimals, total, creator |
| `application` | `id` | Creator, decoded global state |
| `transaction` | `txid` | Uses the indexer, not algod |
| `account_transactions` | `address`, `limit` | Uses the indexer |

Network defaults to `testnet`; `mainnet` is available for the same read-only queries.
Every input is validated (`validateAlgorandInput`) before any network call, so malformed
input never reaches the approval gate or the network.

### Endpoints (env override, optional)

Nothing below is required — the defaults are public AlgoNode URLs. Set these only to point
at your own node/indexer instead:

```
ALGORAND_ALGOD_URL_TESTNET=
ALGORAND_ALGOD_URL_MAINNET=
ALGORAND_INDEXER_URL_TESTNET=
ALGORAND_INDEXER_URL_MAINNET=
```

(Currently the endpoint URLs are compiled into `algorand.ts`'s `PUBLIC_ENDPOINTS`; wiring
these env vars through is a small follow-up if a custom node is ever needed.)

## Enforcement (why this isn't just a prompt)

1. **Function list filtering** — `runToolAgent()` builds the `tools` array sent to the model
   from `hooks.allowedTools` when set; HERMES's model literally never sees `write_file` etc.
   in its function-calling options.
2. **Hard backstop** — even if the model hallucinates a `tool_call` for a name outside the
   allowlist (or a future prompt-injection attack tries to force one), the dispatch loop in
   `runToolAgent()` rejects it *before* it reaches the approval gate:
   ```
   if (hooks.allowedTools && !hooks.allowedTools.includes(call.function.name)) {
     throw new Error(`Tool '${call.function.name}' is not available to this agent profile`);
   }
   ```
   This is the actual security boundary. Filtering the function list is a UX nicety on top of it.

## Running HERMES

CLI:
```bash
kudbee --agent hermes "summarize account <TESTNET_ADDR> on testnet"
```

Interactive shell:
```
/agents              # list agent lanes
/agent hermes         # switch to HERMES for subsequent goals
/agent                # clear — back to the full default worker agent
```

REST/WS: `run_goal` (WS) accepts an `agent` field; unknown agent names return a normal
`result` message with `success: false` (not a raw error) so the CLI never hangs waiting
for a response that was never coming.

`GET /api/agents` lists all registered profiles (id, name, description, allowed tools) —
used by the CLI's `/agents` and `/agent` commands.

## Persistence

`run_metadata.metrics.agent_profile` records which profile (if any) ran a given goal, so
run history and future analytics can tell HERMES runs apart from default worker runs.

## Testing

`apps/web/tests/agent.test.ts` — HERMES-specific tests:
- Allowlist is exactly `algorand`, `recall`, `remember`
- Model is only offered those three tools
- Role context appears in the system prompt
- A disallowed tool call (simulated hallucination) is rejected before the approval gate
- Allowed tools (`algorand`) still go through the normal approval flow
- The default (no profile) worker agent is unaffected

The existing Algorand hermetic test suite (`apps/web/tests/algorand.test.ts`,
`apps/web/tests/agent.test.ts`'s algorand-specific cases) is unchanged and un-weakened.

## Out of scope (this PR)

Wallet connect, mnemonic import, transaction signing, ASA creation, smart-contract deploy,
MCP registry integration. Any future signing capability needs its own explicit scope
decision and design — not something to fold into HERMES, which is deliberately read-only.
