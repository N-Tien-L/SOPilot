// User Types
export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  departmentId: string | null;
  department?: {
    id: string;
    name: string;
    code: string;
  } | null;
  fullName?: string;
  avatar?: string;
  createdAt?: string;
  updatedAt?: string;
}

export enum UserRole {
  USER = 'USER',
  MANAGER = 'MANAGER',
  ADMIN = 'ADMIN',
}

export enum AccountStatus {
  ACTIVE = 'ACTIVE',
  DEACTIVATED = 'DEACTIVATED',
  REVOKED = 'REVOKED',
}

export enum LoginStatus {
  SUCCESS = 'SUCCESS',
  FAILED_CREDENTIALS = 'FAILED_CREDENTIALS',
  FAILED_DEACTIVATED = 'FAILED_DEACTIVATED',
  FAILED_REVOKED = 'FAILED_REVOKED',
  FAILED_LOCKED = 'FAILED_LOCKED',
}

// Auth Types
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: User;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface RefreshTokenResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface LogoutRequest {
  refreshToken: string;
}

// Forgot Password Types
export interface ForgotPasswordRequest {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
  emailSent: boolean;
}

// Change Password Types
export interface ChangePasswordRequest {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export interface ChangePasswordResponse {
  success: boolean;
  message: string;
}

// User Create Types
export interface UserCreateRequest {
  username: string;
  email: string;
  fullName: string;
  role: string;
  departmentId?: string;
}

export interface BulkUserCreateRequest {
  users: UserCreateRequest[];
}

export interface BulkUserCreateResponse {
  totalRequested: number;
  successCount: number;
  failureCount: number;
  successfulUsers: SuccessfulUser[];
  failedUsers: FailedUser[];
}

export interface SuccessfulUser {
  userId: string;
  username: string;
  email: string;
  tempPassword: string;
  emailSent: boolean;
}

export interface FailedUser {
  username: string;
  email: string;
  error: string;
}

// User Update Types
export interface UserUpdateRequest {
  fullName?: string;
  role?: string;
  status?: string;
  departmentId?: string;
}

// User Detail Types
export interface UserDetail {
  id: string;
  username: string;
  email: string;
  fullName?: string;
  role: string;
  status: AccountStatus;
  departmentId?: string;
  createdAt: string;
  updatedAt: string;
  createdBy?: string;
  failedLoginAttempts?: number;
  passwordChangedAt?: string;
  mustChangePassword?: boolean;
}

// User Profile Types
export interface UserProfile {
  id: string;
  username: string;
  email: string;
  fullName?: string;
  role: string;
  status: AccountStatus;
  departmentId?: string | null;
  departmentName?: string | null;
  createdAt: string;
  passwordChangedAt?: string | null;
  mustChangePassword?: boolean;
}

// Login History Types
export interface LoginHistoryEntry {
  id: string;
  username: string;
  ipAddress: string;
  deviceType: string;
  location?: string;
  status: LoginStatus;
  failureReason?: string | null;
  createdAt: string;
}

// Session Types
export interface Session {
  sessionId: string;
  deviceInfo?: string;
  deviceType?: string;
  ipAddress: string;
  createdAt: string;
  expiresAt?: string;
  isCurrent?: boolean;
  isCurrentSession?: boolean;
}

// API Response Types
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp: string;
  traceId?: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination?: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

// Error Types
export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: ValidationError[];
    retryAfter?: number;
  };
  timestamp: string;
  traceId?: string;
}

export interface ValidationError {
  field: string;
  message: string;
}
