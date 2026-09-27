# Audit checklist — PR #164 governance-evidence Live-proof readiness

- [ ] `gate_id`: `governance-evidence-live-proof-readiness`
- [ ] `live_verified`: **false** on audit pass, checklist, and contract summary
- [ ] `live_api_called`: **false** everywhere in hermetic paths
- [ ] `four_state_max`: `TEST_VERIFIED` only — do not claim LIVE VERIFIED
- [ ] Founder ack env `THINKBOX_SWARM_LIVE_ACK` documented as live prereq (not required for hermetic verify)
- [ ] Box URL env `UPSTASH_PUBLIC_BOX_URL` documented as live prereq (not required for hermetic verify)
- [ ] PR #145 `governance-evidence` hermetic_unit passes via `evaluate_governance_evidence_hermetic_unit`
- [ ] `python3 scripts/verify_kilo_governance_evidence_live_proof_readiness.py` exits 0
- [ ] `python3 scripts/verify_kilo_spine.py` exits 0 after spine wiring
