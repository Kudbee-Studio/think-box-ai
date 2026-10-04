// Profile routes: create/list/get/update/delete, switch the active profile, and export/import.
// A profile isolates memory (its own folder) and run history (its own runs file). Switching profiles
// re-points the shared MemoryStore/RunStore objects (see activateProfile in server.ts), so the object
// identity that route modules captured stays valid.
import type { Express, Response } from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { MEMORY_LAYERS, type MemoryLayer } from '../memory.ts';
import { type ProfileExport, type ProfileManager } from '../profile-manager.ts';
import type { RunStore } from '../runs.ts';
import { errorMessage } from '../types.ts';
import type { BroadcastingSession, Request } from './types.ts';

export interface ProfileRouteDeps {
  profileManager: ProfileManager;
  runStore: RunStore;
  sessions: Map<string, BroadcastingSession>;
  /** Re-point the stores at another profile (server.ts activateProfile). */
  activateProfile(profileId: string): void;
  /** Where per-profile data folders live (the manager's dataRoot). */
  profilesDir: string;
}

function profileIdParam(value: unknown): string {
  return String(value ?? '').trim();
}

export function registerProfileRoutes(app: Express, deps: ProfileRouteDeps): void {
  const { profileManager, runStore, sessions, activateProfile, profilesDir } = deps;

  const broadcast = (type: string, data: unknown) => {
    for (const session of sessions.values()) session.broadcast({ type, data });
  };

  app.get('/api/profiles', (_req: Request, res: Response) => {
    res.json({ profiles: profileManager.list(), active: profileManager.getActiveId() });
  });

  app.get('/api/profiles/active', (_req: Request, res: Response) => {
    res.json(profileManager.active());
  });

  app.get('/api/profiles/:id', (req: Request, res: Response) => {
    const profile = profileManager.get(profileIdParam(req.params.id));
    if (!profile) return res.status(404).json({ error: 'Profile not found' });
    res.json(profile);
  });

  app.post('/api/profiles', (req: Request, res: Response) => {
    try {
      const profile = profileManager.create({
        name: String(req.body?.name ?? ''),
        description: String(req.body?.description ?? ''),
        settings: typeof req.body?.settings === 'object' && req.body.settings ? req.body.settings : undefined,
      });
      broadcast('profiles_changed', { id: profile.id });
      res.status(201).json(profile);
    } catch (err) {
      res.status(400).json({ error: errorMessage(err) });
    }
  });

  app.patch('/api/profiles/:id', (req: Request, res: Response) => {
    try {
      const profile = profileManager.update(profileIdParam(req.params.id), {
        ...(req.body?.name !== undefined ? { name: String(req.body.name) } : {}),
        ...(req.body?.description !== undefined ? { description: String(req.body.description) } : {}),
        ...(req.body?.settings !== undefined ? { settings: req.body.settings } : {}),
      });
      broadcast('profiles_changed', { id: profile.id });
      res.json(profile);
    } catch (err) {
      res.status(400).json({ error: errorMessage(err) });
    }
  });

  app.delete('/api/profiles/:id', (req: Request, res: Response) => {
    try {
      const removed = profileManager.delete(profileIdParam(req.params.id));
      if (!removed) return res.status(404).json({ error: 'Profile not found' });
      // The manager may have switched the active profile out from under us (deleting the active one).
      if (profileManager.getActiveId() !== runStore.activeProfile) activateProfile(profileManager.getActiveId());
      broadcast('profiles_changed', { id: req.params.id });
      res.json({ success: true, active: profileManager.getActiveId() });
    } catch (err) {
      res.status(400).json({ error: errorMessage(err) });
    }
  });

  app.post('/api/profiles/:id/activate', (req: Request, res: Response) => {
    try {
      activateProfile(profileIdParam(req.params.id));
      res.json(profileManager.active());
    } catch (err) {
      res.status(404).json({ error: errorMessage(err) });
    }
  });

  // ─── Export / import ────────────────────────────────────────────
  app.get('/api/profiles/:id/export', (req: Request, res: Response) => {
    const id = profileIdParam(req.params.id);
    const profile = profileManager.get(id);
    if (!profile) return res.status(404).json({ error: 'Profile not found' });
    // Read the profile's files directly: exporting a non-active profile must not disturb the active one.
    const memory = readProfileMemory(path.join(profilesDir, id, 'memory'));
    const runs = readProfileRuns(path.join(profilesDir, id, 'runs.json'));
    res.json(profileManager.export(id, memory, runs));
  });

  app.post('/api/profiles/import', (req: Request, res: Response) => {
    try {
      const bundle = req.body as ProfileExport;
      if (!bundle || bundle.format !== 'kudbee-profile') return res.status(400).json({ error: 'Not a kudbee profile export' });
      const profile = profileManager.import(bundle, bundle.memory, bundle.runs);
      writeProfileMemory(path.join(profilesDir, profile.id, 'memory'), bundle.memory ?? {});
      writeProfileRuns(path.join(profilesDir, profile.id, 'runs.json'), bundle.runs ?? []);
      if (profileManager.getActiveId() === profile.id) activateProfile(profile.id);
      broadcast('profiles_changed', { id: profile.id });
      res.status(201).json(profile);
    } catch (err) {
      res.status(400).json({ error: errorMessage(err) });
    }
  });
}

