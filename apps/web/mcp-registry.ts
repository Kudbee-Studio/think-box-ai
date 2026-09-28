import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

export interface MCPServer {
  name: string;
  repo: string;
  description: string;
  category: string;
  tags: string[];
  capabilities: string[];
}

interface GitHubTree {
  sha: string;
  url: string;
  tree: Array<{ path: string; mode: string; type: string; sha: string; url: string }>;
  truncated: boolean;
}

interface GitHubContent {
  name: string;
  path: string;
  sha: string;
  size: number;
  type: string;
  content?: string;
  encoding?: string;
}

export class MCPRegistry {
  private cacheDir: string;
  private githubToken?: string;
  private githubHeaders: Record<string, string>;

  constructor(githubToken?: string, cacheDir?: string) {
    this.githubToken = githubToken;
    this.cacheDir = cacheDir || path.join(os.homedir(), '.kudbee', 'mcp-cache');
    this.githubHeaders = {
      Accept: 'application/vnd.github.v3+json',
      'User-Agent': 'kudbEE/1.0',
    };
    if (githubToken) {
      this.githubHeaders['Authorization'] = `token ${githubToken}`;
    }
  }

  async discoverServers(): Promise<MCPServer[]> {
    // Check cache first (valid for 24h)
    const cached = this.loadCache();
    if (cached && !this.cacheExpired()) {
      return cached;
    }

    // Fetch from official registry
    const servers = await this.fetchFromRegistry();
    this.saveCache(servers);
    return servers;
  }

  private async fetchFromRegistry(): Promise<MCPServer[]> {
    try {
      // Get the tree of servers directory from GitHub
      const treeUrl = 'https://api.github.com/repos/anthropics/mcp-servers/git/trees/main?recursive=1';
      const treeRes = await fetch(treeUrl, { headers: this.githubHeaders });

      if (!treeRes.ok) {
        throw new Error(`GitHub API error: ${treeRes.status}`);
      }

      const treeData = (await treeRes.json()) as GitHubTree;
      const serverDirs = new Set<string>();

      // Find all server directories (immediate subdirs of servers/)
      for (const item of treeData.tree) {
        const match = item.path.match(/^servers\/([^/]+)\/$/);
        if (match) {
          serverDirs.add(match[1]);
        }
      }

      // Parse each server's README
      const servers: MCPServer[] = [];
      for (const serverName of Array.from(serverDirs).sort()) {
        const metadata = await this.parseServerMetadata(serverName);
        if (metadata) {
          servers.push(metadata);
        }
      }

      return servers;
    } catch (error) {
      console.error('Failed to fetch MCP registry:', error);
      return this.getFallbackServers();
    }
  }

  private getFallbackServers(): MCPServer[] {
    return [
      {
        name: 'github',
        repo: 'community/mcp-servers/github',
        description: 'Interact with GitHub repositories, issues, and pull requests',
        category: 'Developer Tools',
        tags: ['version-control', 'github', 'api'],
        capabilities: ['List repositories', 'Create issues', 'Manage pull requests', 'Create branches'],
      },
      {
        name: 'postgres',
        repo: 'community/mcp-servers/postgres',
        description: 'Execute SQL queries and manage PostgreSQL databases',
        category: 'Database',
        tags: ['database', 'sql', 'postgres'],
        capabilities: ['Execute queries', 'List tables', 'Schema inspection', 'Data export'],
      },
      {
        name: 'slack',
        repo: 'community/mcp-servers/slack',
        description: 'Send messages and manage Slack workspaces',
        category: 'Communication',
        tags: ['communication', 'slack', 'api'],
        capabilities: ['Send messages', 'List channels', 'Create threads', 'Upload files'],
      },
      {
        name: 'filesystem',
        repo: 'community/mcp-servers/filesystem',
        description: 'Read and write files on the local filesystem',
        category: 'Files',
        tags: ['filesystem', 'files', 'io'],
        capabilities: ['Read files', 'Write files', 'List directories', 'Delete files'],
      },
      {
        name: 'stripe',
        repo: 'community/mcp-servers/stripe',
        description: 'Process payments and manage billing with Stripe',
        category: 'Finance',
        tags: ['finance', 'payment', 'stripe'],
        capabilities: ['Create charges', 'List transactions', 'Manage customers', 'Issue refunds'],
      },
      {
        name: 'linear',
        repo: 'community/mcp-servers/linear',
        description: 'Create and manage issues in Linear',
        category: 'Project Management',
        tags: ['project-management', 'linear', 'api'],
        capabilities: ['Create issues', 'Update status', 'Assign team members', 'Search issues'],
      },
    ];
  }

