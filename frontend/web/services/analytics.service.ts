import { apiClient } from './api-client';
import { DailyAggregate } from '@/interfaces/models/analytics/daily-aggregate.model';
import { DocumentPopularity } from '@/interfaces/models/analytics/document-popularity.model';
import { PopularQuestion } from '@/interfaces/models/analytics/popular-question.model';
import { UsageStat } from '@/interfaces/models/analytics/usage-stat.model';
import { AuditLog } from '@/interfaces/models/analytics/audit-log.model';
import { PaginatedResponse } from './types';

export interface AnalyticsOverview {
  totalConversations: number;
  totalDocuments: number;
  totalUsers: number;
  avgResponseTime: number;
  topCategories: { categoryId: string; categoryName: string; count: number }[];
  dailyStats: DailyAggregate[];
}

export interface UsageStatsResponse {
  hourly: UsageStat[];
  daily: UsageStat[];
  weekly: UsageStat[];
}

export interface PopularDocumentsResponse {
  documents: DocumentPopularity[];
  period: string;
}

export interface PopularQuestionsResponse {
  questions: PopularQuestion[];
  period: string;
}

export interface AuditLogsParams {
  page?: number;
  size?: number;
  userId?: string;
  action?: string;
  resourceType?: string;
  startDate?: string;
  endDate?: string;
}

class AnalyticsService {
  async getOverview(): Promise<AnalyticsOverview> {
    const response = await apiClient.get<{ success: boolean; data: AnalyticsOverview }>('/api/v1/analytics/overview');
    return response.data;
  }

  async getUsageStats(period: 'hourly' | 'daily' | 'weekly'): Promise<UsageStatsResponse> {
    const response = await apiClient.get<{ success: boolean; data: UsageStatsResponse }>(
      '/api/v1/analytics/usage',
      { period }
    );
    return response.data;
  }

  async getPopularDocuments(period: string, limit?: number): Promise<PopularDocumentsResponse> {
    const response = await apiClient.get<{ success: boolean; data: PopularDocumentsResponse }>(
      '/api/v1/analytics/popular-documents',
      { period, limit }
    );
    return response.data;
  }

  async getPopularQuestions(period: string, limit?: number): Promise<PopularQuestionsResponse> {
    const response = await apiClient.get<{ success: boolean; data: PopularQuestionsResponse }>(
      '/api/v1/analytics/popular-questions',
      { period, limit }
    );
    return response.data;
  }

  async getAuditLogs(params: AuditLogsParams): Promise<PaginatedResponse<AuditLog>> {
    const response = await apiClient.get<{ success: boolean; data: PaginatedResponse<AuditLog> }>(
      '/api/v1/analytics/audit-logs',
      params as Record<string, unknown>
    );
    return response.data;
  }

  async exportReport(
    reportType: string,
    format: 'PDF' | 'EXCEL' | 'CSV',
    params?: Record<string, unknown>
  ): Promise<Blob> {
    const response = await apiClient.get<Blob>('/api/v1/analytics/export', {
      reportType,
      format,
      ...params,
    });
    return response;
  }
}

export const analyticsService = new AnalyticsService();
