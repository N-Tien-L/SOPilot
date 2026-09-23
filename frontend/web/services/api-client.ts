import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/store/auth-store';
// useToast is dynamically imported inside interceptor to avoid circular dependency issues

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

// Separate axios instance for auth endpoints that must NOT trigger interceptors
// (e.g. logout during a failed refresh chain — prevents infinite recursion)
const directClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

// Module-level semaphore to prevent concurrent refresh attempts (stops refresh loops)
let isRefreshing = false;
const refreshSubscribers: Array<(token: string) => void> = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(newToken: string) {
  refreshSubscribers.forEach((cb) => cb(newToken));
  refreshSubscribers.length = 0;
  isRefreshing = false;
}

function getErrorMessage(error: AxiosError): string {
  const data = error.response?.data as Record<string, unknown> | null;
  if (data?.message && typeof data.message === 'string') return data.message;
  if (data?.error && typeof data.error === 'string') return data.error;
  if (typeof error.message === 'string') return error.message;
  switch (error.response?.status) {
    case 400: return 'Yêu cầu không hợp lệ.';
    case 401: return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    case 403: return 'Bạn không có quyền thực hiện thao tác này.';
    case 404: return 'Không tìm thấy tài nguyên yêu cầu.';
    case 500: return 'Lỗi máy chủ. Vui lòng thử lại sau.';
    case 502: return 'Dịch vụ tạm thời không khả dụng.';
    case 503: return 'Hệ thống đang bảo trì. Vui lòng thử lại sau.';
    default: return `Lỗi không xác định (${error.response?.status || 'network'}).`;
  }
}

function parseRefreshTokens(body: unknown): { accessToken: string; refreshToken: string } {
  const root = body as Record<string, unknown> | null;
  if (!root || typeof root !== 'object') {
    throw new Error('Invalid refresh response');
  }
  const payload =
    'data' in root &&
      root.data &&
      typeof root.data === 'object' &&
      'accessToken' in (root.data as object)
      ? (root.data as { accessToken: string; refreshToken: string })
      : (root as { accessToken: string; refreshToken: string });
  if (!payload?.accessToken || !payload?.refreshToken) {
    throw new Error('Invalid refresh response');
  }
  return payload;
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor - Add auth token (use lowercase 'authorization' for consistency)
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = useAuthStore.getState().accessToken;
        if (token && config.headers) {
          config.headers['authorization'] = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - Handle errors gracefully
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // If no response (network error), show toast and don't logout
        if (!error.response) {
          if (typeof window !== 'undefined') {
            const toast = (await import('@/components/ui/toast')).useToast;
            toast().addToast('Không thể kết nối máy chủ. Vui lòng kiểm tra kết nối mạng.', 'warning');
          }
          return Promise.reject(error);
        }

        const status = error.response.status;

        // 401 — try token refresh first
        if (status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          const refreshToken = useAuthStore.getState().refreshToken;
          if (refreshToken) {
            if (isRefreshing) {
              // Another request is already refreshing — queue this one
              return new Promise((resolve, reject) => {
                subscribeTokenRefresh((newToken: string) => {
                  const headers = {
                    ...(originalRequest.headers as Record<string, string>),
                    'authorization': `Bearer ${newToken}`,
                  };
                  // Use directClient to avoid interceptor recursion and stale token
                  resolve(directClient({ ...originalRequest, headers }));
                });
                setTimeout(() => reject(error), 10000);
              });
            }

            isRefreshing = true;
            try {
              const userId =
                useAuthStore.getState().user?.id ||
                (typeof window !== 'undefined' ? localStorage.getItem('userId') : null);
              // Use directClient to avoid interceptor recursion
              const response = await directClient.post<unknown>(
                `${API_BASE_URL}/api/v1/auth/refresh`,
                { refreshToken },
                {
                  headers: { 'x-user-id': userId || '' },
                },
              );

              const { accessToken, refreshToken: newRefreshToken } = parseRefreshTokens(
                response.data,
              );
              useAuthStore.getState().setTokens(accessToken, newRefreshToken);

              if (typeof window !== 'undefined') {
                localStorage.setItem('accessToken', accessToken);
                localStorage.setItem('refreshToken', newRefreshToken);
              }

              onTokenRefreshed(accessToken);

              // Use directClient for retry to avoid stale Zustand/localStorage token
              const headers = {
                ...(originalRequest.headers as Record<string, string>),
                'authorization': `Bearer ${accessToken}`,
              };
              return directClient({ ...originalRequest, headers });
            } catch (refreshError) {
              isRefreshing = false;
              refreshSubscribers.length = 0;
              // Refresh failed — tokens are truly invalid.
              const store = useAuthStore.getState();
              store.setTokens('', '');
              store.logout();
              if (typeof window !== 'undefined') {
                localStorage.removeItem('auth-storage');
                localStorage.removeItem('accessToken');
                localStorage.removeItem('refreshToken');
              }
              if (typeof window !== 'undefined') {
                const toast = (await import('@/components/ui/toast')).useToast;
                toast().addToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'warning');
                window.location.href = '/login';
              }
              return Promise.reject(refreshError);
            }
          } else {
            // No refresh token — session is invalid.
            const store = useAuthStore.getState();
            store.setTokens('', '');
            store.logout();
            if (typeof window !== 'undefined') {
              localStorage.removeItem('auth-storage');
            }
            if (typeof window !== 'undefined') {
              const toast = (await import('@/components/ui/toast')).useToast;
              toast().addToast('Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.', 'warning');
              window.location.href = '/login';
            }
            return Promise.reject(error);
          }
        }

        // For all other errors (400, 403, 404, 500, 502, 503, etc.)
        if (typeof window !== 'undefined') {
          try {
            const toast = (await import('@/components/ui/toast')).useToast;
            toast().addToast(getErrorMessage(error), 'error');
          } catch {
            // Toast context not available
          }
        }

        return Promise.reject(error);
      }
    );
  }

  async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async logout(): Promise<void> {
    // Use directClient so this call does NOT trigger interceptors.
    // This prevents infinite recursion when logout() is called by
    // the 401-interceptor during a failed token refresh.
    await directClient.post('/api/v1/auth/logout');
  }

  async post<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  async put<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async patch<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }

  async upload<T>(url: string, formData: FormData, onProgress?: (progress: number) => void): Promise<T> {
    const response = await this.client.post<T>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    return response.data;
  }
}

export const apiClient = new ApiClient();
