# Skill: rpo-assess

**Description:** Full project status assessment — infrastructure, code, tests, and blockers

# When to Use

Run this skill when you need a complete picture of where the project stands, what's broken, what's blocked, and what the next priorities are. Use it at session start, after merges, or when the user asks for a status update.

# Workflow

## Step 1 — Git State

```bash
git status
git log --oneline -10
git branch -vv
```

Record: current branch, working tree state, last 10 commits.

## Step 2 — Test Results

```bash
python3 -m unittest discover tests/ 2>&1 | tail -5
```

Record: pass/fail count, skipped count, any errors.

## Step 3 — Infrastructure Status

Check each service from STATUS.md Access Inventory:

| Service | Check |
|---------|-------|
| Inception Mercury 2 | `INCEPTION_API_KEY` present? Live call possible? |
| Upstash Vector | `UPSTASH_VECTOR_REST_URL/TOKEN` present? Upsert works? |
| Upstash Box | Preview live? |
| UpCloud | Token valid? SSH key exists? IP reachable? |
| OpenAI-compatible | Key set? Endpoint reachable? |

## Step 4 — Known Defects

Read `STATUS.md` Known defects section and `docs/PREP.md` Known defects table.

## Step 5 — Priority Output

Produce a numbered list:

1. **P0** — Immediate blockers (infrastructure, credentials)
2. **P1** — Test gaps, missing capabilities
3. **P2** — Optimization, polish
4. **P3** — Enhancement, nice-to-have

# Output Format

```
BRANCH: <name>
TESTS: <N> OK / <M> FAIL / <K> SKIP
INFRA: <services OK> / <services blocked>
DEFECTS: <N> open
NEXT:
1. <task>
2. <task>
```

# Rules

- Never invent test counts — run the tests.
- Never hide defects — report them honestly.
- If a service is untested, say "not verified."
