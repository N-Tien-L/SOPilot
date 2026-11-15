// Session lifecycle: dev login, restore from the HttpOnly cookie, refresh, switch workspace,
// sign out. The access token stays in memory (token.ts); the refresh token never reaches JS.

import { isApiError } from '@/lib/api/errors';
import { coreRequest, setAuthHooks } from '@/lib/api/http';
import type { LoginResponse } from '@/lib/api/types';
import { getQueryClient, resetWorkspaceState } from '@/lib/query/client';
import { useSessionStore } from '@/store/session-store';
import { createRefresher, type ChannelLike, type LockManagerLike, type Refresher } from './refresh';
import { setAccessToken } from './token';

const CHANNEL_NAME = 'sopilot-session';

let refresher: Refresher | null = null;

function getRefresher(): Refresher {
  if (refresher) return refresher;
  const locks =
    typeof navigator !== 'undefined' && 'locks' in navigator
      ? (navigator.locks as unknown as LockManagerLike)
      : null;
  const channel: ChannelLike | null =
    typeof BroadcastChannel !== 'undefined' ? (new BroadcastChannel(CHANNEL_NAME) as unknown as ChannelLike) : null;
  refresher = createRefresher({
    callRefresh: () => coreRequest<LoginResponse>('/auth/refresh', { method: 'POST', anonymous: true }),
    locks,
    channel,
    onRemoteSession: (payload) => applySession(payload),
    onRemoteSignedOut: () => endLocalSession(),
  });
  return refresher;
}

/** Stores a session. When the workspace changed, everything cached for the old one is dropped (R7). */
export function applySession(payload: LoginResponse): void {
  const current = useSessionStore.getState();
  const previous = current.workspace?.id ?? null;
  // Synchronously, before the new session is published: queries of the new workspace must not be
  // created first and then wiped. A different user in the same workspace also drops the cache,
  // because what a user may read differs per user.
  const changed = previous !== null && (previous !== payload.workspace.id || current.user?.id !== payload.user.id);
  if (changed) {
    resetWorkspaceState(getQueryClient());
  }
  setAccessToken(payload.accessToken);
  useSessionStore.getState().set({
    user: payload.user,
    workspace: payload.workspace,
    pendingInvitations: payload.pendingInvitations,
  });
}

function endLocalSession(): void {
  setAccessToken(null);
  useSessionStore.getState().clear();
  resetWorkspaceState(getQueryClient());
}

export async function refreshSession(): Promise<void> {
  const payload = await getRefresher().refresh();
  applySession(payload);
}

/** True when the server said the session is gone (as opposed to being unreachable). */
export function isSessionRejected(error: unknown): boolean {
  return isApiError(error) && (error.status === 401 || error.status === 403);
}

/**
 * On page load: try the cookie once. Resolves true when a session was restored. Only a rejection
 * from the server ends the session; a network failure leaves the cookie alone and reports
 * `unreachable` so the user can retry (R1: a refresh must not log the user out by itself).
 */
export async function restoreSession(): Promise<boolean> {
  try {
    await refreshSession();
    return true;
  } catch (error) {
    if (isSessionRejected(error)) endLocalSession();
    else useSessionStore.getState().setUnreachable();
    return false;
  }
}

/** local/test only: core-api returns 404 for this route in any other profile. */
export async function devLogin(email: string, displayName?: string): Promise<void> {
  const payload = await coreRequest<LoginResponse>('/auth/dev-login', {
    method: 'POST',
    anonymous: true,
    body: { email, ...(displayName ? { displayName } : {}) },
  });
  applySession(payload);
  getRefresher().announce(payload);
}

/** Google sign-in: the nonce cookie set by `requestNonce` must still be present (5 minutes). */
export async function requestNonce(): Promise<string> {
  const { nonce } = await coreRequest<{ nonce: string }>('/auth/google/nonce', { method: 'POST', anonymous: true });
  return nonce;
}

export async function googleLogin(idToken: string): Promise<void> {
  const payload = await coreRequest<LoginResponse>('/auth/google', {
    method: 'POST',
    anonymous: true,
    body: { idToken },
  });
  applySession(payload);
  getRefresher().announce(payload);
}

/** After create-workspace or accept-invitation: the response is a login payload for the new workspace. */
export function adoptSession(payload: LoginResponse): void {
  applySession(payload);
  getRefresher().announce(payload);
}

export async function switchWorkspace(workspaceId: string): Promise<void> {
  const payload = await coreRequest<LoginResponse>('/auth/switch-workspace', {
    method: 'POST',
    body: { workspaceId },
  });
  // applySession drops the old workspace's caches and streams because the workspace id changed.
  applySession(payload);
  getRefresher().announce(payload);
}

export async function signOut(): Promise<void> {
  try {
    await coreRequest<void>('/auth/logout', { method: 'POST', anonymous: true });
  } finally {
    endLocalSession();
    getRefresher().announceSignedOut();
  }
}

setAuthHooks({ refresh: refreshSession, onSignedOut: endLocalSession, isSessionRejected });
