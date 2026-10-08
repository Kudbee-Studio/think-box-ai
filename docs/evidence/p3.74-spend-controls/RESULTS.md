# P3.74: spend controls

**Before:** one daily budget (`KUDBEE_DAILY_BUDGET_USD`, off by default), no cap on a single run, no warning before the limit, and no spend report beyond today's meter.

**Now (everything off unless set; default behaviour unchanged):**
- `KUDBEE_RUN_BUDGET_USD`: a cap on any single run. A run that has spent that much stops before its next model call with "Run budget of $X reached (KUDBEE_RUN_BUDGET_USD)".
- The daily budget keeps its exact message; a one-time-per-day warning is raised at 80% of it (stderr and the audit log).
- Both stops are written to the audit log (`budget_stop`, with the run id; once per run and limit), and the warning as `budget_warning`.
- `GET /api/spend` (the active profile's runs: today / 7 days / all time, per day, per model, with limits) and `kudbee spend [--json]` (every profile's saved runs, per day, per model, per profile, with limits).

**Proven by tests:** `tests/budget-guard.test.ts` (6: config parsing, daily message unchanged, off means off, per-run cap and precedence, stop reported once per run, warning once per day), `tests/spend-report.test.ts` (5), and on a real server with a mock model `tests/budget-integration.test.ts`: a run billed about $0.0011 against a $0.0005 cap made exactly one model call, failed with the plain message, left one `budget_stop` row, and `/api/spend` showed the run; the same goal without a cap completed.

**On the founder's real data (`kudbee spend`):** 28 runs across 2 profiles, $0.20 in total (mercury-2 20 runs $0.16, about $0.008 per run).

**Honest limits:**
- Limits are checked between steps, so a run can finish the step it is in: the overshoot is at most one step's cost.
- The cap is per run, not per person or per project: there is no login yet, so a per-person budget has no identity to attach to. The per-profile report is the closest thing.
- `GET /api/spend` covers the active profile only (other profiles' runs are not loaded in the server); `kudbee spend` reads all profiles.
- Costs are what the run records hold: billed cost where the provider reports it, otherwise tokens at the model's price; DeepSeek's price is an estimate.
- Local models cost $0 here; the report does not count electricity or hardware.
- The warning is not shown in the dashboard yet (stderr and audit log only); the existing daily meter appears when a daily budget is set.
