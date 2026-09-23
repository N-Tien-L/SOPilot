import { UserRole } from "@/interfaces/enums/core/user-role.enum";
import { AccountStatus } from "@/interfaces/enums/core/account-status.enum";

export interface User {
  id: string;
  username: string;
  email: string;
  passwordHash: string;
  role: UserRole;
  status: AccountStatus;
  departmentId: string;
  failedLoginAttempts: number;
  lockedUntil?: Date;
  passwordChangedAt?: Date;
  mustChangePassword: boolean;
  createdBy: string;
  createdAt: Date;
  updatedAt: Date;
  deactivatedAt?: Date;
  revokedAt?: Date;
}
