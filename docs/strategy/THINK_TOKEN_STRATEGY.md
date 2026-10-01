# THINK Token & Training Strategy

> **Status (2026-09-30): planning draft, mostly not implemented. Not about the Think Token learning system.**
>
> This file is about the **THNK economic token** (staking, rewards, votes, paying for compute) and a plan to fine-tune a
> model on doginals/ordinals indexer research. It is **not** about the Think Tokens from #288 (learning units;
> `apps/web/think-token*.ts`, AGENTS.md section 1.3a). They share a name and nothing else.
>
> What exists today (checked 2026-09-30): `think_box_ai/token.py` is a 36-line balance/transfer class;
> `thinkbox/economy.py` holds in-memory Phase 9 classes (accounts, staking, slashing, treasury) with unit tests, no
> persistence and no production caller; the research tools (`doge_tx`, `compare_inscription`) live in
> `core/tools/doginals.py`. There is no rate-limit tiering, no training-data export and no fine-tuning pipeline, and nothing
> else in the repository refers to this file.
>
> Enterprise arc: out of scope. THNK must never be an authorization input (who may do what comes from roles, agent grants and
> tenant quotas); see ADR 027, proposed in PR #303. Training on customer data would also need per-tenant consent, and
> changing the default model provider needs benchmarks first (AGENTS.md section 1.5).

## THINK Token (THNK) — Utility Plan

The token exists in `think_box_ai/token.py` as a basic balance/transfer class.
Here's how to give it real utility in the research agent:

### 1. Access Control
- Stake THNK to unlock advanced tools (compare_inscription, doge_tx)
- Higher stake = higher rate limits on API calls
- Free tier: 5 requests/day, Staked tier: unlimited

### 2. Research Rewards
- Earn THNK for contributing verified findings
- Peer review system: validate others' research for rewards
- Canonical findings (agreed by 3+ indexers) earn bonus

### 3. Governance
- Vote on which indexers to add
- Vote on dispute resolution when indexers disagree
- Propose new research targets

### 4. Payment
- Pay for API calls with THNK (instead of fiat)
- Pay for compute (box time) with THNK
- Marketplace for research reports

## Training the System

### What to train on:
1. **Research findings** — Every verified indexer split becomes training data
2. **Tool call patterns** — How the agent uses tools to prove/disprove claims
3. **Source reliability** — Which indexers are most accurate over time

### How to train:
1. **Collect** — Run the proof script, store findings in SQLite
2. **Curate** — Manually verify findings, mark as true/false splits
3. **Fine-tune** — Use curated data to fine-tune a small model (Llama 8B)
4. **Evaluate** — Test the fine-tuned model on new inscription IDs

### Training data format:
```json
{
  "inscription_id": "...",
  "indexers_tested": ["ordinalsdotcom", "wonky", "doginals_org"],
  "split_detected": true,
  "original_deploy_visible_on": ["ordinalsdotcom"],
  "later_deploy_visible_on": ["wonky"],
  "conclusion": "Indexer split confirmed for DOGI token",
  "confidence": 0.95
}
```

### Next steps:
1. Run 10+ proof runs with different inscription IDs
2. Store all findings in SQLite
3. Export to JSONL for fine-tuning
4. Fine-tune Llama 8B on the research patterns
5. Deploy the fine-tuned model as the default provider
