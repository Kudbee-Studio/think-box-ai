// GET /api/setup: the "Get started" checklist (setup-status.ts). Probes Ollama with a short timeout; reports whether keys exist, never their values.
import type { Express } from 'express';
import { setupSteps } from '../setup-status.ts';
import type { Request } from './types.ts';

export function registerSetupRoute(app: Express, deps: { runCount: () => number; ollamaBaseUrl: string; env: Record<string, string | undefined> }): void {
  app.get('/api/setup', async (_req: Request, res) => {
    let ollamaReachable = false;
    try { ollamaReachable = (await fetch(`${deps.ollamaBaseUrl}/api/tags`, { signal: AbortSignal.timeout(800) })).ok; } catch { /* not running */ }
    res.json(setupSteps({ env: deps.env, ollamaReachable, runs: deps.runCount() }));
  });
}
