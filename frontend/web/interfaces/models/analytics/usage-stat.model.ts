export interface UsageStat {
  id: string;
  userId: string;
  userRole: string;
  userDepartmentId: string;
  serviceName: string;
  endpoint: string;
  method: string;
  responseTimeMs: number;
  statusCode: number;
  requestSizeBytes: number;
  responseSizeBytes: number;
  isError: boolean;
  errorCode?: string;
  errorMessage?: string;
  tokensUsed: number;
  modelUsed?: string;
  chunksRetrieved: number;
  confidence?: string;
  traceId: string;
  ipAddress: string;
  userAgent: string;
  createdAt: Date;
}
