// Outbound HTTP from operator plugins (http_request, rss_feed) runs on this machine, so a URL can reach
// services that trust loopback or the LAN: Ollama, the governed backend, a router admin page. Private
// targets need explicit human approval (server.ts operatorApprovalReason), and redirects are followed
// hop by hop so a public URL cannot bounce into one.
import dns from 'node:dns/promises';
import net from 'node:net';

export function isPrivateAddress(ip: string): boolean {
  let a = ip.toLowerCase();
  if (a.startsWith('::ffff:')) a = a.slice(7);
  if (net.isIPv4(a)) {
    const [x, y] = a.split('.').map(Number);
    return x === 127 || x === 10 || x === 0 || (x === 172 && y >= 16 && y <= 31) || (x === 192 && y === 168)
      || (x === 169 && y === 254) || (x === 100 && y >= 64 && y <= 127);
  }
  if (net.isIPv6(a)) return a === '::1' || a === '::' || /^f[cd]/.test(a) || /^fe[89ab]/.test(a);
  return false;
}

export async function targetsPrivateNetwork(rawUrl: string): Promise<boolean> {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return false; // not a URL: the fetch itself fails
  }
  const host = url.hostname.replace(/^\[|\]$/g, '');
  if (net.isIP(host)) return isPrivateAddress(host);
  if (host === 'localhost' || host.endsWith('.localhost')) return true;
  try {
    return (await dns.lookup(host, { all: true })).some((entry) => isPrivateAddress(entry.address));
  } catch {
    return false;
  }
}

export async function fetchChecked(
  rawUrl: string,
  init: RequestInit,
  allowPrivate: boolean,
  isPrivateUrl: (url: string) => Promise<boolean> = targetsPrivateNetwork,
): Promise<Response> {
  let url = rawUrl;
  for (let hop = 0; hop < 5; hop++) {
    if (!allowPrivate && await isPrivateUrl(url)) {
      throw new Error('Refused: the URL resolves to a local or private network address (needs approval)');
    }
    const response = await fetch(url, { ...init, redirect: 'manual' });
    const location = response.headers.get('location');
    if (response.status >= 300 && response.status < 400 && location) {
      url = new URL(location, url).toString();
      continue;
    }
    return response;
  }
  throw new Error('Too many redirects');
}

/**
 * `fetch_url` for the agent: the human approved the first host, so the first request goes out as is; every redirect hop is followed by hand and a hop to a host
 * that is not approved yet asks the human first (naming both hosts, and saying so when the new host is a local or private address). Denied means the new
 * host is never contacted. Only http(s) hops are followed, at most 5.
 */
export async function fetchApprovingRedirects(
  rawUrl: string,
  init: RequestInit,
  gate: { approved: Set<string>; ask: (url: string, reason: string) => Promise<boolean> },
  isPrivateUrl: (url: string) => Promise<boolean> = targetsPrivateNetwork,
): Promise<Response> {
  let url = rawUrl;
  for (let hop = 0; hop < 5; hop++) {
    const response = await fetch(url, { ...init, redirect: 'manual' });
    const location = response.headers.get('location');
    if (!(response.status >= 300 && response.status < 400 && location)) return response;
    const next = new URL(location, url);
    if (!['http:', 'https:'].includes(next.protocol)) throw new Error('Only http(s) URLs are allowed (a redirect pointed somewhere else)');
    const from = new URL(url).hostname;
    if (next.hostname !== from && !gate.approved.has(next.hostname)) {
      const where = (await isPrivateUrl(next.toString())) ? ' (a local or private network address)' : '';
      if (!(await gate.ask(next.toString(), `Redirected from ${from} to ${next.hostname}${where}`))) throw new Error(`Denied by human reviewer (redirect to ${next.hostname})`);
      gate.approved.add(next.hostname);
    }
    url = next.toString();
  }
  throw new Error('Too many redirects');
}
