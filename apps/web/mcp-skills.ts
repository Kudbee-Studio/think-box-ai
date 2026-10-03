// MCP skill discovery helpers. Moved out of server.ts unchanged.
import type { MCPServer } from './mcp-registry.ts';

export async function discoverMCPSkills(): Promise<any[]> {
  try {
    const MCPRegistry = (await import('./mcp-registry.ts')).default;
    const registry = new MCPRegistry(process.env.GITHUB_TOKEN);
    return await registry.discoverServers();
  } catch (err) {
    console.error('Failed to discover MCP skills:', err);
    return [];
  }
}

export function groupSkillsByCategory(skills: MCPServer[]): Record<string, MCPServer[]> {
  const groups: Record<string, MCPServer[]> = {};
  for (const skill of skills) {
    const cat = skill.category || 'Other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(skill);
  }
  return groups;
}

export function filterSkills(skills: MCPServer[], query: string): MCPServer[] {
  if (!query) return skills;
  const q = query.toLowerCase();
  return skills.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.description?.toLowerCase().includes(q) ||
      s.tags?.some((t: string) => t.toLowerCase().includes(q))
  );
}

