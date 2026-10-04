// Profile import: strict validation of an untrusted export bundle, and confined writes of its contents.
// Nothing from the request becomes a path except through the fixed layer list and a sanitised slug, and every
// write goes through writeConfined (real-path check, O_NOFOLLOW, descriptor check) rooted at the profile folder.
import fs from 'node:fs';
import path from 'node:path';
import { MEMORY_LAYERS, type MemoryLayer } from './memory.ts';
import { ProfileError } from './profile-manager.ts';
import { writeConfined } from './workspace-fs.ts';

export const IMPORT_LIMITS = {
  itemsPerLayer: 500,
  runs: 500,
  contentChars: 20_000,
  titleChars: 200,
  tags: 12,
  tagChars: 40,
  fieldChars: 64,
  runBytes: 20_000,
} as const;

export interface ImportedMemory { id: string; layer: MemoryLayer; slug: string; title: string; tags: string[]; source: string; created: string; updated: string; content: string }
export interface ValidatedBundle {
  profile: { name: string; description: string; settings: Record<string, unknown> };
  memory: ImportedMemory[];
  runs: Array<Record<string, unknown>>;
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

function text(value: unknown, field: string, max: number, { required = false } = {}): string {
  if (value === undefined || value === null) {
    if (required) throw new ProfileError(`Import: ${field} is required`);
    return '';
  }
  if (typeof value !== 'string') throw new ProfileError(`Import: ${field} must be a string`);
  if (value.length > max) throw new ProfileError(`Import: ${field} is longer than ${max} characters`);
  return value;
}

const oneLine = (value: string) => value.replace(/\s+/g, ' ').trim();

export function slugFor(layer: MemoryLayer, id: string): string {
  return id.slice(`${layer}/`.length).replace(/[^a-zA-Z0-9._-]/g, '-').replace(/^\.+/, '').slice(0, 60) || 'memory';
}

/** Throws ProfileError for anything malformed or oversized; returns freshly built values, never the request's own objects. */
export function parseProfileBundle(raw: unknown): ValidatedBundle {
  if (!isRecord(raw) || raw.format !== 'kudbee-profile') throw new ProfileError('Not a kudbee profile export');
  const src = isRecord(raw.profile) ? raw.profile : {};
  const settings = isRecord(src.settings) && JSON.stringify(src.settings).length <= 10_000 ? { ...src.settings } : {};
  const profile = { name: text(src.name, 'profile.name', 80) || 'Imported profile', description: text(src.description, 'profile.description', 500), settings };

  const memory: ImportedMemory[] = [];
  if (raw.memory !== undefined && !isRecord(raw.memory)) throw new ProfileError('Import: memory must be an object keyed by layer');
  const byLayer = isRecord(raw.memory) ? raw.memory : {};
  for (const layerName of Object.keys(byLayer)) {
    if (!(MEMORY_LAYERS as readonly string[]).includes(layerName)) throw new ProfileError(`Import: unknown memory layer '${layerName.slice(0, 40)}'`);
  }
  for (const layer of MEMORY_LAYERS) {
    const items = byLayer[layer];
    if (items === undefined) continue;
    if (!Array.isArray(items)) throw new ProfileError(`Import: memory.${layer} must be a list`);
    if (items.length > IMPORT_LIMITS.itemsPerLayer) throw new ProfileError(`Import: memory.${layer} has more than ${IMPORT_LIMITS.itemsPerLayer} items`);
    for (const item of items) {
      if (!isRecord(item)) throw new ProfileError(`Import: memory.${layer} holds a non-object item`);
      const id = text(item.id, 'memory id', 200, { required: true });
      if (!id.startsWith(`${layer}/`)) throw new ProfileError(`Import: memory id '${id.slice(0, 60)}' is not in layer ${layer}`);
      if (item.tags !== undefined && !Array.isArray(item.tags)) throw new ProfileError('Import: tags must be a list');
      const tags = (item.tags as unknown[] | undefined ?? []).slice(0, IMPORT_LIMITS.tags).map((t) => oneLine(text(t, 'tag', IMPORT_LIMITS.tagChars)));
      const slug = slugFor(layer, id);
      memory.push({
        id: `${layer}/${slug}`, layer, slug,
        title: oneLine(text(item.title, 'title', IMPORT_LIMITS.titleChars)),
        tags: tags.filter(Boolean),
        source: oneLine(text(item.source, 'source', IMPORT_LIMITS.fieldChars)) || 'human',
        created: oneLine(text(item.created, 'created', IMPORT_LIMITS.fieldChars)),
        updated: oneLine(text(item.updated, 'updated', IMPORT_LIMITS.fieldChars)),
        content: text(item.content, 'content', IMPORT_LIMITS.contentChars).trim(),
      });
    }
  }

  if (raw.runs !== undefined && !Array.isArray(raw.runs)) throw new ProfileError('Import: runs must be a list');
  const rawRuns = (raw.runs as unknown[] | undefined) ?? [];
  if (rawRuns.length > IMPORT_LIMITS.runs) throw new ProfileError(`Import: more than ${IMPORT_LIMITS.runs} runs`);
  const runs = rawRuns.map((run) => {
    if (!isRecord(run)) throw new ProfileError('Import: a run is not an object');
    if (JSON.stringify(run).length > IMPORT_LIMITS.runBytes) throw new ProfileError(`Import: a run is larger than ${IMPORT_LIMITS.runBytes} bytes`);
    return { ...run };
  });
  return { profile, memory, runs };
}

function memoryFileBody(item: ImportedMemory): string {
  return `---\nid: ${item.id}\nlayer: ${item.layer}\ntitle: ${item.title}\ntags: ${item.tags.join(', ')}\nsource: ${item.source}\ncreated: ${item.created}\nupdated: ${item.updated}\n---\n${item.content}\n`;
}

/** Write validated memory into the profile folder; an id that is already present is skipped, never overwritten. */
export async function writeProfileMemory(profileRoot: string, items: ImportedMemory[]): Promise<void> {
  await fs.promises.mkdir(profileRoot, { recursive: true });
  for (const item of items) {
    const file = path.join(profileRoot, item.layer, `${item.slug}.md`);
    if (await fs.promises.lstat(file).catch(() => null)) continue;
    await writeConfined(profileRoot, file, memoryFileBody(item), { mkdirs: true });
  }
}

export async function writeProfileRuns(profileRoot: string, runs: Array<Record<string, unknown>>): Promise<void> {
  await fs.promises.mkdir(profileRoot, { recursive: true });
  await writeConfined(profileRoot, path.join(profileRoot, 'runs.json'), JSON.stringify(runs));
}
