import { apiClient } from './api-client';
import { Feedback } from '@/interfaces/models/analytics/feedback.model';
import { UnansweredQuestion } from '@/interfaces/models/conversation/unanswered-question.model';
import { PaginatedResponse } from './types';

export interface FeedbackSubmitRequest {
  conversationId: string;
  messageId: string;
  type: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
  comment?: string;
  rating?: number;
}

export interface FeedbackSearchParams {
  page?: number;
  size?: number;
  conversationId?: string;
  type?: string;
  startDate?: string;
  endDate?: string;
}

class FeedbackService {
  async submitFeedback(data: FeedbackSubmitRequest): Promise<Feedback> {
    const response = await apiClient.post<{ success: boolean; data: Feedback }>('/api/v1/feedback', data);
    return response.data;
  }

  async getFeedback(id: string): Promise<Feedback> {
    const response = await apiClient.get<{ success: boolean; data: Feedback }>(`/api/v1/feedback/${id}`);
    return response.data;
  }

  async searchFeedback(params: FeedbackSearchParams): Promise<PaginatedResponse<Feedback>> {
    const response = await apiClient.get<{ success: boolean; data: PaginatedResponse<Feedback> }>(
      '/api/v1/feedback',
      params as Record<string, unknown>
    );
    return response.data;
  }

  async getUnansweredQuestions(page?: number, size?: number): Promise<PaginatedResponse<UnansweredQuestion>> {
    const response = await apiClient.get<{ success: boolean; data: PaginatedResponse<UnansweredQuestion> }>(
      '/api/v1/feedback/unanswered',
      { page, size }
    );
    return response.data;
  }

  async answerQuestion(questionId: string, answer: string): Promise<void> {
    await apiClient.post(`/api/v1/feedback/unanswered/${questionId}/answer`, { answer });
  }
}

export const feedbackService = new FeedbackService();
