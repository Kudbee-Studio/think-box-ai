# Best Practices — Think Box AI

**Purpose:** Operational rules for every agent working on this project.
**Enforced by:** Code review, CI, self-governance.

---

## 1. Branch Rules

1. **Always work on your session branch** — `session/agent_<id>` or `session/agent_<id>-clean`
2. **Never commit to `main` directly** — main is protected
3. **Create a new clean branch if secrets leak** — never rewrite public history without approval
4. **Push after every commit** — if no secrets detected
5. **Use descriptive commit messages** — `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`

## 2. Security Rules

1. **Never commit secrets** — no API keys, SSH private keys, tokens, or passwords
2. **Scan before push** — `git log -p --all | grep -E 'sk_|gsk_|password'` must be empty
3. **Use environment variables** — never hardcode credentials
4. **If a secret is committed** — remove immediately, rotate the key, notify Kudbee
5. **`.gitignore` must include** — `.env`, `.env.*`, `.ssh/`, `*.key`, `__pycache__/`

## 3. Documentation Rules

1. **Update STATUS.md** — after every meaningful change
2. **Update MEMORY.md** — when new facts are discovered
3. **Update SESSION.md** — last commit hash, phase, next owner notes
4. **Update WORK_QUEUE.md** — check off completed items, add new ones
5. **Create GAME_PLAN_*.md** — for any new phase with 5+ items

## 4. Code Quality

1. **No console.log in production** — use the logging module
2. **No comments that explain what** — only explain why
3. **Type hints on all public functions** — Python 3.10+
4. **Test before commit** — `python3 scripts/run_tests.py`
5. **Lint before push** — `python3 -m py_compile` or equivalent

## 5. Frontend Rules

1. **Mobile-first** — design for phones, enhance for desktop
2. **No framework dependencies** — pure HTML/CSS/JS only
3. **Every page gets:** meta title, description, OG tags, canonical URL
4. **Breadcrumbs on every page** — except home
5. **Skip-to-content link** — for accessibility
6. **404 page exists** — with search and navigation

## 6. Communication Rules

1. **Be concise** — no filler, no "great question"
2. **Be direct** — state the problem, state the solution
3. **No questions unless necessary** — figure it out, then report
4. **Report blocked items early** — don't wait until the end
5. **Document gaps** — if you can't fix it, document it for the next agent

## 7. Handoff Rules

1. **Leave the next agent better informed** — update all docs before stopping
2. **Commit everything** — no uncommitted changes when stopping
3. **Update WORK_QUEUE.md** — mark what's done, what's next
4. **Write SESSION.md** — last commit, phase, next owner instructions
5. **Test everything** — verify it works before handing off

---

## Checklist Before Stopping

- [ ] All changes committed
- [ ] All changes pushed (if no secrets)
- [ ] STATUS.md updated
- [ ] MEMORY.md updated
- [ ] SESSION.md updated
- [ ] WORK_QUEUE.md updated
- [ ] No secrets in git history
- [ ] Tests pass
- [ ] Next owner knows exactly where to pick up
