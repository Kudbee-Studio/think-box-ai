// Stop spawned server/CLI child processes so their V8 coverage is written before the test process exits.
//
// NODE_V8_COVERAGE is only flushed on a clean exit; SIGTERM is a clean exit and SIGKILL writes nothing.
// Awaiting 'exit' removes the race where the parent (and c8) finish before the child has written its file.
import type { ChildProcess } from 'node:child_process';

export async function stopProc(p: ChildProcess | undefined | null): Promise<void> {
  if (!p || p.exitCode !== null || p.signalCode !== null) return;
  await new Promise<void>((resolve) => {
    const timer = setTimeout(() => {
      if (p.exitCode === null && p.signalCode === null) p.kill('SIGKILL');
      resolve();
    }, 3000);
    timer.unref?.();
    p.once('exit', () => { clearTimeout(timer); resolve(); });
    p.kill('SIGTERM');
  });
}

export async function stopProcs(procs: Array<ChildProcess | undefined | null>): Promise<void> {
  await Promise.all(procs.map((p) => stopProc(p)));
}
