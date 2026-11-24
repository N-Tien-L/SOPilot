// Typed calls for the V2-15 screens. Components use these (through lib/query/hooks.ts), never
// fetch. Paths are relative to /api/v1 (core) and /ai/v1 (ai-service).

import type { UploadScope } from '@/lib/upload/queue';
import { aiRequest, coreRequest, coreRequestPage } from './http';
import type {
  AuditEntry,
  CategoryView,
  ConversationDetail,
  CreatedInvitation,
  DepartmentView,
  ConversationSummary,
  ChunkDetail,
  DocumentContent,
  ProcessingReport,
  DocumentStatus,
  DocumentView,
  DownloadUrl,
  InvitationView,
  KnowledgeGap,
  LoginResponse,
  MemberView,
  MyMemberView,
  OwnershipResponse,
  PipelineTrace,
  PublishersOverview,
  TagView,
  VisibilityResponse,
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

// ---- members and invitations (V2-33) ----
export const listMembers = () => coreRequest<MemberView[]>('/members');
export const getMyMember = () => coreRequest<MyMemberView>('/members/me');
export const listInvitations = () => coreRequest<InvitationView[]>('/invitations');

/** Patchable keys: displayName, employeeCode, jobTitle, departmentId, role. `null` clears a field. */
export interface MemberPatch {
  displayName?: string | null;
  employeeCode?: string | null;
  jobTitle?: string | null;
  departmentId?: string | null;
  role?: string;
}
const member = (userId: string) => `/members/${encodeURIComponent(userId)}`;
export const updateMember = (userId: string, patch: MemberPatch) =>
  coreRequest<MemberView>(member(userId), { method: 'PATCH', body: patch });
export const suspendMember = (userId: string) => coreRequest<void>(`${member(userId)}/suspend`, { method: 'POST' });
export const reactivateMember = (userId: string) =>
  coreRequest<void>(`${member(userId)}/reactivate`, { method: 'POST' });
export const removeMember = (userId: string) => coreRequest<void>(member(userId), { method: 'DELETE' });

export interface InvitationInput {
  email: string;
  role: string;
  displayName?: string;
  employeeCode?: string;
  jobTitle?: string;
  departmentId?: string;
}
export const createInvitation = (input: InvitationInput) =>
  coreRequest<CreatedInvitation>('/invitations', { method: 'POST', body: input });
export const revokeInvitation = (id: string) =>
  coreRequest<void>(`/invitations/${encodeURIComponent(id)}`, { method: 'DELETE' });
/** Exactly one of the two: the secret token from the link, or the id of a pending invitation for this account. */
export const acceptInvitation = (input: { invitationToken: string } | { invitationId: string }) =>
  coreRequest<LoginResponse>('/invitations/accept', { method: 'POST', body: input });

// ---- departments, categories, tags (flat lists) ----
export const listDepartments = (includeArchived = false) =>
  coreRequest<DepartmentView[]>('/departments', { query: { includeArchived } });
export const createDepartment = (name: string) =>
  coreRequest<DepartmentView>('/departments', { method: 'POST', body: { name } });
export const updateDepartment = (id: string, patch: { name?: string; status?: 'ACTIVE' | 'ARCHIVED' }) =>
  coreRequest<DepartmentView>(`/departments/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch });
/** `409` while members, invitations or documents still reference it: archive instead. */
export const deleteDepartment = (id: string) =>
  coreRequest<void>(`/departments/${encodeURIComponent(id)}`, { method: 'DELETE' });

export const createCategory = (name: string) =>
  coreRequest<CategoryView>('/categories', { method: 'POST', body: { name } });
export const updateCategory = (id: string, patch: { name?: string; status?: 'ACTIVE' | 'ARCHIVED' }) =>
  coreRequest<CategoryView>(`/categories/${encodeURIComponent(id)}`, { method: 'PATCH', body: patch });
export const deleteCategory = (id: string) =>
  coreRequest<void>(`/categories/${encodeURIComponent(id)}`, { method: 'DELETE' });
export const listTags = () => coreRequest<TagView[]>('/tags');

// ---- publishers (OWNER, ADR-009) and the audit log (OWNER, FR-20) ----
export const getPublishers = (includeArchived = false) =>
  coreRequest<PublishersOverview>('/publishers', { query: { includeArchived } });
export const assignWorkspacePublisher = (userId: string) =>
  coreRequest<void>('/publishers/workspace', { method: 'PUT', body: { userId } });
export const unassignWorkspacePublisher = () => coreRequest<void>('/publishers/workspace', { method: 'DELETE' });
export const assignDepartmentPublisher = (departmentId: string, userId: string) =>
  coreRequest<void>(`/departments/${encodeURIComponent(departmentId)}/publisher`, { method: 'PUT', body: { userId } });
export const unassignDepartmentPublisher = (departmentId: string) =>
  coreRequest<void>(`/departments/${encodeURIComponent(departmentId)}/publisher`, { method: 'DELETE' });

export interface AuditFilters {
  action?: string;
  actorId?: string;
  from?: string;
  to?: string;
  cursor?: string;
  limit?: number;
}
export const listAuditLogs = (filters: AuditFilters) =>
  coreRequestPage<AuditEntry>('/audit-logs', { query: { limit: 50, ...filters } });

// ---- documents (list; upload V2-31; viewer V2-32) ----
export interface DocumentFilters {
  status?: DocumentStatus;
  categoryId?: string;
  tag?: string;
  /** Title search. */
  q?: string;
  /** One department's documents. Owners and admins, or members of that department, only. */
  ownerDepartmentId?: string;
  visibility?: 'WORKSPACE' | 'DEPARTMENTS';
  cursor?: string;
  limit?: number;
}
export const listDocuments = (filters: DocumentFilters) =>
  coreRequestPage<DocumentView>('/documents', { query: { limit: 20, ...filters } });
export const listCategories = (includeArchived = false) =>
  coreRequest<CategoryView[]>('/categories', { query: { includeArchived } });
/** `inline` signs the URL so a browser may show the file (the PDF viewer); the default downloads it. */
export const getDownloadUrl = (documentId: string, options: { inline?: boolean } = {}) =>
  coreRequest<DownloadUrl>(`/documents/${encodeURIComponent(documentId)}/download-url`, {
    query: options.inline ? { disposition: 'inline' } : undefined,
  });
export const getDocument = (documentId: string, signal?: AbortSignal) =>
  coreRequest<DocumentView>(`/documents/${encodeURIComponent(documentId)}`, { signal });

// ---- document upload (V2-31): one multipart request per file ----
function fileForm(file: File): FormData {
  const form = new FormData();
  form.append('file', file);
  return form;
}
/** A department document is read by that department and owned by it (`ownerDepartmentId` defaults to the caller's own). */
function createForm(file: File, scope: UploadScope, preparedBy: string | null): FormData {
  const form = fileForm(file);
  if (preparedBy) form.append('preparedBy', preparedBy);
  form.append('visibility', scope.kind === 'DEPARTMENT' ? 'DEPARTMENTS' : 'WORKSPACE');
  if (scope.kind === 'DEPARTMENT') {
    form.append('ownerDepartmentId', scope.departmentId);
    form.append('departmentIds', scope.departmentId);
  }
  return form;
}
/** Creates a document in `scope`. `201` with the new document, `409` for duplicates and quota, `403 NOT_PUBLISHER`. */
export const uploadDocument = (file: File, scope: UploadScope, preparedBy: string | null, signal?: AbortSignal) =>
  coreRequest<DocumentView>('/documents', { method: 'POST', body: createForm(file, scope, preparedBy), signal });
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
/** Only the keys that changed: title, description, language, categoryId, preparedBy (null clears). */
export interface DocumentPatch {
  title?: string;
  description?: string | null;
  language?: string | null;
  categoryId?: string | null;
  /** Who drafted the content; `null` clears it. */
  preparedBy?: string | null;
}
export const updateDocument = (documentId: string, patch: DocumentPatch) =>
  coreRequest<DocumentView>(`/documents/${encodeURIComponent(documentId)}`, { method: 'PATCH', body: patch });
/** `departmentIds` is required for `DEPARTMENTS`. `accessSync: PENDING` = still reaching ai-service. */
export const updateDocumentVisibility = (
  documentId: string,
  visibility: 'WORKSPACE' | 'DEPARTMENTS',
  departmentIds: string[],
) =>
  coreRequest<VisibilityResponse>(`/documents/${encodeURIComponent(documentId)}/visibility`, {
    method: 'PUT',
    body: { visibility, departmentIds },
  });
/** OWNER only (ADR-009 decision 8): another scope or owner department; keeps content and history. */
export const transferDocumentOwnership = (
  documentId: string,
  input: { visibility: 'WORKSPACE' | 'DEPARTMENTS'; ownerDepartmentId: string | null; departmentIds: string[] },
) =>
  coreRequest<OwnershipResponse>(`/documents/${encodeURIComponent(documentId)}/ownership`, {
    method: 'PUT',
    body: input,
  });
export const deleteDocument = (documentId: string) =>
  coreRequest<void>(`/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });

