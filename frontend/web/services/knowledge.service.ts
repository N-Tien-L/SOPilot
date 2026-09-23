import { apiClient } from './api-client';
import { Document } from '@/interfaces/models/knowledge/document.model';
import { ProcessingJob } from '@/interfaces/models/knowledge/processing-job.model';
import { PaginatedResponse } from './types';

export interface DocumentSearchParams {
  page?: number;
  size?: number;
  keyword?: string;
  categoryId?: string;
  status?: string;
  fileType?: string;
  startDate?: string;
  endDate?: string;
}

export interface DocumentUploadResponse {
  document: Document;
  job: ProcessingJob;
}

class KnowledgeService {
  async getDocuments(params: DocumentSearchParams): Promise<PaginatedResponse<Document>> {
    const response = await apiClient.get<{ success: boolean; data: PaginatedResponse<Document> }>(
      '/api/v1/documents',
      params as Record<string, unknown>
    );
    return response.data;
  }

  async getDocumentById(documentId: string): Promise<Document> {
    const response = await apiClient.get<{ success: boolean; data: Document }>(`/api/v1/documents/${documentId}`);
    return response.data;
  }

  async uploadDocument(file: File, metadata?: Record<string, unknown>): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }

    const response = await apiClient.upload<{ success: boolean; data: DocumentUploadResponse }>(
      '/api/v1/documents/upload',
      formData
    );
    return response.data;
  }

  async updateDocument(documentId: string, data: Partial<Document>): Promise<Document> {
    const response = await apiClient.put<{ success: boolean; data: Document }>(
      `/api/v1/documents/${documentId}`,
      data
    );
    return response.data;
  }

  async deleteDocument(documentId: string): Promise<void> {
    await apiClient.delete(`/api/v1/documents/${documentId}`);
  }

  async downloadDocument(documentId: string): Promise<Blob> {
    const response = await apiClient.get<Blob>(`/api/v1/documents/${documentId}/download`);
    return response;
  }

  async getDocumentVersions(documentId: string): Promise<Document[]> {
    const response = await apiClient.get<{ success: boolean; data: Document[] }>(
      `/api/v1/documents/${documentId}/versions`
    );
    return response.data;
  }

  async getProcessingJob(jobId: string): Promise<ProcessingJob> {
    const response = await apiClient.get<{ success: boolean; data: ProcessingJob }>(
      `/api/v1/documents/jobs/${jobId}`
    );
    return response.data;
  }

  async searchDocuments(keyword: string, limit?: number): Promise<Document[]> {
    const response = await apiClient.get<{ success: boolean; data: Document[] }>('/api/v1/documents/search', {
      keyword,
      limit,
    });
    return response.data;
  }
}

export const knowledgeService = new KnowledgeService();
