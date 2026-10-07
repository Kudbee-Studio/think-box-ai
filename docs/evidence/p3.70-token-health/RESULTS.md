# P3.70: Think Token health

Read-only counts over the saved tokens (`think-token-health.ts`), shown as a card at the top of the Think Tokens window and by `kudbee tokens health [--json]`. No model, no network. It is observational: it does NOT say tokens make runs better (that is what the A/B experiments measure).

**On the founder's real store (2026-10-07):** 37 saved, 29 accepted; 15 of 29 accepted tokens used by a run, all 15 in the last 7 days; 0 waiting, 0 stale; 82 of 85 runs that used a token finished; challenge 29 passed / 4 failed. Most used: TT-000006 "HTML fallback for PR details" (22x), TT-000005 "Query open PRs with GitHub API" (21x), TT-000007 "Trust fresh tool output over stale memory" (15x).

**What it shows:** 14 accepted tokens have never been used, and the most-used ones are about GitHub PR lookups: nothing in the store yet covers fixing code in a customer repository. That is the gap for the next steps (learn from repo fixes; tokens per repository).

Proven by tests: `tests/think-token-health.test.ts` (counts, stale/waiting boundaries, rejected tokens excluded, text form) and the dashboard test (card from server counts; empty when the message has none). Checked in Chromium on the real store.

Not claimed: that any token helps; the 82/85 figure has no comparison group.
