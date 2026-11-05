# Think Token Live-Provider Trial Plan (FOUNDER-GATED — NOT AUTHORIZED)

**Status:** PLAN ONLY. No live model calls have been made. This document is a
request for authorization, not authorization.

## 1. Why this plan exists

The hermetic harness in `thinkbox/think_token_eval.py` proves the **injection
mechanism**: accepted Think Tokens reach the artifact path and can change the
emitted artifact, and the objective verifier is sensitive to that change
(Arm A: 5/5 vs 0/5, one-sided Fisher p = 0.004). A negative control shows the
verifier detects behavioral change rather than context text (Arm B: 0/5 vs
0/5, p = 1.0).

What it does **not** prove: whether a **real model** would produce better
outputs *because* of the tokens. The harness uses a scripted provider. Answering
the real question requires a live provider, which requires a governance token
and founder gate. This plan specifies exactly how that trial would run, so it
can be approved or rejected in under two minutes.

## 2. Decision requested

Approve or reject a single bounded live run that measures whether injecting
the two accepted Think Tokens (`org:pattern:1`, `org:pattern:2` from
`learned.db`) changes a real model's behavior on 5 held-out REST-API goals,
versus not injecting them.

## 3. Held-out goals (unchanged)

The same 5 goals as the hermetic harness — no change, so the live numbers are
directly comparable to the hermetic numbers:

| id | family | goal |
|----|--------|------|
| `heldout_001_inventory_api` | rest_api | REST endpoint accepting JSON inventory items, Pydantic schema, SQLite storage, parameterized search |
| `heldout_002_order_api` | rest_api | REST endpoint accepting JSON orders, Pydantic schema, SQLite storage, parameterized search |
| `heldout_003_product_api` | rest_api | REST endpoint accepting JSON products, Pydantic schema, SQLite storage, parameterized search |
| `heldout_004_shipment_api` | rest_api | REST endpoint accepting JSON shipments, Pydantic schema, SQLite storage, parameterized search |
| `heldout_005_invoice_api` | rest_api | REST endpoint accepting JSON invoices, Pydantic schema, SQLite storage, parameterized search |

Each goal is verified by the same objective, machine-checkable verifier in
`thinkbox/think_token_eval.py::verify_artifact` (valid Python, required
structural elements, and a parameterized search endpoint with no interpolated
SQL string). The verifier is unchanged, so the live verdict is on the same
scale as the hermetic verdict.

## 4. Provider path

- Provider: **any OpenAI-compatible `/chat/completions` endpoint** (no provider is
  hardcoded; the adapter is provider-agnostic). Configured via
  `THINKBOX_LIVE_BASE_URL` / `THINKBOX_LIVE_MODEL` / `THINKBOX_LIVE_API_KEY`
  (see §4.2). Mercury is **unavailable** and is not required — the adapter
  makes no reference to it.
- No new code paths. The harness's `HermeticAgentProvider` is swapped for a
  thin live adapter that calls the same `complete(prompt)` contract; the rest
  of the harness (token loading, goal set, verifier, statistics, evidence
  writer, anti-claim guard) is untouched.
- Loopback only. No public endpoints, no `:8000`/`:8001` exposure.

## 4.1 Live adapter (built — NOT AUTHORIZED)

A thin adapter matching the harness `complete(prompt)` contract now exists at
`thinkbox/live_adapter.py` (`ThinkTokenLiveAdapter`). It wraps any
OpenAI-compatible `/chat/completions` endpoint and is the only module in the
repo that can reach the network for this trial.

### 4.2 Provider configuration (no Mercury dependency)

The adapter is **provider-agnostic**. It does not depend on Mercury (or any
other specific provider). Configure the provider with environment variables:

| Variable | Required for live | Default | Notes |
|----------|-------------------|---------|-------|
| `THINKBOX_LIVE_BASE_URL` | Yes (live) | `https://api.openai.com/v1` | Base URL, trailing slash stripped |
| `THINKBOX_LIVE_MODEL` | Yes (live) | `gpt-4o-mini` | Model id sent in the request |
| `THINKBOX_LIVE_API_KEY` | Yes (live) | `THINKBOX_OPENAI_COMPAT_API_KEY` | Bearer token; never printed |

`THINKBOX_LIVE_*` takes precedence over the shared `THINKBOX_OPENAI_COMPAT_*`
variables, so the adapter can point at any OpenAI-compatible endpoint without
code changes.

