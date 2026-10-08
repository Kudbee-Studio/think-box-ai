# P3.75: safe-by-default runs

Survey of every tool the agent can call (14 in `TOOLS`), by what it can do to the machine and what stands between a model's request and that effect.

| Tool | Can do | Gate | State |
|---|---|---|---|
| list_files, read_file | read the session folder (or the chosen repository) | path confinement, symlink check | PROVEN (`tests/tool-safety.test.ts`, `file-confinement`) |
| repo_search, repo_read | read the repository root | confinement; opt-in tool | PROVEN |
| recall | read memory | none needed | READ |
| write_file | write in the session folder or chosen repository | confinement, `.git` refused; **overwriting an existing file asks a human**; a new file does not | PROVEN (ask + denial leaves the file as it was) |
| fetch_url | HTTP GET to any URL | **asks on the first visit to a host; a redirect to another host now asks too** | PROVEN (this PR) |
| read_rss | HTTP GET through the `rss_feed` plugin | asks on first host; the plugin's own guard follows redirects hop by hop and refuses local/private addresses without approval (`net-guard.ts`) | PROVEN (asks; nothing leaves on denial) |
| live_lookup, algorand, medication | HTTP GET to one fixed API host each | asks on first use of the host | PROVEN (asks; nothing leaves on denial) |
| remember | write long-term memory | evidence rule (needs evidence the run observed); **no human prompt** | PROVEN refused without evidence; see "left for the founder" |
| run_checks | run a repository's tests in a sandbox | opt-in; validated before any prompt; **asks a human on every call**, bound to the exact commit | PROVEN (`run-checks-tool.test.ts`) |
| propose_change | build a patch proposal (writes nothing to the repository) | opt-in | READ |

**Found and fixed (proven before and after):** `fetch_url` asked about the first host and then followed redirects silently. A page on an approved host could send the agent to another host, including `localhost` and the dashboard's own API, with no question. Before the fix, `tests/fetch-redirects.test.ts` failed 3 of 5: the other host received the request. Now a redirect to a host that is not approved asks the human (naming both hosts, and saying so when the new host is a local or private address); denied means that host is never contacted; same-host redirects, non-web schemes (refused) and loops (5 hops) are handled.

**A guard that stays:** `tests/tool-safety.test.ts` fails if a tool is added without a safety class, proves for every network tool that a "no" means no request leaves the machine (and that it did ask), that overwrite asks and a denial leaves the file untouched, that read tools cannot leave their folder, and that the opt-in tools stay opt-in with their own gate tests present.

**Left for the founder (not changed, behaviour would change):**
1. `remember` saves to memory with no human prompt; the evidence rule counts a fetched web page as evidence, so a hostile page could plant a memory (it is labelled unverified ORG memory, and a human must promote it to VERIFIED). Option: ask a human when the evidence came from a fetched page.
2. A new file (not an overwrite) is created without a question. In a chosen repository the Changes panel shows it and undo removes it; the draft PR step lists it.
3. `live_lookup`, `algorand` and `medication` call fixed hosts and do not re-check redirects from those hosts (the hosts are trusted APIs; `fetch_url` and `rss_feed` are the arbitrary-URL tools).

**Not claimed:** that no other path exists. This covers the tools the agent loop offers and the paths I read; the operator plugins (`http_request`, `rss_feed`) were read and have their own guard; HTTP routes that change state were checked only where earlier PRs touched them. A second reviewer (Kilo, read-only) was prepared for exactly this and has not run.
