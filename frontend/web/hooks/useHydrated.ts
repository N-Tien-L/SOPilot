import { useState, useEffect } from 'react';

/**
 * Hook to track if the client has hydrated.
 * Returns true after the first client-side render.
 * This is useful for preventing hydration mismatches when using
 * client-only values (like localStorage, window, etc.)
 */
export function useHydrated() {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  return hydrated;
}
