import { describe, expect, it, vi } from 'vitest';
import type { LoginResponse } from '@/lib/api/types';
import { createRefresher, type ChannelLike, type LockManagerLike } from './refresh';

function payload(token: string): LoginResponse {
  return {
    accessToken: token,
    expiresIn: 900,
    user: { id: 'u1', email: 'a@b.c', displayName: 'A' },
    workspace: { id: 'w1', name: 'W', kind: 'TEAM', role: 'MEMBER' },
    pendingInvitations: [],
  };
}

/** Same semantics as navigator.locks for one name: callbacks run one at a time, in order. */
function fakeLocks(): LockManagerLike {
  let tail: Promise<unknown> = Promise.resolve();
  return {
    request<T>(_name: string, callback: () => Promise<T>): Promise<T> {
      const run = tail.then(callback, callback);
      tail = run.catch(() => undefined);
      return run;
    },
  };
}

/** Delivers messages to every other endpoint on the bus, asynchronously like BroadcastChannel. */
function fakeBus() {
  const endpoints: { listeners: ((e: { data: unknown }) => void)[] }[] = [];
  return {
    create(): ChannelLike {
      const self = { listeners: [] as ((e: { data: unknown }) => void)[] };
      endpoints.push(self);
      return {
        postMessage(message: unknown) {
          const copy = structuredClone(message);
          for (const other of endpoints) {
            if (other === self) continue;
            queueMicrotask(() => other.listeners.forEach((l) => l({ data: copy })));
          }
        },
        addEventListener(_type, listener) {
          self.listeners.push(listener);
        },
        close() {},
      };
    },
  };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('refresh single-flight', () => {
  it('merges concurrent callers in one tab into one request', async () => {
    const callRefresh = vi.fn(async () => payload('t1'));
    const refresher = createRefresher({ callRefresh, locks: fakeLocks(), channel: null });
    const results = await Promise.all([refresher.refresh(), refresher.refresh(), refresher.refresh()]);
    expect(callRefresh).toHaveBeenCalledTimes(1);
    expect(results.every((r) => r.accessToken === 't1')).toBe(true);
  });

  it('allows a new refresh after the previous one finished', async () => {
    let n = 0;
    const callRefresh = vi.fn(async () => payload(`t${++n}`));
    const refresher = createRefresher({ callRefresh, locks: null, channel: null });
    await refresher.refresh();
    const second = await refresher.refresh();
    expect(callRefresh).toHaveBeenCalledTimes(2);
    expect(second.accessToken).toBe('t2');
  });

  it('merges refreshes from several tabs into one request (Web Locks)', async () => {
    const locks = fakeLocks(); // one lock manager per origin
    const bus = fakeBus();
    let n = 0;
    const callRefresh = vi.fn(async () => {
      await tick();
      return payload(`t${++n}`);
    });
    const tabs = [1, 2, 3].map(() =>
      createRefresher({ callRefresh, locks, channel: bus.create() }),
    );
    const results = await Promise.all(tabs.map((tab) => tab.refresh()));
    expect(callRefresh).toHaveBeenCalledTimes(1);
    expect(results.map((r) => r.accessToken)).toEqual(['t1', 't1', 't1']);
  });

  it('merges refreshes from several tabs without Web Locks (BroadcastChannel fallback)', async () => {
    const bus = fakeBus();
    let n = 0;
    const callRefresh = vi.fn(async () => {
      await tick();
      return payload(`t${++n}`);
    });
    const a = createRefresher({ callRefresh, locks: null, channel: bus.create() });
    const b = createRefresher({ callRefresh, locks: null, channel: bus.create() });
    const first = a.refresh();
    await Promise.resolve();
    await Promise.resolve(); // let tab B see tab A's claim
    const second = b.refresh();
    const results = await Promise.all([first, second]);
    expect(callRefresh).toHaveBeenCalledTimes(1);
    expect(results.map((r) => r.accessToken)).toEqual(['t1', 't1']);
  });

  it('propagates a failure to every waiting caller and recovers afterwards', async () => {
    let fail = true;
    const callRefresh = vi.fn(async () => {
      if (fail) throw new Error('401');
      return payload('ok');
    });
    const refresher = createRefresher({ callRefresh, locks: fakeLocks(), channel: null });
    const settled = await Promise.allSettled([refresher.refresh(), refresher.refresh()]);
    expect(settled.every((s) => s.status === 'rejected')).toBe(true);
    expect(callRefresh).toHaveBeenCalledTimes(1);
    fail = false;
    await expect(refresher.refresh()).resolves.toMatchObject({ accessToken: 'ok' });
  });

  it('tells other tabs about a sign-out', async () => {
    const bus = fakeBus();
    const signedOut = vi.fn();
    createRefresher({ callRefresh: async () => payload('x'), locks: null, channel: bus.create(), onRemoteSignedOut: signedOut });
    const other = createRefresher({ callRefresh: async () => payload('x'), locks: null, channel: bus.create() });
    other.announceSignedOut();
    await tick();
    expect(signedOut).toHaveBeenCalledTimes(1);
  });

  it('reports a session announced by another tab', async () => {
    const bus = fakeBus();
    const seen: string[] = [];
    createRefresher({
      callRefresh: async () => payload('x'),
      locks: null,
      channel: bus.create(),
      onRemoteSession: (p) => seen.push(p.accessToken),
    });
    const other = createRefresher({ callRefresh: async () => payload('x'), locks: null, channel: bus.create() });
    other.announce(payload('switched'));
    await tick();
    expect(seen).toEqual(['switched']);
  });
});
