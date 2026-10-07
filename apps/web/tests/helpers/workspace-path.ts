// Interactive sessions share one persistent workspace per profile (workspace-resolver.ts): the folder a session's files live in is under <root>/_profiles/, not <root>/<sessionId>.
import fs from 'node:fs';
import path from 'node:path';

/** The directory a session's files really live in. Asking for the file list first makes the server create it. */
export async function workspaceOf(baseUrl: string, workspacesRoot: string, sessionId: string): Promise<string> {
  await fetch(`${baseUrl}/api/sessions/${sessionId}/files`);
  const profiles = path.join(workspacesRoot, '_profiles');
  const dirs = fs.readdirSync(profiles);
  if (dirs.length !== 1) throw new Error(`expected exactly one profile workspace, found ${dirs.join(', ')}`);
  return path.join(profiles, dirs[0]!);
}
