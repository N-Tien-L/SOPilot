// The only place that calls fetch. Relative base URLs keep every request on the page's origin,
// so it goes through proxy.ts (C4, C13). Two adapters cover the two backends' conventions (C2).

import { getAccessToken } from '@/lib/session/token';
import { networkError, parseAiError, parseCoreError, ApiError } from './errors';
import type { CorePage, PageInfo } from './types';

export const CORE_BASE = '/api/v1';
export const AI_BASE = '/ai/v1';

export interface AuthHooks {
  /** Refreshes the session (single-flight); rejects when the session cannot be restored. */
  refresh: () => Promise<void>;
  /** Called when the server rejected the refresh: the session is gone. */
  onSignedOut: () => void;
  /** Tells a rejection (sign out) from a transient failure such as a network error (keep the session). */
  isSessionRejected: (error: unknown) => boolean;
}

let authHooks: AuthHooks | null = null;

export function setAuthHooks(hooks: AuthHooks | null): void {
  authHooks = hooks;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /** Plain objects are sent as JSON; FormData is sent as multipart. */
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
  /** Skip the Bearer header and the refresh-on-401 retry (login, refresh, logout). */
  anonymous?: boolean;
  headers?: Record<string, string>;
}

function buildUrl(base: string, path: string, query?: RequestOptions['query']): string {
  const url = `${base}${path.startsWith('/') ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

function buildInit(options: RequestOptions, token: string | null): RequestInit {
  const headers = new Headers(options.headers);
  if (token && !options.anonymous) headers.set('Authorization', `Bearer ${token}`);
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.body);
  }
  return { method: options.method ?? 'GET', headers, body, signal: options.signal, credentials: 'same-origin' };
}

/** fetch with the access token attached and one refresh-and-retry on 401. */
export async function authorizedFetch(
  base: string,
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const url = buildUrl(base, path, options.query);
  const send = async (): Promise<Response> => {
    try {
      return await fetch(url, buildInit(options, getAccessToken()));
    } catch (error) {
      if (options.signal?.aborted) throw error;
      throw networkError();
    }
  };
  const first = await send();
  if (first.status !== 401 || options.anonymous || !authHooks) return first;
  try {
    await authHooks.refresh();
  } catch (error) {
    if (!authHooks.isSessionRejected(error)) throw error;
    authHooks.onSignedOut();
    return first;
  }
  return send();
}

async function readJson(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** core-api: unwraps `{ data, traceId }`; errors follow `{ error: { code, message, details } }`. */
export async function coreRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await authorizedFetch(CORE_BASE, path, options);
  const body = await readJson(response);
  if (!response.ok) throw parseCoreError(response.status, body, response.headers.get('X-Trace-Id'));
  if (body === undefined) return undefined as T;
  return (isRecord(body) && 'data' in body ? body.data : body) as T;
}

/** core-api list endpoints: `{ data: [...], page: { cursor, hasMore } }`. */
export async function coreRequestPage<T>(
  path: string,
  options: RequestOptions = {},
): Promise<CorePage<T>> {
  const response = await authorizedFetch(CORE_BASE, path, options);
  const body = await readJson(response);
  if (!response.ok) throw parseCoreError(response.status, body, response.headers.get('X-Trace-Id'));
  const root = isRecord(body) ? body : {};
  const page = isRecord(root.page) ? (root.page as unknown as PageInfo) : { cursor: null, hasMore: false };
  return { data: Array.isArray(root.data) ? (root.data as T[]) : [], page };
}

/** ai-service: plain JSON; errors are `{ detail }`. */
export async function aiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await authorizedFetch(AI_BASE, path, options);
  const body = await readJson(response);
  if (!response.ok) throw parseAiError(response.status, body);
  return body as T;
}

export { ApiError };