**Working OpenAI-compatible alternative (documented, not executed):** the
standard OpenAI endpoint above is the documented default and is known to
accept the OpenAI request shape this adapter emits. A local alternative is any
vLLM or Ollama server at `http://127.0.0.1:8000/v1` (loopback only — never
expose publicly), which accepts the identical `/chat/completions` payload.
Mercury (`api.inceptionlabs.ai`) is **unavailable** and is not required; the
adapter makes no reference to it.

### 4.3 Gate

The adapter is **off by default**. It refuses every call unless
`THINKBOX_LIVE_TRIAL_ACK=1` is set in the environment. Setting the flag is a
local toggle, not authorization — the governance token and founder approval in
section 9 are still required before any live call is made.

**The gate is independent of provider config.** Setting `THINKBOX_LIVE_BASE_URL`,
`THINKBOX_LIVE_MODEL`, or `THINKBOX_LIVE_API_KEY` does **not** enable live
calls. With the flag absent the adapter raises `LiveTrialNotAuthorizedError`
and opens no socket, even when all three provider vars are set. Hermetic tests
in `tests/unit/test_live_adapter.py` (`TestProviderConfigDoesNotBypassGate`)
prove this.

### 4.4 Dry-run (no network, no authorization needed)

Dry-run prints the exact request payload and returns a sentinel. It is safe to
run anywhere and is the recommended way to inspect what a live call would send:

```bash
# Prints the chat/completions payload for one prompt; opens no socket.
python3 -m thinkbox.live_adapter --dry-run "build a rest endpoint with pydantic and parameterized search"

# With provider config set, dry-run reflects the configured provider:
THINKBOX_LIVE_BASE_URL="http://127.0.0.1:8000/v1" \
THINKBOX_LIVE_MODEL="llama-3.1-8b" \
python3 -m thinkbox.live_adapter --dry-run "heldout goal prompt"

# Harness dry-run: replays every prompt the trial would send (5 goals x 2 arms)
# and prints the expected hermetic statistics. No network, no flag required.
python3 -m thinkbox.think_token_eval --dry-run
```

### 4.5 Direct refusal (no flag, no dry-run)

```bash
$ python3 -m thinkbox.live_adapter "hello"
Refusing live call: THINKBOX_LIVE_TRIAL_ACK is not set. The live Think Token trial is NOT AUTHORIZED.
$ echo $?
2

# Provider vars set but flag still absent — same refusal, no socket:
$ THINKBOX_LIVE_API_KEY="sk-fake" python3 -m thinkbox.live_adapter "hello"
Refusing live call: THINKBOX_LIVE_TRIAL_ACK is not set. The live Think Token trial is NOT AUTHORIZED.
$ echo $?
2
```

Hermetic tests in `tests/unit/test_live_adapter.py` (14 tests) prove the gate:
the adapter raises `LiveTrialNotAuthorizedError` when the flag is absent (even
with provider env vars set), accepts `1`/`yes`/`true` only, and dry-run never
opens a socket even when the flag is set.

## 5. Required environment and governance token

The adapter (`thinkbox/live_adapter.py`) is configured by these variables.
Mercury is **unavailable** and is not required — any OpenAI-compatible endpoint
works (see §4.2).

| Variable | Required | Notes |
|----------|----------|-------|
| `THINKBOX_LIVE_TRIAL_ACK` | **Yes** | The only gate that enables live calls. Must be `1`/`yes`/`true`. Absent → adapter refuses with exit 2, no socket. |
| `THINKBOX_LIVE_BASE_URL` | **Yes** (live) | Provider base URL; default `https://api.openai.com/v1`. |
| `THINKBOX_LIVE_MODEL` | **Yes** (live) | Model id; default `gpt-4o-mini`. |
| `THINKBOX_LIVE_API_KEY` | **Yes** (live) | Bearer token; the adapter never prints it. Falls back to `THINKBOX_OPENAI_COMPAT_API_KEY`. |
| `THINKBOX_GOVERNANCE_SIGNING_KEY` | **Yes** | Used by `GovernanceTokenService` to issue/verify the gate token. |
| `THINKBOX_LIVE_BUDGET_CALLS` | No (default 12) | Hard cap on model calls. |
| `THINKBOX_LIVE_BUDGET_USD` | No (default 2.00) | Hard cap on spend. |

