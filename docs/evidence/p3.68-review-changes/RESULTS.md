# P3.68: review what the agent changed, and undo it

Checked 2026-10-07 on the dashboard (:3000) in Chromium, with the demo repository (Kudbee-Studio/kudbee-demo-bugs) after the agent's real fix run (P3.67).

- The Files panel showed "Changes in kudbee-demo-bugs (4)": `src/cart.js`, `src/paginate.js`, `src/slug.js` (changed) and `report.md` (new).
- "diff" on `src/cart.js` opened the real diff under the row (added lines green, removed red).
- "undo" on `report.md` (confirmation accepted) deleted the file; the list went to three files; `ls` of the clone confirmed it was gone.

Proven by tests: `tests/repo-changes.test.ts` (real git: modified/deleted/new files, ignored files not listed, bounded diff, undo one, undo all keeps ignored files, staged change undone) and `tests/repo-changes-routes.test.ts` (undo refused unless from the dashboard or the local token; no repository chosen).

Not claimed: the panel shows no test result yet; "Keep" is simply leaving the files as they are (nothing is committed); one browser, one repository.
