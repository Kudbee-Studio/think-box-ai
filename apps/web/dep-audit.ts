// Known-vulnerable dependencies: reads `npm audit --json`. High and critical fail the gate; low and moderate are reported, not blocking.
// With no report (offline, registry error) the answer is "not run", never "pass".
export interface AuditCounts { low: number; moderate: number; high: number; critical: number }

export function parseAudit(json: string): AuditCounts | null {
  let v: any;
  try { v = JSON.parse(json); } catch { return null; }
  const c = v?.metadata?.vulnerabilities;
  if (!c || typeof c !== 'object') return null;
  const n = (x: unknown): number => (typeof x === 'number' && x >= 0 ? x : 0);
  return { low: n(c.low), moderate: n(c.moderate), high: n(c.high), critical: n(c.critical) };
}

export function auditVerdict(c: AuditCounts | null): { status: 'pass' | 'fail' | 'not_run'; detail: string } {
  if (!c) return { status: 'not_run', detail: 'no audit report (offline or registry error)' };
  const detail = `${c.critical} critical, ${c.high} high, ${c.moderate} moderate, ${c.low} low`;
  return { status: c.high + c.critical > 0 ? 'fail' : 'pass', detail };
}
