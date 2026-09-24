# KILO Live-proof readiness runbook

**Status:** PR #141–#149 merged + PR #150 `live-proof-exec` (PR #144 = CI/post-merge fix only) — **arc season closed** at hermetic TEST VERIFIED; **not** Live proof executed.  
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
| LIVE VERIFIED | **Forbidden in #141–#150 hermetic PR.** Earned only after founder-run bounded Live proof + audit artifact |
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
| H12 | KILO proof-schema operator gate (`scripts/verify_kilo_proof_schema.py` exit 0) | PR #148 tests |
| H13 | KILO dashboard-slots operator gate (`scripts/verify_kilo_dashboard_slots.py` exit 0) | PR #149 tests |
| H14 | KILO live-proof-exec operator gate (`scripts/verify_kilo_live_proof_exec.py` exit 0) | PR #150 tests |
| H15 | KILO live-smoke-evidence operator gate (`scripts/verify_kilo_live_smoke_evidence.py` exit 0) | PR #152 tests |
| H16 | KILO live-smoke-operator gate (`scripts/verify_kilo_live_smoke_operator.py` exit 0) | PR #153 tests |
| H17 | KILO control-plane-api gate (`scripts/verify_kilo_control_plane_api.py` exit 0) | PR #154 tests |
| H18 | KILO receipt-chain-etag gate (`scripts/verify_kilo_receipt_chain_etag.py` exit 0) | PR #155 tests |
| H19 | KILO dashboard-receipt-chain-bind gate (`scripts/verify_kilo_dashboard_receipt_chain_bind.py` exit 0) | PR #156 tests |
| H20 | KILO api-ops-harden gate (`scripts/verify_kilo_api_ops_harden.py` exit 0) | PR #157 tests |
| H21 | KILO end-link-deepen gate (`scripts/verify_kilo_end_link_deepen.py` exit 0) | PR #158 tests |
| H22 | KILO end-link-operator-ux gate (`scripts/verify_kilo_end_link_operator_ux.py` exit 0) | PR #159 tests |
| H23 | KILO receipt-chain-end-link-docs gate (`scripts/verify_kilo_receipt_chain_end_link_docs.py` exit 0) | PR #160 tests |
| H24 | KILO governance-evidence Live-proof readiness gate (`scripts/verify_kilo_governance_evidence_live_proof_readiness.py` exit 0) | PR #164 tests |
| H25 | KILO PR #165 combined harden + era chronicle (`scripts/verify_kilo_pr165_combined_harden.py` exit 0) | PR #165 tests |
| H26 | KILO PR #166 combined post-#165 lane (`scripts/verify_kilo_pr166_combined_post165_lane.py` exit 0) | PR #166 tests |
| H27 | KILO PR #167 combined post-#166 lane (`scripts/verify_kilo_pr167_combined_post166_lane.py` exit 0) | PR #167 tests |
| H28 | KILO PR #168 combined post-#167 lane (`scripts/verify_kilo_pr168_combined_post167_lane.py` exit 0) | PR #168 tests |
| H29 | KILO PR #169 combined post-#168 lane (`scripts/verify_kilo_pr169_combined_post168_lane.py` exit 0) | PR #169 tests |
| H30 | Beyond-KILO lint readiness (`scripts/verify_kilo_beyond_kilo_lint.py` exit 0; ruff/mypy/bandit scoped) | PR #170 tests |

No `INCEPTION_API_KEY` consumption is required for #141–#170 hermetic gates.

**Spine verify modes:** `python3 -u scripts/verify_kilo_spine.py` defaults to **fast** mode
(skips nested control-plane e2e unittest subprocess; static gates still run). Use
`python3 -u scripts/verify_kilo_spine.py --e2e` for the full nested e2e unittest suite
(bounded timeout; not required on every PR).

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
| **150** | Live-proof **execution plan** + founder ack contract (`THINKBOX_SWARM_LIVE_ACK` + `UPSTASH_PUBLIC_BOX_URL`; LIVE VERIFIED only when founder runs proof) | `live-proof-exec` | **#150 (season close)** |

