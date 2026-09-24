/** Typed HTTP client for the kudbEE web shell (PR #177). */

import type { KudbeeSdkConfig } from './config.ts';
import { KudbeeSdkError } from './errors.ts';

export const SDK_VERSION = '0.1.0';

export function buildWsUrl(config: KudbeeSdkConfig, host?: string): string {
  const hostname = host ?? '127.0.0.1';
  const proto = config.baseUrl.startsWith('https') ? 'wss' : 'ws';
  const portMatch = config.baseUrl.match(/:(\d+)/);
  const port = portMatch ? portMatch[1] : '3000';
  return `${proto}://${hostname}:${port}${config.wsPath}`;
}

export async function fetchHealth(
  config: KudbeeSdkConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<{ ready: boolean; detail: Record<string, unknown> }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.requestTimeoutMs);
  try {
    const res = await fetchImpl(`${config.baseUrl}/api/health`, {
      signal: controller.signal,
      headers: { accept: 'application/json' },
    });
    if (!res.ok) {
      throw new KudbeeSdkError('KUD_BEE_TRANSPORT', `health ${res.status}`);
    }
    const detail = (await res.json()) as Record<string, unknown>;
    const ready = Boolean(detail.ready ?? detail.status === 'ok');
    return { ready, detail };
  } finally {
    clearTimeout(timer);
  }
}
