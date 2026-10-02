// Source-level check (torch is not installed in CI): the Janus service pins its model weights to a commit and keeps the model-id allow-list.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const src = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '../janus_service.py'), 'utf8');

test('janus_service pins the model weights to a 40-hex commit and passes it to from_pretrained', () => {
  const m = src.match(/^MODEL_REVISION = "([0-9a-f]{40})"$/m);
  assert.ok(m, 'MODEL_REVISION is a full commit hash');
  assert.match(src, /AutoModelForCausalLM\.from_pretrained\(\s*MODEL_ID,\s*revision=MODEL_REVISION,/);
});

test('janus_service refuses any model id other than the allowed one', () => {
  assert.match(src, /ALLOWED_MODEL_ID = "deepseek-ai\/Janus-Pro-1B"/);
  assert.match(src, /if MODEL_ID != ALLOWED_MODEL_ID:\s*raise RuntimeError/);
});
