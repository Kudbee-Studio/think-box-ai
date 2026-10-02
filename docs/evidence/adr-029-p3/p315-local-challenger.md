# P3.15: can the small local model challenge Think Token lessons?

Founder question: use the small local model (SmolLM2) to challenge and strengthen Think Tokens, ideally "just like Mercury 2", on the founder's GPU.

## Answer: not SmolLM2-360M. It does not judge; it answers the same thing to everything.

Rule, written into `scripts/think-token-local-challenge-eval.ts` before any local run: the local model may become a first-pass *rejector* (its fail stops a lesson; its pass never accepts; Mercury still decides every accept) only if, on lessons that get past the deterministic checks, it rejects at least 60% of bad lessons, wrongly rejects at most 10% of good lessons, and at most 10% of replies are unusable.

Set: the fixed run record and 10 true + 10 plausible-but-false lessons that tuned the Mercury challenge (`challenge-tune.ts.txt`; Mercury there: 17 right, 1 wrong reject, 0 wrong accept, 19 rejects, 3 unjudged). Real `challengeLesson` code path, local model only, $0. 2 repetitions each.

| Configuration (smollm2:360m) | Usable replies | Bad lessons caught | Good lessons wrongly rejected | Qualifies |
|---|---|---|---|---|
| Free-form JSON as production asks, 700-token cap | no: it echoes the input JSON back; first 3 calls hit the 30 s timeout, run stopped | n/a | n/a | no |
| Same, reply capped at 160 tokens | no: 5 of 5 calls unusable at about 14 s each, run stopped | n/a | n/a | no |
| Forced to the verdict JSON schema (Ollama structured output) | yes: 38 of 38 usable, 1.2 s per call | 18 of 18 (100%) | 20 of 20 (100%) | **no** |

Why the schema row looks good on the bad lessons: the model returned the same verdict for every lesson (true, specific, supported, but `novel: false`), so everything fails. A good lesson, a false checksum claim and a false caching claim all got the identical reply. Catching everything and keeping nothing is not judging. Raw rows: `p315-local-challenge-smollm2-360m-schema.json`.

## Hardware (founder's laptop)

Ollama 0.35.1 found the GPU through CUDA: Quadro M1000M, 2 GiB VRAM (1.6 GiB free), compute 5.0. `ollama ps` for this model: 1.1 GB, **58% on GPU** (42% CPU) at a 4096 context. Speed is not the problem (1.2 s a call); judgement is.

## What this does and does not change

- The deterministic checks plus Mercury 2 stay the challenge. Nothing was wired to the local model. A 360M model cannot "work just like Mercury 2".
- Shipped: the `smollm2` alias bug (any `smollm2` name was silently rewritten to qwen2.5:1.5b) is removed; an untagged model name matches Ollama's `name:latest`. The evaluation script, reusable on any local model.
- Next candidates need a stronger model that fits 2 GiB: for example `qwen2.5:1.5b` (about 1 GB, fits on the GPU). The founder pulls it; the same script and rule then decide.

## Seen in the dashboard (not fixed here)

A goal run on the local model answered with an invented plan (made-up tools `http_response`, `image_analyze`) with 0 tool calls, and the final answer printed three times in the terminal. Both are separate issues: local models must not be routed goals that need tools, and the repeated answer is a display bug.

## Four-state table

| Item | State |
|---|---|
| smollm2 alias fix, `:latest` matching | CODE COMPLETE, TEST VERIFIED |
| Local-model evaluation script | CODE COMPLETE, LIVE VERIFIED (ran on the real local model) |
| smollm2:360m as a challenge judge | LIVE VERIFIED **negative** (rejects everything, 20 of 20 good lessons wrongly rejected) |
| Local model as first-pass challenger | NOT BUILT (rule not met) |
| A stronger local model (qwen2.5:1.5b or similar) as challenger | UNPROVEN: not installed, not measured |
| Local model fully on the GPU | UNPROVEN: 58% on GPU at the default context |
