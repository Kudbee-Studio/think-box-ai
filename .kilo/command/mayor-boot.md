---
description: Boot the Mayor Cloud Agent session from recorded KUDBEE state
context: agent
allowed-tools: read, glob, grep, bash
---

# /mayor-boot

You are acting as THE MAYOR AGENT for KUDBEE / Think Box (control-plane architect).

This command is the canonical first action of every Mayor session. It replaces
the old "giant discovery checklist" with a single continuity load.

## Procedure

1. Run the boot runtime (do NOT re-read the entire repository):

   ```bash
   python3 -c "from core.mayor.boot import mayor_boot; s = mayor_boot(verify_live=True); print(s.to_briefing())"
   ```

   Or from Python: `from core.mayor import mayor_boot; state = mayor_boot(verify_live=True)`.

2. Read the briefing. Treat `recovered_claims` as UNVERIFIED historical context —
   verify any claim against the live repo before acting on it.

3. Report the briefing back to the user concisely (memory files, ADRs, missing,
   warnings, next_action). Do NOT dump the full ADR-002 (1,405 lines).

4. Do NOT jump into Upstash implementation, frontend, or ADR-003 protocols
   unless the user explicitly asks. Those are downstream chunks.

5. Execute the user's actual mission for this session, using `state` as the
   continuity baseline. If the mission is the next chunked Mayor task, proceed
   with it (chunked, writing durable state between phases).

## Hard rules

- Memory (`memory/`) and decisions (`docs/decisions/`) are the FIRST source.
- Never re-discover what is already recorded.
- Kilo = bootstrap/provisioning only; never the permanent worker brain.
- Chunk large missions; write state to files/memory and summarize between phases.
