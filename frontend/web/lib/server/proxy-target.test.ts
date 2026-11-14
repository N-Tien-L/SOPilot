import { describe, expect, it } from 'vitest';
import { resolveProxyTarget } from './proxy-target';

describe('resolveProxyTarget', () => {
  it('routes /api/v1 to core-api and /ai/v1 to ai-service using the given env', () => {
    const env = { CORE_API_URL: 'http://core:8080/', AI_SERVICE_URL: 'http://ai:8000' };
    expect(resolveProxyTarget('/api/v1/documents', '?limit=5', env)).toBe('http://core:8080/api/v1/documents?limit=5');
    expect(resolveProxyTarget('/ai/v1/conversations/new/messages', '', env)).toBe(
      'http://ai:8000/ai/v1/conversations/new/messages',
    );
  });

  it('follows a different env value on the next call (run-time, not build-time)', () => {
    const a = resolveProxyTarget('/api/v1/x', '', { CORE_API_URL: 'http://a:1' });
    const b = resolveProxyTarget('/api/v1/x', '', { CORE_API_URL: 'http://b:2' });
    expect([a, b]).toEqual(['http://a:1/api/v1/x', 'http://b:2/api/v1/x']);
  });

  it('uses host defaults when the variables are unset or blank', () => {
    expect(resolveProxyTarget('/api/v1/x', '', {})).toBe('http://localhost:8080/api/v1/x');
    expect(resolveProxyTarget('/ai/v1/x', '', { AI_SERVICE_URL: '  ' })).toBe('http://localhost:8000/ai/v1/x');
  });

  it('refuses paths that would leave the proxied prefix after URL normalisation', () => {
    expect(resolveProxyTarget('/ai/v1/../internal/ingestions', '', {})).toBeNull();
    expect(resolveProxyTarget('/api/v1/%2e%2e/internal/x', '', {})).toBeNull();
  });

  it('does not proxy other paths', () => {
    expect(resolveProxyTarget('/login', '', {})).toBeNull();
    expect(resolveProxyTarget('/api/v2/x', '', {})).toBeNull();
  });
});
