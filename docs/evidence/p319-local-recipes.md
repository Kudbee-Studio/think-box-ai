# P3.19: local recipes ("the local model should do this")

Founder: the local model should answer "WHAT PR ARE WE ON" itself, for free, instead of escalating to Mercury (#330). `smollm2:360m` cannot call tools (Ollama reports `capabilities: ["completion"]`), so the **code** makes the lookup and the model only words the answer.

## What it does

- `apps/web/local-recipes.ts` (pure): three read-only recipes, matched from the goal: **open pull requests** (GitHub pulls API for `KUDBEE_REPO` / the git remote), **list the workspace files**, **read a named file**. A goal that changes something (merge, close, create, write, delete...), names a URL, or is anything else is not a recipe and goes to the worker agent as before. `buildFacts` turns the tool output into plain lines, by code. `groundedAnswer` checks the model's sentence.
- `apps/web/agent.ts`: the per-call governance (allowlist, approval gate, execution, thoughts, run event) moved out of the agent loop into one exported `runGovernedTool`. The worker agent and the recipes both call it, so a recipe's first GitHub access asks for approval exactly like Mercury's did, files stay confined to the workspace, and the call is audited as a run event. (All 62 existing agent/evidence/server tests still pass.)
- `apps/web/server.ts`: a local-model goal that matches a recipe runs it ($0, no worker agent), asks the local model for one or two sentences from the data (plain chat, no tool talk), and shows the sentence only if it passes the check, always followed by the data itself. The CLI auto-router treats recipe goals as local-eligible.
- The check: every number and link in the sentence must be in the data; for pull requests it must name a listed PR and must not pair one PR's distinctive title words with another PR's number; for files it must name a listed file; it must be short enough to check. When the data is empty ("none open", "workspace is empty") the model is not asked at all. A read-file summary can only be checked for numbers and links and is labelled so.

## Evidence

- Tests: `tests/local-recipes.test.ts` (13: matching incl. what must NOT match, tool args, facts incl. real-shaped truncated JSON and hostile titles, the grounding rules incl. real model mix-ups) and `tests/local-recipes-server.test.ts` (5, real `server.ts`, fake Ollama and fake GitHub): approval requested and answered, answer = sentence + data, invented PR number dropped, denied approval fails plainly with no lookup or model call, empty data skips the model, a goal that changes something is not a recipe, Mercury never touched.
- Live, real GitHub, real Ollama on the GPU (69% of the model on it), real approval gate, CLI `--yes`: `p319-local-recipes/cli-live.txt` (facebook/react: 5 real PRs, the reply was 106 KB and cut off by the fetch limit, which the parser now handles; the model's sentence was too long to check, so the data is shown), `cli-live-this-repo.txt` (this repo: none open; empty workspace). A goal that changes something ("merge the open PR") went to mercury-2 ($0.0027). Cost of every recipe run: $0.0000.
- What a real run found that fakes hid: real GitHub pull-request objects are 10-20 KB each, so five exceed the fetch limit; the parser reads the complete objects from a cut-off array and says the reply was cut off.
- Measurement (`scripts/local-recipe-eval.ts`, 20 runs on real facebook/react data, `recipe-eval-facebook-react.json`): the 360M model's sentence passed the final check in **11 of 20 (55%)**; 9 were dropped (5 named no listed PR, 2 mixed another PR's title with a number, 1 too long, 1 invented a link). Dropped sentences fall back to the data, so a drop is a missed convenience, not a wrong answer.

## Limits (honest)

- The check catches invented numbers and links, mixed-up PR numbers and titles, and sentences that name nothing real. It does **not** prove a sentence is true or sensible: passing sentences were sometimes clumsy ("...and is named #5"). The data block under every sentence is the answer to trust.
- Three recipes only. Anything else that needs live data still escalates to Mercury (#330).
- The PR recipe asks for the first 5 open PRs; with more, the count line says how many fit.
- Not run live in the dashboard: the CLI path is the same server code and the same WebSocket protocol (tested), but a dashboard approval click was not driven.
- The pairing check is word-based and could drop a correct sentence or pass a wrong one that avoids distinctive title words.

## Four-state table

| Item | State |
|---|---|
| Local model answers "what PR are we on" with a code-made lookup, $0 | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (CLI, real GitHub, real Ollama on the GPU, real approval gate) |
| One governed tool path shared by the worker agent and recipes | CODE COMPLETE, TEST VERIFIED (existing agent tests unchanged) |
| Workspace-listing and read-file recipes | CODE COMPLETE, TEST VERIFIED; listing live-verified on an empty workspace only; read-file not run live |
| Sentence quality from the 360M model | MEASURED: 55% pass the check (11/20); passing is not proof it is correct |
| Same flow in the dashboard UI | TEST VERIFIED (same WebSocket protocol); UNPROVEN live |
| A tool-calling local model (qwen2.5:1.5b) | UNPROVEN, not installed |
