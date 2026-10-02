// P3.6 second held-out set. Targets the 10 seed lessons the first set (p35) did NOT use. Written without copying lesson wording; the expected
// lesson for each goal was fixed and committed before either ranker was run on it, and no weight was tuned afterwards.
export const GOALS = [
  { id: 'accents-and-checkmark', related: true, expectedLesson: 'bytes-not-chars', goal: 'Store a short greeting with accented letters and a check-mark glyph, then tell me the storage size the writer returned rather than the number of characters.' },
  { id: 'entries-below-folder', related: true, expectedLesson: 'list-subdir', goal: 'After creating two notes inside a new subfolder, tell me which entries the workspace inventory contains below that folder.' },
  { id: 'preferences-fallback', related: true, expectedLesson: 'missing-then-create', goal: 'Look for a preferences document; if it is absent, make one that selects a low-light colour scheme and then confirm what it says.' },
  { id: 'sibling-directory-memo', related: true, expectedLesson: 'dotdot-path', goal: 'Put a short memo in a sibling directory that is referenced relative to the parent of the working area.' },
  { id: 'tally-bump', related: true, expectedLesson: 'counter', goal: 'Start a tally file at one, then raise it by a single unit, checking the current value beforehand every time, until it shows four.' },
  { id: 'three-named-notes', related: true, expectedLesson: 'three-files', goal: 'Make three markdown notes whose bodies each carry their own label, then open the middle one and quote it in your answer.' },
  { id: 'headline-digest', related: true, expectedLesson: 'noise-rss', goal: 'Condense today\'s headlines from a news syndication feed, naming each item\'s headline.' },
  { id: 'ledger-token-amount', related: true, expectedLesson: 'noise-algo', goal: 'Convert the raw circulating amount of a ledger token into its human-readable form using its precision digits.' },
  { id: 'persist-a-fact', related: true, expectedLesson: 'noise-memory', goal: 'Persisting a long-term fact is refused until I have inspected some prior material first; explain what I must do before saving.' },
  { id: 'never-contacted-site', related: true, expectedLesson: 'noise-approval', goal: 'Pull a web page from a site we have never contacted before and describe what the dashboard asks of me.' },
];
