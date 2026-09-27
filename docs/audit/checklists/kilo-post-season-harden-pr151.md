# Audit checklist — post-season harden (PR #151)

- [ ] `thinkbox/kilo_post_season_harden.py` layers on live-proof-exec
- [ ] `scripts/verify_kilo_post_season_harden.py` exit 0 hermetic
- [ ] `scripts/cleanup_merged_cursor_branches.py` dry-run default; protected branches
- [ ] `.github/workflows/test.yml` runs spine + post-season + secrets scan
- [ ] `verify_kilo_spine.py` requires `post_season_harden.hermetic_operator_ok`
- [ ] Docs: arc season closed; #151 ops harden documented
- [ ] Audit pass `live_verified: false`
- [ ] No live HTTP in PR #151 paths

Runbook: `docs/runbooks/branch-hygiene.md`
