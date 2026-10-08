# P3.81 project home (product idea 7)

Tools > Project (`GET /api/project`): for the repository the agent is working on: uncommitted changes, runs on that repository (count, failures, total and today's cost, the five newest), Think Tokens learned there, recent repository decisions from the audit log (draft PRs, undos, repository changes), and next steps. Runs now record `repo` when they start.

| Claim | State | Basis |
|---|---|---|
| Only runs on this repository count; newest first; cost totals; five-run cap; goal shortened | PROVEN | tests/project-home.test.ts |
| Changes list (first eight) and review hint; tokens counted only if accepted and tagged for this repo; audit events limited to repository kinds | PROVEN | same file |
| Route answers with and without a chosen repository; an unreadable folder shows no changes instead of an error | PROVEN | tests/project-route.test.ts |
| Panel renders every section, shows text not HTML, page has button/panel/script | PROVEN | tests/project-panel.test.ts |
| A real run started on a chosen repository records `repo` | UNPROVEN | the one-line change in `newRun` is not covered by a test that starts a run; not exercised live |
| Looks right in a real browser | UNPROVEN | not opened |
| Runs before this change | NOT ATTRIBUTED | they have no `repo` field; the page says so |
| Per-repo spend limits, per-repo audit filtering | NOT CLAIMED | audit events carry no repository, so decisions shown are the profile's recent repository decisions |
