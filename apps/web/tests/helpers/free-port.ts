// A free loopback port chosen by the OS. Tests boot real servers in parallel; picking `20000 + random()` collided with another test's
// server (EADDRINUSE with the health probe answered by the other server) and overlapped the OS's own outbound ports.
import net from 'node:net';
import type { AddressInfo } from 'node:net';

const handedOut = new Set<number>();

export async function freePort(): Promise<number> {
  for (;;) {
    const port = await new Promise<number>((resolve, reject) => {
      const probe = net.createServer();
      probe.once('error', reject);
      probe.listen(0, '127.0.0.1', () => {
        const { port: p } = probe.address() as AddressInfo;
        probe.close(() => resolve(p));
      });
    });
    if (!handedOut.has(port)) { handedOut.add(port); return port; }
  }
}
