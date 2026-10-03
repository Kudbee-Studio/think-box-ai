# PR #337: dashboard and CLI hardening, CodeQL fixes, `/capacity` and `/config`

Code head tested by every gate below: `59de351`. Commits after it add only this file, the files it links and `AGENTS.md` (`git diff 59de351..HEAD --stat` lists no code).

## What changed

- **Dashboard storage:** header panels (Approvals, Performance, Execution Logs, Integrations, Collaboration, Settings) and `Enterprise.init()` survive corrupt, `null` or blocked `localStorage` (`readStoredJson` in `enterprise.js`).
- **Git panel escaping:** file tree names, the repository label, the file editor heading, the generated-files list and the clone dialog's `value="..."` are escaped; the editor's Save button no longer puts the file path into an inline `onclick`. The panel's `escapeHtml` now escapes quotes.
- **Other CodeQL fixes:** `htmlToText` (end tags with spaces, entity order), `memory.ts` README race, `git-repo-manager.ts` log format strings, thought status class, `runProgress` prototype, offline and mock pages, middleware-test reply.
- **CLI:** `/capacity` and `/config` (parity gaps 6 → 4), `/model` with no name, `httpError()` keeps the server's message (an earlier pass of mine had reduced it to `HTTP <status>`).
- **CI:** `think-token-embed.ts` typechecks whether or not the optional `@huggingface/transformers` is installed.

## Gate 1: local checks

`cd apps/web`: `npm test` 549/549, `npm run typecheck` clean, `npm run lint` clean.

## Gate 2: local CI with `act`

| Workflow / job | Ran | Result |
|---|---|---|
| `test` / `web-typecheck`: checkout, setup-node 22, `npm install`, `npm run typecheck`, `npm test` | yes | green, tests 549/549 |

- Log: `docs/evidence/ci-local/feat-pr337-dashboard-cli-checks-act.log`. act 0.2.89, image `catthehacker/ubuntu:act-latest`, Docker 29.6.2, run from a real clone of `59de351` whose `origin` is `https://github.com/Kudbee-Studio/think-box-ai.git` (what `actions/checkout` gives CI).
- Skipped: none. The "Analyze (javascript-typescript / python)" checks on GitHub are default code scanning, not a workflow job; gate 3 covers JavaScript.
- `act` found a real CI break: `think-token-embed.ts(88,7) TS2578 Unused '@ts-expect-error'`. A fresh `npm install` installs the optional package, so the directive I added in `4d9608a7` (on `main`) had nothing to suppress. Fixed in `d72a375a`; `main` has the same break until this merges.
- An earlier `act` run from a `git worktree` failed one test (`tests/live-fixes.test.ts`, `detectRepo` returned `null`): a worktree's `.git` is a file pointing at a host path the container cannot see. The real clone passes; not a code issue.

## Gate 3: CodeQL against `main`

CodeQL 2.27.1, `codeql/javascript-queries:codeql-suites/javascript-code-scanning.qls`, source root `apps/web`, on `main` (`ca180bb7`) and on this head (`59de351`). SARIF: `pr337-dashboard-cli/codeql-pr337-apps-web.sarif`.

| | Alerts |
|---|---|
| `main` | 35 |
| this PR | 27 |
| new | 0 |
| fixed | 8 |

- Fixed: `js/bad-tag-filter` and `js/double-escaping` (`agent.ts`), `js/tainted-format-string` x2 (`git-repo-manager.ts`), `js/xss` (`app.js`, `git-integration.js`), `js/xss-through-dom` (`index-offline.html`, `app-mock.js`).
- One alert shows a new fingerprint: `js/path-injection` at `git-repo-manager.ts:119`. The same alert is on `main` at the same, unchanged line; editing line 121 changed its line hash (0.2 warns about this). It is not new.
- The `javascript-security-extended` run (45 findings, triage in `AGENTS.md`) is wider than this gate's suite.

## Browser checks (Chromium, real `server.ts`, no model involved)

- **Git panel**, five attacks that set `window.__xssN` only if injected code runs (`git-panel-*.json`): a file named `<img src=x onerror=...>` in the tree, a pasted `github.com/a/b" autofocus onfocus="...` in the clone dialog, `<img onerror>` in an edited file's name, `');...;('` in a file path then Save, and an agent-written file named `<img onerror>`.

  | Version | Injected code ran |
  |---|---|
  | `main` | 5 of 5 |
  | my first fix `b851dcfa` | 5 of 5 (the clone dialog still broke out: its `escapeHtml` left quotes) |
  | this PR | 0 of 5; the pasted URL arrives intact in the input |

  `git-panel-current.png` shows the attack file name rendered as plain text in the editor heading.
- **Corrupted storage**, 12 keys set to `{oops` or `null` before load (`dashboard-storage-current.txt`): all 6 header panels start, session and audit lists stay arrays, 0 page errors. The old-code run (2 of 6 panels started, 6 page errors) is recorded in commit `4b85c3d1`; its output was not saved as a file.

## Red-team pass

| Claim | How I tried to break it | Result |
|---|---|---|
| Git panel output is escaped | quote breakout in `value="..."`, HTML in names, `'` in an inline handler, in Chromium | held after `0e6e301e`..`59de3514`; broke my first fix `b851dcfa` |
| `httpError` keeps the server's message | non-JSON body, JSON without `error`, an object as `error` | first two tested; every server route sends a string (`errorMessage()`), so an object cannot reach the CLI |
| Panels survive bad storage | corrupt JSON, `null`, throwing `getItem`, in a sandbox and in Chromium | held |
| `htmlToText` | `</script >`, `</script foo="bar">`, `</style\t>`, `&amp;lt;` | held |
| Typecheck in CI | fresh `npm install` in `act` | broke before `d72a375a`, green after |

## Four-state table

| Item | State |
|---|---|
| Storage hardening (panels, `Enterprise.init`) | CODE COMPLETE, TEST VERIFIED; browser-checked |
| Git panel escaping | CODE COMPLETE, TEST VERIFIED; browser-checked before and after |
| Other CodeQL fixes | CODE COMPLETE, TEST VERIFIED; not each browser-checked |
| CLI `/capacity`, `/config`, `/model`, `httpError` | CODE COMPLETE, TEST VERIFIED (tests run the real CLI against the real server) |
| CI typecheck with the optional package installed | CODE COMPLETE, TEST VERIFIED (`act`) |
| LIVE VERIFIED (real model) | UNPROVEN: no change here involves a model call |
| GitHub CI | UNPROVEN: Actions is billing-locked |
| PRODUCTION READY | UNPROVEN |

## Process notes

- I read 0.1 and 0.2 only at merge time. Before that this PR was pushed several times (0.2 says once), and #333 to #336 were merged without gates 2 to 4 (no `act`, no CodeQL comparison, no evidence table), #336 at the founder's request.
- 0.1 says merge by squash. The founder asked for at least 20 commits per PR and agreed to a merge commit that keeps them.
