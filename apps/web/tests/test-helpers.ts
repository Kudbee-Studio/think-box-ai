// Minimal `expect()` shim. `node:test` does not export `expect` — only
// describe/it/before/after/mock — so every test file in this suite that wrote
// `import { expect } from 'node:test'` was importing `undefined` and failing
// at module load before a single assertion ran. This restores just the
// matcher surface actually used across the suite.
import assert from 'node:assert/strict';

export function expect<T>(actual: T) {
  return {
    toBe(expected: T) {
      assert.strictEqual(actual, expected);
    },
    toEqual(expected: unknown) {
      assert.deepStrictEqual(actual, expected);
    },
    toBeDefined() {
      assert.notStrictEqual(actual, undefined);
    },
    toBeUndefined() {
      assert.strictEqual(actual, undefined);
    },
    toBeGreaterThan(expected: number) {
      assert.ok((actual as unknown as number) > expected, `expected ${actual} > ${expected}`);
    },
    toBeGreaterThanOrEqual(expected: number) {
      assert.ok((actual as unknown as number) >= expected, `expected ${actual} >= ${expected}`);
    },
    toContain(expected: unknown) {
      assert.ok((actual as unknown as unknown[]).includes(expected), `expected ${actual} to contain ${expected}`);
    },
    toMatch(pattern: RegExp) {
      assert.ok(pattern.test(actual as unknown as string), `expected ${actual} to match ${pattern}`);
    },
  };
}
