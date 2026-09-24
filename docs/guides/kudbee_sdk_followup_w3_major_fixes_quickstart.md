# Kudbee SDK follow-up wave 3 major fixes (PR #192)

Hermetic major-fix pack for `thinkbox/kudbee_sdk_followup_w3_major_fixes/` after merged **#191**.
**Four-state cap:** CODE COMPLETE / TEST VERIFIED only — not LIVE VERIFIED.

## Verify gate

```bash
python3 scripts/verify_kilo_pr192_kudbee_sdk_followup_w3_major_fixes.py
```

## Run all fixes (dry-run)

```bash
python3 examples/kudbee_sdk_followup_w3_major_fixes_quickstart.py
```

## Gate id

`kudbee-sdk-followup-w3-major-fixes` — 35 fixes (`FIX01`–`FIX35`).

## Expansion packs (long-range connections + energy loops)

26 hermetic expansion packs (`EXP01`–`EXP26`) under `thinkbox/kudbee_sdk_followup_w3_expansion/`:

```bash
python3 -m unittest tests.unit.test_kudbee_sdk_followup_w3_expansion_packs -v
```

Manifest: `data/kudbee_sdk_followup_w3_major/pr192_expansion_packs.json`
