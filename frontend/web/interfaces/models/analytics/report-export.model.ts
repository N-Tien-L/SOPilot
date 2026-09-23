import { ReportType, ExportFormat } from "@/interfaces/enums/analytics";

export interface ReportExport {
  id: string;
  reportType: ReportType;
  title: string;
  dateFrom: Date;
  dateTo: Date;
  departmentId?: string;
  filters?: Record<string, unknown>;
  format: ExportFormat;
  fileKey: string;
  fileSizeBytes: number;
  status: string;
  errorMessage?: string;
  requestedBy: string;
  createdAt: Date;
  completedAt?: Date;
  downloadedAt?: Date;
  expiresAt?: Date;
}
