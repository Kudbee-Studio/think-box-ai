# KILO Live-proof readiness runbook

**Status:** PR **#141** spine + PR **#142** `env-matrix` + PR **#143** `substrate-checklist` — **not** Live proof.  
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

No `INCEPTION_API_KEY` consumption is required for #141–#143 hermetic gates.

---

## Arc gates (#141–#150)

| PR | Theme (founder arc) | Gate ID | Closes in |
|----|---------------------|---------|-----------|
| **141** | Env docs + runbook spine | `spine-docs` | **Merged** |
| **142** | Hermetic KILO env matrix + redacted env contract tests | `env-matrix` | **Merged** |
| **143** | Substrate readiness checklist (Box URL/token contract) | `substrate-checklist` | **This PR (draft)** |
| 144 | Governance token + admission evidence shape for live burst | `governance-evidence` | #144 |
| 145 | Bounded Mercury hermetic mocks + live-gate stub alignment | `mercury-hermetic` | #145 |
| 146 | Swarm instrumentation verify (11/11) as prereq gate | `swarm-instrumentation` | #146 |
| 147 | Ledger + proof JSON schema for KILO live artifact | `proof-schema` | #147 |
| 148 | Dashboard / control-plane Live proof slots (hermetic) | `dashboard-slots` | #148 |
| 149 | Founder ack env (`THINKBOX_SWARM_LIVE_ACK`) runbook wiring | `founder-ack` | #149 |
| 150 | Integrated rehearsal + **Live proof execution** runbook (still earns LIVE VERIFIED only when run) | `live-proof-exec` | #150 |

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
- Operator scripts: `scripts/verify_kilo_spine.py`, `scripts/verify_kilo_env_matrix.py`, `scripts/verify_kilo_substrate_checklist.py`
- Substrate checklist: `thinkbox/kilo_substrate_checklist.py`

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

## Verification commands

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr141 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr142 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr143 -v
python3 scripts/verify_kilo_env_matrix.py
python3 scripts/verify_kilo_substrate_checklist.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
python3 -m unittest discover -s tests -t .
```

**Revision:** PR #143 substrate-checklist — hermetic only; Live proof not executed.
