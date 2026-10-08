// `kudbee init`: creates .env from .env.example (owner-only) so there is one obvious file to edit. Never overwrites an existing .env.
import fs from 'node:fs';
import path from 'node:path';

export function initEnv(root: string): { created: boolean; message: string } {
  const env = path.join(root, '.env');
  const example = path.join(root, '.env.example');
  if (fs.existsSync(env)) {
    fs.chmodSync(env, 0o600);
    return { created: false, message: '.env already exists; left as it is (permissions set to owner-only).' };
  }
  if (!fs.existsSync(example)) throw new Error(`cannot create .env: ${example} is missing`);
  fs.writeFileSync(env, fs.readFileSync(example, 'utf8'), { mode: 0o600 });
  return { created: true, message: 'Created .env (owner-only). Open it and set ONE of INCEPTION_API_KEY, DEEPSEEK_API_KEY or XAI_API_KEY, or start Ollama for a local model. Then start the dashboard and open Tools > Health check.' };
}