/** Raw memory files of a profile, grouped by layer, for export. Best-effort: a missing folder is empty. */
function readProfileMemory(root: string): ProfileExport['memory'] {
  const out: ProfileExport['memory'] = {};
  for (const layer of MEMORY_LAYERS) {
    out[layer] = [];
    const dir = path.join(root, layer);
    if (!fs.existsSync(dir)) continue;
    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith('.md')) continue;
      const raw = fs.readFileSync(path.join(dir, file), 'utf8');
      const match = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
      const meta: Record<string, string> = {};
      if (match) for (const line of match[1].split('\n')) { const i = line.indexOf(':'); if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim(); }
      out[layer].push({
        id: `${layer}/${file.slice(0, -3)}`,
        layer,
        title: meta.title || file.slice(0, -3),
        tags: (meta.tags || '').split(',').map((t) => t.trim()).filter(Boolean),
        source: meta.source || 'human',
        created: meta.created || '',
        updated: meta.updated || '',
        content: (match ? match[2] : raw).trim(),
      });
    }
  }
  return out;
}

function readProfileRuns(file: string): Array<Record<string, unknown>> {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8')) as Array<Record<string, unknown>>;
  } catch {
    return [];
  }
}

/** Write imported memory items into a profile's folder, skipping anything already present by id. */
function writeProfileMemory(root: string, memory: ProfileExport['memory']): void {
  for (const layer of MEMORY_LAYERS) {
    const items = memory[layer] ?? [];
    fs.mkdirSync(path.join(root, layer), { recursive: true });
    for (const item of items) writeMemoryFile(root, layer, item);
  }
}

function writeMemoryFile(root: string, layer: MemoryLayer, item: ProfileExport['memory'][string][number]): void {
  const slug = String(item.id).slice(`${layer}/`.length).replace(/[^a-zA-Z0-9._-]/g, '-').slice(0, 60) || 'memory';
  const oneLine = (value: string) => String(value ?? '').replace(/\s+/g, ' ').trim();
  const body = `---
id: ${layer}/${slug}
layer: ${layer}
title: ${oneLine(item.title)}
tags: ${(item.tags ?? []).map(oneLine).join(', ')}
source: ${oneLine(item.source)}
created: ${oneLine(item.created)}
updated: ${oneLine(item.updated)}
---
${String(item.content ?? '').trim()}
`;
  try {
    fs.writeFileSync(path.join(root, layer, `${slug}.md`), body, { flag: 'wx' });
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== 'EEXIST') throw err;
  }
}

function writeProfileRuns(file: string, runs: Array<Record<string, unknown>>): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(runs));
  fs.renameSync(tmp, file);
}
