/** Structured Kudbee SDK errors (PR #177 F02 mirror). */

export class KudbeeSdkError extends Error {
  readonly code: string;
  readonly context: Record<string, unknown>;

  constructor(code: string, message: string, context: Record<string, unknown> = {}) {
    super(message);
    this.code = code;
    this.context = context;
    this.name = 'KudbeeSdkError';
  }
}
