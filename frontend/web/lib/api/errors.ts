// Error adapters for the two backends (frontend-nfrs C2, S4, O2).
// Users only ever see the API's fixed sentence or a local fixed string, never a raw exception.

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly traceId: string | null;
  readonly details: unknown;

  constructor(
    status: number,
    message: string,
    code: string | null = null,
    traceId: string | null = null,
    details: unknown = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.traceId = traceId;
    this.details = details;
  }
}

export const NETWORK_ERROR_MESSAGE = 'The server could not be reached. Check your connection and try again.';
const GENERIC_MESSAGE = 'Something went wrong. Please try again.';
const MAX_MESSAGE_LENGTH = 300;

const STATUS_MESSAGES: Record<number, string> = {
  400: 'The request was not valid.',
  401: 'Sign in to continue.',
  403: 'You do not have permission to do this.',
  404: 'Not found.',
  409: 'This action conflicts with the current state.',
  413: 'The file is too large.',
  415: 'This file type is not supported.',
  422: 'The request was not valid.',
  429: 'Too many requests. Try again shortly.',
  503: 'This service is not available right now.',
};

export function fallbackMessage(status: number): string {
  return STATUS_MESSAGES[status] ?? GENERIC_MESSAGE;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function fixedText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed.length > 0 && trimmed.length <= MAX_MESSAGE_LENGTH ? trimmed : null;
}

/** core-api: `{ error: { code, message, details }, traceId }`. */
export function parseCoreError(status: number, body: unknown, headerTraceId?: string | null): ApiError {
  const root = isRecord(body) ? body : {};
  const error = isRecord(root.error) ? root.error : {};
  const traceId = fixedText(root.traceId) ?? fixedText(headerTraceId);
  return new ApiError(
    status,
    fixedText(error.message) ?? fallbackMessage(status),
    fixedText(error.code),
    traceId,
    error.details ?? null,
  );
}

/** ai-service: FastAPI `{ detail }` (a fixed sentence, or a validation list that is not shown). */
export function parseAiError(status: number, body: unknown): ApiError {
  const detail = isRecord(body) ? body.detail : undefined;
  return new ApiError(status, fixedText(detail) ?? fallbackMessage(status));
}

export function networkError(): ApiError {
  return new ApiError(0, NETWORK_ERROR_MESSAGE, 'NETWORK_ERROR');
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/** What an error screen shows: the fixed message and, when present, the trace id (O2). */
export function describeError(error: unknown): { message: string; traceId: string | null } {
  if (isApiError(error)) return { message: error.message, traceId: error.traceId };
  return { message: GENERIC_MESSAGE, traceId: null };
}
