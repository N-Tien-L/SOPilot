export interface DocumentVersion {
  id: string;
  documentId: string;
  versionNumber: number;
  fileKey: string;
  fileSizeBytes: number;
  changelog?: string;
  extractedText: string;
  createdBy: string;
  createdAt: Date;
}
