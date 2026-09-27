# KILO governance-evidence Live-proof readiness (PR #164)

Hermetic gate: **governance-evidence-live-proof-readiness**. Four-state on this branch:
**CODE COMPLETE / TEST VERIFIED** only — not KILO LIVE VERIFIED.

## Honesty markers

- `live_verified: false`
- `live_api_called: false`
- `four_state_max`: `TEST_VERIFIED`

Do not claim `KILO LIVE VERIFIED`, `KILO PRODUCTION READY`, or `KILO live build verified`
on spine paths until founder-run proof + audit + artifacts say otherwise.

## Layers

1. PR #162 `control-plane-e2e-deepen` (immediate prior)
2. PR #145 `governance-evidence` (admission + evidence shape)
3. PR #164 `governance-evidence-live-proof-readiness` (this gate)

## Documented live prerequisites (not required for hermetic verify)

| Env key | Purpose |
|---------|---------|
| `THINKBOX_SWARM_LIVE_ACK` | Founder acknowledgment before optional live prep |
| `UPSTASH_PUBLIC_BOX_URL` | Public Box substrate URL for live prep |

Hermetic operator verify **must not** call Box/Mercury/Inception. If both prereqs are
satisfied while running in `hermetic_unit` / `hermetic_ci`, the gate fails closed
(`live_prereqs_in_hermetic`).

## Readiness checks

- `governance_evidence_hermetic_unit` — `evaluate_governance_evidence` with in-memory token
- `documented_founder_ack` — documented, not satisfied in CI
- `documented_box_url` — documented, not satisfied in CI
- `no_live_api_in_hermetic` — `live_api_called: false`

## Verify commands

```bash
python3 scripts/verify_kilo_governance_evidence_live_proof_readiness.py
python3 -m unittest tests.unit.test_governance_evidence_live_proof_readiness -v
python3 -m unittest tests.unit.test_kilo_governance_evidence_live_proof_readiness_gate -v
python3 -m unittest tests.unit.test_kilo_live_proof_readiness_pr164 -v
python3 scripts/verify_kilo_spine.py
```

## Audit

- Pass: `docs/audit/passes/2026-09-23-pr164.json` (`live_verified: false`)
- Checklist: `docs/audit/checklists/kilo-governance-evidence-live-proof-readiness-pr164.md`
