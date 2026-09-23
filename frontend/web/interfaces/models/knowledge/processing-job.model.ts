import { ProcessingStep, ProcessingStatus } from "@/interfaces/enums/knowledge";

export interface ProcessingJob {
  id: string;
  documentId: string;
  jobType: ProcessingStep;
  status: ProcessingStatus;
  progressPercent: number;
  startedAt?: Date;
  completedAt?: Date;
  success: boolean;
  errorMessage?: string;
  errorDetails?: Record<string, unknown>;
  retryCount: number;
  maxRetries: number;
  outputMetrics?: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
}
