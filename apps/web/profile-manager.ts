// kudbEE profiles: named operating contexts, each with its own memory, run history and settings.
//
// A profile is a durable, isolated workspace for one line of work (a customer, a project, a persona).
// The memory layer folders and the run store live under a per-profile directory, so switching profiles
// swaps the knowledge the agent sees without deleting anything (AGENTS.md §1.3: memory is not chat history).
//
// Storage: SQLite (the same kudbee.db the persistence layer uses) for the profile list + the active id,
// with an in-memory cache so the hot path (every memory search / run list) never opens the DB.
// The schema is additive: `profiles` and the `active_profile` key are new tables/rows only.
import Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

/** Settings a profile carries; applying them on switch changes the session's model and (browser-side) theme. */
export interface ProfileSettings {
  model?: string;
  provider?: string;
  theme?: string;
  route_reason?: string;
  [key: string]: unknown;
}

export interface Profile {
  id: string;
  name: string;
  description: string;
  created_at: number;
  updated_at: number;
  is_active: boolean;
  settings: ProfileSettings;
}

export interface ProfileInput {
  name: string;
  description?: string;
  settings?: ProfileSettings;
}

/** A profile row as stored (settings JSON text); the public shape parses it. */
interface ProfileRow {
  id: string;
  name: string;
  description: string;
  created_at: number;
  updated_at: number;
  settings: string | null;
}

/** Export bundle: profile metadata + memory layers (as raw items) + runs, so a profile can be shared or backed up. */
export interface ProfileExport {
  format: 'kudbee-profile';
  version: 1;
  exported_at: number;
  profile: { name: string; description: string; settings: ProfileSettings };
  memory: Record<string, Array<{ id: string; layer: string; title: string; tags: string[]; source: string; created: string; updated: string; content: string }>>;
  runs: Array<Record<string, unknown>>;
}

export class ProfileError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ProfileError';
  }
}

/**
 * Named, isolated profiles. One database row each plus a single `active_profile` pointer.
 * Callers read from the in-memory cache; every mutation writes through to SQLite and refreshes the cache.
 */
export class ProfileManager {
  private readonly db: Database.Database;
  private readonly cache = new Map<string, Profile>();
  private activeId = '';
  /** Where per-profile data (memory folder, run file) is rooted. */
  readonly dataRoot: string;

  constructor(dataRoot: string, dbDir?: string) {
    this.dataRoot = dataRoot;
    const dir = dbDir || path.join(dataRoot, '..');
    fs.mkdirSync(dir, { recursive: true });
    this.db = new Database(path.join(dir, 'kudbee.db'));
    this.db.pragma('journal_mode = WAL');
    this.initSchema();
    this.load();
  }

