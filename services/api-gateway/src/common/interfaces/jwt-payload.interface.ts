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

export interface IJwtPayload {
  sub: string;
  username: string;
  email: string;
  role: UserRole;
  status: AccountStatus;
  department: string | null;
  iat: number;
  exp: number;
  iss: string;
  jti: string;
  mustChangePassword?: boolean;
  identityKind?: 'enterprise' | 'demo';
  workspaceId?: string;
}

export interface IUserContext {
  userId: string;
  username: string;
  email: string;
  role: string;
  status: string;
  department: string | null;
  jti: string;
  mustChangePassword?: boolean;
  identityKind?: 'enterprise' | 'demo';
  workspaceId?: string;
}
