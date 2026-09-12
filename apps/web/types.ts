/** Shared types for the Think Box AI web runtime. */

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export interface PluginResult {
  success: boolean;
  error?: string;
  [key: string]: unknown;
}

/** Plugin inputs are open-ended JSON from tool callers. */
export type PluginInput = Record<string, any>;

export interface PluginConfig {
  name: string;
  type: 'tool';
  permission: 'read_only' | 'read_write' | 'network' | 'exec';
  description: string;
  icon: string;
  execute: (input: PluginInput) => Promise<PluginResult>;
}

export interface Plugin extends PluginConfig {
  enabled: boolean;
  callCount: number;
}

export interface AgentSessionConfig {
  model: string;
  provider: string;
  maxIterations: number;
  temperature: number;
}

export interface SessionConfigInput {
  model?: string;
  provider?: string;
  maxIterations?: number;
  temperature?: number;
}

export interface Thought {
  id: string;
  timestamp: number;
  type: string;
  status?: string;
  [key: string]: unknown;
}

export interface Task {
  id: string;
  timestamp: number;
  status: string;
  description?: string;
  result?: string;
  error?: string;
  [key: string]: unknown;
}

export interface MemoryEntry {
  timestamp: number;
  type: string;
  [key: string]: unknown;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface OllamaTokenMessage {
  message?: { content?: string };
  done?: boolean;
  error?: string;
}

export interface WsMessage {
  type: string;
  [key: string]: unknown;
}

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
