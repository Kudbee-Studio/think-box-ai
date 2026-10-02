# P3.16: the local model in the Agent OS (CLI and dashboard)

Founder: "the CLI works with the model, not the Agent OS dashboard", and `ollama run smollm2:360m "..."` in a terminal answers fine.

## What was wrong

When a local Ollama model ran a goal (dashboard, or CLI auto-routing a simple goal), `server.ts` sent a chat that said "Use the available plugins to accomplish tasks", listed every plugin name, and ended "Execute this goal step by step" - but attached no tools. A 360M model obeyed the wording and invented a tool plan. "What is 2 plus 2?" came back as "Step 1: Send a GET request to the domain of the webpage..." (`docs/evidence/p316-local-chat/` holds the after runs; the before text is quoted here). The same answer then printed three times: as streamed tokens, as a "reasoning complete" thought, and as the final result.

## What it is now

- The local model gets a plain chat, like `ollama run`: no system prompt, no plugin list, default sampling. Only a reply cap (`num_predict` 512, stops a runaway "0000000000") and `num_ctx` 2048 (more of the model fits the 2 GiB GPU: 69% on GPU, was 58%).
- I first tried an instruction-heavy "no tools" system prompt plus low temperature and a repeat penalty. It made the 360M model worse (three of four answers empty), so it was dropped. The terminal-style call is what works.
- Earlier plain-chat answers are replayed as assistant turns (they used to be replayed as raw JSON "user" messages).
- The thought no longer repeats the answer, and the result carries `streamed: true`, so the CLI prints `✓ done` and the dashboard `✓ Done` instead of the text a second time. API consumers still get the text in `result`.

## Evidence

- Tests `tests/local-chat.test.ts` (4, real `server.ts` against a fake Ollama): no system prompt and no plugin list sent; the answer streams once and the thought and result do not repeat it; prior answers replayed as assistant turns; both terminals skip a streamed answer.
- Live, real Ollama on the GPU (`p316-local-chat/cli-live.txt`): "What is 2 plus 2?" gives "2 + 2 = 4." once; "Say hi" gives a normal greeting; an image goal is auto-routed to Mercury-2 (needs tools). Dashboard with the local model selected (`dashboard-local-check.json`, `dashboard-local-1024.png`): "2 + 2 = 4." once, then "✓ Done".

## Limits (honest)

SmolLM2-360M is a weak model. Across the runs it answered "France" wrongly once ("Frencie") and gives long generic lists for open questions. It is fine for simple chat; it should not be asked to use tools or judge lessons (see P3.15). Sampling at default temperature varies run to run.

## Four-state table

| Item | State |
|---|---|
| Plain no-tools chat, answer shown once | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (CLI and dashboard) |
| Local fallback (no cloud model for simple goals) | LIVE VERIFIED: trace `p316-local-chat/cli-live.txt`, dashboard `dashboard-local-check.json` and `dashboard-local-1024.png` (was UNPROVEN: Ollama unreachable) |
| Local answers are correct | UNPROVEN beyond a handful of runs; one wrong answer seen |
| Local model fully on GPU | PARTIAL: 69% on GPU at 2048 context (2 GiB card) |
| Local model fit for tool use or judging | NO (see P3.15) |
