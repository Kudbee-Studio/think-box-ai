# P3.43 live check of the draft pull request (slice 4) against the real GitHub: pre-registration (written BEFORE the run)

Question: slice 4 (#381) was verified only against a local bare repository and a fake `gh`. Does it work against the REAL `Kudbee-Studio/think-box-ai` with the machine's real git and `gh` logins: one new branch, one DRAFT pull request, nothing else on GitHub touched?

The founder said GO to one real branch and one real draft pull request. That is the only thing this run is allowed to create on GitHub.

## Setup (frozen)
- **Repository the convoy works on:** a throwaway `git clone` of `https://github.com/Kudbee-Studio/think-box-ai.git` into a private temp directory (never the founder's checkout, which is behind GitHub's `main`). Its `HEAD` must equal GitHub's `main` tip when the run starts (checked with `git ls-remote`; if not, the run is aborted and reported NOT RUN). `apps/web/node_modules` in the clone is a symlink to this machine's installed one (the sandbox mounts it read-only).
- **Server:** a real server on a random 127.0.0.1 port, throwaway data dir, never :3000, real Mercury (key from the repo `.env`, never printed or written), `KUDBEE_DAILY_BUDGET_USD=0.05`, `KUDBEE_DRAFT_PR=on`, `KUDBEE_REPO=Kudbee-Studio/think-box-ai`, default base `main`, default remote (GitHub). The real `gh` and git logins are the machine's own; the script never reads a token.
- **Browser:** real Chromium driven by Playwright. Every click (plan, submit, approve the convoy, approve the sandbox run, accept the review, deny then approve the draft-PR request) is Playwright acting on the founder's GO, not a person at the keyboard: the honest limit of this proof.
- **The goal (one, frozen):** "In docs/scratch-runner-design.md, the Status line near the top says slice 4 is '4 (the next PR, below)'. That PR is now merged as #381. Change that phrase to '4 (PR #381, below)' and change nothing else." A true correction of a stale phrase, so the draft is useful if the founder merges it. The convoy runs the repository's own four checks (lint, typecheck, tsc, test) in the sandbox.
- **Order:** plan, submit, approve convoy, approve the sandbox run, convoy completes verified, review pending (button absent) -> accept the review (button appears) -> click "Open a draft PR…" and DENY -> click again and APPROVE.

## Pass criteria (each decided from sources independent of the app: GitHub's API, `git ls-remote`, git plumbing; the app's own records are only compared against them)
1. **Preconditions:** the clone's HEAD equals GitHub's `main` tip at the start; `gh auth status` succeeds; the sandbox probe passes (else NOT RUN, not FAIL).
2. **Verified before any offer:** the convoy ends COMPLETED/success with `simulation.verified === true`, all four checks passed, files exactly `["docs/scratch-runner-design.md"]`, no flags; before the review is accepted the "Open a draft PR…" button is absent and the detail says `draft_pr_available: false`; after acceptance it is present.
3. **A denied request creates nothing:** `git ls-remote --heads` of GitHub is identical before and after the denied click, and the open-PR list is unchanged.
4. **The approval prompt** names `Kudbee-Studio/think-box-ai`, base `main`, a branch `kudbee/sim-<8 hex of the convoy id>-<8 hex of the patch hash>`, the 12-character patch hash, the file, and says it never merges.
5. **After the approved request, GitHub's heads differ from before by exactly ONE added ref** (that branch); `main` is the same sha as before; no ref was removed or moved.
6. **The pull request, read from GitHub's API:** exists as #N (N = the newest PR number before + 1), `draft: true`, `state: open`, `merged: false`, base `main`, head ref = the branch, head repo = the same repository, `commits: 1`, `changed_files: 1`, the one file is `docs/scratch-runner-design.md`, the title starts "kudbEE: ", the body contains the 12-character patch hash, the words "the model's summary (its words, not a verdict)" and "not proof".
7. **The commit is what was verified:** the branch commit's only parent is the pinned sha; its tree equals (built with a temporary git index: read-tree the pinned sha, `git apply --cached` the recorded patch, write-tree) the tree of the branch commit; its author is `kudbEE agent (draft)`.
8. **Nothing else changed:** the convoy records `draft_pr.state === "opened"` with the same URL GitHub returns; a second request for that convoy is refused ("already opened") with no new ref; the founder's real checkout (this repository) hashes identically before and after (status, diff, HEAD, ignoring this evidence directory); no scratch copy is left; the Mercury key value and any token-shaped string (`ghp_`, `github_pat_`, `gho_`) appear nowhere in any text the script fetched or captured; no browser console errors; cost <= $0.05; :3000 never contacted.
9. **Screenshots:** the draft-PR approval modal; the convoy detail with the link.

## Known limits (stated now)
- One goal, one run, a one-line documentation fix: this shows the path works against GitHub with these logins, not that Mercury's changes to real source are good. "Verified" still means only that the repository's own checks passed on a throwaway copy.
- Not exercised live: the `branch_pushed` recovery path, a base tip that moved, an existing branch, a GitHub or network failure. Those remain hermetic-only.
- The pull request and its branch stay on GitHub when the run ends: I will not merge, close or delete them; the founder decides. This run also uses PR number #382, so this evidence is PR #383.
- If any criterion fails, I report FAIL with the reading of why, keep every run, and disclose amendments in this file; I will not tune a criterion to pass.

## Amendment after run 1 (disclosed; criteria unchanged)
Run 1 (`run1-live.json`) ended NOT RUN-like before anything was written: after the plan and submit clicks the "Approve and run LIVE" button never appeared within 20 s, so the convoy was never approved, no prompt was shown, and GitHub is provably untouched (no ref added or removed, newest PR still #381, read from `git ls-remote` and `gh pr list` after the run). The script did not record why. I added a diagnostic block (convoy state, plan executability and blocked reasons, policy decision) to the failure path and will run again as run 2. No criterion, goal or setup value changed. Every run is kept.
