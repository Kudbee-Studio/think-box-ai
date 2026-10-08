// A bounded `git` call for the dashboard's Git panel (Layer 1: no I/O beyond the child process).
import { execFile } from 'node:child_process';

export function runGit(args: string[], cwd?: string): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd, encoding: 'utf8', timeout: 120000, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) reject(err);
      else resolve({ stdout, stderr });
    });
  });
}
