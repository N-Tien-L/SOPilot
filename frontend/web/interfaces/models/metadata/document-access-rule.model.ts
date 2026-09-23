import { UserRole } from "@/interfaces/enums/core";

export interface DocumentAccessRule {
  id: string;
  documentMetadataId: string;
  targetType: string;
  targetRole?: UserRole;
  targetDepartmentId?: string;
  targetUserId?: string;
  permission: string;
  createdBy: string;
  createdAt: Date;
}
