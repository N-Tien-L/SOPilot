// Typed calls for the V2-15 screens. Components use these (through lib/query/hooks.ts), never
// fetch. Paths are relative to /api/v1 (core) and /ai/v1 (ai-service).

import { aiRequest, coreRequest, coreRequestPage } from './http';
import type {
  CategoryView,
  ConversationDetail,
  ConversationSummary,
  DocumentStatus,
  DocumentView,
  DownloadUrl,
  InvitationView,
  KnowledgeGap,
  LoginResponse,
  MemberView,
  MyMemberView,
  WorkspaceDetail,
  WorkspaceView,
} from './types';

// ---- workspaces ----
export const listWorkspaces = () => coreRequest<WorkspaceView[]>('/workspaces');
export const getWorkspace = () => coreRequest<WorkspaceDetail>('/workspaces/current');
export const renameWorkspace = (name: string) =>
  coreRequest<WorkspaceDetail>('/workspaces/current', { method: 'PATCH', body: { name } });
export const deleteWorkspace = () => coreRequest<void>('/workspaces/current', { method: 'DELETE' });
/** Creates a TEAM workspace; the response is a login payload for it (apply it as a session). */
export const createWorkspace = (name: string) =>
  coreRequest<LoginResponse>('/workspaces', { method: 'POST', body: { name } });
export const leaveWorkspace = () => coreRequest<void>('/members/leave', { method: 'POST' });

// ---- members and invitations (read-only here; editing is V2-33) ----
export const listMembers = () => coreRequest<MemberView[]>('/members');
export const getMyMember = () => coreRequest<MyMemberView>('/members/me');
export const listInvitations = () => coreRequest<InvitationView[]>('/invitations');

// ---- documents (list; upload V2-31; viewer V2-32) ----
export interface DocumentFilters {
  status?: DocumentStatus;
  categoryId?: string;
  tag?: string;
  /** Title search. */
  q?: string;
  cursor?: string;
  limit?: number;
}
export const listDocuments = (filters: DocumentFilters) =>
  coreRequestPage<DocumentView>('/documents', { query: { limit: 20, ...filters } });
export const listCategories = () => coreRequest<CategoryView[]>('/categories');
export const getDownloadUrl = (documentId: string) =>
  coreRequest<DownloadUrl>(`/documents/${encodeURIComponent(documentId)}/download-url`);
export const getDocument = (documentId: string, signal?: AbortSignal) =>
  coreRequest<DocumentView>(`/documents/${encodeURIComponent(documentId)}`, { signal });

// ---- document upload (V2-31): one multipart request per file ----
function fileForm(file: File): FormData {
  const form = new FormData();
  form.append('file', file);
  return form;
}
/** Creates a WORKSPACE-visible document. `201` with the new document, `409` for duplicates and quota. */
export const uploadDocument = (file: File, signal?: AbortSignal) =>
  coreRequest<DocumentView>('/documents', { method: 'POST', body: fileForm(file), signal });
/** A replacement file for an existing document (a new version). */
export const uploadDocumentVersion = (documentId: string, file: File, signal?: AbortSignal) =>
  coreRequest<DocumentView>(`/documents/${encodeURIComponent(documentId)}/versions`, {
    method: 'POST',
    body: fileForm(file),
    signal,
  });
/** Reprocess a document whose latest version is FAILED (`409 VERSION_NOT_FAILED` otherwise). */
export const retryDocument = (documentId: string) =>
  coreRequest<DocumentView>(`/documents/${encodeURIComponent(documentId)}/retry`, { method: 'POST' });
export const deleteDocument = (documentId: string) =>
  coreRequest<void>(`/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });

// ---- conversations, feedback, knowledge gaps (ai-service) ----
export const listConversations = (limit = 50) =>
  aiRequest<ConversationSummary[]>('/conversations', { query: { limit } });
export const getConversation = (id: string) =>
  aiRequest<ConversationDetail>(`/conversations/${encodeURIComponent(id)}`);
export const renameConversation = (id: string, title: string) =>
  aiRequest<{ id: string; title: string }>(`/conversations/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: { title },
  });
export const deleteConversation = (id: string) =>
  aiRequest<void>(`/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' });
export const sendFeedback = (messageId: string, vote: 1 | -1, comment?: string) =>
  aiRequest<void>(`/messages/${encodeURIComponent(messageId)}/feedback`, {
    method: 'PUT',
    body: { vote, ...(comment ? { comment } : {}) },
  });
export const listKnowledgeGaps = (status: 'open' | 'resolved', limit: number, offset: number) =>
  aiRequest<KnowledgeGap[]>('/knowledge-gaps', { query: { status, limit, offset } });
export const resolveKnowledgeGap = (messageId: string, note?: string) =>
  aiRequest<{ messageId: string; status: string }>(
    `/knowledge-gaps/${encodeURIComponent(messageId)}/resolve`,
    { method: 'POST', body: note ? { note } : {} },
  );
