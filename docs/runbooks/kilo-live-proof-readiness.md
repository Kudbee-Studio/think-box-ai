# KILO Live-proof readiness runbook

**Status:** PR #141 spine + PR #142 `env-matrix` + PR #143 `substrate-checklist` + PR #145 `governance-evidence` + PR #146 `mercury-hermetic` + PR #147 `swarm-instrumentation` + PR #148 `proof-schema` + PR #149 `dashboard-slots` (PR #144 = CI/post-merge fix only) — **not** Live proof.  
**Four-state:** CODE COMPLETE / TEST VERIFIED on branch only.  
**Audience:** Agents and founders preparing KILO for an honest **Live proof** (earned later, not in #141).

---

## Purpose

This runbook defines what **“KILO ready for Live proof”** means in `Kudbee-Studio/think-box-ai`:

1. Canonical spine docs exist and stay aligned (`AGENTS.md`, `STATUS.md`, `docs/CONTINUITY.md`, `docs/STATUS.md`).
2. Hermetic gates pass in CI without live Mercury, GPU spin-up, or production deploy.
3. No affirmative **KILO** Live / production claims until Live proof artifacts and audit pass say otherwise.

PRs **#141–#150** close checklist gates; **#141** is the documentation and contract spine only.

---

## Four-state ladder

| State | Meaning for this arc |
|-------|----------------------|
| CODE COMPLETE | Runbook, arc map, and spine modules merged on branch |
| TEST VERIFIED | Hermetic tests assert contracts; full unittest suite green (minus documented expected failures) |
| LIVE VERIFIED | **Forbidden in #141–#149 spine.** Earned only after bounded Live proof is executed and recorded |
| PRODUCTION READY | **Forbidden** until Live VERIFIED + founder sign-off on production gates |

Historical Mercury/swarm Live evidence elsewhere in the repo does **not** substitute for a future **KILO Live proof** pass.

---

## Forbidden claims until Live proof

Do **not** document or commit affirmative statements equivalent to:

- `KILO LIVE VERIFIED`
- `KILO PRODUCTION READY`
- `KILO live build verified`

Negations (“do not claim LIVE VERIFIED”) and historical chronicle entries about other subsystems are allowed.

Hermetic tests in `tests/unit/test_kilo_live_proof_readiness_pr141.py` enforce this on spine paths.

---

## Hermetic prerequisites (before any Live proof PR)

| ID | Prerequisite | Verified by |
|----|--------------|-------------|
| H1 | `python3 -m unittest discover -s tests -t .` green (8 skipped, 3 expected failures documented) | CI / agent session |
| H2 | `python3 scripts/scan_doc_secrets.py` exit 0 | F010 gate |
| H3 | Spine docs present (see `thinkbox.kilo_live_proof_readiness.SPINE_DOC_PATHS`) | PR #141 tests |
| H4 | Runbook headings complete (`REQUIRED_RUNBOOK_HEADINGS`) | PR #141 tests |
| H5 | No affirmative KILO Live/production claims in spine files | PR #141 tests |
| H6 | Governance: side effects remain behind AdmissionGate in runtime code (architecture unchanged) | Review + existing suites |
| H7 | KILO env matrix operator gate (`scripts/verify_kilo_env_matrix.py` exit 0) | PR #142 tests |
| H8 | KILO substrate checklist operator gate (`scripts/verify_kilo_substrate_checklist.py` exit 0) | PR #143 tests |
| H9 | KILO governance-evidence operator gate (`scripts/verify_kilo_governance_evidence.py` exit 0) | PR #145 tests |
| H10 | KILO mercury-hermetic operator gate (`scripts/verify_kilo_mercury_hermetic.py` exit 0) | PR #146 tests |
| H11 | KILO swarm-instrumentation operator gate (`scripts/verify_kilo_swarm_instrumentation.py` exit 0) | PR #147 tests |
| H12 | KILO proof-schema operator gate (`scripts/verify_kilo_proof_schema.py`, `scripts/verify_kilo_dashboard_slots.py` exit 0) | PR #148 tests |
| H13 | KILO dashboard-slots operator gate (`scripts/verify_kilo_dashboard_slots.py` exit 0) | PR #149 tests |

No `INCEPTION_API_KEY` consumption is required for #141–#149 hermetic gates.

---

## Arc gates (#141–#150)

| PR | Theme (founder arc) | Gate ID | Closes in |
|----|---------------------|---------|-----------|
| **141** | Env docs + runbook spine | `spine-docs` | **Merged** |
| **142** | Hermetic KILO env matrix + redacted env contract tests | `env-matrix` | **Merged** |
| **143** | Substrate readiness checklist (Box URL/token contract) | `substrate-checklist` | **Merged** |
| **144** | CI/post-merge unittest discover green (bot merge; no arc gate closure) | `ci-post-merge` | **Merged** |
| **145** | Governance token + admission evidence shape for live burst | `governance-evidence` | **Merged** |
| **146** | Bounded Mercury hermetic mocks + live-gate stub alignment | `mercury-hermetic` | **Merged** |
| **147** | Swarm instrumentation verify (11/11 hermetic catalog) as prereq gate | `swarm-instrumentation` | #147 |
| 148 | Ledger + proof JSON schema for KILO live artifact | `proof-schema` | #148 |
| 149 | Dashboard / control-plane Live proof slots (hermetic) | `dashboard-slots` | #149 |
| 150 | Integrated rehearsal + **Live proof execution** runbook + founder ack (`THINKBOX_SWARM_LIVE_ACK`; still earns LIVE VERIFIED only when run) | `live-proof-exec` | #150 |

Optional follow-on (non-binding): cross-tab control-plane telemetry export can land in #142 if founder prioritizes UI over env matrix — must stay inside this arc.

---

## Do not claim LIVE VERIFIED

Until PR **#150** (or successor) executes a bounded Live proof and writes:

- An audit pass under `docs/audit/passes/` with `live_verified: true` **only** for the KILO Live proof scope, and  
- A proof artifact under `data/thinkboxmd/artifacts/` referenced from `docs/CONTINUITY.md`,

agents must mark this arc **CODE COMPLETE / TEST VERIFIED** at most.

---

## Spine cross-links

- Agent rules: `AGENTS.md` § KILO Live-proof readiness arc  
- Chronicle: `docs/CONTINUITY.md` (PR #141 entry)  
- Health: `docs/STATUS.md` + root `STATUS.md`  
- Arc overview: `docs/kilo-live-proof-arc.md`  
- Hermetic contract: `thinkbox/kilo_live_proof_readiness.py`
- Env matrix contract: `thinkbox/kilo_env_matrix.py`
- Operator scripts: `scripts/verify_kilo_spine.py`, `scripts/verify_kilo_env_matrix.py`, `scripts/verify_kilo_substrate_checklist.py`, `scripts/verify_kilo_governance_evidence.py`, `scripts/verify_kilo_mercury_hermetic.py`, `scripts/verify_kilo_swarm_instrumentation.py`, `scripts/verify_kilo_proof_schema.py`
- Substrate checklist: `thinkbox/kilo_substrate_checklist.py`
- Governance evidence: `thinkbox/kilo_governance_evidence.py`
- Mercury hermetic: `thinkbox/kilo_mercury_hermetic.py`
- Swarm instrumentation: `thinkbox/kilo_swarm_instrumentation.py`, `thinkbox/swarm_instrumentation_checks.py`
- Proof schema: `thinkbox/kilo_proof_schema.py`, `data/kilo_proof_schema/fixtures/`, guide `docs/guides/kilo_proof_schema.md`
- Dashboard slots: `thinkbox/kilo_dashboard_slots.py`, `data/kilo_dashboard_slots/fixtures/`, guide `docs/guides/kilo_dashboard_slots.md`

---

## Env-matrix gate (PR #142)

Gate ID: **`env-matrix`**. Hermetic only — defines modes (`hermetic_unit`, `hermetic_ci`,
`live_proof_prep`), watched env contracts, forbidden live defaults (founder live ack, KILO claim
flags, public `:8000` / `:8001` binds), and loopback/mock provider URLs when
`THINKBOX_KILO_HERMETIC_MODE` is set.

| Mode | Purpose |
|------|---------|
| `hermetic_unit` | Default unittest / agent spine checks (no provider keys) |
| `hermetic_ci` | CI runner (`CI` / `GITHUB_ACTIONS`) with operator-only forbidden checks |
| `live_proof_prep` | Checklist completeness for later Live proof (Box URL + token shapes) |

Operator verify uses **forbidden live defaults only** — presence of provider API keys in founder
CI does not fail the spine gate; unit tests use `minimal_hermetic_environ()` for strict matrix
assertions.

---

## Substrate-checklist gate (PR #143)

Gate ID: **`substrate-checklist`**. Hermetic only — layers on **`env-matrix`** (calls
`evaluate_env_matrix` / `hermetic_operator_check` first). Validates Upstash Box
`UPSTASH_PUBLIC_BOX_URL` and `UPSTASH_PUBLIC_BOX_TOKEN` readiness without live HTTP.

| Mode | Box URL / token expectation |
|------|-----------------------------|
| `hermetic_unit` / `hermetic_ci` | Absent, or mock/loopback/placeholder shapes only |
| `live_proof_prep` | `https://*.box.upstash.com` host + token shape (min length, no whitespace) |

Operator verify uses **forbidden live Box credential pairs** in hermetic paths — summaries
redact values via `redact_box_url` / `redact_box_token`.

---

## Governance-evidence gate (PR #145)

Gate ID: **`governance-evidence`**. Hermetic only — layers on **`env-matrix`** and
**`substrate-checklist`** (calls those evaluators first). Defines a redacted **live-burst
evidence** shape binding `agent_id`, capability scope, `policy_version`, admission
allow/deny + reason codes, **token fingerprint only** (never raw `token_value`), substrate
and env-matrix summary refs, timestamps, `evidence_label` (`inferred` | `recorded`), and
`live_api_called=False` in hermetic modes.

| Mode | Admission / evidence expectation |
|------|----------------------------------|
| `hermetic_unit` / `hermetic_ci` | Valid in-memory governance token + identity capability; deny missing/expired/revoked/capability miss |
| `live_proof_prep` | Same admission contract; substrate + env-matrix prep shapes must pass |

Operator verify uses **forbidden production governance tokens** in hermetic paths and never
consumes `INCEPTION_API_KEY`. Summaries redact via `redact_secret_value` / `token_fingerprint`.

---

## Mercury-hermetic gate (PR #146)

Gate ID: **`mercury-hermetic`**. Hermetic only — layers on **`governance-evidence`**
(calls `evaluate_governance_evidence` / `hermetic_governance_operator_check` first).
Provides bounded **`BoundedMercuryMockClient`** fixtures (JSON answer + reasoning fields)
for Live-proof prep shape, aligned with **`thinkbox/cli_live_gate`** authorization-only
reporting (`authorized` when founder ack + provider credential present;
`live_api_called=False` always in hermetic modes).

| Mode | Mercury mock / live-gate expectation |
|------|----------------------------------------|
| `hermetic_unit` / `hermetic_ci` | `THINKBOX_KILO_MERCURY_MOCK=hermetic` or `mock://` provider URL; mock completion only |
| `live_proof_prep` | Same mock contract + governance token admission; no live HTTP |

Operator verify fails closed on production-shaped provider keys without mock mode.
Summaries redact via `redact_secret_value` / `redact_mercury_summary`.

---

## Swarm-instrumentation gate (PR #147)

Gate ID: **`swarm-instrumentation`**. Hermetic only — layers on **`mercury-hermetic`**
(calls `hermetic_mercury_operator_check` first). Wraps ten self-contained instrumentation
checks from `thinkbox/swarm_instrumentation_checks` (shared with
`experiments/verify_instrumentation.py`) plus an eleventh catalog entry:
**live swarm deferred** (the optional `--live` swarm path is never run in this gate).

| Check band | Expectation |
|------------|-------------|
| `inst-01` … `inst-10` | Hermetic instrument checks (10/10 pass) |
| `inst-11` | Verifier script present; `live_swarm_invoked=false`; `live_api_called=false` |

Operator verify fails closed on production-shaped provider keys without mercury mock.
Summaries redact via `redact_secret_value` / `redact_swarm_summary`.

---

## Proof-schema gate (PR #148)

Gate ID: **`proof-schema`**. Hermetic only — layers on **`swarm-instrumentation`**
(calls `hermetic_swarm_operator_check` first). Defines a JSON document contract
(`kilo-proof-v1`) for KILO ledger + live-proof artifacts: `receipt_key`, `etag`,
`prior_gate_ids` (intersection admission — all listed gates must be
`hermetic_operator_ok`), dependency graph (`depends_on` over gate node ids with
cycle rejection), cue types (`user` vs `injected_nudge` / `cron` / `subagent_completion`
/ `gate_ready` / `blocker` — injected cues must not set `counts_as_user_intent`),
optional north-star / roadmap / tasks refs, idle/resume fields (`idle_secs`,
`max_cycles`, `stop_sentinel`), `definition_of_done` predicates, and `halt_reason`
kill-switch enums. Four-state honesty is fail-closed: `LIVE_VERIFIED` /
`PRODUCTION_READY` require `live_verified: true` and all DoD `met: true`.

| Fixture band | Expectation |
|--------------|-------------|
| `valid_*.json` | `validate_proof_document` returns ok |
| `invalid_*.json` | Fail-closed with `_expect: invalid` |

Operator verify runs after swarm-instrumentation; `live_api_called=false` always in
hermetic modes. Summaries redact via `redact_proof_summary`.

Optional non-binding next gate: **#149 `dashboard-slots`**.

---

## Verification commands

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr141 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr142 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr143 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr145 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr146 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr147 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr148 -v
python3 scripts/verify_kilo_env_matrix.py
python3 scripts/verify_kilo_substrate_checklist.py
python3 scripts/verify_kilo_governance_evidence.py
python3 scripts/verify_kilo_mercury_hermetic.py
python3 scripts/verify_kilo_swarm_instrumentation.py
python3 scripts/verify_kilo_proof_schema.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
python3 -m unittest discover -s tests -t .
```

**Revision:** PR #148 proof-schema — hermetic only; Live proof not executed.
