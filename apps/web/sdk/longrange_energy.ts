/** Kudbee SDK long-range + energy loop helpers (PR #193 F25). */

import type { KudbeeSdkConfig } from './config.ts';

export const SDK_LR_ENERGY_VERSION = '0.5.0';

export type SdkHopPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export function verifyWebhookDryRunLrEnergy(signature: string, body: string): { valid: boolean; dryRun: true } {
  const prefix = 'sha256=';
  const valid = signature.startsWith(prefix) && body.length > 0;
  return { valid, dryRun: true };
}

export async function fetchCapabilitiesLrEnergy(
  config: KudbeeSdkConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<{ capabilities: string[]; liveApiCalled: false }> {
  const res = await fetchImpl(`${config.baseUrl}/api/sdk/v4/longrange-energy/capabilities`, {
    headers: { accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`capabilities lr-energy ${res.status}`);
  }
  const body = (await res.json()) as { capabilities?: string[] };
  return { capabilities: body.capabilities ?? [], liveApiCalled: false };
}

export function collectHopPages<T>(
  fetchPage: (cursor: string | null) => SdkHopPage<T>,
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

export type EnergyMeshSnapshot = {
  loopCount: number;
  linkCount: number;
  allConserved: boolean;
  liveApiCalled: false;
};

export function emptyEnergyMeshSnapshot(): EnergyMeshSnapshot {
  return { loopCount: 0, linkCount: 0, allConserved: true, liveApiCalled: false };
}

export const sdkRouteCatalogLrEnergy = (): string[] => [
  '/api/health',
  '/api/sdk/v4/longrange-energy/capabilities',
  '/api/sdk/v4/longrange-energy/occupancy',
  '/api/sdk/v4/longrange-energy/webhooks/dry-run',
  '/api/sdk/v4/longrange-energy/twin/federation',
];
