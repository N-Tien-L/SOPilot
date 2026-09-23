import { apiClient } from './api-client';
import { UserRole } from '@/interfaces/enums/core/user-role.enum';
import { AccountStatus } from '@/interfaces/enums/core/account-status.enum';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  fullName?: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
  user: {
    id: string;
    username: string;
    email: string;
    role: UserRole;
    status: AccountStatus;
  };
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface RefreshTokenResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface SessionInfo {
  id: string;
  userId: string;
  userAgent: string;
  ipAddress: string;
  location?: string;
  createdAt: string;
  lastAccessedAt: string;
  expiresAt: string;
  isCurrent: boolean;
}

class AuthService {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const response = await apiClient.post<{ success: boolean; data: AuthResponse }>(
      '/api/v1/auth/login',
      credentials
    );
    return response.data;
  }

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await apiClient.post<{ success: boolean; data: AuthResponse }>(
      '/api/v1/auth/register',
      data
    );
    return response.data;
  }

  async refreshToken(refreshToken: string): Promise<RefreshTokenResponse> {
    const response = await apiClient.post<{ success: boolean; data: RefreshTokenResponse }>(
      '/api/v1/auth/refresh',
      { refreshToken }
    );
    return response.data;
  }

  async logout(): Promise<void> {
    await apiClient.post('/api/v1/auth/logout');
  }

  async logoutAll(): Promise<void> {
    await apiClient.post('/api/v1/auth/logout-all');
  }

  async getSessions(): Promise<SessionInfo[]> {
    const response = await apiClient.get<{ success: boolean; data: SessionInfo[] }>(
      '/api/v1/auth/sessions'
    );
    return response.data;
  }
}

export const authService = new AuthService();
