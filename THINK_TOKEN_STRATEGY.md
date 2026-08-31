# THINK Token & Training Strategy

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
