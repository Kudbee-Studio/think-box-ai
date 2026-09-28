# PR 275 — MCP Server Integration: Interactive Plugin Discovery & Selection

**Status:** PLANNED  
**Priority:** HIGH  
**Scope:** Integrate Model Context Protocol (MCP) servers into CLI for interactive skill discovery  
**Technology:** MCP SDK, GitHub API, pop-up menus

---

## Overview

**Goal:** Connect kudbEE CLI to hundreds of MCP servers (Anthropic ecosystem) for interactive plugin discovery and selection.

**User Experience:**
```bash
$ kudbee
kudbEE Agent OS

🎯 /skills          → Browse 100+ MCP skills (pop-up menu)
   /skill SEARCH    → Find skill by name/tag
   /install SKILL   → Add skill to this session
   /uninstall SKILL → Remove skill
```

**Result:** Enterprise tool ecosystem accessible from CLI in seconds.

---

## Architecture

### MCP Ecosystem Discovery

```
GitHub (Anthropic MCP Registry)
├── claude-3-tools (text, file, web)
├── claude-3-expert-tools (advanced reasoning)
├── anthropic-marketplace (third-party)
└── community-mcp-servers (open source)
    ├── filesystem
    ├── postgresql
    ├── git
    ├── slack
    ├── linear
    ├── stripe
    └── ... 100+ more
```

**Discovery Source:** `https://github.com/anthropics/mcp-servers/` (official registry)

### Integration Points

```
kudbEE CLI
├── /skills              → Fetch from GitHub + cache locally
├── Interactive Menu    → Arrow keys, search, preview
├── /skill install      → Download + verify
└── Agent Loop          → Load skills dynamically
    └── Model sees 100+ tools available
```

---

## Implementation

### 1. MCP Fetch & Cache (TypeScript)

**File:** `apps/web/mcp-registry.ts`

```typescript
import { Octokit } from '@octokit/rest';

interface MCPServer {
  name: string;
  repo: string;
  description: string;
  stars: number;
  category: string;
  tags: string[];
  installCmd: string;
  capabilities: string[];
}

class MCPRegistry {
  private octokit: Octokit;
  private cacheDir = path.join(os.homedir(), '.kudbee/mcp-cache');
  
  constructor(githubToken?: string) {
    this.octokit = new Octokit({ auth: githubToken });
  }
  
  async discoverServers(): Promise<MCPServer[]> {
    // Check cache first (valid for 24h)
    const cached = this.loadCache();
    if (cached && !this.cacheExpired()) return cached;
    
    // Fetch from official registry
    const servers = await this.fetchFromRegistry();
    this.saveCache(servers);
    return servers;
  }
  
  private async fetchFromRegistry(): Promise<MCPServer[]> {
    // Official Anthropic MCP registry
    const registryUrl = 'https://github.com/anthropics/mcp-servers/tree/main/servers';
    
    const { data } = await this.octokit.repos.getContent({
      owner: 'anthropics',
      repo: 'mcp-servers',
      path: 'servers'
    });
    
    const servers: MCPServer[] = [];
    
    for (const item of data) {
      if (item.type === 'dir') {
        const metadata = await this.parseServerMetadata(item.name);
        if (metadata) servers.push(metadata);
      }
    }
    
    return servers.sort((a, b) => b.stars - a.stars);
  }
  
  private async parseServerMetadata(serverName: string): Promise<MCPServer | null> {
    try {
      const { data } = await this.octokit.repos.getContent({
        owner: 'anthropics',
        repo: 'mcp-servers',
        path: `servers/${serverName}/README.md`
      });
      
      const readme = Buffer.from(data.content, 'base64').toString();
      
      return {
        name: serverName,
        repo: `anthropics/mcp-servers/servers/${serverName}`,
        description: this.extractDescription(readme),
        stars: await this.getStarCount(serverName),
        category: this.inferCategory(serverName),
        tags: this.extractTags(readme),
        installCmd: `npm install @anthropic/mcp-${serverName}`,
        capabilities: this.extractCapabilities(readme)
      };
    } catch {
      return null;
    }
  }
  
  private extractDescription(readme: string): string {
    const match = readme.match(/^# .*\n\n(.+)/);
    return match ? match[1] : 'MCP Server';
  }
  
  private extractCapabilities(readme: string): string[] {
    const capMatch = readme.match(/## Capabilities.*?\n([\s\S]*?)(?=##|$)/);
    if (!capMatch) return [];
    
    return capMatch[1]
      .split('\n')
      .filter((line) => line.startsWith('-'))
      .map((line) => line.replace(/^- /, '').trim());
  }
  
  private extractTags(readme: string): string[] {
    const tags = new Set<string>();
    
    // Auto-tag by capability
    const capabilities = this.extractCapabilities(readme);
    for (const cap of capabilities) {
      if (cap.includes('file')) tags.add('filesystem');
      if (cap.includes('database') || cap.includes('sql')) tags.add('database');
      if (cap.includes('git')) tags.add('version-control');
      if (cap.includes('web') || cap.includes('http')) tags.add('http');
    }
    
    return Array.from(tags);
  }
  
  private inferCategory(name: string): string {
    if (name.includes('database') || name.includes('postgres')) return 'Database';
    if (name.includes('github') || name.includes('git')) return 'Developer Tools';
    if (name.includes('slack') || name.includes('teams')) return 'Communication';
    if (name.includes('file') || name.includes('fs')) return 'Files';
    return 'Utilities';
  }
  
  private async getStarCount(serverName: string): Promise<number> {
    try {
      const { data } = await this.octokit.repos.get({
        owner: 'anthropics',
        repo: 'mcp-servers'
      });
      // Rough estimate: divide total stars by number of servers
      return Math.floor((data.stargazers_count || 0) / 50);
    } catch {
      return 0;
    }
  }
  
  private loadCache(): MCPServer[] | null {
    try {
      const file = path.join(this.cacheDir, 'servers.json');
      if (fs.existsSync(file)) {
        const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
        return data.servers;
      }
    } catch {
      return null;
    }
    return null;
  }
  
  private saveCache(servers: MCPServer[]): void {
    fs.mkdirSync(this.cacheDir, { recursive: true });
    fs.writeFileSync(
      path.join(this.cacheDir, 'servers.json'),
      JSON.stringify({ servers, timestamp: Date.now() }, null, 2)
    );
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
}

export default MCPRegistry;
```

