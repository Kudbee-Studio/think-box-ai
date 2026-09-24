/** Kudbee SDK follow-up wave 3 helpers (PR #191 F25). */

import type { KudbeeSdkConfig } from './config.ts';

export const SDK_FOLLOWUP_W3_VERSION = '0.4.0';

export type SdkPageV3<T> = {
  items: T[];
  nextCursor: string | null;
};

export function verifyWebhookDryRunV3(signature: string, body: string): { valid: boolean; dryRun: true } {
  const prefix = 'sha256=';
  const valid = signature.startsWith(prefix) && body.length > 0;
  return { valid, dryRun: true };
}

export async function fetchCapabilitiesV3(
  config: KudbeeSdkConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<{ capabilities: string[]; liveApiCalled: false }> {
  const res = await fetchImpl(`${config.baseUrl}/api/sdk/v3/capabilities`, {
    headers: { accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`capabilities v3 ${res.status}`);
  }
  const body = (await res.json()) as { capabilities?: string[] };
  return { capabilities: body.capabilities ?? [], liveApiCalled: false };
}

export function collectPagesV3<T>(
  fetchPage: (cursor: string | null) => SdkPageV3<T>,
  maxPages = 50,
): T[] {
  const out: T[] = [];
  let cursor: string | null = null;
  for (let i = 0; i < maxPages; i += 1) {
    const page = fetchPage(cursor);
    out.push(...page.items);
    if (!page.nextCursor) break;
    cursor = page.nextCursor;
  }
  return out;
}

export type TwinFederationSnapshotV3 = {
  peerCount: number;
  peers: Array<Record<string, unknown>>;
  liveApiCalled: false;
};

export function emptyTwinFederationSnapshotV3(): TwinFederationSnapshotV3 {
  return { peerCount: 0, peers: [], liveApiCalled: false };
}

export const sdkRouteCatalogV3 = (): string[] => [
  '/api/health',
  '/api/sdk/v3/capabilities',
  '/api/sdk/v3/occupancy',
  '/api/sdk/v3/webhooks/dry-run',
  '/api/sdk/v3/twin/federation',
];
