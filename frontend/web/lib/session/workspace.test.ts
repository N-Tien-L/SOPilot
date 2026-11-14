import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createQueryClient, getQueryClient, resetWorkspaceState, workspaceKey } from '@/lib/query/client';
import type { LoginResponse } from '@/lib/api/types';
import { openStreamCount, trackStream } from '@/lib/sse/registry';
import { useSessionStore } from '@/store/session-store';
import { applySession, devLogin, refreshSession, restoreSession, switchWorkspace } from './auth';
import { getAccessToken, setAccessToken } from './token';

function login(workspaceId: string, token: string): LoginResponse {
  return {
    accessToken: token,
    expiresIn: 900,
    user: { id: 'u1', email: 'a@b.c', displayName: 'A' },
    workspace: { id: workspaceId, name: workspaceId, kind: 'TEAM', role: 'OWNER' },
    pendingInvitations: [],
  };
}

const envelope = (data: unknown) =>
  new Response(JSON.stringify({ data, traceId: 'trace-12345' }), { status: 200, headers: { 'Content-Type': 'application/json' } });

describe('resetWorkspaceState (R7)', () => {
  it('clears cached queries and aborts open streams', async () => {
    const client = createQueryClient();
    client.setQueryData(workspaceKey('w1', 'documents'), [{ id: 'd1' }]);
    const controller = new AbortController();
    trackStream(controller);
    resetWorkspaceState(client);
    expect(client.getQueryData(workspaceKey('w1', 'documents'))).toBeUndefined();
    expect(controller.signal.aborted).toBe(true);
    expect(openStreamCount()).toBe(0);
  });
});

describe('workspace switch and session', () => {
  beforeEach(() => {
    vi.stubGlobal('window', {}); // getQueryClient() is a singleton only in a browser
    setAccessToken(null);
    useSessionStore.getState().clear();
    getQueryClient().clear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it('POSTs switch-workspace with the bearer token, then drops the old workspace data and streams', async () => {
    applySession(login('w1', 'tok-1'));
    getQueryClient().setQueryData(workspaceKey('w1', 'documents'), ['secret-of-w1']);
    const stream = new AbortController();
    trackStream(stream);
    const fetchMock = vi.fn(async () => envelope(login('w2', 'tok-2')));
    vi.stubGlobal('fetch', fetchMock);

    await switchWorkspace('w2');

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/switch-workspace');
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok-1');
    expect(JSON.parse(init.body as string)).toEqual({ workspaceId: 'w2' });
    expect(getQueryClient().getQueryData(workspaceKey('w1', 'documents'))).toBeUndefined();
    expect(stream.signal.aborted).toBe(true);
    expect(getAccessToken()).toBe('tok-2');
    expect(useSessionStore.getState().workspace?.id).toBe('w2');
  });

  it('keeps the cache when the same workspace is re-applied (plain refresh)', () => {
    applySession(login('w1', 'tok-1'));
    getQueryClient().setQueryData(workspaceKey('w1', 'documents'), ['kept']);
    applySession(login('w1', 'tok-2'));
    expect(getQueryClient().getQueryData(workspaceKey('w1', 'documents'))).toEqual(['kept']);
  });

  it('drops the cache when a different user signs in to the same workspace (also from another tab)', () => {
    applySession(login('w1', 'tok-x'));
    getQueryClient().setQueryData(workspaceKey('w1', 'documents'), ['x-only']);
    const other = login('w1', 'tok-y');
    other.user = { id: 'u2', email: 'y@b.c', displayName: 'Y' };
    applySession(other);
    expect(getQueryClient().getQueryData(workspaceKey('w1', 'documents'))).toBeUndefined();
  });

  it('retries once after a 401 using one refresh, and signs out when the refresh fails', async () => {
    applySession(login('w1', 'old'));
    let apiCalls = 0;
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/api/v1/auth/refresh') return envelope(login('w1', 'fresh'));
      apiCalls++;
      return apiCalls === 1
        ? new Response(JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: 'Sign in to continue.' } }), { status: 401 })
        : envelope([]);
    });
    vi.stubGlobal('fetch', fetchMock);
    const { coreRequest } = await import('@/lib/api/http');
    await expect(coreRequest('/documents')).resolves.toEqual([]);
    expect(fetchMock.mock.calls.filter(([u]) => u === '/api/v1/auth/refresh')).toHaveLength(1);
    expect(getAccessToken()).toBe('fresh');

    vi.stubGlobal('fetch', vi.fn(async (url: string) =>
      url === '/api/v1/auth/refresh'
        ? new Response(JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: 'Sign in to continue.' } }), { status: 401 })
        : new Response(JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: 'Sign in to continue.' } }), { status: 401 })));
    await expect(coreRequest('/documents')).rejects.toMatchObject({ status: 401, code: 'UNAUTHENTICATED' });
    expect(getAccessToken()).toBeNull();
    expect(useSessionStore.getState().status).toBe('anonymous');
  });

  it('keeps the session when a refresh fails for a network reason, and ends it when rejected', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    }));
    expect(await restoreSession()).toBe(false);
    expect(useSessionStore.getState().status).toBe('unreachable');

    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: 'UNAUTHENTICATED', message: 'Sign in to continue.' } }), { status: 401 })));
    expect(await restoreSession()).toBe(false);
    expect(useSessionStore.getState().status).toBe('anonymous');
  });

  it('never writes tokens to web storage', async () => {
    const storage = { setItem: vi.fn(), getItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() };
    vi.stubGlobal('localStorage', storage);
    vi.stubGlobal('sessionStorage', storage);
    vi.stubGlobal('fetch', vi.fn(async () => envelope(login('w1', 'secret-token'))));
    await devLogin('a@b.c');
    await refreshSession();
    expect(storage.setItem).not.toHaveBeenCalled();
  });
});
