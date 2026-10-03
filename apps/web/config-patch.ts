// Validation of a session config patch (WebSocket update_config, or settings restored from disk). Moved out of server.ts unchanged.
import type { AgentSessionConfig } from './types.ts';

export const MAX_AGENT_ITERATIONS = 50;

/** Validate a config patch from the WebSocket (or restored settings). Unknown keys and bad values throw. */
export function sanitizeConfigPatch(input: unknown): Partial<AgentSessionConfig> {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('config must be an object');
  const patch: Partial<AgentSessionConfig> = {};
  for (const [key, value] of Object.entries(input)) {
    switch (key) {
      case 'model':
        if (typeof value !== 'string' || !value.trim() || value.length > 100) throw new Error('model must be a model name');
        patch.model = value.trim();
        break;
      case 'provider':
        if (value !== 'inception' && value !== 'ollama') throw new Error('provider must be inception or ollama');
        patch.provider = value;
        break;
      case 'maxIterations':
        if (!Number.isInteger(value) || (value as number) < 1 || (value as number) > MAX_AGENT_ITERATIONS) {
          throw new Error(`maxIterations must be an integer from 1 to ${MAX_AGENT_ITERATIONS}`);
        }
        patch.maxIterations = value as number;
        break;
      case 'temperature':
        if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 2) throw new Error('temperature must be from 0 to 2');
        patch.temperature = value;
        break;
      default:
        throw new Error(`unknown config key: ${key}`);
    }
  }
  return patch;
}

