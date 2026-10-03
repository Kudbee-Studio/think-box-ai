// Last-resort error handling for the local server. Nothing here replaces a handler's own try/catch; it is the net under them.
//
// Without it: a rejected async route handler reaches Express's default handler, which answers with an HTML page that includes the
// stack trace outside production; a malformed JSON body gets the same page; and a stray unhandled rejection takes the whole server
// (and every live session) down with no useful line in the log.

export interface Logger { error(...args: unknown[]): void }

export function describeError(err: unknown): string {
  if (err instanceof Error) return err.message || err.name;
  if (typeof err === 'string') return err;
  try { return JSON.stringify(err) ?? String(err); } catch { return String(err); }
}

interface HttpishError { status?: unknown; statusCode?: unknown; type?: unknown; expose?: unknown; message?: unknown; stack?: unknown }
export interface ErrReq { method?: string; originalUrl?: string; url?: string }
export interface ErrRes { headersSent?: boolean; status(code: number): { json(body: unknown): unknown } }

/** 4xx statuses set by body-parser and friends are the caller's fault and safe to report; anything else is a 500 with no detail. */
function statusOf(err: HttpishError): number {
  const s = Number(err.status ?? err.statusCode);
  return Number.isInteger(s) && s >= 400 && s < 500 ? s : 500;
}

export function jsonErrorHandler(log: Logger = console) {
  return (err: unknown, req: ErrReq, res: ErrRes, next: (e?: unknown) => void): void => {
    const e = (err ?? {}) as HttpishError;
    const status = statusOf(e);
    const where = `${req.method ?? 'GET'} ${String(req.originalUrl ?? req.url ?? '').split('?')[0]}`; // never log the query string
    log.error(`[http] ${where} -> ${status}: ${describeError(err)}${status === 500 && typeof e.stack === 'string' ? `\n${e.stack}` : ''}`);
    if (res.headersSent) { next(err); return; }
    if (status === 500) { res.status(500).json({ error: 'internal_error' }); return; }
    const error = e.type === 'entity.parse.failed' ? 'invalid_json' : e.type === 'entity.too.large' ? 'payload_too_large' : 'bad_request';
    res.status(status).json({ error, ...(e.expose === true && typeof e.message === 'string' ? { detail: e.message.slice(0, 200) } : {}) });
  };
}

interface ProcessLike {
  on(event: string, listener: (...args: any[]) => void): unknown;
  removeListener(event: string, listener: (...args: any[]) => void): unknown;
  exit(code?: number): never | void;
}

/**
 * A rejected promise nobody awaited is logged and the server keeps serving. An uncaught exception leaves the process in an unknown
 * state, so it is logged (synchronously, before anything else can go wrong) and the process exits non-zero.
 */
export function installProcessHandlers(proc: ProcessLike, log: Logger = console): () => void {
  const onRejection = (reason: unknown) => {
    log.error(`[process] unhandled rejection: ${describeError(reason)}${reason instanceof Error && reason.stack ? `\n${reason.stack}` : ''}`);
  };
  const onException = (err: unknown) => {
    log.error(`[process] uncaught exception, exiting: ${describeError(err)}${err instanceof Error && err.stack ? `\n${err.stack}` : ''}`);
    proc.exit(1);
  };
  proc.on('unhandledRejection', onRejection);
  proc.on('uncaughtException', onException);
  return () => { proc.removeListener('unhandledRejection', onRejection); proc.removeListener('uncaughtException', onException); };
}
