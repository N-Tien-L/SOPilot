// Analytics Types
export interface DashboardStats {
  totalQuestions: number;
  questionsToday: number;
  questionsThisWeek: number;
  questionsThisMonth: number;
  averageResponseTime?: number;
  satisfactionRate?: number;
  totalDocuments: number;
  activeDocuments: number;
  totalUsers: number;
  activeUsers: number;
}

export interface QuestionStats {
  date: string;
  count: number;
}

export interface QuestionsByDepartment {
  department: string;
  count: number;
  percentage: number;
}

export interface TopQuestion {
  question: string;
  askCount: number;
  lastAskedAt: string;
}

export interface TopDocument {
  documentId: string;
  documentTitle: string;
  viewCount: number;
  lastViewedAt: string;
}

export interface SatisfactionStats {
  likes: number;
  dislikes: number;
  rate: number;
}

export interface DepartmentStats {
  department: string;
  questions: number;
  satisfaction: number;
  avgResponseTime?: number;
}

export interface AnalyticsOverview {
  stats: DashboardStats;
  questionTrend: QuestionStats[];
  questionsByDepartment: QuestionsByDepartment[];
  topQuestions: TopQuestion[];
  topDocuments: TopDocument[];
  satisfaction: SatisfactionStats;
}

export interface ExportRequest {
  type: ExportType;
  format: ExportFormat;
  dateFrom?: string;
  dateTo?: string;
  department?: string;
}

export enum ExportType {
  QUESTIONS = 'QUESTIONS',
  DOCUMENTS = 'DOCUMENTS',
  USERS = 'USERS',
  FEEDBACK = 'FEEDBACK',
  COMPREHENSIVE = 'COMPREHENSIVE',
}

export enum ExportFormat {
  CSV = 'CSV',
  PDF = 'PDF',
  EXCEL = 'EXCEL',
}

export interface ExportJob {
  id: string;
  type: ExportType;
  format: ExportFormat;
  status: ExportStatus;
  downloadUrl?: string;
  createdAt: string;
  completedAt?: string;
}

export enum ExportStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

// API Health Metrics Types
export interface ApiEndpointMetrics {
  path: string;
  total: number;
  success: number;
  failure: number;
  avgResponseTime: number;
  recentErrors: Array<{
    timestamp: string;
    method: string;
    statusCode: number;
    path: string;
  }>;
}

export interface ApiServiceHealth {
  service: string;
  status: 'up' | 'down' | 'unknown';
  responseTime?: number;
}

export interface ApiOverallMetrics {
  totalRequests: number;
  totalErrors: number;
  successRate: number;
}

export interface ApiDailyErrorCount {
  date: string;
  errors: number;
}

export interface ApiMetricsResponse {
  timestamp: string;
  overall: ApiOverallMetrics;
  endpoints: ApiEndpointMetrics[];
  dailyErrors: ApiDailyErrorCount[];
  services: ApiServiceHealth[];
}