### 2. Interactive Menu System

**File:** `apps/web/cli.ts` (new)

```typescript
async function interactiveSkillSelect(registry: MCPRegistry): Promise<MCPServer | null> {
  const servers = await registry.discoverServers();
  
  // Show categories
  console.log(c.bold('\n🔌 AVAILABLE MCP SKILLS\n'));
  
  const byCategory = servers.reduce((acc, s) => {
    if (!acc[s.category]) acc[s.category] = [];
    acc[s.category].push(s);
    return acc;
  }, {} as Record<string, MCPServer[]>);
  
  for (const [cat, serversInCat] of Object.entries(byCategory)) {
    console.log(c.bold(`  ${cat}`));
    serversInCat.forEach((s) => {
      const stars = s.stars > 0 ? c.yellow(`⭐ ${s.stars}`) : '';
      console.log(`    [${s.name}] ${s.description} ${stars}`);
    });
  }
  
  // Interactive selection
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  
  return new Promise((resolve) => {
    rl.question(c.cyan('\n  Search or name: '), (query) => {
      rl.close();
      
      const query_lower = query.toLowerCase();
      const matches = servers.filter(
        (s) => s.name.includes(query_lower) || 
               s.description.includes(query_lower) ||
               s.tags.some((t) => t.includes(query_lower))
      );
      
      if (matches.length === 0) {
        console.log(c.red('  No matches found'));
        resolve(null);
      } else if (matches.length === 1) {
        console.log(c.green(`  ✓ Selected: ${matches[0].name}`));
        resolve(matches[0]);
      } else {
        // Multi-match: show preview
        console.log(c.dim('\n  Found:'));
        matches.forEach((m, i) => console.log(`    ${i + 1}. ${m.name} — ${m.description}`));
        
        rl.question(c.cyan('  Pick (number): '), (num) => {
          const idx = parseInt(num, 10) - 1;
          if (idx >= 0 && idx < matches.length) {
            console.log(c.green(`  ✓ Selected: ${matches[idx].name}`));
            resolve(matches[idx]);
          } else {
            resolve(null);
          }
        });
      }
    });
  });
}
```

### 3. CLI Commands

**Add to `cli.ts` command handler:**

