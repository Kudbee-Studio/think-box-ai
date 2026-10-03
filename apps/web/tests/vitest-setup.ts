// VITEST setup: Bridge Node.js test API to VITEST
import { describe as vitestDescribe, it as vitestIt, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

// Export as node:test compatible APIs for existing tests
Object.assign(global, {
  describe: vitestDescribe,
  it: vitestIt,
  beforeEach,
  afterEach,
  beforeAll,
  afterAll,
});
