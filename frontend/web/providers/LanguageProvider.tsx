'use client';

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import { usePreferencesStore } from '@/store/preferences-store';
import { t, interpolate, type TranslationKey } from '@/lib/i18n';

interface LanguageContextValue {
  language: 'vi' | 'en';
  setLanguage: (lang: 'vi' | 'en') => void;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
  isReady: boolean;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const storeLanguage = usePreferencesStore((s) => s.language);
  const storeSetLanguage = usePreferencesStore((s) => s.setLanguage);
  const hasHydrated = usePreferencesStore((s) => s._hasHydrated);

  // Read localStorage synchronously on first render so client initial state
  // matches what will be hydrated from the store. This prevents React #418
  // hydration mismatch between SSR (language='vi') and client (language='en').
  const [language, setLanguageState] = useState<'vi' | 'en'>(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('preferences-storage');
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed.state?.language === 'en' || parsed.state?.language === 'vi') {
            return parsed.state.language;
          }
        }
      } catch { /* ignore */ }
    }
    return 'vi';
  });

  // After the store rehydrates from localStorage, reconcile if the stored value
  // differs from our initial guess (e.g. store was empty → default 'vi' was right;
  // or store had 'en' but we guessed 'vi' from the same storage).
  useEffect(() => {
    if (hasHydrated && storeLanguage !== language) {
      setLanguageState(storeLanguage);
    }
  }, [hasHydrated, storeLanguage, language]);

  const setLanguage = useCallback(
    (lang: 'vi' | 'en') => {
      setLanguageState(lang);
      storeSetLanguage(lang);
    },
    [storeSetLanguage]
  );

  const translate = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>): string => {
      const text = t(key, language);
      return params ? interpolate(text, params) : text;
    },
    [language]
  );

  return (
    <LanguageContext.Provider
      value={{
        language,
        setLanguage,
        t: translate,
        isReady: hasHydrated,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error('useLanguage must be used inside LanguageProvider');
  }
  return ctx;
}
