// Roster Status enum
export enum RosterStatus {
  PENDING = 'PENDING',
  CLAIMED = 'CLAIMED',
  DEACTIVATED = 'DEACTIVATED',
}

// Single roster record from backend
export interface RosterItem {
  id: string;
  employeeCode: string;
  email: string;
  fullName: string;
  phone: string | null;
  position: string | null;
  departmentId: string;
  departmentName: string;
  departmentCode: string;
  role: string;           // 'USER' | 'MANAGER' | 'ADMIN'
  status: RosterStatus;
  isClaimed: boolean;
  claimedAt: string | null;
  claimedUserId: string | null;
  importBatchId: string | null;
  createdAt: string;
  updatedAt: string;
}

// Import result from POST /roster/import
export interface RosterImportResponse {
  batchId: string;
  totalRows: number;
  importedCount: number;
  failedCount: number;
  errors: RosterImportError[];
}

export interface RosterImportError {
  row: number;
  employeeCode: string;
  email?: string;
  reason: string;
}

// Query params for GET /roster
export interface RosterSearchParams {
  keyword?: string;
  departmentId?: string;
  status?: RosterStatus | string;
  isClaimed?: boolean;
  page?: number;
  limit?: number;
}
