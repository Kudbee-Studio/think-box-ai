# P3.69: a draft pull request from what the agent changed

**Proven by tests (`tests/agent-pr.test.ts`, `tests/agent-pr-socket.test.ts`), with a local bare repository standing in for GitHub:**
- off unless `KUDBEE_DRAFT_PR=on`; needs a chosen repository, a github.com origin and real changes;
- a human approval naming repository, base, branch and files comes first; "not approved" pushes nothing and calls nothing;
- approved: ONE new branch is pushed whose tree has the changed and the new files; the base branch is untouched; the clone's files, index and branch are untouched (the changes stay visible and undoable);
- a clone that is behind the base branch is refused (so no unpublished history is pushed); an unreadable remote and a failed `gh` are reported, a token in the error is scrubbed, and a push without a PR says the branch is pushed;
- `gh pr create` is called with `--draft`, never `--web`; only one request at a time;
- through the real server socket with the default setting: refused with a plain reason.

**Checked in the dashboard (Chromium):** "Open draft PR" shows next to "Undo all"; pressed with the default (off) it says "Draft pull requests are off. Set KUDBEE_DRAFT_PR=on ... and restart".

**NOT proven:** a real push to GitHub and a real `gh pr create` (`gh` is replaced by a stub in the tests). That needs the founder to turn the switch on and approve; the first real use should be on the demo repository.