Governance token: a founder-issued `GovernanceToken` (HMAC-signed, TTL-bound,
revocable) granting the `kilo:live_burst` capability to the trial agent, bound
to this plan's experiment id. The gate is **fail-closed**: no token, no start.

**Note on `THINKBOX_LIVE_TRIAL_ACK` vs `THINKBOX_SWARM_LIVE_ACK`:** the adapter
gate is `THINKBOX_LIVE_TRIAL_ACK`. `THINKBOX_SWARM_LIVE_ACK` is the separate
founder-acknowledgment flag referenced in the broader swarm live protocol; both
are required before any live call, and neither alone is sufficient.

## 6. Pass / fail criteria (same statistics as the hermetic harness)

The live trial uses the identical paired design and statistics as the hermetic
harness: 5 held-out goals, two arms (`with_tokens` vs `without_tokens`), the
same objective verifier, and the same one-sided Fisher exact test plus Cohen's
h.

- **Pass (real-model benefit detected):** with-tokens success rate strictly
  greater than without-tokens, one-sided Fisher p < 0.05, and the paired delta
  is positive on a majority of goals. The verdict would be recorded as
  `LIVE_BENEFIT_DETECTED` and would override the current hermetic
  `MECHANISM_DEMONSTRATED` finding.
- **No measurable improvement:** the two arms do not differ, or the difference
  is not statistically detectable at n = 5. The verdict would be
  `LIVE_NO_MEASURABLE_IMPROVEMENT`, and the UNPROVEN status stands. This is an
  acceptable, honest outcome — it closes the question.
- **Harming:** the without-tokens arm outperforms the with-tokens arm. Recorded
  as `LIVE_HARMING`; the tokens would be flagged for removal from the injection
  path.

## 7. Abort conditions (hard stops, no retries past them)

- Call budget (`THINKBOX_LIVE_BUDGET_CALLS`) exhausted → stop, report
  `BUDGET_EXHAUSTED`, do not continue the other arm to "balance" the numbers.
- Spend budget (`THINKBOX_LIVE_BUDGET_USD`) exceeded → stop immediately.
- Any non-`2xx` response, timeout, or connection error on a model call → count
  as a failure for that goal and that arm; do not silently substitute a
  hermetic fallback. A hermetic fallback would invalidate the live measurement.
- The model emits a tool call other than the permitted `file_write` of the
  artifact → abort that goal, record `UNEXPECTED_TOOL_USE`, and stop the run.
- Rate limiting (HTTP 429) on more than 2 consecutive calls → back off once,
  then abort with `RATE_LIMITED`.
- The governance token expires or is revoked mid-run → abort immediately with
  `TOKEN_INVALID`.

## 8. What the two outcomes look like

**Success:** on at least 4 of 5 held-out goals the real model emits a
parameterized, injection-safe artifact *only* when the accepted Think Token
context block is present, and the verifier rejects the naive f-string artifact
when it is absent; one-sided Fisher p < 0.05. That would mean the tokens have a
measurable, causal effect on real-model behavior on this task family, and the
finding would move from UNPROVEN to LIVE_BENEFIT_DETECTED.

**No measurable improvement:** the real model produces the same objective
verdict in both arms (e.g. it already emits parameterized artifacts by default,
or it ignores the token block entirely), or the difference is not
statistically detectable at n = 5. That would confirm the hermetic finding and
close the question: accepted Think Tokens, as currently stored and injected,
do not measurably improve real-model performance on this family. The honest
recommendation would be to stop investing in this injection shape and look for
a retrieval-and-application mechanism that changes the *tool call* rather than
the prompt context.

## 9. Authorization required

This plan makes **no** live calls. To execute it, a founder must:

1. Set the adapter env vars in section 5 (`THINKBOX_LIVE_TRIAL_ACK`,
   `THINKBOX_LIVE_BASE_URL`, `THINKBOX_LIVE_MODEL`, `THINKBOX_LIVE_API_KEY`).
2. Issue a governance token granting `kilo:live_burst` for this experiment id.
3. Set `THINKBOX_SWARM_LIVE_ACK`.
4. Run the gated trial.

Until all four happen, the live trial is **NOT AUTHORIZED** and must not run.
Setting `THINKBOX_LIVE_TRIAL_ACK=1` alone is a local toggle, not authorization;
it only lets the adapter *attempt* a call, and the call still requires the
governance token and founder approval.
