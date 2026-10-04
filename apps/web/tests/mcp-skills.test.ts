// Unit tests for mcp-skills.ts: category grouping, query filtering and the offline discovery fallback.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { groupSkillsByCategory, filterSkills, discoverMCPSkills } from '../mcp-skills.ts';
import type { MCPServer } from '../mcp-registry.ts';

const server = (over: Partial<MCPServer>): MCPServer => ({ name: 'n', repo: 'r', description: 'd', category: 'Utilities', tags: [], capabilities: [], ...over });

test('groupSkillsByCategory groups by category and puts a blank category under Other', () => {
  const groups = groupSkillsByCategory([
    server({ name: 'a', category: 'Database' }),
    server({ name: 'b', category: 'Database' }),
    server({ name: 'c', category: 'Files' }),
    server({ name: 'd', category: '' }),
  ]);
  assert.equal(groups.Database.length, 2);
  assert.equal(groups.Files.length, 1);
  assert.equal(groups.Other.length, 1);
});

test('filterSkills returns all for an empty query and matches name, description or tags', () => {
  const servers = [
    server({ name: 'postgres', description: 'SQL database', tags: ['db'] }),
    server({ name: 'github', description: 'source control', tags: ['vcs'] }),
  ];
  assert.equal(filterSkills(servers, '').length, 2);
  assert.equal(filterSkills(servers, 'POST').length, 1);
  assert.equal(filterSkills(servers, 'source').length, 1);
  assert.equal(filterSkills(servers, 'vcs').length, 1);
  assert.equal(filterSkills(servers, 'nothing-matches').length, 0);
});

test('discoverMCPSkills returns a list even with no network', async () => {
  const original = global.fetch;
  global.fetch = (() => { throw new Error('offline'); }) as unknown as typeof global.fetch;
  try {
    const skills = await discoverMCPSkills();
    assert.ok(Array.isArray(skills));
    assert.ok(skills.length >= 1, 'falls back to the built-in list');
  } finally {
    global.fetch = original;
  }
});
