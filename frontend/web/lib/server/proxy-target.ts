// Resolves the backend URL for a same-origin request path. Read per request so one build
// follows the run-time CORE_API_URL / AI_SERVICE_URL (ADR-010 §4.3).

export interface ProxyEnv {
  CORE_API_URL?: string;
  AI_SERVICE_URL?: string;
}

export const DEFAULT_CORE_API_URL = 'http://localhost:8080';
export const DEFAULT_AI_SERVICE_URL = 'http://localhost:8000';

const CORE_PREFIX = '/api/v1/';
const AI_PREFIX = '/ai/v1/';

function base(value: string | undefined, fallback: string): string {
  const trimmed = value?.trim();
  return (trimmed ? trimmed : fallback).replace(/\/+$/, '');
}

/** Returns the absolute upstream URL, or null when the path is not proxied. */
export function resolveProxyTarget(
  pathname: string,
  search: string,
  env: ProxyEnv,
): string | null {
  if (pathname.startsWith(CORE_PREFIX)) {
    return confined(`${base(env.CORE_API_URL, DEFAULT_CORE_API_URL)}${pathname}${search}`, CORE_PREFIX);
  }
  if (pathname.startsWith(AI_PREFIX)) {
    return confined(`${base(env.AI_SERVICE_URL, DEFAULT_AI_SERVICE_URL)}${pathname}${search}`, AI_PREFIX);
  }
  return null;
}

/** Defence in depth: URL parsing normalises dot segments, so the upstream path must keep its prefix. */
function confined(target: string, prefix: string): string | null {
  try {
    return new URL(target).pathname.startsWith(prefix) ? target : null;
  } catch {
    return null;
  }
}
