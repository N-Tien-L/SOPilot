import { AccessLevel, DocumentStatus } from "@/interfaces/enums/metadata";

export interface DocumentMetadata {
  id: string;
  documentId: string;
  title: string;
  description?: string;
  documentType: string;
  categoryId: string;
  departmentId: string;
  accessLevel: AccessLevel;
  effectiveDate: Date;
  expiryDate?: Date;
  status: DocumentStatus;
  currentVersion: number;
  createdBy: string;
  updatedBy?: string;
  publishedBy?: string;
  publishedAt?: Date;
  createdAt: Date;
  updatedAt: Date;
  deletedAt?: Date;
}
