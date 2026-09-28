/**
 * Real model execution for swarm agents — a single-shot chat completion,
 * no tool use.
 *
 * This is deliberately NOT the full runToolAgent loop in apps/web/agent.ts.
 * That loop needs AgentHooks (workspace, approval gates, memory, RSS) that
 * live in the server-side session runtime (apps/web/server.ts) — the swarm
 * is a CLI-side, in-process construct with no access to any of that. Giving
 * swarm agents real tools (write_file, fetch_url, ...) is a separate,
 * larger follow-up: it needs a concurrency-safe approval flow and a real
 * per-agent workspace, not just a model call. See "Not done" in
 * docs/MULTI_AGENT_SWARM_ARCHITECTURE.md.
 *
 * Fails closed: no API key, no reachable Ollama, a non-2xx response, or an
 * empty completion all surface as a thrown ModelCallError. Nothing here
 * fabricates a response or a cost (AGENTS.md §4.4, mirroring the existing
 * ModelCallError pattern in thinkbox/model_client.py and apps/web/agent.ts's
 * own inceptionConfigured() gate).
 */

import { costUsd, inceptionConfigured, isInceptionModel } from "../agent.ts";

const INCEPTION_BASE_URL = process.env.INCEPTION_BASE_URL || "https://api.inceptionlabs.ai/v1";
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
const REQUEST_TIMEOUT_MS = 90_000;

export class ModelCallError extends Error {
  readonly model: string;

  constructor(message: string, model: string) {
    super(message);
    this.name = "ModelCallError";
    this.model = model;
  }
}

export interface ModelCallResult {
  content: string;
  model: string;
  promptTokens: number;
  completionTokens: number;
  costUsd: number;
  latencyMs: number;
}

function withTimeout(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

async function callMercury2(
  model: string,
  goal: string,
  systemPrompt: string,
  signal?: AbortSignal
): Promise<ModelCallResult> {
  if (!inceptionConfigured()) {
    throw new ModelCallError("INCEPTION_API_KEY is not set — cannot call " + model, model);
  }

  const started = Date.now();
  let response: Response;
  try {
    response = await fetch(`${INCEPTION_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.INCEPTION_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: goal },
        ],
        temperature: 0.3,
        max_tokens: 4000,
      }),
      signal: withTimeout(signal),
    });
  } catch (err) {
    throw new ModelCallError(
      `${model} request failed: ${err instanceof Error ? err.message : String(err)}`,
      model
    );
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new ModelCallError(`Inception API HTTP ${response.status}: ${body.slice(0, 300)}`, model);
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string | null } }>;
    usage?: { prompt_tokens?: number; completion_tokens?: number };
  };
  const content = data.choices?.[0]?.message?.content?.trim();
  if (!content) {
    throw new ModelCallError(`${model} returned no content`, model);
  }

  const promptTokens = data.usage?.prompt_tokens ?? 0;
  const completionTokens = data.usage?.completion_tokens ?? 0;

  return {
    content,
    model,
    promptTokens,
    completionTokens,
    costUsd: costUsd(model, promptTokens, completionTokens),
    latencyMs: Date.now() - started,
  };
}

async function callLocalModel(
  model: string,
  goal: string,
  systemPrompt: string,
  signal?: AbortSignal
): Promise<ModelCallResult> {
  const started = Date.now();
  let response: Response;
  try {
    response = await fetch(`${OLLAMA_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: goal },
        ],
        stream: false,
      }),
      signal: withTimeout(signal),
    });
  } catch (err) {
    throw new ModelCallError(
      `local model '${model}' unreachable at ${OLLAMA_BASE_URL} (is Ollama running and pulled? ollama pull ${model}) — ${err instanceof Error ? err.message : String(err)}`,
      model
    );
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new ModelCallError(`Ollama HTTP ${response.status}: ${body.slice(0, 300)}`, model);
  }

  const data = (await response.json()) as {
    message?: { content?: string };
    prompt_eval_count?: number;
    eval_count?: number;
  };
  const content = data.message?.content?.trim();
  if (!content) {
    throw new ModelCallError(`local model '${model}' returned no content`, model);
  }

  return {
    content,
    model,
    promptTokens: data.prompt_eval_count ?? 0,
    completionTokens: data.eval_count ?? 0,
    costUsd: 0, // local inference has no per-token API cost
    latencyMs: Date.now() - started,
  };
}

/**
 * Dispatch to whichever backend the routed model name actually belongs to.
 * Uses isInceptionModel() (apps/web/agent.ts) rather than a hardcoded
 * "mercury-2" string, so adding a model to INCEPTION_MODELS there is
 * picked up here automatically.
 */
export async function callModel(
  model: string,
  goal: string,
  systemPrompt: string,
  signal?: AbortSignal
): Promise<ModelCallResult> {
  return isInceptionModel(model)
    ? callMercury2(model, goal, systemPrompt, signal)
    : callLocalModel(model, goal, systemPrompt, signal);
}