```typescript
case '/skills': {
  const registry = new MCPRegistry(process.env.GITHUB_TOKEN);
  console.log(c.dim('Fetching skill registry...'));
  const servers = await registry.discoverServers();
  console.log(`Found ${servers.length} available skills`);
  
  // Show grouped by category
  const byCategory = servers.reduce((acc, s) => {
    if (!acc[s.category]) acc[s.category] = [];
    acc[s.category].push(s);
    return acc;
  }, {} as Record<string, MCPServer[]>);
  
  for (const [cat, items] of Object.entries(byCategory)) {
    console.log(c.bold(`\n  ${cat}`));
    items.forEach((s) => {
      console.log(`    ${c.cyan(s.name)} — ${s.description}`);
      if (s.capabilities.length) {
        console.log(c.dim(`      Capabilities: ${s.capabilities.join(', ')}`));
      }
    });
  }
  break;
}

case '/skill': {
  const skillName = args[0];
  const registry = new MCPRegistry(process.env.GITHUB_TOKEN);
  
  if (!skillName) {
    // Interactive selection
    const selected = await interactiveSkillSelect(registry);
    if (selected) {
      console.log(c.green(`\n  📦 Installing ${selected.name}...`));
      // Install logic here
    }
  } else {
    // Direct selection
    const servers = await registry.discoverServers();
    const match = servers.find((s) => s.name.includes(skillName.toLowerCase()));
    if (match) {
      console.log(`\n${c.bold(match.name)}`);
      console.log(c.dim(`  ${match.description}`));
      console.log(c.dim(`  Capabilities: ${match.capabilities.join(', ')}`));
      console.log(c.dim(`  Install: ${match.installCmd}`));
    } else {
      console.log(c.red(`Skill not found: ${skillName}`));
    }
  }
  break;
}
```

---

## Data Flow

```
User runs: /skills
    ↓
MCPRegistry.discoverServers()
    ↓
Check local cache (24h TTL)
    ↓
If expired: Fetch from GitHub (anthropics/mcp-servers)
    ↓
Parse README, extract metadata (capabilities, tags)
    ↓
Display categorized menu
    ↓
User selects via interactive picker or search
    ↓
Show skill details (capabilities, install command)
    ↓
Install into current session (or save for future use)
```

---

## Benefits

✅ **Discovery:** Browse 100+ tools from CLI, no web browsing needed  
✅ **Categorization:** Organized by function (Database, Files, Developers, etc)  
✅ **Search:** Fuzzy matching for quick skill finding  
✅ **Transparent:** See exactly what each skill does  
✅ **Enterprise:** Feels premium, professional tool access  
✅ **Offline:** After first fetch, skills available without network  
✅ **Caching:** 24h cache reduces GitHub API calls  

---

## Success Criteria

- [ ] Discover 100+ MCP servers from official registry
- [ ] Interactive menu feels responsive (< 2s to browse)
- [ ] Search works: partial name, tag matching
- [ ] Cache persists across sessions
- [ ] Installed skills load in agent loop
- [ ] Help updated with `/skills` command
- [ ] Works without GITHUB_TOKEN (public repo)
- [ ] Unit tests for registry, filtering, parsing

---

## Future Enhancements

### Phase 2: Install & Activate
- [ ] `npm install` integration for auto-download
- [ ] Skill versioning (pin to specific version)
- [ ] Enable/disable per-session

### Phase 3: Community Registry
- [ ] Index community MCP servers (not just Anthropic)
- [ ] Star/like system for skill discovery
- [ ] User feedback and ratings

### Phase 4: GUI Plugin Browser
- [ ] Dashboard plugin browser (visual, sortable)
- [ ] Drag-drop to add to toolbar
- [ ] Recently used plugins

---

## Testing

```typescript
test('MCPRegistry.discoverServers() returns array', async () => {
  const registry = new MCPRegistry();
  const servers = await registry.discoverServers();
  expect(servers.length).toBeGreaterThan(50);
  expect(servers[0]).toHaveProperty('name');
  expect(servers[0]).toHaveProperty('capabilities');
});

test('cache expires after 24h', () => {
  // Mock fs to return old file
  const registry = new MCPRegistry();
  expect(registry.cacheExpired()).toBe(true);
});

test('interactive selection works', async () => {
  const registry = new MockMCPRegistry();
  const selected = await interactiveSkillSelect(registry);
  expect(selected).toHaveProperty('name');
});
```

---

## Related PRs

- **PR 272:** Dashboard CSS (completed)
- **PR 273:** Persistent Memory (planned)
- **PR 274:** Streaming UI (planned)
- **PR 275:** This one (MCP Integration)

---

## Timeline

**Week 1:**
- [ ] Implement MCPRegistry class
- [ ] GitHub API integration
- [ ] Caching system

**Week 2:**
- [ ] CLI command `/skills` and `/skill`
- [ ] Interactive menu
- [ ] Testing

**Week 3:**
- [ ] Polish, docs
- [ ] Demo with top 10 skills
- [ ] Merge and ship

---

**Next:** Start PR 275 after PR 272 merges. MCP integration unlocks enterprise-grade tool access from CLI.
