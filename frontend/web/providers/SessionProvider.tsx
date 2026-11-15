'use client';

import { useEffect } from 'react';
import { restoreSession } from '@/lib/session/auth';
import { useSessionStore } from '@/store/session-store';

/** Restores the session from the HttpOnly cookie once per page load. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (useSessionStore.getState().status === 'unknown') {
      void restoreSession();
    }
  }, []);
  return <>{children}</>;
}
