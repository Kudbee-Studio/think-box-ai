// Dashboard → governed backend bridge. The browser never receives the backend API key or a governance
// token, and never chooses the substrate: this server-side module fixes execution_substrate to
// `upcloud-ssh`, only forwards allow-listed read-only commands, obtains a short-lived admission token
// from the backend, and submits through the existing governed POST /api/v1/run.
import type { Request, Response } from 'express';

export const GOVERNED_SUBSTRATE = 'upcloud-ssh';
export const GOVERNED_CAPABILITY = 'shell:upcloud-ssh:readonly';
export const CLIENT_HEADER = 'x-kudbee-client';
export const CLIENT_HEADER_VALUE = 'dashboard';

// Defense in depth only: the backend (thinkbox/remote_exec_policy.py) is the authoritative policy and
// enforces the same exact-match list. Anything else is rejected here before it leaves this process.
export const ALLOWED_REMOTE_COMMANDS: readonly string[] = ['hostname', 'uname -a', 'uptime', 'whoami', 'df -h /', 'free -m'];

export interface BridgeConfig {
  backendUrl: string;
  apiKey: string;
}

export function bridgeConfigFromEnv(env: NodeJS.ProcessEnv = process.env): BridgeConfig {
  return {
    backendUrl: (env.THINKBOX_BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/+$/, ''),
    apiKey: (env.THINKBOX_API_KEY || env.THINKBOX_API_KEYS?.split(',')[0] || '').trim(),
  };
}

async function backend(cfg: BridgeConfig, path: string, init: { method: string; body?: unknown }): Promise<{ status: number; json: any }> {
  const res = await fetch(`${cfg.backendUrl}${path}`, {
    method: init.method,
    headers: { 'X-API-Key': cfg.apiKey, 'Content-Type': 'application/json' },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    signal: AbortSignal.timeout(15000),
  });
  let json: any = null;
  try {
    json = await res.json();
  } catch {
    // non-JSON error body
  }
  return { status: res.status, json };
}

function guard(req: Request, res: Response, cfg: BridgeConfig): boolean {
  if (req.get(CLIENT_HEADER) !== CLIENT_HEADER_VALUE) {
    res.status(403).json({ error: `missing ${CLIENT_HEADER} header` });
    return false;
  }
  if (!cfg.apiKey) {
    res.status(503).json({ error: 'governed bridge not configured: THINKBOX_API_KEY is not set' });
    return false;
  }
  return true;
}

export function submitGovernedRun(cfg: BridgeConfig) {
  return async (req: Request, res: Response): Promise<void> => {
    if (!guard(req, res, cfg)) return;
    const command = typeof req.body?.command === 'string' ? req.body.command.trim() : '';
    if (!ALLOWED_REMOTE_COMMANDS.includes(command)) {
      res.status(400).json({ error: 'command not allowed', allowed: ALLOWED_REMOTE_COMMANDS });
      return;
    }
    try {
      const adm = await backend(cfg, '/api/v1/run/admission-token', { method: 'POST' });
      if (adm.status !== 200 || !adm.json?.governance_token) {
        res.status(502).json({ error: 'admission token unavailable', backend_status: adm.status });
        return;
      }
      const run = await backend(cfg, '/api/v1/run', {
        method: 'POST',
        body: {
          goal: `dashboard remote exec: ${command}`,
          agent_id: adm.json.agent_id,
          governance_token: adm.json.governance_token,
          capability: GOVERNED_CAPABILITY,
          execution_substrate: GOVERNED_SUBSTRATE,
          exec_command: command,
        },
      });
      if (run.status !== 200) {
        // Governance/validation errors are passed through, without the request that carried the token.
        res.status(run.status === 403 ? 403 : 502).json({ error: 'backend rejected run', backend_status: run.status, detail: run.json?.detail ?? null });
        return;
      }
      res.status(202).json({
        engine_id: run.json.engine_id,
        receipt_id: run.json.summary?.receipt_id,
        session_id: run.json.session_id,
        execution_substrate: GOVERNED_SUBSTRATE,
        command,
      });
    } catch (err) {
      res.status(502).json({ error: `backend unreachable: ${err instanceof Error ? err.message : String(err)}` });
    }
  };
}

export function getGovernedRun(cfg: BridgeConfig) {
  return async (req: Request, res: Response): Promise<void> => {
    if (!guard(req, res, cfg)) return;
    const id = String(req.params.engineId || '');
    if (!/^engine_[A-Za-z0-9]+$/.test(id)) {
      res.status(400).json({ error: 'invalid engine id' });
      return;
    }
    try {
      const st = await backend(cfg, `/api/v1/run/job/${id}/status`, { method: 'GET' });
      if (st.status !== 200) {
        res.status(st.status === 404 ? 404 : 502).json({ error: 'status unavailable', backend_status: st.status });
        return;
      }
      res.json(st.json);
    } catch (err) {
      res.status(502).json({ error: `backend unreachable: ${err instanceof Error ? err.message : String(err)}` });
    }
  };
}
