'use client';

import { useCallback, useRef, useState } from 'react';

/**
 * Runs one async action with a busy flag and the error kept in context (the caller renders it
 * with ErrorNote). A second call while one is running is ignored. Resolves to true on success.
 */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const running = useRef(false);

  const run = useCallback(async (action: () => Promise<unknown>): Promise<boolean> => {
    if (running.current) return false;
    running.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      running.current = false;
      setBusy(false);
    }
  }, []);

  const reset = useCallback(() => setError(null), []);
  return { run, busy, error, reset };
}
