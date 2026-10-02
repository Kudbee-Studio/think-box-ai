// P3.8 decision set (set 4): 12 goals over REAL lessons, in deliberately different styles from sets 1-3 (terse, long and rambling, typos).
// Expected lessons were fixed and committed BEFORE any ranker was run on this set, and it is run exactly once (scripts/think-token-ranker-eval.mjs).
// Seed: docs/evidence/adr-029-p3/p37-seed.db. Each goal shares at most one distinctive word with its lesson (checked in tests/think-token-p3.test.ts).
export const GOALS = [
  { id: 'terse-deep-folders', style: 'terse', related: true, expectedLesson: 'deep-mkdir', goal: 'file four levels down, none of the parent folders exist yet' },
  { id: 'rambling-stub', style: 'rambling', related: true, expectedLesson: 'zero-byte', goal: 'So here is the thing, my colleague wants one of those files that has absolutely no content whatsoever, like a stub, and she would like me to confirm what number the tool gave for how big it is, can you do that for me' },
  { id: 'typos-replace-letter', style: 'typos', related: true, expectedLesson: 'replace-not-append', goal: 'chnage the leter in the nte from X to Y so it ONLY says Y nw, dont keep the old one' },
  { id: 'terse-rocket-icon', style: 'terse', related: true, expectedLesson: 'emoji-utf8', goal: 'save one rocket icon, how many bytes on disk' },
  { id: 'rambling-quarter-recap', style: 'rambling', related: true, expectedLesson: 'missing-no-invent', goal: 'My manager mentioned a report from last quarter that supposedly sits in the shared area, and I would love a quick recap of its main points before the call, though I have not actually checked whether anyone put it there' },
  { id: 'typos-config-fallback', style: 'typos', related: true, expectedLesson: 'missing-then-create', goal: 'see if config exists if no creat it with dark colours then show me whats in it' },
  { id: 'typos-accented-greeting', style: 'typos', related: true, expectedLesson: 'bytes-not-chars', goal: 'writ a gretting wit acented lettrs in it and tel me the disk size not the lenght of the string' },
  { id: 'terse-tack-on-line', style: 'terse', related: true, expectedLesson: 'append', goal: 'tack one more line on the end of my notes without losing whats there' },
  { id: 'terse-five-letters', style: 'terse', related: true, expectedLesson: 'size-match', goal: 'first five lowercase alphabet letters into a file, report returned size' },
  { id: 'rambling-machine-config', style: 'rambling', related: true, expectedLesson: 'json-line', goal: 'I need a tiny machine-readable config with a sucess flag set to true all crammed in a single row with no pretty printing at all' },
  { id: 'terse-memo-above', style: 'terse', related: true, expectedLesson: 'dotdot-path', goal: 'drop a memo one level above where i am working' },
  { id: 'rambling-three-labelled', style: 'rambling', related: true, expectedLesson: 'three-files', goal: 'Can you spin up three little notes, each one stating which note it is, and then show me only the second one' },
];
