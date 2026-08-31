# Roadmap

Last updated: 2026-08-31
Branch of record: `session/agent_79e656bf-clean` (latest known commit `641903b`)

## Now — phone / Upstash (GPU stopped)

- [x] Clean branch with no `gsk_`
- [x] Honest DOGI finding (unproven)
- [x] Researcher hat notes
- [ ] `jobs/` schema in repo (Think Job JSON)
- [ ] `AGENTS.md` + MISSION + this file in the repo
- [ ] Tool-only proof stays the default when no LLM is on the box

## Next laptop session (human starts GPU)

1. Start `00d832ec-8565-447b-86ac-74bf9bd41e57` from the panel only.
2. SSH to `87.58.150.62` with a key Kudbee names. Halt if the key is missing.
3. `nvidia-smi`, find 20B then 120B on **data** disks, not the 50GB boot disk.
4. Write paths into `data/infra_upcloud.ini`.
5. Serve 20B only if Kudbee says serve. `openai_compat` → that host.
6. One Researcher Job against DOGI fixtures. Shut down when done.

## After first GPU proof

- Wallet scan for holdings Kudbee already has
- Public "marketplace vs chain" page or paid single-report
- Same Job schema on Bitcoin BRC-20 / Runes (pack swap, not a rewrite)

## Later (not this week)

- Director hat + child Jobs
- Media / film packs
- THINK COMMONS index of completed Jobs
- Optional credit rail, then maybe $THINK

## Kill list

Create/delete UpCloud servers · assume `~/.ssh/kilo-upcloud` · push secrets · call `api.inception.ai` from the box · leave 3×L40S started idle · declare indexer-split proven on 403/404/DNS.
