import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { type User, UserRole } from '@/types';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  _hasHydrated: boolean;

  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setLoading: (isLoading: boolean) => void;
  logout: () => void;
  updateUser: (updates: Partial<User>) => void;
  setHasHydrated: (state: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,
      _hasHydrated: false,

      setUser: (user) =>
        set((state) => ({ 
          user, 
          isAuthenticated: !!user || !!state.accessToken 
        })),

      setTokens: (accessToken, refreshToken) => {
        if (typeof window !== 'undefined') {
          localStorage.setItem('accessToken', accessToken);
          localStorage.setItem('refreshToken', refreshToken);
        }
        set((state) => ({ 
          accessToken, 
          refreshToken, 
          isAuthenticated: true,
          user: state.user // Preserve existing user
        }));
      },

      setLoading: (isLoading) => set({ isLoading }),

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('accessToken');
          localStorage.removeItem('refreshToken');
          localStorage.removeItem('user');
          localStorage.removeItem('userId');
          localStorage.removeItem('userRole');
        }
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      updateUser: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),

      setHasHydrated: (state) => set({ _hasHydrated: state }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

// Helper hooks
export const useUser = () => useAuthStore((state) => state.user);
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);
export const useUserRole = (): UserRole | null => useAuthStore((state) => state.user?.role || null);
export const useIsAdmin = () => {
  const user = useAuthStore((state) => state.user);
  const isHydrated = useAuthStore((state) => state._hasHydrated);

  let adminStatus = user?.role === UserRole.ADMIN;

  if (!isHydrated && typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('auth-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        const storedUser = parsed.state?.user;
        adminStatus = storedUser?.role === UserRole.ADMIN;
      }
    } catch {
      // ignore parse errors
    }
  }

  return adminStatus;
};
export const useIsManager = () => {
  const user = useAuthStore((state) => state.user);
  const isHydrated = useAuthStore((state) => state._hasHydrated);

  let managerStatus = user?.role === UserRole.ADMIN || user?.role === UserRole.MANAGER;

  if (!isHydrated && typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('auth-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        const storedUser = parsed.state?.user;
        managerStatus = storedUser?.role === UserRole.ADMIN || storedUser?.role === UserRole.MANAGER;
      }
    } catch {
      // ignore parse errors
    }
  }

  return managerStatus;
};
