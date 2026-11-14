// Single-flight refresh across calls and tabs (frontend-nfrs C5, R1). Rotation is strict: two
// concurrent refreshes with the same cookie count as reuse and revoke the session.
//  1. Same tab: concurrent callers share one promise.
//  2. Several tabs: a Web Lock serialises the refreshes. A tab that waited re-uses the result the
//     previous holder broadcast instead of calling the server again.
//  3. No Web Locks: a best-effort BroadcastChannel claim; a tab that sees a refresh in flight
//     elsewhere waits for its result.
// The broadcast stays in memory between same-origin tabs and is never persisted.

import type { LoginResponse } from '@/lib/api/types';

export interface LockManagerLike {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>;
}

export interface ChannelLike {
  postMessage(message: unknown): void;
  addEventListener(type: 'message', listener: (event: { data: unknown }) => void): void;
  close(): void;
}

export type SessionMessage =
  | { kind: 'refresh-start'; at: number }
  | { kind: 'session'; at: number; payload: LoginResponse }
  | { kind: 'refresh-failed'; at: number }
  | { kind: 'signed-out'; at: number };

export interface RefresherDeps {
  callRefresh: () => Promise<LoginResponse>;
  locks: LockManagerLike | null;
  channel: ChannelLike | null;
  now?: () => number;
  /** Fallback only: how long to wait for another tab's refresh before refreshing here. */
  remoteWaitMs?: number;
  onRemoteSession?: (payload: LoginResponse) => void;
  /** Another tab signed out: end the local session too. */
  onRemoteSignedOut?: () => void;
}

export const REFRESH_LOCK_NAME = 'sopilot-session-refresh';
const DEFAULT_REMOTE_WAIT_MS = 5000;

function isSessionMessage(value: unknown): value is SessionMessage {
  if (typeof value !== 'object' || value === null) return false;
  const kind = (value as { kind?: unknown }).kind;
  return (
    (kind === 'refresh-start' || kind === 'session' || kind === 'refresh-failed' || kind === 'signed-out') &&
    typeof (value as { at?: unknown }).at === 'number'
  );
}

export function createRefresher(deps: RefresherDeps) {
  const now = deps.now ?? Date.now;
  const remoteWaitMs = deps.remoteWaitMs ?? DEFAULT_REMOTE_WAIT_MS;
  let inflight: Promise<LoginResponse> | null = null;
  let latest: LoginResponse | null = null;
  let received = 0; // bumps whenever a fresh session arrives, from this tab or another
  let remoteStartedAt: number | null = null;
  const remoteWaiters = new Set<(payload: LoginResponse | null) => void>();

  deps.channel?.addEventListener('message', (event) => {
    const message = event.data;
    if (!isSessionMessage(message)) return;
    if (message.kind === 'session') {
      latest = message.payload;
      received++;
      remoteStartedAt = null;
      deps.onRemoteSession?.(message.payload);
      remoteWaiters.forEach((resolve) => resolve(message.payload));
      remoteWaiters.clear();
    } else if (message.kind === 'refresh-start') {
      remoteStartedAt = message.at;
    } else if (message.kind === 'signed-out') {
      latest = null;
      deps.onRemoteSignedOut?.();
    } else {
      remoteStartedAt = null;
      remoteWaiters.forEach((resolve) => resolve(null));
      remoteWaiters.clear();
    }
  });

  async function refreshOnce(seen: number): Promise<LoginResponse> {
    // A session arrived while this call waited for the lock: use it instead of rotating again.
    if (latest && received > seen) return latest;
    deps.channel?.postMessage({ kind: 'refresh-start', at: now() } satisfies SessionMessage);
    try {
      const payload = await deps.callRefresh();
      latest = payload;
      received++;
      deps.channel?.postMessage({ kind: 'session', at: now(), payload } satisfies SessionMessage);
      return payload;
    } catch (error) {
      deps.channel?.postMessage({ kind: 'refresh-failed', at: now() } satisfies SessionMessage);
      throw error;
    }
  }

  function waitForRemote(): Promise<LoginResponse | null> {
    return new Promise((resolve) => {
      const finish = (payload: LoginResponse | null) => {
        clearTimeout(timer);
        remoteWaiters.delete(finish);
        resolve(payload);
      };
      const timer = setTimeout(() => finish(null), remoteWaitMs);
      remoteWaiters.add(finish);
    });
  }

  async function run(): Promise<LoginResponse> {
    const startedAt = now();
    const seen = received;
    if (deps.locks) {
      return deps.locks.request(REFRESH_LOCK_NAME, async () => {
        // The holder's broadcast is asynchronous; give it a moment to land if we had to wait.
        if (now() - startedAt > 5) await new Promise((resolve) => setTimeout(resolve, 25));
        return refreshOnce(seen);
      });
    }
    if (remoteStartedAt !== null && startedAt - remoteStartedAt < remoteWaitMs) {
      const remote = await waitForRemote();
      if (remote) return remote;
    }
    return refreshOnce(seen);
  }

  return {
    refresh(): Promise<LoginResponse> {
      if (!inflight) {
        inflight = run().finally(() => {
          inflight = null;
        });
      }
      return inflight;
    },
    /** Tells other tabs about a session this tab obtained another way (e.g. a workspace switch). */
    announce(payload: LoginResponse): void {
      latest = payload;
      received++;
      deps.channel?.postMessage({ kind: 'session', at: now(), payload } satisfies SessionMessage);
    },
    /** Tells other tabs this tab signed out. */
    announceSignedOut(): void {
      latest = null;
      deps.channel?.postMessage({ kind: 'signed-out', at: now() } satisfies SessionMessage);
    },
    close(): void {
      deps.channel?.close();
    },
  };
}

export type Refresher = ReturnType<typeof createRefresher>;
