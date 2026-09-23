'use client';

import { useEffect } from 'react';
import { usePreferencesStore } from '@/store/preferences-store';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = usePreferencesStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  return <>{children}</>;
}
