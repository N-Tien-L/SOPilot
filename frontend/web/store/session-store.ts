import { create } from 'zustand';
import type { PendingInvitationView, UserView, WorkspaceView } from '@/lib/api/types';

// Memory only: no persist middleware, nothing token-like (the token lives in lib/session/token.ts).
export type SessionStatus = 'unknown' | 'authenticated' | 'anonymous' | 'unreachable';

interface SessionState {
  status: SessionStatus;
  user: UserView | null;
  workspace: WorkspaceView | null;
  pendingInvitations: PendingInvitationView[];
  set: (value: {
    user: UserView;
    workspace: WorkspaceView;
    pendingInvitations: PendingInvitationView[];
  }) => void;
  clear: () => void;
  /** The server could not be reached while restoring; the cookie may still be valid. */
  setUnreachable: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  status: 'unknown',
  user: null,
  workspace: null,
  pendingInvitations: [],
  set: ({ user, workspace, pendingInvitations }) =>
    set({ status: 'authenticated', user, workspace, pendingInvitations }),
  clear: () => set({ status: 'anonymous', user: null, workspace: null, pendingInvitations: [] }),
  setUnreachable: () => set({ status: 'unreachable', user: null, workspace: null, pendingInvitations: [] }),
}));
