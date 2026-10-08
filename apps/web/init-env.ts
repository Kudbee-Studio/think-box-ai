// `kudbee init`: creates .env from .env.example (owner-only) so there is one obvious file to edit. Never overwrites an existing .env.
import fs from 'node:fs';
import path from 'node:path';

export function initEnv(root: string): { created: boolean; message: string } {
  const env = path.join(root, '.env');
  const example = path.join(root, '.env.example');
  let text: string;
  try { text = fs.readFileSync(example, 'utf8'); } catch { throw new Error(`cannot create .env: ${example} is missing`); }
  try {
    fs.writeFileSync(env, text, { mode: 0o600, flag: 'wx' }); // 'wx' fails if the file exists, so there is no check-then-write gap
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== 'EEXIST') throw e;
    const fd = fs.openSync(env, 'r');
    try { fs.fchmodSync(fd, 0o600); } finally { fs.closeSync(fd); }
    return { created: false, message: '.env already exists; left as it is (permissions set to owner-only).' };
  }
  return { created: true, message: 'Created .env (owner-only). Open it and set ONE of INCEPTION_API_KEY, DEEPSEEK_API_KEY or XAI_API_KEY, or start Ollama for a local model. Then start the dashboard and open Tools > Health check.' };
}
