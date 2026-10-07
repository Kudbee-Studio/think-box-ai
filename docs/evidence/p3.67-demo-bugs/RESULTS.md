# P3.67: the agent's file tools work inside the repository chosen with "use for agent"

Found on 2026-10-07 by running the agent on https://github.com/Kudbee-Studio/kudbee-demo-bugs (three planted bugs; 5 of 9 tests fail).

**Before (merged main, port 3000):** the agent read the clone correctly and wrote correct fixes, but `write_file` saved them in the profile folder (`<workspace>/src/cart.js`), not in the clone. `git status` in the clone was clean and 5 tests still failed. The run reported success.

**After (this branch, fresh data and workspace, port 3100, real Mercury-2, one run, 3 write approvals clicked):** only `src/cart.js`, `src/paginate.js` and `src/slug.js` changed in the clone (`agent-fix.patch`); the tests were not touched; `npm test` in the clone: 9 pass, 0 fail.

Not claimed: one run, one model, a tiny repository. The write approvals were clicked by a script standing in for the human.
