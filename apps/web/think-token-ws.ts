// Validation for the Think Token WebSocket actions (ADR 028). Pure, so the size and shape limits are unit-tested.
// Unknown keys are rejected, every string is length-capped, and nothing here can carry a permission or tool grant.
import { LIMITS, TOKEN_STATUSES, type TokenStatus } from './think-token-store.ts';

export const TOKEN_ID_PATTERN = /^tt_[a-f0-9]{16}$/;
export const TOKEN_ACTIONS = ['accept', 'retire', 'thumb_up', 'thumb_down'] as const;
export type TokenAction = (typeof TOKEN_ACTIONS)[number];
export const MAX_WS_FIELD_CHARS = 4096;

export type TokenWsRequest =
  | { type: 'think_tokens_list'; query?: string; status?: TokenStatus; limit: number }
  | { type: 'think_token_action'; action: TokenAction; id: string };

function onlyKeys(msg: Record<string, unknown>, allowed: string[]): string | null {
  const extra = Object.keys(msg).filter((k) => !allowed.includes(k));
  return extra.length ? `unexpected field(s): ${extra.slice(0, 5).join(', ').slice(0, 80)}` : null;
}

export function validateTokenMessage(msg: unknown): { ok: true; req: TokenWsRequest } | { ok: false; error: string } {
  if (!msg || typeof msg !== 'object' || Array.isArray(msg)) return { ok: false, error: 'message must be an object' };
  const m = msg as Record<string, unknown>;
  if (m.type === 'think_tokens_list') {
    const bad = onlyKeys(m, ['type', 'query', 'status', 'limit']);
    if (bad) return { ok: false, error: bad };
    let query: string | undefined;
    if (m.query !== undefined) {
      if (typeof m.query !== 'string' || m.query.length > LIMITS.query) return { ok: false, error: `query must be a string up to ${LIMITS.query} chars` };
      query = m.query;
    }
    let status: TokenStatus | undefined;
    if (m.status !== undefined) {
      if (typeof m.status !== 'string' || !(TOKEN_STATUSES as readonly string[]).includes(m.status)) return { ok: false, error: 'invalid status' };
      status = m.status as TokenStatus;
    }
    let limit = 50;
    if (m.limit !== undefined) {
      if (typeof m.limit !== 'number' || !Number.isInteger(m.limit) || m.limit < 1 || m.limit > LIMITS.list) return { ok: false, error: `limit must be an integer 1..${LIMITS.list}` };
      limit = m.limit;
    }
    return { ok: true, req: { type: 'think_tokens_list', query, status, limit } };
  }
  if (m.type === 'think_token_action') {
    const bad = onlyKeys(m, ['type', 'action', 'id']);
    if (bad) return { ok: false, error: bad };
    if (typeof m.action !== 'string' || !(TOKEN_ACTIONS as readonly string[]).includes(m.action)) return { ok: false, error: 'invalid action' };
    if (typeof m.id !== 'string' || !TOKEN_ID_PATTERN.test(m.id)) return { ok: false, error: 'invalid token id' };
    return { ok: true, req: { type: 'think_token_action', action: m.action as TokenAction, id: m.id } };
  }
  return { ok: false, error: 'unknown think token message' };
}
