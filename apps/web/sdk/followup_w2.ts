/** Kudbee SDK follow-up wave 2 helpers (PR #181 F25). */

import type { KudbeeSdkConfig } from './config.ts';

export const SDK_FOLLOWUP_W2_VERSION = '0.3.0';

export type SdkPageV2<T> = {
  items: T[];
  nextCursor: string | null;
};

export function verifyWebhookDryRun(signature: string, body: string): { valid: boolean; dryRun: true } {
  const prefix = 'sha256=';
  const valid = signature.startsWith(prefix) && body.length > 0;
  return { valid, dryRun: true };
}

export async function fetchCapabilitiesV2(
  config: KudbeeSdkConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<{ capabilities: string[]; liveApiCalled: false }> {
  const res = await fetchImpl(`${config.baseUrl}/api/sdk/v2/capabilities`, {
    headers: { accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`capabilities v2 ${res.status}`);
  }
  const body = (await res.json()) as { capabilities?: string[] };
  return { capabilities: body.capabilities ?? [], liveApiCalled: false };
}

export function collectPagesV2<T>(
  fetchPage: (cursor: string | null) => SdkPageV2<T>,
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

export const sdkRouteCatalogV2 = (): string[] => [
  '/api/health',
  '/api/sdk/v2/capabilities',
  '/api/sdk/v2/occupancy',
  '/api/sdk/v2/webhooks/dry-run',
];