  private initSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        settings TEXT
      );

      CREATE TABLE IF NOT EXISTS profile_meta (
        key TEXT PRIMARY KEY,
        value TEXT
      );
    `);
  }

  private load(): void {
    const rows = this.db.prepare('SELECT * FROM profiles ORDER BY created_at ASC').all() as ProfileRow[];
    this.cache.clear();
    for (const row of rows) this.cache.set(row.id, this.fromRow(row));
    const meta = this.db.prepare('SELECT value FROM profile_meta WHERE key = ?').get('active_profile') as { value: string } | undefined;
    // A pointer to a deleted profile is repaired on load; a fresh database gets a default profile.
    this.activeId = meta?.value && this.cache.has(meta.value) ? meta.value : [...this.cache.keys()][0] ?? '';
    if (!this.activeId && rows.length === 0) {
      const created = this.create({ name: 'Default', description: 'The initial profile' });
      this.activeId = created.id;
    } else if (!this.activeId) {
      this.activeId = [...this.cache.keys()][0]!;
    }
    this.persistActive();
  }

  private fromRow(row: ProfileRow): Profile {
    let settings: ProfileSettings = {};
    if (row.settings) {
      try {
        settings = JSON.parse(row.settings) as ProfileSettings;
      } catch {
        settings = {};
      }
    }
    return {
      id: row.id,
      name: row.name,
      description: row.description,
      created_at: row.created_at,
      updated_at: row.updated_at,
      is_active: row.id === this.activeId,
      settings,
    };
  }

  private persistActive(): void {
    this.db.prepare('INSERT OR REPLACE INTO profile_meta (key, value) VALUES (?, ?)').run('active_profile', this.activeId);
  }

  private refreshActiveFlags(): void {
    for (const profile of this.cache.values()) profile.is_active = profile.id === this.activeId;
  }

  /** The active profile; never empty for a manager that finished loading (a default is created). */
  active(): Profile {
    const profile = this.cache.get(this.activeId);
    if (!profile) throw new ProfileError('No active profile');
    return profile;
  }

  getActiveId(): string {
    return this.activeId;
  }

  /** Directory holding this profile's memory folder and runs file. Created on demand. */
  dataDirFor(id: string): string {
    return path.join(this.dataRoot, id);
  }

  get(id: string): Profile | undefined {
    return this.cache.get(id);
  }

  list(): Profile[] {
    return [...this.cache.values()].sort((a, b) => a.created_at - b.created_at).map((p) => ({ ...p, is_active: p.id === this.activeId }));
  }

  create(input: ProfileInput): Profile {
    const name = String(input.name ?? '').trim();
    if (!name) throw new ProfileError('A profile needs a name');
    if (name.length > 80) throw new ProfileError('Profile name is too long (max 80)');
    const now = Date.now();
    const profile: Profile = {
      id: randomUUID(),
      name,
      description: String(input.description ?? '').trim().slice(0, 400),
      created_at: now,
      updated_at: now,
      is_active: false,
      settings: { ...(input.settings ?? {}) },
    };
    this.db
      .prepare('INSERT INTO profiles (id, name, description, created_at, updated_at, settings) VALUES (?, ?, ?, ?, ?, ?)')
      .run(profile.id, profile.name, profile.description, now, now, JSON.stringify(profile.settings));
    this.cache.set(profile.id, profile);
    fs.mkdirSync(this.dataDirFor(profile.id), { recursive: true });
    this.refreshActiveFlags();
    return { ...profile, is_active: profile.id === this.activeId };
  }

  update(id: string, patch: Partial<ProfileInput>): Profile {
    const profile = this.cache.get(id);
    if (!profile) throw new ProfileError(`Profile not found: ${id}`);
    if (patch.name !== undefined) {
      const name = String(patch.name).trim();
      if (!name) throw new ProfileError('A profile needs a name');
      if (name.length > 80) throw new ProfileError('Profile name is too long (max 80)');
      profile.name = name;
    }
    if (patch.description !== undefined) profile.description = String(patch.description).trim().slice(0, 400);
    if (patch.settings !== undefined) profile.settings = { ...profile.settings, ...patch.settings };
    profile.updated_at = Date.now();
    this.db
      .prepare('UPDATE profiles SET name = ?, description = ?, updated_at = ?, settings = ? WHERE id = ?')
      .run(profile.name, profile.description, profile.updated_at, JSON.stringify(profile.settings), id);
    return { ...profile };
  }

  /** Deletes a profile and its data directory. The last profile cannot be deleted, and deleting the active one switches to another. */
  delete(id: string): boolean {
    const profile = this.cache.get(id);
    if (!profile) return false;
    if (this.cache.size <= 1) throw new ProfileError('Cannot delete the last profile');
    this.db.prepare('DELETE FROM profiles WHERE id = ?').run(id);
    this.cache.delete(id);
    try {
      fs.rmSync(this.dataDirFor(id), { recursive: true, force: true });
    } catch {
      // The row is gone; a leftover directory is harmless and can be cleaned up by hand.
    }
    if (this.activeId === id) {
      this.activeId = [...this.cache.keys()][0]!;
      this.persistActive();
    }
    this.refreshActiveFlags();
    return true;
  }

  /** Switch the active profile. Unknown ids are refused so a typo cannot silently point at nothing. */
  setActive(id: string): Profile {
    const profile = this.cache.get(id);
    if (!profile) throw new ProfileError(`Profile not found: ${id}`);
    this.activeId = id;
    this.persistActive();
    this.refreshActiveFlags();
    return profile;
  }

  /** A full copy of a profile's stored data, with a brand-new UUID on import. */
  export(id: string, memory: ProfileExport['memory'], runs: ProfileExport['runs']): ProfileExport {
    const profile = this.cache.get(id);
    if (!profile) throw new ProfileError(`Profile not found: ${id}`);
    return {
      format: 'kudbee-profile',
      version: 1,
      exported_at: Date.now(),
      profile: { name: profile.name, description: profile.description, settings: { ...profile.settings } },
      memory,
      runs,
    };
  }

  /**
   * Import: always a new profile with a fresh UUID (never overwrites the source). The memory items and
   * runs are written by the caller into the new profile's directory, so this only returns the profile.
   */
  import(bundle: ProfileExport, memory: ProfileExport['memory'], runs: ProfileExport['runs']): Profile {
    if (!bundle || bundle.format !== 'kudbee-profile') throw new ProfileError('Not a kudbee profile export');
    const source = bundle.profile ?? { name: 'Imported profile', description: '' };
    const name = `${source.name || 'Imported profile'} (imported)`.slice(0, 80);
    const profile = this.create({ name, description: source.description ?? '', settings: source.settings ?? {} });
    void memory;
    void runs;
    return profile;
  }

  close(): void {
    this.db.close();
  }
}

export default ProfileManager;
