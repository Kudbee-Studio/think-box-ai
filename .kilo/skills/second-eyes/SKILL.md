# Skill: second-eyes

**Description:** Review recent merged work in this repository as an independent, read-only second reviewer. Find real defects; change nothing.

# When to Use

When the founder asks Kilo to review a range of commits or PRs ("second set of eyes"). Not for writing features or fixes.

# Rules (the reviewer is bound by these)

1. **Read-only.** Do not edit any file except your one findings file `docs/reviews/kilo-<range>.md`. Do not commit, push, merge, open or comment on a PR, change git config or remotes, or install anything. Never run `git pull origin`, `git push`, or any command that reaches GitHub.
2. **Work only in your own worktree** (`.kilo/worktrees/second-eyes`), never in the main checkout, which another agent is using.
3. **Evidence over opinion.** Every finding names `file:line`, quotes the code, and says exactly what input or state makes it fail. If you cannot show it, label it `UNVERIFIED` or leave it out. Run the relevant test or a small script when that settles the question (`cd apps/web && node --experimental-strip-types --no-warnings --test tests/<file>.test.ts`).
4. **No padding.** Style nits, naming and "could be refactored" are out unless they hide a bug. An empty review is a valid review: say "no findings" and list what you checked.
5. **Judge against this repository's rules:** AGENTS.md and CLAUDE.md (layer discipline, no provider SDKs in runtime code, tests with every change, four-state evidence in PR bodies, nothing outward-facing without a human approval, no secrets), and the security model (path confinement, no shell for the model, human approval before writes/pushes).
6. **Report honestly** in four states per claim: PROVEN (you ran it), READ (you read the code and are confident), UNVERIFIED (suspicion), NOT CHECKED (out of scope or no time). Say which files and tests you did not look at.

# Output format (`docs/reviews/kilo-<range>.md`)

Start with: range reviewed, commits, date, what you ran. Then findings, most severe first, each as:

`### <n>. <one-line claim>`  — severity (high / medium / low), state (PROVEN / READ / UNVERIFIED), `file:line`, the quoted code, the failing scenario in concrete terms, a suggested fix (words, not an edit). End with "Checked and found fine" and "Not checked".
