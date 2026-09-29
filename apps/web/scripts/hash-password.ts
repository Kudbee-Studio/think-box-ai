// Prints a scrypt hash for KUDBEE_DASHBOARD_PASSWORD_HASH. Reads the password from stdin so it never
// appears in shell history or process arguments:  printf '%s' "$PW" | node --experimental-strip-types scripts/hash-password.ts
import { hashPassword } from '../auth.ts';

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => (input += c));
process.stdin.on('end', () => {
  const pw = input.replace(/\r?\n$/, '');
  if (pw.length < 12) {
    console.error('password must be at least 12 characters');
    process.exit(1);
  }
  console.log(hashPassword(pw));
});
