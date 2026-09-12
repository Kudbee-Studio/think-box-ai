  # RESEARCH.md — Doginals Indexer-Split Thesis

## The Thesis

Different Doginals/DRC-20 indexers disagree on which deployment transaction is
"canonical" for a given token. Specifically for DOGI:

- The **original 21M DOGI deploy** is recognized by some indexers as the canonical token.You
- A **later 2.1B DOGI deploy** is recognized by other indexers as canonical.
- This creates a split where different marketplaces/wallets show different
  supplies, holders, and transaction histories for the "same" token ticker.

## What This Proves

By querying multiple public indexers for the same inscription IDs and comparing
responses, we can prove that:

1. Different indexers return different data for the same inscription.
2. Some indexers recognize the original deploy, others recognize the later one.
3. This is a **data availability / consensus problem**, not a bug in any single indexer.

## How to Rerun

```bash
# 1. Start Ollama (if using local models)
ollama serve &

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Run the proof script
python scripts/prove_dogi.py

# 4. Or use the API directly
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Verify the Doginals indexer-split case..."}'

# 5. View findings
cat data/findings/dogi_indexer_split.md
```

## Architecture

```
Agent Loop (core/runtime/loop.py)
  │
  ├── fs_read / fs_write / fs_list    → data/ directory (jailed)
  ├── http_get                        → public APIs (rate-limited, saved to data/raw/)
  ├── memory_put / memory_get / search → SQLite (data/thinkbox.sqlite)
  ├── doge_tx                         → dogechain.info
  ├── doginals_inscription            → multiple indexers
  ├── compare_inscription             → cross-indexer diff
  ├── parse_drc20                     → DRC-20 JSON parsing
  └── load_fixture                    → data/fixtures/*.json
```

## Sources Tested

| Source | Type | Status |
|--------|------|--------|
| dogechain.info | Dogecoin tx explorer | Public API |
| ordinalswallet.com | Ordinals indexer | Public API |
| wonky-ordinals.fly.dev | Ordinals indexer | Public API |
| doginals.org | Doginals-specific | Public API |
| unisat.io | Multi-chain indexer | Public API (key may be needed) |

## Success Criteria

- [ ] Agent can list data/ and write files
- [ ] Agent can hit at least one live indexer
- [ ] compare_inscription produces a real diff object
- [ ] data/findings/dogi_indexer_split.md exists after one run
- [ ] SQLite has the run + findings
- [ ] A second run with a NEW inscription id works without code changes

## Future Work

- Same pattern applies to BRC-20 (different ordinal indexers disagree)
- Same pattern applies to Runes (different rune indexers disagree)
- Could extend to CEX vs on-chain balance mismatches
- Could add automated monitoring that alerts when indexer consensus breaks
