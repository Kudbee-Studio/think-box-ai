# P3.71: Think Tokens per repository

A token learned while the agent worked on a chosen repository carries a `repo:<owner>:<name>` tag (shortened with a hash when longer than a tag may be) and is recalled only in that repository. Tokens with no such tag (everything saved before) are general and are recalled everywhere. With no repository chosen, repository tokens stay out.

**Proven by tests:** `tests/think-token-repo.test.ts` (tag format, length, stability, separator survives the store's tag cleaner; scope rules; the 8-tag limit; retrieval returns general + own-repository tokens only, and only general ones with none chosen; the pipeline tags what a repository run learns and leaves a no-repository run general) and `tests/think-token-health.test.ts` (repository-scoped count).

**Real run, isolated server and empty token store (one run, Mercury-2):** the agent fixed the three demo bugs (9 of 9 tests pass, only `src/` files changed), the extractor ran (1 model call) and proposed 3 lessons ("Handle percentage inputs correctly", "Use 1-based indexing for pagination", "Trim extra hyphens in slug generation"). The existing quality gate **rejected all three as generic** ("names no tool, file or argument from the run"), so **no token was saved and the repository tag was not observed end to end on a live run.**

**What that shows:** scoping is in place and tested, but a repository fix does not yet yield a reusable token, because the lessons the model writes are about the bug, not about how to work in the repository. Making repository runs produce reusable tokens (for example repository facts: how to run its tests, where its sources are) is the next step, not claimed here.

Not claimed: that scoping improves any run (that needs the A/B).
