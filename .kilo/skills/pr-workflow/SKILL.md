# Skill: pr-workflow

**Description:** Create, review, and merge PRs following project conventions

# When to Use

Use for every code change — from bug fixes to features to docs updates.

# Prerequisites

- Working tree clean (commit or stash changes first)
- Synced to latest main
- Know the branch naming convention

# Workflow

## Step 1 — Sync to Main

```bash
git checkout main
git pull origin main
git checkout -b feat/descriptive-name
```

Branch naming: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/` prefix + short description.

## Step 2 — Make Changes

Follow AGENTS.md rules:
- PEP 8, type hints on all public functions
- Docstrings on all public classes and functions
- No comments explaining what code does
- All errors carry: agent_id, task_id, think_box_id, timestamp, error_type, context
- Test every public function, every error path

## Step 3 — Run Tests

```bash
python3 -m unittest discover tests/
```

All tests must pass (or have justified skips). Minimum acceptable: 390 OK.

## Step 4 — Commit

Conventional commit message:
```
type(scope): description
```
Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

Example: `fix(upstash): embedder + vector upsert fail closed`

## Step 5 — Push and Create PR

```bash
git push origin feat/descriptive-name
```

Create PR targeting `main`. Title matches commit message. Description includes:
- What changed
- Test results
- Out of scope items
- Verification steps

## Step 6 — Wait for Review

Do NOT merge without founder review. Do NOT create a second PR until the first is reviewed.

## Step 7 — Merge

After approval:
```bash
git checkout main
git merge --no-ff feat/descriptive-name -m "Merge PR #N: description"
git push origin main
```

# Rules

- ONE PR AT A TIME. Do not merge. Stop after PR is open.
- Never touch open draft PRs unless explicitly told.
- Never reopen dead convoy branches (#28, #32).
- No secrets in commits or PR descriptions.
- No public binding of services.
- PR descriptions must include test pass count.
