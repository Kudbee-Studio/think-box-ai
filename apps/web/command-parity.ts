// CLI <-> dashboard parity map (P3.11). Every slash command that exists in the kudbee CLI (cli.ts) or the dashboard terminal (public/js/app.js) is
// declared here with what the other side offers. tests/command-parity.test.ts fails when a command is added to either side without an entry, when an
// entry names a command that no longer exists, when a claimed counterpart is missing from the other side's source, or when the number of known gaps grows.
export type Parity =
  | { kind: 'both' }
  | { kind: 'counterpart'; side: 'cli' | 'dashboard'; what: string; proof: string } // exists on one side as a command; the other side has it as a view/control. `proof` must appear in the other side's source.
  | { kind: 'surface-only'; reason: string } // meaningless on the other surface (quit a terminal, change the theme)
  | { kind: 'gap'; note: string }; // a real feature missing on the other surface: tracked, and the count may only shrink

/** Capabilities the founder named, in both surfaces; each side's proof string must be present in its source. */
export const CORE: Array<{ capability: string; cli: string; dashboard: string }> = [
  { capability: 'run a goal', cli: "client.run(goal)", dashboard: "type: 'run_goal'" },
  { capability: 'Think Tokens list', cli: "sub === 'list'", dashboard: "type: 'think_tokens_list'" },
  { capability: 'Think Tokens show', cli: "sub === 'show'", dashboard: 'tt-card' },
  { capability: 'Think Token links', cli: "sub === 'links'", dashboard: 'tt-links' },
  { capability: 'lessons (= Think Tokens)', cli: "case '/lessons'", dashboard: "case '/lessons'" },
  { capability: 'memory', cli: "case '/memory'", dashboard: "case '/memory'" },
  { capability: 'status', cli: "case '/status'", dashboard: "case '/status'" },
  { capability: 'run history', cli: "case '/runs'", dashboard: "case '/runs'" },
  { capability: 'Think Token 100-cell cube', cli: "sub === 'cube'", dashboard: "type: 'think_token_cube'" },
];

export const PARITY: Record<string, Parity> = {
  // both sides
  '/agent': { kind: 'both' }, '/algo': { kind: 'both' }, '/help': { kind: 'both' }, '/lessons': { kind: 'both' }, '/memory': { kind: 'both' }, '/metrics': { kind: 'both' },
  '/model': { kind: 'both' }, '/models': { kind: 'both' }, '/notes': { kind: 'both' }, '/plugins': { kind: 'both' }, '/promote': { kind: 'both' }, '/remember': { kind: 'both' },
  '/run': { kind: 'both' }, '/runs': { kind: 'both' }, '/select': { kind: 'both' }, '/skill': { kind: 'both' }, '/skills': { kind: 'both' }, '/status': { kind: 'both' }, '/token': { kind: 'both' }, '/tokens': { kind: 'both' },
  // CLI commands whose dashboard counterpart is a view or control
  '/agents': { kind: 'counterpart', side: 'cli', what: '/agent in the dashboard terminal lists the available agents', proof: 'Available agents:' },
  '/files': { kind: 'counterpart', side: 'cli', what: 'the dashboard Files panel', proof: 'refreshFiles' },
  '/cat': { kind: 'counterpart', side: 'cli', what: 'the dashboard file viewer', proof: 'files/content' },
  '/forget': { kind: 'counterpart', side: 'cli', what: 'delete in the dashboard memory panel', proof: 'deleteMemory' },
  '/stop': { kind: 'counterpart', side: 'cli', what: 'the dashboard Stop button', proof: "type: 'stop'" },
  // terminal-only
  '/quit': { kind: 'surface-only', reason: 'exits the CLI process' }, '/exit': { kind: 'surface-only', reason: 'exits the CLI process' },
  '/open': { kind: 'surface-only', reason: 'prints the dashboard URL; the dashboard is already open' },
  '/clear': { kind: 'surface-only', reason: 'clears the dashboard terminal pane' }, '/refresh': { kind: 'surface-only', reason: 'repaints the dashboard' },
  '/shortcuts': { kind: 'surface-only', reason: 'dashboard keyboard shortcuts' }, '/theme': { kind: 'surface-only', reason: 'dashboard theme' },
  // real gaps (tracked; may only shrink)
  '/capacity': { kind: 'gap', note: 'dashboard-only capacity view' },
  '/config': { kind: 'gap', note: 'dashboard-only settings command' },
  '/export': { kind: 'gap', note: 'dashboard-only export' },
  '/logs': { kind: 'gap', note: 'dashboard-only execution logs' },
  '/plugin': { kind: 'gap', note: 'running a plugin by name exists only in the dashboard terminal' },
  '/remote': { kind: 'gap', note: 'dashboard-only remote command' },
  '/session': { kind: 'gap', note: 'dashboard-only session info' },
  '/sessions': { kind: 'gap', note: 'dashboard-only session list' },
  '/specialists': { kind: 'gap', note: 'specialist swarm runs exist only in the dashboard terminal' },
};

/** The number of gaps at the time this map was written. A new gap must be fixed (or consciously raise this number in a reviewed change). */
export const MAX_GAPS = 9;