// ---- recognized content and the citation viewer (V2-32; the active version only, else 404) ----
export const getDocumentContent = (documentId: string, versionId: string, signal?: AbortSignal) =>
  aiRequest<DocumentContent>(
    `/documents/${encodeURIComponent(documentId)}/versions/${encodeURIComponent(versionId)}/content`,
    { signal },
  );

// ---- processing report (V2-46; the active version only, else 404) ----
const reportPath = (documentId: string, versionId: string) =>
  `/documents/${encodeURIComponent(documentId)}/versions/${encodeURIComponent(versionId)}/processing-report`;
export const getProcessingReport = (documentId: string, versionId: string, signal?: AbortSignal) =>
  aiRequest<ProcessingReport>(reportPath(documentId, versionId), { signal });
export const getProcessingChunk = (documentId: string, versionId: string, ordinal: number, signal?: AbortSignal) =>
  aiRequest<ChunkDetail>(`${reportPath(documentId, versionId)}?ordinal=${ordinal}`, { signal });

// ---- conversations, feedback, knowledge gaps (ai-service) ----
export const listConversations = (limit = 50) =>
  aiRequest<ConversationSummary[]>('/conversations', { query: { limit } });
export const getConversation = (id: string) =>
  aiRequest<ConversationDetail>(`/conversations/${encodeURIComponent(id)}`);
export const getMessageTrace = (conversationId: string, messageId: string, signal?: AbortSignal) =>
  aiRequest<PipelineTrace>(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/trace`,
    { signal },
  );
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
