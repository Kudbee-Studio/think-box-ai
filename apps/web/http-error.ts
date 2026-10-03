/** An Error for a failed response: the server's own `error`/`message` when it sent one, else just `HTTP <status>`. */
export async function httpError(res: Response): Promise<Error> {
  let detail = '';
  try {
    const body = (await res.json()) as { error?: unknown; message?: unknown };
    detail = String(body.error ?? body.message ?? '');
  } catch {
    // not a JSON body
  }
  return new Error(detail ? `${detail} (HTTP ${res.status})` : `HTTP ${res.status}`);
}
