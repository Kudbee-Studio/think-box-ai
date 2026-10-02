// P3.5 held-out retrieval set. Written against docs/evidence/adr-029-p3/p33-seed.db WITHOUT copying lesson wording; the correct lesson for each goal
// (`expectedLesson`, the [lesson:slug] in the seed title) was fixed before the eval was run, and no retrieval weight was changed afterwards.
// tests/think-token-p3.test.ts checks that a goal shares at most one distinctive word with its lesson.
export const GOALS = [
  { id: 'three-levels-down', related: true, expectedLesson: 'deep-mkdir', goal: 'Save the word hello into a document that sits three folders down in a directory tree that does not exist yet.' },
  { id: 'blank-document', related: true, expectedLesson: 'zero-byte', goal: 'Make a blank document with nothing inside it, then say what size the tool reported.' },
  { id: 'redundant-dots', related: true, expectedLesson: 'path-normalize', goal: 'Store the phrase ok at a location whose written form has redundant current-directory markers in the middle.' },
  { id: 'buried-file-inventory', related: true, expectedLesson: 'recursive-list', goal: 'Create a file buried two directories deep, then check whether the workspace inventory shows it.' },
  { id: 'five-letter-length', related: true, expectedLesson: 'size-match', goal: 'Write the first five letters of the alphabet in lowercase to a markdown file and tell me the length the tool gave back.' },
  { id: 'swap-the-letter', related: true, expectedLesson: 'replace-not-append', goal: 'Create a note holding one capital letter, then swap it for a different letter so only the new one remains.' },
  { id: 'dartboard-size', related: true, expectedLesson: 'emoji-utf8', goal: 'Save a lone dart-board pictograph to a file and report the size the writer reported.' },
  { id: 'minified-flag', related: true, expectedLesson: 'json-line', goal: 'Produce a configuration document with a single success flag set to true, minified onto one row.' },
  { id: 'second-journal-entry', related: true, expectedLesson: 'append', goal: 'A journal already has one entry; add a second entry after it without destroying the first.' },
  { id: 'digest-of-unknown-report', related: true, expectedLesson: 'missing-no-invent', goal: 'Give me a digest of the quarterly numbers document; I am not sure it was ever uploaded.' },
];
