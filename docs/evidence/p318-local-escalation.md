# P3.18: goals that need tools or live data are escalated off the local model

Founder: on the dashboard, "WHAT PR ARE WE ON" run on `smollm2:360m` returned a confident essay about machine learning. A local chat has no tools; it cannot know. Decision: **escalate** such goals to the worker agent instead of refusing.

## What it does

- `apps/web/goal-routing.ts` (pure): `needsToolsOrLiveData(goal)` returns a reason, or null. It looks for: repository/PR/issue/branch/CI words, live state ("is it up", "currently", "right now"), the current date or recent events (today, latest, news, weather, price), a file, folder, URL or website, an action (read, list, fetch, download, run, install, save, send), an image request, or this system (Think Tokens, memory, runs, tasks). The CLI's complexity patterns moved into the same module, so the CLI auto-router and the server use one classifier.
- `server.ts`: when a goal arrives for a local (non-Inception) model and `needsToolsOrLiveData` finds a reason, the goal runs on mercury-2 instead, and a `routing` thought says "Routed to mercury-2 instead of <model>: <reason>. A local chat has no tools and cannot check live state." If no worker agent is configured the goal fails with that reason and "set INCEPTION_API_KEY"; it is never answered from the small model.
- Plain knowledge and chat goals ("2 plus 2", "say hi", "capital of France", "translate...") stay on the local model.

## Evidence

- Tests: `tests/goal-routing.test.ts` (9 stay-local goals, 13 must-escalate goals with the expected reason, empty/non-string/100k-character input, the CLI rule), and `tests/local-escalation.test.ts` (real `server.ts`, fake Ollama, mock Inception): routed with a worker agent (the goal is never chatted to the small model, a routing thought appears, Mercury answers), a plain goal stays local with Mercury untouched, and with no worker agent the goal fails with an explanation and no made-up answer.
- Live, dashboard at 1024 px with `smollm2:360m` selected, real Mercury: "WHAT PR ARE WE ON" shows the thought "Routed to mercury-2 instead of smollm2:360m: it asks about this repository or its pull requests, issues, branches, commits or CI. ..." and mercury-2 immediately asks to fetch the GitHub pulls API (`dashboard-pr-check.json`, `dashboard-pr-1024.png`). The same session's "What is 2 plus 2?" stays local: "2 plus 2 equals 4.", $0.0000 (`dashboard-simple-check.json`).
- **Founder's own end-to-end run** (`founder-run-dashboard-terminal.txt`): local model selected, "WHAT PR ARE WE ON", routing thought, mercury-2 fetched the real GitHub pulls API, the operator approved network access, and the final answer was correct and matches GitHub at that moment (PR #330, open, draft). 3 steps, 2 tool calls, $0.0049.
- Mercury spend for the proof: $0.0019 (two runs that stopped at the network-approval prompt, which a headless browser cannot answer).

## Limits (honest)

- It is a keyword classifier. It will send some local-safe goals to Mercury (for example "check my grammar" is fine, but "open source licences explained" matches "open") and could miss a goal that needs live data without any of those words. A false positive costs a Mercury call; a false negative is a wrong local answer. Neither is measured on a real set of goals.
- A goal that needs only the model's knowledge but mentions a file name or the word "run" will be escalated.
- The approval prompt for network access still applies to the escalated run.

## Side effects seen in the founder's run (not part of this change)

- The run saved TT-000014 (accepted): "When the fetched open-PR list has exactly one item, pull its number, title, URL, state, draft flag, and timestamps, then write a concise markdown file." It is narrow (it hinges on there being exactly one open PR) and could mislead a later run; the founder may want to retire it.
- The terminal printed both "Saved 1 Think Token ... (accepted 1)" and "1 Think Token candidate(s) saved for review" for the same run. One of the two messages is redundant or wrong; not investigated.

## Four-state table

| Item | State |
|---|---|
| Escalate tool/live-data goals from the local model to the worker agent, with a visible reason | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED (dashboard, real Mercury) |
| No worker agent: fail plainly, no made-up answer | CODE COMPLETE, TEST VERIFIED; not run live (a worker agent is configured here) |
| Plain goals stay local | CODE COMPLETE, TEST VERIFIED, LIVE VERIFIED |
| Classifier accuracy on real goals | UNPROVEN (hand-picked cases only) |
