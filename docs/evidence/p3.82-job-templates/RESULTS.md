# P3.82 job templates (product idea 8)

Tools > Job templates: six ready goals (explain the codebase, collect TODOs, review for bugs, fix a bug, document a file, write tests for a file). "Put in goal box" fills the goal box; the person reads it and presses run. Nothing starts by itself.

Written for what a normal run can really do: list, read and write files in the chosen repository. Running tests or lint (`run_checks`) and reading a repository at a git ref (`repo_search`, `repo_read`) are offered only to a profile that names them (e.g. VERIFIER), not to a normal run, so no template promises them. Every goal says the agent cannot run code and must finish with a "Could not verify" list.

| Claim | State | Basis |
|---|---|---|
| Unique ids, names, descriptions; each goal is under 1200 characters | PROVEN | tests/job-templates.test.ts |
| A goal only names tools that exist and that a normal run has | PROVEN | same file (checks every snake_case word in every goal against the tool registry and the normal-run set) |
| Every goal states the limits and asks for "Could not verify" | PROVEN | same file |
| Required input is enforced; input is cleaned (control characters, newlines) and capped at 300 characters | PROVEN | same file |
| Routes list, fill, and refuse bad ids / missing input; the goal builder is not sent to the browser | PROVEN | tests/job-templates-route.test.ts |
| Panel: card per template, input only where needed, repository warning, fills the goal box, shows a refusal without overwriting | PROVEN | tests/job-templates-panel.test.ts |
| A real model does a good job from these goals | UNPROVEN | no template was run against a model or a repository in this change |
| "Fix failing tests" and "write a changelog" | NOT OFFERED | they need to run tests or read git history, which a normal run cannot do |
| Per-template budgets | NOT CLAIMED | the spend limit is global (KUDBEE_DAILY_BUDGET_USD / per-run cap), not per template |
