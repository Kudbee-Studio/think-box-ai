/** Kudbee SDK config (PR #177 F03 mirror). */

export interface KudbeeSdkConfig {
  baseUrl: string;
  wsPath: string;
  requestTimeoutMs: number;
  maxRetries: number;
  dryRun: boolean;
  correlationHeader: string;
}

export function loadConfigFromEnv(env: Record<string, string | undefined> = process.env): KudbeeSdkConfig {
  const baseUrl = (env.KUDBEE_SDK_BASE_URL ?? 'http://127.0.0.1:3000').replace(/\/$/, '');
  const wsPath = env.KUDBEE_SDK_WS_PATH ?? '/ws';
  const requestTimeoutMs = Number(env.KUDBEE_SDK_TIMEOUT_S ?? '30') * 1000;
  const maxRetries = Number(env.KUDBEE_SDK_MAX_RETRIES ?? '2');
  const dryRun = ['1', 'true', 'yes'].includes((env.KUDBEE_SDK_DRY_RUN ?? '').toLowerCase());
  const correlationHeader = env.KUDBEE_SDK_CORRELATION_HEADER ?? 'x-kudbee-correlation-id';
  if (!baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
    throw new Error('KUDBEE_SDK_BASE_URL must be http(s)');
  }
  if (!wsPath.startsWith('/')) {
    throw new Error('KUDBEE_SDK_WS_PATH must start with /');
  }
  return {
    baseUrl,
    wsPath,
    requestTimeoutMs,
    maxRetries,
    dryRun,
    correlationHeader,
  };
}
