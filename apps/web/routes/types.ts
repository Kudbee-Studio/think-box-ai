// Shapes the route modules need from the live server objects. Structural on purpose: route modules never import server.ts.
import type { Request as ExpressRequest } from 'express';
import type { WsMessage } from '../types.ts';

/** Express 5 types route params as string | string[]; every route here uses plain named params, which are always strings. */
export type Request = ExpressRequest<Record<string, string>>;

export interface BroadcastingSession {
  broadcast(message: WsMessage): void;
}
