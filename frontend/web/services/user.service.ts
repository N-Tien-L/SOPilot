import { apiClient } from './api-client';
import { UserProfile } from '@/interfaces/models/core/user-profile.model';
import { PaginatedResponse } from './types';

export interface UserProfileUpdateRequest {
  fullName?: string;
  phone?: string;
  position?: string;
  avatarUrl?: string;
  bio?: string;
  dateOfBirth?: string;
}

export interface UserStatusResponse {
  status: 'ACTIVE' | 'DEACTIVATED' | 'REVOKED';
  lockedUntil?: string;
  failedLoginAttempts: number;
  mustChangePassword: boolean;
}

export interface UserSearchParams {
  page?: number;
  size?: number;
  keyword?: string;
  role?: string;
  status?: string;
  departmentId?: string;
}

export interface UserSearchResponse {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  departmentId?: string;
  createdAt: string;
}

class UserService {
  async getMyProfile(): Promise<UserProfile> {
    const response = await apiClient.get<{ success: boolean; data: UserProfile }>('/api/v1/users/me');
    return response.data;
  }

  async updateMyProfile(data: UserProfileUpdateRequest): Promise<UserProfile> {
    const response = await apiClient.put<{ success: boolean; data: UserProfile }>('/api/v1/users/me', data);
    return response.data;
  }

  async getMyStatus(): Promise<UserStatusResponse> {
    const response = await apiClient.get<{ success: boolean; data: UserStatusResponse }>('/api/v1/users/me/status');
    return response.data;
  }

  async getUserById(userId: string): Promise<UserSearchResponse> {
    const response = await apiClient.get<{ success: boolean; data: UserSearchResponse }>(`/api/v1/users/${userId}`);
    return response.data;
  }

  async searchUsers(params: UserSearchParams): Promise<PaginatedResponse<UserSearchResponse>> {
    const response = await apiClient.get<{ success: boolean; data: PaginatedResponse<UserSearchResponse> }>(
      '/api/v1/users',
      params as Record<string, unknown>
    );
    return response.data;
  }

  async updateUserStatus(userId: string, status: string): Promise<void> {
    await apiClient.patch(`/api/v1/users/${userId}/status`, { status });
  }

  async deleteUser(userId: string): Promise<void> {
    await apiClient.delete(`/api/v1/users/${userId}`);
  }
}

export const userService = new UserService();
