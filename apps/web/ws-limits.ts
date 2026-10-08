// Limits on what one WebSocket client can make the server do: how big one message may be, and how many it may send per window.
export const WS_MAX_BYTES = 1_000_000;

/** A per-connection counter: call it once per message; false means "too many, drop this one". */
export function createMessageLimiter(o: { max?: number; windowMs?: number; now?: () => number } = {}): () => boolean {
  const max = o.max ?? 120;
  const windowMs = o.windowMs ?? 10_000;
  const now = o.now ?? Date.now;
  let start = now();
  let count = 0;
  return () => {
    const t = now();
    if (t - start >= windowMs) { start = t; count = 0; }
    return ++count <= max;
  };
}