**Season close (#150):** Arc #141–#150 checklist is complete at CODE COMPLETE / TEST VERIFIED. Cloud Bot on standby — no #151 unless founder asks. Spine `live_verified: true` remains earned only via founder-run bounded smoke + `data/thinkboxmd/artifacts/kilo_live_proof_*.json` + audit pass scoped to KILO Live proof.

---

## Do not claim LIVE VERIFIED

Until PR **#150** (or successor) executes a bounded Live proof and writes:

- An audit pass under `docs/audit/passes/` with `live_verified: true` **only** for the KILO Live proof scope, and  
- A proof artifact under `data/thinkboxmd/artifacts/` referenced from `docs/CONTINUITY.md`,

agents must mark this arc **CODE COMPLETE / TEST VERIFIED** at most.

---

## Bounded live smoke evidence (#152)

Gate ID: **`live-smoke-evidence`**. Layers on **`post-season-harden`** and **`live-proof-exec`**.
Hermetic only in CI — binds receipt ids, etags, and gate-chain hops into
`kilo-live-smoke-evidence-v1` JSON. `audit_flip_candidate` refuses `live_verified: true`
unless founder ack marker, Box URL present flag, `live_api_called`, and on-disk artifact path
all validate.

### Founder bounded smoke → artifact → audit flip

1. `python3 scripts/verify_kilo_spine.py` and `python3 scripts/verify_kilo_live_smoke_evidence.py` (hermetic).
2. Export `THINKBOX_SWARM_LIVE_ACK=1` and `UPSTASH_PUBLIC_BOX_URL` (preview Box host only).
3. Run bounded smoke (single governed call path); set `founder_ack_marker_present` and `box_url_present` in evidence JSON.
4. Write `data/thinkboxmd/artifacts/kilo_live_smoke_<id>.json`; record SHA256 in this chronicle.
5. Use `thinkbox.kilo_live_smoke_evidence.audit_flip_candidate` to build a **candidate** audit pass; founder writes `docs/audit/passes/*` only when predicates pass.

Optional `--live` on the verify script checks env readiness only (no HTTP). Default CI path keeps `live_verified: false`.

Guide: `docs/guides/kilo_live_smoke_evidence.md`

---

## Live-smoke operator path (#153)

Gate ID: **`live-smoke-operator`**. Layers on **`live-smoke-evidence`** (#152 merged).
Hermetic CLI writes `data/thinkboxmd/artifacts/kilo_live_smoke_*.json` and emits
`docs/audit/passes/*-live-candidate.json` via `audit_flip_candidate` — default CI keeps
`live_api_called: false` and audit `live_verified: false`.

### Founder bounded smoke → write artifact → flip candidate

1. `python3 scripts/verify_kilo_live_smoke_operator.py` (hermetic).
2. Export `THINKBOX_SWARM_LIVE_ACK=1` and `UPSTASH_PUBLIC_BOX_URL` for live prep only.
3. `python3 scripts/kilo_live_smoke_operator.py write --evidence-id <id>` (hermetic dry-run) or record real smoke fields.
4. `python3 scripts/kilo_live_smoke_operator.py audit-flip-candidate --evidence-path <artifact>` → review candidate JSON.
5. Founder promotes audit pass only when #152 predicates pass; chronicle SHA256.

Guide: `docs/guides/kilo_live_smoke_operator.md`

---

## Spine cross-links

- Agent rules: `AGENTS.md` § KILO Live-proof readiness arc  
- Chronicle: `docs/CONTINUITY.md` (PR #141 entry)  
- Health: `docs/STATUS.md` + root `STATUS.md`  
- Arc overview: `docs/kilo-live-proof-arc.md`  
- Hermetic contract: `thinkbox/kilo_live_proof_readiness.py`
- Env matrix contract: `thinkbox/kilo_env_matrix.py`
- Operator scripts: `scripts/verify_kilo_spine.py`, `scripts/verify_kilo_env_matrix.py`, `scripts/verify_kilo_substrate_checklist.py`, `scripts/verify_kilo_governance_evidence.py`, `scripts/verify_kilo_mercury_hermetic.py`, `scripts/verify_kilo_swarm_instrumentation.py`, `scripts/verify_kilo_proof_schema.py`, `scripts/verify_kilo_dashboard_slots.py`, `scripts/verify_kilo_live_proof_exec.py`
- Substrate checklist: `thinkbox/kilo_substrate_checklist.py`
- Governance evidence: `thinkbox/kilo_governance_evidence.py`
- Mercury hermetic: `thinkbox/kilo_mercury_hermetic.py`
- Swarm instrumentation: `thinkbox/kilo_swarm_instrumentation.py`, `thinkbox/swarm_instrumentation_checks.py`
- Proof schema: `thinkbox/kilo_proof_schema.py`, `data/kilo_proof_schema/fixtures/`, guide `docs/guides/kilo_proof_schema.md`
- Dashboard slots: `thinkbox/kilo_dashboard_slots.py`, `data/kilo_dashboard_slots/fixtures/`, guide `docs/guides/kilo_dashboard_slots.md`
- Live-proof exec: `thinkbox/kilo_live_proof_exec.py`, `data/kilo_live_proof_exec/fixtures/`, guide `docs/guides/kilo_live_proof_exec.md`
- Live smoke evidence: `thinkbox/kilo_live_smoke_evidence.py`, `data/kilo_live_smoke_evidence/fixtures/`, guide `docs/guides/kilo_live_smoke_evidence.md`
- Live smoke operator: `thinkbox/kilo_live_smoke_operator.py`, `scripts/kilo_live_smoke_operator.py`, guide `docs/guides/kilo_live_smoke_operator.md`
- Control-plane API (PR #154): `thinkbox/kilo_control_plane_api.py`, guide `docs/guides/kilo_control_plane_api.md`
- Receipt-chain / ETag (PR #155): `thinkbox/kilo_receipt_chain_etag.py`, guide `docs/guides/kilo_receipt_chain_etag.md`
- Dashboard receipt-chain / END_LINK bind (PR #156): `thinkbox/kilo_dashboard_receipt_chain_bind.py`, guide `docs/guides/kilo_dashboard_receipt_chain_bind.md`

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

---

## Dashboard-slots gate (PR #149)

Gate ID: **`dashboard-slots`**. Hermetic only — layers on **`proof-schema`**
(calls `hermetic_proof_schema_operator_check` first). Defines control-plane
**slot bindings** for future Live-proof UI (not live HTTP in this gate):
`proof_receipt`, `gate_status`, `swarm_digest`, `governance_evidence`,
`mercury_hermetic`, `cue_inbox`, `dod_checklist`. Each slot binds
`receipt_key` + `etag` + optional `multiplex_digest_id` (via
`build_multiplex_digest_identity`, aligned with Think Job receipt watch /
jobs digest multiplex from PR #139–#140). Fail-closed on unbound slots,
stale etags (`stale_after_etag`), exclusive receipt multiplex conflicts,
slot `depends_on` cycles, injected cues marked as user intent, and any
`dashboard_live_claim` that affirms KILO Live/production status. Slot-level
`prior_gate_ids` and `definition_of_done_display` are **display-only**
metadata — they do not earn LIVE VERIFIED.

| Fixture band | Expectation |
|--------------|-------------|
| `valid_*.json` | `validate_slot_registry_document` returns ok |
| `invalid_*.json` | Fail-closed (unbound, stale, multiplex, cycle, live claim) |

Operator verify runs after proof-schema; `live_api_called=false` always in
hermetic modes. Summaries redact via `redact_dashboard_slots_summary`.

---

## Live-proof-exec gate (PR #150) — season closer

Gate ID: **`live-proof-exec`**. Hermetic only — layers on **`dashboard-slots`**
(calls `hermetic_dashboard_slots_operator_check` first). Defines a bounded **execution
plan** (`kilo-live-proof-exec-v1`) for a future founder-run Live proof: full
`prior_gate_ids` chain (spine through dashboard-slots), canonical
`THINKBOX_SWARM_LIVE_ACK` + `UPSTASH_PUBLIC_BOX_URL` env keys, smoke step catalog,
artifact path under `data/thinkboxmd/artifacts/kilo_live_proof_*.json`, halt reasons
from proof-schema `HALT_REASONS`, and season marker
`kilo-live-proof-arc-141-150-season-closed`. Fail-closed: `live_verified: true` and
`live_api_called: true` are rejected in hermetic plans; hermetic modes reject
founder ack + Box URL together (live prep belongs to optional `--live` check only).

| Step (bounded smoke) | Network |
|----------------------|---------|
| `verify_kilo_spine.py` | none |
| `verify_kilo_live_proof_exec.py` | none |
| Substrate URL shape check | none |
| Founder ack export | none |
| Single bounded Mercury smoke | founder-run optional |
| Write proof artifact | none |
| Audit flip (`live_verified: true`) | none — only after artifact on disk |

Operator `scripts/verify_kilo_live_proof_exec.py` defaults to hermetic mode
(`live_api_called=false`). Optional `--live` verifies ack + URL presence only — **no HTTP**.

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
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr149 -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr150 -v
python3 scripts/verify_kilo_env_matrix.py
python3 scripts/verify_kilo_substrate_checklist.py
python3 scripts/verify_kilo_governance_evidence.py
python3 scripts/verify_kilo_mercury_hermetic.py
python3 scripts/verify_kilo_swarm_instrumentation.py
python3 scripts/verify_kilo_proof_schema.py
python3 scripts/verify_kilo_dashboard_slots.py
python3 scripts/verify_kilo_live_proof_exec.py
python3 scripts/verify_kilo_post_season_harden.py
python3 scripts/verify_kilo_spine.py
python3 scripts/scan_doc_secrets.py
python3 -m unittest discover -s tests -t .
```

**Revision:** PR #151 post-season harden — ops CI + branch hygiene; arc #141–#150 remains closed at TEST VERIFIED.

---

## Post-season harden (PR #151)

Gate ID: **`post-season-harden`**. Hermetic only — layers on **`live-proof-exec`**
(`hermetic_live_proof_exec_operator_check` first). Not an arc #141–#150 gate. Validates
CI workflow snippets (`verify_kilo_spine.py`, `verify_kilo_post_season_harden.py`,
`scan_doc_secrets.py`), presence of spine operator scripts, frozen checklist
`data/kilo_post_season_harden/checklist.json`, and branch hygiene tooling
(`scripts/cleanup_merged_cursor_branches.py` + `docs/runbooks/branch-hygiene.md`).
Dry-run is the default for remote branch deletes; protected branches never removed.

| Check | Expectation |
|-------|-------------|
| `verify_kilo_post_season_harden.py` | exit 0, `live_api_called=false` |
| `cleanup_merged_cursor_branches.py` | dry-run unless `--execute` |
| Four-state | TEST VERIFIED max — not LIVE VERIFIED |

Add to verification block:

```bash
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr151 -v
python3 scripts/verify_kilo_post_season_harden.py
python3 scripts/cleanup_merged_cursor_branches.py
```
