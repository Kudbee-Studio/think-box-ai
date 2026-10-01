# Agent PR Instructions — copy/paste task-kickoff template

**Purpose:** a ready-to-fill prompt for starting a scoped PR. It assembles the
relevant rules already in `AGENTS.md` (branching §6.1, PR-before-work §6.4,
PRs-required §7.1, code-change workflow §13.3, TDD §13.8, failure recovery
§13.9) into one operational script, so every agent session runs the same
process instead of improvising.

**AGENTS.md is authoritative.** If anything here conflicts with it, AGENTS.md
wins — tell the founder and stop.

To use this: copy the template below, fill in the `TASK` block (goal, files/
modules in scope, acceptance criteria), and send it as the kickoff message.
An unfilled `TASK` block means the agent doesn't know the scope and will
guess — don't send it that way.

---

```text
ROLE
You are working in this repository (THINK BOX AI), at the repo root. You have
full control of the PR lifecycle up to, but not including, the merge. The
founder reviews and merges. Follow AGENTS.md; if anything below conflicts
with it, AGENTS.md wins and you tell the founder.

STEP 0 — ORIENT (no changes yet)
1. Read AGENTS.md, STATUS.md, docs/PREP.md.
2. Run: git status, git branch --show-current, git log --oneline -5, gh pr list --state open
3. Run the baseline tests: python3 -m unittest discover tests/
4. Report: current branch, test count/failures, open PRs, dirty files.
STOP if any PR is open (AGENTS.md §6.4 rule 3: one PR at a time). Tell the
founder, and don't start new work.

CHECK FOR UNCOMMITTED WORK BEFORE BRANCHING
`git status` may show a dirty working tree that predates this task — someone
else's in-progress edits, not yours to sweep up.
- Do NOT commit unrelated dirty files by accident and do NOT discard them.
- Inspect with `git diff`. If they're unrelated to the task, leave them alone.
- Use `git stash push -m "pre-pr-wip"` only if needed to branch cleanly, and
  tell the founder you did it (and what's in the stash).
- If the dirty files ARE part of the task, say so explicitly and include them
  deliberately — don't include them by default.
- Never use `git add -A` or `git add .`. Stage files by explicit path.

TASK
<<< DESCRIBE THE TASK HERE: goal, files/modules in scope, acceptance criteria >>>

STEP 1 — BRANCH
- git checkout main && git pull
- Name by AGENTS.md §6.1: feat/phase-N-desc | fix/NNN-desc | docs/desc | refactor/desc
- git checkout -b <branch>
- Never commit or push directly to main.

STEP 2 — OPEN THE PR FIRST (PR-before-work, §6.4)
- Make one seed commit, e.g. `chore(scope): start <task>` (or the real first commit
  if the work is small enough to land in one piece).
- git push -u origin <branch>
- gh pr create --draft --base main --title "type(scope): description" --body "<plan + acceptance criteria>"
- Title format is type(scope): description (types: feat, fix, docs, refactor, test, chore).

STEP 3 — IMPLEMENT (TDD, §13.8)
1. Write failing tests first: valid input, invalid input, edge case, error path.
2. Implement the minimum that passes.
3. Refactor without breaking tests.
Code rules:
- Python 3.10+, stdlib only unless a documented dependency trigger exists.
- Type hints and docstrings on public APIs. Comments explain why, not what.
- Async for I/O. Structured errors, never swallowed exceptions.
- Layer discipline: import only from lower layers. No provider SDKs in the runtime layer.
- Every side effect goes through AdmissionGate and is logged to ActionLedger. Never bypass GovernedEngine.
- Dashboard-visible changes (jobs, tests, infra): emit state via
  `get_dashboard_state().emit(category, event_type, data, source, evidence_label)`
  (see `thinkbox/dashboard_state.py`, `backend/main.py`).
- Evidence labels on data: simulated / inferred / verified / physically_measured.
- Significant architectural decision: write docs/decisions/NNN-*.md (ADR) BEFORE the code.
- Phase boundaries: don't implement Phase 2+ features early.

STEP 4 — SECURITY SWEEP (before every commit)
- No secrets, tokens, .env, keys, model weights, __pycache__, .pytest_cache, .vscode/.idea in the diff.
- Run: git diff --cached | grep -iE "token|secret|api[_-]?key|password|BEGIN .*PRIVATE"
- Env vars only for credentials. Do not paste any credential values into code, docs, PR text, or chat.
- No public exposure of local service ports (e.g. backend :8000/:8001). Shell execution needs the
  founder's explicit approval.

STEP 5 — COMMIT
- One logical change per commit, message `type(scope): description`. No "wip"/"fix stuff".
- Stage by explicit path. Review `git diff --cached` before each commit.
- Commit early and often. Push after each checkpoint.
- Keep the branch current with main using rebase, not merge commits.

STEP 6 — VERIFY (all must pass before marking ready)
- python3 -m unittest discover tests/    (no regressions; report the exact count, e.g. "N OK, M skipped")
- Run the targeted tests for the touched module with -v.
- Confirm minimum test counts in AGENTS.md §13.8 for touched modules.
- Update docs: STATUS.md, AGENTS.md test counts, and docs/CONTINUITY.md if the change is significant
  (AGENTS.md §4.3 — every meaningful product change updates Markdown in the same PR). Keep counts
  accurate and never invent numbers.
- Label verification state honestly: CODE COMPLETE / TEST VERIFIED / LIVE VERIFIED / PRODUCTION READY
  (AGENTS.md's four-state convention — never a bare "COMPLETE"). Do not claim LIVE VERIFIED without
  real infrastructure proof, and never claim PRODUCTION READY without the founder's sign-off.

STEP 7 — FINALIZE THE PR
- git push
- gh pr ready
- Update the PR body with: Summary, Changes, Tests (command + result), Docs/ADR links, Risks,
  Verification state (four-state), Out of scope.
- Append to the PR description: 🤖 Generated with [Claude Code](https://claude.com/claude-code)
- Check CI with `gh pr checks`. Do not poll in a loop. If CI fails, read the logs, fix, commit, push.
  If a failing check is pre-existing and unrelated to this diff, say so explicitly rather than ignoring
  it silently.

STEP 8 — STOP
- Paste the PR URL, final test count, and any failures or deferred items in the summary.
- Do NOT merge. Do NOT enable auto-merge. Do NOT start another PR or new product work while this one
  is open (AGENTS.md §6.4 rule 3).
- Wait for founder review. Address review comments with new commits on the same branch.
- After the founder approves: merge with --no-ff as in §13.3, push main, and stop.

FAILURE RULES (§13.9)
- If something fails, do not hide it. Classify it (infrastructure / code / environment / external),
  state the scope, then fix it or work around it honestly.
- If blocked or uncertain, stop and ask. If still unclear after reading docs/decisions/, write an
  ADR first.
- Report outcomes faithfully: failing tests get reported with output, and skipped steps get stated
  as skipped.

HARD PROHIBITIONS
- No direct push to main. No force-push. No --no-verify. No merging. No deleting branches or data
  without asking.
- No new dependencies without a documented trigger. No unrelated refactors in this PR.
- No actions outside this repo (network, cloud, UpCloud, Upstash writes) without the founder's
  explicit OK.
```
