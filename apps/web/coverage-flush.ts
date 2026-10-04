// Coverage flush for spawned processes (server.ts, cli.ts).
//
// The test harness starts whole programs in child processes. V8 only writes the data named by
// NODE_V8_COVERAGE when a process exits cleanly; a process stopped with SIGKILL cannot write anything,
// which is why most of the uncovered lines lived in spawned server/cli processes. Installing a
// SIGTERM/SIGINT handler turns those signals into a normal exit so the child's coverage lands in the same
// directory the parent writes to and the merged report sees it.
//
// A no-op unless NODE_V8_COVERAGE is set, so running the server or CLI normally is unchanged.

export interface CoverageProc {
  env: Record<string, string | undefined>;
  on(event: string, listener: () => void): unknown;
  exit(code?: number): unknown;
}

export function installCoverageFlush(proc: CoverageProc = process): boolean {
  if (!proc.env.NODE_V8_COVERAGE) return false;
  const flush = (): void => { proc.exit(0); };
  proc.on('SIGTERM', flush);
  proc.on('SIGINT', flush);
  return true;
}
