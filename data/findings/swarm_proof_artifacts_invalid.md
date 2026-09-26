# Finding: 14 of 38 committed swarm proof artifacts fail the repo's own validator

**Date:** 2026-09-26
**Discovered by:** repo audit (`thinkbox.cli_inspect.validate_proof_document`)
**Severity:** Low — none of these files are cited as evidence in AGENTS.md
**Status:** Fixed in PR #253 (artifacts patched to mark partial runs honestly)

## Evidence

```
python3 -c "import json,glob; from thinkbox.cli_inspect import validate_proof_document as v; \
  [print(f, v(json.load(open(f)))) for f in sorted(glob.glob('data/thinkboxmd/big_swarm_*.json')) if v(json.load(open(f)))]"
```

All 14 report `total_calls 224 != primary+validators (256)`:
`big_swarm_20260921_152505`, `_152808`, `_152920`, `_164615`, `_164621`,
`_164715`, `_171840`, `_171936`, `_171948`, `_172040`, `_172051`, `_172313`,
`_172322`, `_172331`.

The artifacts AGENTS.md §13.7 cites (`_135102`, `_135330`, `_152452`,
`_152726`, `_152748`, `_152836`, `_152859`, `_152948`) validate.

## Impact

- `thinkbox swarm agents|status` (newest-first) silently skip these files, so
  "newest proof" views reflect older runs.
- `tests.unit.test_cli.TestCliSwarm.test_swarm_agents_json` failed on `main`
  because it read the newest (invalid) file; it now isolates its sample.

## Resolution (PR #253)

All 14 files patched to honestly reflect partial execution:
- `partial_run: true` and `partial_run_reason` added
- `declared_validator_workers` preserves the original 32
- `validator_workers` corrected to 0 (no validator calls were made)
- `reconciliation.total_calls` left at 224 (the actual call count)
- All 38 proof artifacts now pass `validate_proof_document`
