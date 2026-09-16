# AGENT CONTRACT — `dashboard-evolution`

**Template branch:** `agent-template/dashboard-evolution`
**Domain:** dashboard / observability surface
**Applies to:** any change to `experiments/swarm_dashboard.py`, its API routes, or the
instruments that feed it.

This contract is the operating procedure. It is intentionally stricter than a
prompt because it is executable: `scripts/agent_work.py` enforces the parts that
can be checked mechanically.

---

## 1. Branch naming (enforced)

```
agent/dashboard-evolution/<agent>-<YYYYMMDD>
```

Also accepted: `agent/dashboard-command-center/<agent>-<YYYYMMDD>`.

Never commit directly to `main`. Never force-push `main`.

## 2. Baseline (must pass BEFORE any work)

```bash
python3 -m unittest discover tests/
python3 experiments/verify_instrumentation.py
```

Record the baseline counts. If baseline is red, stop and report — do not build on
a broken floor.

## 3. Required tests

- **Every new API route** gets at least one test that calls the underlying reader
  function with a populated fixture and asserts the returned shape.
- **Every new instrument or store** gets valid-input, empty-input, and
  malformed-input tests.
- **Every bug fix** gets a regression test that fails before the fix.
- Keep the suite green: `python3 -m unittest discover tests/`.

## 4. Verification commands (these are the proof)

```bash
python3 -m unittest discover tests/                     # full suite
python3 experiments/verify_instrumentation.py --live    # instruments + live E2E
python3 scripts/agent_work.py verify --template dashboard-evolution
```

A run is only "verified" when all three are green **and** the dashboard has been
exercised end-to-end (every tab returns HTTP 200 and non-empty payloads where
data exists).

## 5. Evidence requirements

Every claimed capability must point at **one** of:

- a test name,
- a generated artifact (JSON/MD path),
- a telemetry source in SQLite (table + column), or
- an explicitly labelled **synthetic fixture**.

Forbidden:
- numbers that exist only in the UI,
- a metric with no reader function behind it,
- "it works" without a command.

## 6. Failure semantics (non-negotiable)

- **No fake green.** If you cannot run something, say so and label it unverified.
- **Signals are not failures.** Challenge activity, disagreement, and validator
  tier inflation are *reported signals*, never penalties.
- **Environment ≠ software.** Missing `pip`, absent `fastapi`, a rejected cloud
  token, or disabled CI is an environment limitation. Report it separately from
  a code failure.
- **Unproven stays unproven.** Never upgrade a hypothesis to a fact in the docs.

## 7. Security

- Never print, commit, or transmit secret values. Probe for **presence only**.
- Dashboard binds `127.0.0.1` by default; it must never default to `0.0.0.0`.
- All SQLite reads from the dashboard are read-only (`mode=ro`).
- Keep response headers: `Content-Security-Policy`, `X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`.
- No new network calls from the dashboard; it renders persisted state.

## 8. Review protocol

1. **Self-review** the diff before opening the PR: regressions, security, fake
   metrics, dead code, accidental architecture changes, copy-paste leftovers.
2. **Independent review** of the PR as if by another engineer: read the diff, not
   the description. Post findings; fix them; re-test.
3. Only then merge.

## 9. Merge conditions & final report

Merge only when: baseline green, required tests added, verification commands green,
dashboard exercised E2E, self-review and independent review complete, docs updated.

Final report must include: PR number + URL, merge commit, final `main` SHA,
commits, test counts, verification results, dashboard E2E result, capabilities
implemented, known limitations, verification commands, live dashboard URL, and the
next larger improvement.

---

## Design rules specific to this domain

- **Files over servers.** No broker, no framework, no build step, no second
  process. SQLite + append-only JSONL + one stdlib HTTP server.
- **Every displayed metric has a traceable source.** The UI renders the API; the
  API reads a store; the store is written by a run.
- **Evolve, do not rewrite.** Preserve existing routes (`/api/live`,
  `/api/strength`, `/api/instruments`, `/api/proof`, `/api/sessions`, `/healthz`)
  and their payload shape; additive changes only.
- **Mobile-first.** One column on a phone, tabs not dropdowns, tap targets ≥ 40px.
- **Label synthetic data.** If a panel is seeded by a fixture, it says so.
