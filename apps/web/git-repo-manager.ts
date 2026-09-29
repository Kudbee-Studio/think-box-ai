// kudbEE Git Repository Manager — Clone and sync repos to the dashboard

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export interface GitRepoConfig {
  url: string;
  localPath: string;
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
    const repoName = this.extractRepoName(config.url);
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
        // Clone the repository
        const cloneCmd = [
          'git clone',
          config.depth ? `--depth ${config.depth}` : '',
          config.branch ? `-b ${config.branch}` : '',
          config.url,
          localPath
        ].filter(Boolean).join(' ');

        execSync(cloneCmd, { encoding: 'utf-8', stdio: 'pipe' });
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
            const entryStat = fs.statSync(entryPath);

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
  readFile(filePath: string): string {
    try {
      return fs.readFileSync(filePath, 'utf-8');
    } catch (error) {
      throw new Error(`Failed to read file: ${error}`);
    }
  }

  /**
   * Write file to workspace
   */
  writeFile(filePath: string, content: string, createDirs: boolean = true): string {
    try {
      if (createDirs) {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
          fs.mkdirSync(dir, { recursive: true });
        }
      }

      fs.writeFileSync(filePath, content, 'utf-8');
      return filePath;
    } catch (error) {
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