  private async parseServerMetadata(serverName: string): Promise<MCPServer | null> {
    try {
      const contentUrl = `https://api.github.com/repos/anthropics/mcp-servers/contents/servers/${serverName}/README.md`;
      const contentRes = await fetch(contentUrl, { headers: this.githubHeaders });

      if (!contentRes.ok) {
        return null;
      }

      const contentData = (await contentRes.json()) as GitHubContent;
      const readme = Buffer.from(contentData.content || '', 'base64').toString();

      return {
        name: serverName,
        repo: `anthropics/mcp-servers/servers/${serverName}`,
        description: this.extractDescription(readme),
        category: this.inferCategory(serverName),
        tags: this.extractTags(readme),
        capabilities: this.extractCapabilities(readme),
      };
    } catch {
      return null;
    }
  }

  private extractDescription(readme: string): string {
    // Try to extract description from README header or first paragraph
    const lines = readme.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('#') && !line.startsWith('##')) {
        // Found main title, look for description after it
        for (let j = i + 1; j < lines.length; j++) {
          const descLine = lines[j].trim();
          if (descLine && !descLine.startsWith('#') && !descLine.startsWith('-') && !descLine.startsWith('*')) {
            return descLine.substring(0, 100);
          }
        }
      }
    }
    return 'MCP Server';
  }

  private extractCapabilities(readme: string): string[] {
    const capMatch = readme.match(/## Capabilities.*?\n([\s\S]*?)(?=##|$)/i);
    if (!capMatch) {
      return [];
    }

    return capMatch[1]
      .split('\n')
      .filter((line) => line.trim().startsWith('-') || line.trim().startsWith('*'))
      .map((line) => line.replace(/^[\s\-\*]+/, '').trim())
      .filter((cap) => cap.length > 0);
  }

  private extractTags(readme: string): string[] {
    const tags = new Set<string>();

    // Auto-tag by capability
    const capabilities = this.extractCapabilities(readme);
    for (const cap of capabilities) {
      const lower = cap.toLowerCase();
      if (lower.includes('file') || lower.includes('filesystem')) tags.add('filesystem');
      if (lower.includes('database') || lower.includes('sql') || lower.includes('postgres')) tags.add('database');
      if (lower.includes('git')) tags.add('version-control');
      if (lower.includes('web') || lower.includes('http') || lower.includes('fetch')) tags.add('http');
      if (lower.includes('api')) tags.add('api');
      if (lower.includes('slack')) tags.add('communication');
    }

    return Array.from(tags);
  }

  private inferCategory(name: string): string {
    const lower = name.toLowerCase();
    if (lower.includes('database') || lower.includes('postgres') || lower.includes('sql')) return 'Database';
    if (lower.includes('github') || lower.includes('git')) return 'Developer Tools';
    if (lower.includes('slack') || lower.includes('teams') || lower.includes('discord')) return 'Communication';
    if (lower.includes('file') || lower.includes('fs') || lower.includes('drive')) return 'Files';
    if (lower.includes('stripe') || lower.includes('payment')) return 'Finance';
    if (lower.includes('linear') || lower.includes('jira') || lower.includes('asana')) return 'Project Management';
    return 'Utilities';
  }

  private loadCache(): MCPServer[] | null {
    try {
      const file = path.join(this.cacheDir, 'servers.json');
      if (fs.existsSync(file)) {
        const data = JSON.parse(fs.readFileSync(file, 'utf-8')) as { servers: MCPServer[] };
        return data.servers;
      }
    } catch {
      return null;
    }
    return null;
  }

  private saveCache(servers: MCPServer[]): void {
    try {
      fs.mkdirSync(this.cacheDir, { recursive: true });
      fs.writeFileSync(
        path.join(this.cacheDir, 'servers.json'),
        JSON.stringify({ servers, timestamp: Date.now() }, null, 2),
      );
    } catch {
      // Silently fail cache save; discovery still works without persistence
    }
  }

  private cacheExpired(): boolean {
    try {
      const file = path.join(this.cacheDir, 'servers.json');
      const stat = fs.statSync(file);
      const ageMs = Date.now() - stat.mtimeMs;
      return ageMs > 24 * 60 * 60 * 1000; // 24 hours
    } catch {
      return true;
    }
  }

  groupByCategory(servers: MCPServer[]): Record<string, MCPServer[]> {
    return servers.reduce(
      (acc, s) => {
        if (!acc[s.category]) acc[s.category] = [];
        acc[s.category].push(s);
        return acc;
      },
      {} as Record<string, MCPServer[]>,
    );
  }

  filter(servers: MCPServer[], query: string): MCPServer[] {
    const lower = query.toLowerCase();
    return servers.filter(
      (s) =>
        s.name.toLowerCase().includes(lower) ||
        s.description.toLowerCase().includes(lower) ||
        s.tags.some((t) => t.toLowerCase().includes(lower)) ||
        s.capabilities.some((c) => c.toLowerCase().includes(lower)),
    );
  }
}

export default MCPRegistry;
