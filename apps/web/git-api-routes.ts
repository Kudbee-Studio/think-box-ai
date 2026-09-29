// kudbEE Git API Routes — Backend endpoints for git integration

import { Router } from 'express';
import { GitRepoManager, GitInputError } from './git-repo-manager.ts';
import * as fs from 'fs';
import * as path from 'path';


/**
 * Build the /api/git router over one workspace directory. All file access is confined to `baseDir`.
 */
export function createGitRouter(baseDir: string): Router {
const router = Router();
const gitManager = new GitRepoManager(baseDir);

/**
 * POST /api/git/clone — Clone a git repository
 */
router.post('/clone', async (req, res) => {
  try {
    const { url, branch = 'main', shallow = true } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'Repository URL is required' });
    }

    const state = await gitManager.cloneRepository({
      url,
      branch,
      depth: shallow ? 1 : undefined
    });

    res.json(state);
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

/**
 * GET /api/git/repos — List all repositories
 */
router.get('/repos', (req, res) => {
  try {
    const repos = gitManager.listRepositories();
    res.json(repos);
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

/**
 * GET /api/git/tree — Get file tree for a repository
 */
router.get('/tree', (req, res) => {
  try {
    const { repo } = req.query;

    if (!repo) {
      return res.status(400).json({ error: 'Repository name is required' });
    }

    const repoState = gitManager.getRepositoryInfo(repo as string);
    if (!repoState) {
      return res.status(404).json({ error: 'Repository not found' });
    }

    const tree = gitManager.getFileTree(repoState.localPath, 15);
    res.json(tree);
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

/**
 * GET /api/git/file — Read file content
 */
router.get('/file', (req, res) => {
  try {
    const { path: filePath } = req.query;

    if (!filePath) {
      return res.status(400).json({ error: 'File path is required' });
    }

    // Security: prevent path traversal
    const normalizedPath = path.normalize(filePath as string);
    if (normalizedPath.includes('..')) {
      return res.status(403).json({ error: 'Path traversal not allowed' });
    }

    const content = gitManager.readFile(normalizedPath);
    const language = detectLanguage(normalizedPath);

    res.json({ content, language });
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

/**
 * POST /api/git/save — Save file to workspace
 */
router.post('/save', async (req, res) => {
  try {
    const { path: filePath, content } = req.body;

    if (!filePath || content === undefined) {
      return res.status(400).json({ error: 'Path and content are required' });
    }

    // Security: prevent path traversal
    const normalizedPath = path.normalize(filePath);
    if (normalizedPath.includes('..')) {
      return res.status(403).json({ error: 'Path traversal not allowed' });
    }

    const savedPath = gitManager.writeFile(normalizedPath, content, true);

    res.json({
      success: true,
      path: savedPath,
      size: content.length
    });
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

/**
 * GET /api/git/status — Get repository status
 */
router.get('/status', (req, res) => {
  try {
    const { repo } = req.query;

    if (!repo) {
      return res.status(400).json({ error: 'Repository name is required' });
    }

    const repoState = gitManager.getRepositoryInfo(repo as string);
    if (!repoState) {
      return res.status(404).json({ error: 'Repository not found' });
    }

    const status = gitManager.getRepositoryStatus(repoState.localPath);

    res.json({
      ...repoState,
      ...status
    });
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

/**
 * DELETE /api/git/repos/:name — Delete a repository
 */
router.delete('/repos/:name', (req, res) => {
  try {
    const { name } = req.params;

    const success = gitManager.deleteRepository(name);
    if (!success) {
      return res.status(404).json({ error: 'Repository not found' });
    }

    res.json({ success: true, message: `Repository '${name}' deleted` });
  } catch (error) {
    res.status(error instanceof GitInputError ? 400 : 500).json({ error: (error as Error).message });
  }
});

return router;
}

/**
 * Helper: Detect language from file extension
 */
function detectLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase();
  const languages: Record<string, string> = {
    'js': 'javascript',
    'ts': 'typescript',
    'jsx': 'jsx',
    'tsx': 'tsx',
    'py': 'python',
    'java': 'java',
    'go': 'go',
    'rs': 'rust',
    'cpp': 'cpp',
    'c': 'c',
    'cs': 'csharp',
    'rb': 'ruby',
    'php': 'php',
    'swift': 'swift',
    'kt': 'kotlin',
    'sql': 'sql',
    'html': 'html',
    'css': 'css',
    'json': 'json',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sh': 'bash'
  };

  return languages[ext || ''] || 'plaintext';
}

