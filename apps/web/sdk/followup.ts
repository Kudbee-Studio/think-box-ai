/** Kudbee SDK follow-up helpers (PR #179 F25). */

import type { KudbeeSdkConfig } from './config.ts';

export const SDK_FOLLOWUP_VERSION = '0.2.0';

export type SdkPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export function parseSseChunk(buffer: string): { events: { event?: string; data: string }[]; remainder: string } {
  if (!buffer.includes('\n\n')) {
    return { events: [], remainder: buffer };
  }
  const parts = buffer.split('\n\n');
  const remainder = parts.pop() ?? '';
  const events = parts
    .map((block) => {
      let event: string | undefined;
      const dataLines: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length && !event) return null;
      return { event, data: dataLines.join('\n') };
    })
    .filter((ev): ev is { event?: string; data: string } => ev !== null);
  return { events, remainder };
}

export async function fetchCapabilities(
  config: KudbeeSdkConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<{ capabilities: string[]; liveApiCalled: false }> {
  const res = await fetchImpl(`${config.baseUrl}/api/sdk/capabilities`, {
    headers: { accept: 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`capabilities ${res.status}`);
  }
  const body = (await res.json()) as { capabilities?: string[] };
  return { capabilities: body.capabilities ?? [], liveApiCalled: false };
}

export function collectPages<T>(
  fetchPage: (cursor: string | null) => SdkPage<T>,
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

export const sdkRouteCatalog = (): string[] => [
  '/api/health',
  '/api/sdk/capabilities',
  '/api/sdk/version',
  '/api/sdk/sessions',
  '/api/sdk/tasks',
];
