// TanStack Query v5 conventions (M5): one client, keys start with the workspace id so cached data
// of one workspace can never be read under another, and the cache is cleared on workspace switch.

import { QueryClient } from '@tanstack/react-query';
import { clearWarnings } from '@/lib/chat/warning-store';
import { abortAllStreams } from '@/lib/sse/registry';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          const status = (error as { status?: number }).status;
          if (status !== undefined && status >= 400 && status < 500) return false;
          return failureCount < 2;
        },
      },
    },
  });
}

let browserClient: QueryClient | null = null;

/** The shared client in the browser; a fresh one per call on the server. */
export function getQueryClient(): QueryClient {
  if (typeof window === 'undefined') return createQueryClient();
  browserClient ??= createQueryClient();
  return browserClient;
}

/** Query key helper: always scoped by workspace id. */
export function workspaceKey(workspaceId: string, ...parts: readonly unknown[]): readonly unknown[] {
  return ['ws', workspaceId, ...parts];
}

/** R7: forget everything of the previous workspace: open streams, in-flight and cached queries. */
export function resetWorkspaceState(client: QueryClient): void {
  abortAllStreams();
  clearWarnings();
  void client.cancelQueries(); // starts cancelling synchronously
  client.clear();
}
