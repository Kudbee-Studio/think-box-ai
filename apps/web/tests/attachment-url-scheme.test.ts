// Regression guard for the attachment image URL scheme check (audit hardening).
// The server builds attachment URLs as same-origin relative paths, but the client must not assume it:
// a `javascript:`/`vbscript:`/absolute or `data:text/html` value must never reach an <img>.
// app.js is a browser module (imports + DOM), so this asserts the guard is present at every sink and that
// the helper implements the intended scheme allow-list.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const appSrc = fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'public', 'js', 'app.js'), 'utf8');

test('isSafeImageUrl only allows same-origin paths and data:image/* URLs', () => {
  const m = /function isSafeImageUrl\(url\) \{\s*return typeof url === 'string' && (\/.+\/)\.test\(url\);\s*\}/.exec(appSrc);
  assert.ok(m, 'isSafeImageUrl helper with a scheme regex is missing from app.js');
  const re = new RegExp(m![1].slice(1, -1));
  for (const ok of ['/api/sessions/abc/files/raw?path=x', '/x.png', 'data:image/png;base64,AAAA', 'data:image/svg+xml;base64,AA']) assert.equal(re.test(ok), true, ok);
  for (const bad of ['javascript:alert(1)', 'vbscript:msgbox(1)', 'data:text/html,<script>alert(1)</script>', 'http://evil.example/x.png', 'https://evil.example/x.png', '//evil.example/x.png', 'ftp://x/y', '']) assert.equal(re.test(bad), false, bad);
});

test('every <img> sink that takes an imageUrl is guarded by isSafeImageUrl', () => {
  // appendTerminalImage: property assignment.
  assert.match(appSrc, /if \(isSafeImageUrl\(imageUrl\)\) image\.src = imageUrl;/, 'appendTerminalImage must guard image.src');
  // task attachments: filter before the template that interpolates image.imageUrl into src="".
  const attachmentsLine = appSrc.split('\n').find((l) => l.includes('class="task-attachment"') && l.includes('image.imageUrl'));
  assert.ok(attachmentsLine, 'the task-attachment <img> line was not found');
  assert.match(attachmentsLine!, /\.filter\(image => isSafeImageUrl\(image\.imageUrl\)\)/, 'task attachments must filter on isSafeImageUrl');
});
