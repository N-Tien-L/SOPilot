import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark';
export type Language = 'vi' | 'en';

interface PreferencesState {
  theme: Theme;
  language: Language;
  _hasHydrated: boolean;

  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
  setLanguage: (language: Language) => void;
  setHasHydrated: (state: boolean) => void;
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set, get) => ({
      theme: 'light',
      language: 'vi',
      _hasHydrated: false,

      setTheme: (theme) => set({ theme }),

      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'light' ? 'dark' : 'light',
        })),

      setLanguage: (language) => set({ language }),

      setHasHydrated: (state) => set({ _hasHydrated: state }),
    }),
    {
      name: 'preferences-storage',
      partialize: (state) => ({
        theme: state.theme,
        language: state.language,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
