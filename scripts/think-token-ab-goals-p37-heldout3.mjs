// P3.7 third held-out set: 10 goals over REAL (non-noise) lessons, new wording. The expected lesson for each goal was fixed and committed before any ranker
// was run on it. The lessons are ones sets 1 and 2 also used (all 16 real seed lessons were already in use), so this tests new goal wording, not unseen lessons;
// the lesson-side retrieval text (when_to_use) was generated before these goals were written and from the lessons alone.
export const GOALS = [
  { id: 'unmade-hierarchy', related: true, expectedLesson: 'deep-mkdir', goal: 'Place a one-line message inside a file whose enclosing hierarchy of directories has not been made.' },
  { id: 'vacant-placeholder', related: true, expectedLesson: 'zero-byte', goal: 'I need a placeholder that is completely vacant; afterwards tell me how large the tool says it is.' },
  { id: 'rewrite-a-to-b', related: true, expectedLesson: 'replace-not-append', goal: 'A scratch file contains the letter A. Rewrite it so that it afterwards contains just B and not the pair together.' },
  { id: 'party-popper', related: true, expectedLesson: 'emoji-utf8', goal: 'Persist a single party-popper symbol in a file and tell me its footprint on disk.' },
  { id: 'budget-forecast-upload', related: true, expectedLesson: 'missing-no-invent', goal: 'Tell me what the budget forecast file says; I think the upload may have failed.' },
  { id: 'boolean-settings', related: true, expectedLesson: 'json-line', goal: 'Emit a settings file holding one boolean key named ok that is true, with every unnecessary space removed.' },
  { id: 'two-levels-beneath', related: true, expectedLesson: 'recursive-list', goal: 'Make a file two levels beneath the root, afterwards enumerate the project\'s contents and tell me if it shows up.' },
  { id: 'dot-slash-segment', related: true, expectedLesson: 'path-normalize', goal: 'Write a short line into a path that contains a dot-slash segment in its middle.' },
  { id: 'numeric-file-steps', related: true, expectedLesson: 'counter', goal: 'Initialise a numeric file with 1 and increase it step by step to 4, always re-reading it first.' },
  { id: 'fresh-subdirectory', related: true, expectedLesson: 'list-subdir', goal: 'Create two documents inside a fresh subdirectory and tell me what the project inventory shows under it.' },
];
