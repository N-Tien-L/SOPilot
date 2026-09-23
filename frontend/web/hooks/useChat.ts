'use client';

import { useQuery, useMutation, useQueryClient } from 'react-query';
import { api } from '@/lib/api';
import type { ChatRequest, QuestionRequest, SourceDocument } from '@/types';

export function useConversations(params?: { page?: number; size?: number; keyword?: string }) {
  return useQuery({
    queryKey: ['conversations', params],
    queryFn: () => api.ai.getConversationList(params),
  });
}

export function useConversation(id?: string) {
  return useQuery({
    queryKey: ['conversation', id],
    queryFn: () => api.ai.getConversationById(id!),
    enabled: !!id,
  });
}

export function useMessages(conversationId?: string) {
  return useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => api.ai.getMessages(conversationId!),
    enabled: !!conversationId,
  });
}

export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.ai.deleteConversation(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['conversations'] });
    },
  });
}

export function useMarkAsUnanswered() {
  return useMutation({
    mutationFn: ({ conversationId, messageId }: { conversationId: string; messageId: string }) =>
      api.ai.markAsUnanswered(conversationId, messageId),
  });
}

export function useFeedback() {
  return useMutation({
    mutationFn: ({ conversationId, messageId, type }: { conversationId: string; messageId: string; type: 'LIKE' | 'DISLIKE' }) =>
      api.feedback.submit(conversationId, messageId, type),
  });
}

export interface StreamingState {
  conversationId: string | null;
  content: string;
  sources: SourceDocument[];
  isStreaming: boolean;
  error: string | null;
}

export async function* streamChat(
  request: QuestionRequest,
  onStateUpdate: (partial: Partial<StreamingState>) => void,
  signal?: AbortSignal
): AsyncGenerator<string, void, unknown> {
  const stream = api.ai.askStream(request, signal);
  const reader = stream.getReader();
  let fullContent = '';
  let conversationId: string | null = null;
  let sources: SourceDocument[] = [];

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      switch (value.type) {
        case 'conversationId':
          conversationId = value.conversationId;
          onStateUpdate({ conversationId: value.conversationId });
          break;
        case 'sources':
          sources = value.sources;
          onStateUpdate({ sources: value.sources });
          break;
        case 'content':
          fullContent += value.content;
          onStateUpdate({ content: fullContent });
          yield value.content;
          break;
        case 'done':
          onStateUpdate({ isStreaming: false });
          break;
        case 'error':
          onStateUpdate({ error: value.error, isStreaming: false });
          break;
      }
    }
  } finally {
    reader.releaseLock();
    onStateUpdate({ isStreaming: false });
  }
}