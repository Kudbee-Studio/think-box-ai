// kudbEE Git Repository Manager — Clone and sync repos to the dashboard

import { execSync, execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export interface GitRepoConfig {
  url: string;
  // The one caller (git-api-routes.ts /clone) never sets this; cloneRepository() already
  // falls back to path.join(this.baseDir, repoName) below when it's absent.
  localPath?: string;
  branch?: string;
  depth?: number;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  modified?: number;
  children?: FileTreeNode[];
}

export interface RepositoryState {
  url: string;
  name: string;
  localPath: string;
  branch: string;
  lastSync: number;
  fileCount: number;
  isDirty: boolean;
  status: 'idle' | 'cloning' | 'syncing' | 'error';
  error?: string;
}

/**
 * Git Repository Manager — Clone, track, and sync repositories
 */
// Input validation. Repository URLs and branches reach `git` as arguments (never a shell string), and only
// public github.com HTTPS repositories are cloneable. File access is confined to the manager's base directory.
export class GitInputError extends Error {}

export const GITHUB_HTTPS_URL = /^https:\/\/github\.com\/[A-Za-z0-9][A-Za-z0-9_.-]*\/[A-Za-z0-9][A-Za-z0-9_.-]*?(?:\.git)?$/;
export const SAFE_BRANCH = /^[A-Za-z0-9_][A-Za-z0-9_./-]{0,99}$/;

export class GitRepoManager {
  private baseDir: string;
  private repos: Map<string, RepositoryState> = new Map();

  constructor(baseDir: string = './workspaces') {
    this.baseDir = baseDir;
    if (!fs.existsSync(baseDir)) {
      fs.mkdirSync(baseDir, { recursive: true });
    }
  }

  /**
   * Clone a git repository
   */
  async cloneRepository(config: GitRepoConfig): Promise<RepositoryState> {
    if (typeof config.url !== 'string' || !GITHUB_HTTPS_URL.test(config.url)) {
      throw new GitInputError('Only public https://github.com/<owner>/<repo> URLs can be cloned');
    }
    if (config.branch !== undefined && !(typeof config.branch === 'string' && SAFE_BRANCH.test(config.branch))) {
      throw new GitInputError('Invalid branch name');
    }
    if (config.depth !== undefined && !(Number.isInteger(config.depth) && config.depth > 0 && config.depth <= 1000)) {
      throw new GitInputError('Invalid clone depth');
    }
    const repoName = this.extractRepoName(config.url);
    if (repoName.startsWith('.')) throw new GitInputError('Invalid repository name');
    const localPath = config.localPath || path.join(this.baseDir, repoName);

    const state: RepositoryState = {
      url: config.url,
      name: repoName,
      localPath,
      branch: config.branch || 'main',
      lastSync: Date.now(),
      fileCount: 0,
      isDirty: false,
      status: 'cloning'
    };

    try {
      // Check if already cloned
      if (fs.existsSync(localPath)) {
        await this.syncRepository(localPath);
      } else {
        // Clone the repository: arguments go to git directly (no shell), after strict validation.
        const args = ['clone'];
        if (config.depth) args.push('--depth', String(Math.trunc(config.depth)));
        if (config.branch) args.push('-b', config.branch);
        args.push('--', config.url, localPath);
        execFileSync('git', args, { encoding: 'utf-8', stdio: 'pipe' });
      }

      // Count files
      state.fileCount = this.countFiles(localPath);
      state.status = 'idle';
      state.lastSync = Date.now();

      this.repos.set(repoName, state);
      return state;
    } catch (error) {
      state.status = 'error';
      state.error = String(error);
      throw new Error(`Failed to clone repository: ${error}`);
    }
  }

  /**
   * Sync repository with remote
   */
  private async syncRepository(localPath: string): Promise<void> {
    try {
      execSync('git fetch origin', { cwd: localPath, stdio: 'pipe' });
      execSync('git pull origin', { cwd: localPath, stdio: 'pipe' });
    } catch (error) {
      console.warn(`Failed to sync repository at ${localPath}:`, error);
    }
  }

  /**
   * Get file tree for a repository
   */
  getFileTree(localPath: string, maxDepth: number = 10): FileTreeNode {
    const buildTree = (dirPath: string, depth: number): FileTreeNode => {
      const name = path.basename(dirPath) || dirPath;
      const stat = fs.statSync(dirPath);

      const node: FileTreeNode = {
        name,
        path: dirPath,
        type: 'directory',
        size: stat.size,
        modified: stat.mtime.getTime(),
        children: []
      };

      if (depth < maxDepth) {
        try {
          const entries = fs.readdirSync(dirPath, { withFileTypes: true })
            .filter(entry => !entry.name.startsWith('.git') && !entry.name.startsWith('.'))
            .sort((a, b) => {
              if (a.isDirectory() && !b.isDirectory()) return -1;
              if (!a.isDirectory() && b.isDirectory()) return 1;
              return a.name.localeCompare(b.name);
            });

          for (const entry of entries) {
            const entryPath = path.join(dirPath, entry.name);
            let entryStat: fs.Stats;
            try {
              entryStat = fs.statSync(entryPath);
            } catch {
              continue; // broken symlink or entry removed mid-listing: skip it, keep the rest
            }

            if (entry.isDirectory()) {
              node.children!.push(buildTree(entryPath, depth + 1));
            } else {
              node.children!.push({
                name: entry.name,
                path: entryPath,
                type: 'file',
                size: entryStat.size,
                modified: entryStat.mtime.getTime()
              });
            }
          }
        } catch (error) {
          console.warn(`Failed to read directory ${dirPath}:`, error);
        }
      }

      return node;
    };

    return buildTree(localPath, 0);
  }

  /**
   * Read file content
   */
  /** Resolve a caller-supplied path inside baseDir; anything that escapes (absolute, `..`, symlink) is refused. */
  resolveInside(filePath: string): string {
    const root = fs.realpathSync(path.resolve(this.baseDir));
    const target = path.resolve(root, filePath);
    if (target !== root && !target.startsWith(root + path.sep)) throw new GitInputError('Path is outside the workspace');
    // Refuse symlinks that leave the workspace: check the deepest existing ancestor.
    let probe = target;
    while (!fs.existsSync(probe) && probe !== root) probe = path.dirname(probe);
    const real = fs.realpathSync(probe);
    if (real !== root && !real.startsWith(root + path.sep)) throw new GitInputError('Path is outside the workspace');
    return target;
  }

  readFile(filePath: string): string {
    try {
      return fs.readFileSync(this.resolveInside(filePath), 'utf-8');
    } catch (error) {
      if (error instanceof GitInputError) throw error;
      throw new Error(`Failed to read file: ${error}`);
    }
  }

  /**
   * Write file to workspace
   */
  writeFile(filePath: string, content: string, createDirs: boolean = true): string {
    try {
      const target = this.resolveInside(filePath);
      if (createDirs) {
        const dir = path.dirname(target);
        if (!fs.existsSync(dir)) {
          fs.mkdirSync(dir, { recursive: true });
        }
      }

      fs.writeFileSync(target, content, 'utf-8');
      return target;
    } catch (error) {
      if (error instanceof GitInputError) throw error;
      throw new Error(`Failed to write file: ${error}`);
    }
  }

  /**
   * Check repository status
   */
  getRepositoryStatus(localPath: string): { isDirty: boolean; changes: string[] } {
    try {
      const status = execSync('git status --porcelain', {
        cwd: localPath,
        encoding: 'utf-8',
        stdio: 'pipe'
      });

      const changes = status
        .split('\n')
        .filter(line => line.trim())
        .map(line => line.substring(3));

      return {
        isDirty: changes.length > 0,
        changes
      };
    } catch (error) {
      return { isDirty: false, changes: [] };
    }
  }

  /**
   * Get repository info
   */
  getRepositoryInfo(repoName: string): RepositoryState | undefined {
    return this.repos.get(repoName);
  }

  /**
   * List all tracked repositories
   */
  listRepositories(): RepositoryState[] {
    return Array.from(this.repos.values());
  }

  /**
   * Extract repository name from URL
   */
  private extractRepoName(url: string): string {
    const match = url.match(/(?:https?:\/\/)?(?:www\.)?github\.com\/[^/]+\/([^/]+?)(?:\.git)?$/);
    if (match) {
      return match[1];
    }

    const lastPart = url.split('/').pop() || 'repo';
    return lastPart.replace(/\.git$/, '');
  }

  /**
   * Count files recursively
   */
  private countFiles(dirPath: string, maxDepth: number = 10, currentDepth: number = 0): number {
    let count = 0;

    if (currentDepth >= maxDepth) {
      return count;
    }

    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true })
        .filter(entry => !entry.name.startsWith('.'));

      for (const entry of entries) {
        if (entry.isDirectory()) {
          count += this.countFiles(path.join(dirPath, entry.name), maxDepth, currentDepth + 1);
        } else {
          count++;
        }
      }
    } catch (error) {
      console.warn(`Failed to count files in ${dirPath}:`, error);
    }

    return count;
  }

  /**
   * Delete repository from disk
   */
  deleteRepository(repoName: string): boolean {
    const state = this.repos.get(repoName);
    if (!state) return false;

    try {
      if (fs.existsSync(state.localPath)) {
        fs.rmSync(state.localPath, { recursive: true, force: true });
      }
      this.repos.delete(repoName);
      return true;
    } catch (error) {
      console.error(`Failed to delete repository: ${error}`);
      return false;
    }
  }
}
