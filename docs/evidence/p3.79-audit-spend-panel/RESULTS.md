# P3.79 Tools > Audit & spend

A read-only panel: spend (today, 7 days, all time, daily and per-run limits with an 80% warning bar, cost per model) and the audit log (chain status, the newest 50 events). Uses the existing `/api/spend`, `/api/audit` and `/api/audit/verify`; no server change.

| Claim | State | Basis |
|---|---|---|
| Figures, limit bar, 80% warning, no-limit message, empty log, broken-chain message render correctly | PROVEN | tests/audit-panel.test.ts (rendering against a fake DOM) |
| Event text is shown as text, never as HTML | PROVEN | same file (an `<img onerror>` summary stays a string) |
| The page has the button/panel and loads the script; existing menu tests still pass | PROVEN | same file, tests/dashboard-menus.test.ts |
| Looks right in a real browser | UNPROVEN | not opened in a browser in this change |
| Filtering by kind or run, paging beyond 50 events | NOT CLAIMED | not built |
