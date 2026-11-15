// Contract types declared once (frontend-nfrs M2). Shapes follow TECH-V2-core-api §5.1 and
// TECH-V2-ai-service §7.2; later tickets extend this file per endpoint.

export interface UserView {
  id: string;
  email: string;
  displayName: string;
}

export type WorkspaceRole = 'OWNER' | 'ADMIN' | 'MEMBER';

export interface WorkspaceView {
  id: string;
  name: string;
  kind: string;
  role: WorkspaceRole;
  /** Present on `GET /workspaces`; the login payload omits it. */
  status?: string;
}

/** `GET|PATCH /workspaces/current`: counts only; the limits are server env and not exposed. */
export interface WorkspaceDetail {
  id: string;
  name: string;
  kind: string;
  role: WorkspaceRole;
  documentCount: number;
  bytesUsed: number;
}

export interface PendingInvitationView {
  id: string;
  workspaceName: string;
  role: WorkspaceRole;
}

/** Login, refresh, switch-workspace and create-workspace all return this payload. */
export interface LoginResponse {
  accessToken: string;
  expiresIn: number;
  user: UserView;
  workspace: WorkspaceView;
  pendingInvitations: PendingInvitationView[];
}

export interface PageInfo {
  cursor: string | null;
  hasMore: boolean;
}

export interface CorePage<T> {
  data: T[];
  page: PageInfo;
}

// ---- ai-service SSE (TECH-V2-ai-service §7.2) ----

export type RefusalReason = 'NO_EVIDENCE' | 'OUT_OF_SCOPE' | 'INPUT_INVALID' | 'GUARD' | 'GENERATOR_NOT_FOUND';

export interface Citation {
  n: number;
  documentId: string;
  versionId: string;
  title: string;
  page: number | null;
  charStart: number;
  charEnd: number;
  snippet: string;
}

export interface AnswerWarning {
  code: string;
  values: string[];
}

export type StreamEvent =
  | { type: 'meta'; conversationId: string; messageId: string; mode: string; lang: string }
  | { type: 'delta'; text: string }
  | { type: 'replace'; text: string; reason: string }
  | {
      type: 'refusal';
      text: string;
      reason: RefusalReason;
      nearestDocuments: { documentId: string; title: string }[];
    }
  | { type: 'citations'; citations: Citation[] }
  | {
      type: 'done';
      finalText: string;
      outcome: string;
      refusalReason: RefusalReason | string | null;
      warnings: AnswerWarning[];
      usage: { questionsLeftToday: number } | null;
    }
  | { type: 'error'; code: string; message: string };

// ---- core-api resources (TECH-V2-core-api §5) ----

export type MemberStatus = 'ACTIVE' | 'SUSPENDED' | string;

export interface MemberView {
  userId: string;
  email: string;
  displayName: string;
  employeeCode: string | null;
  jobTitle: string | null;
  role: WorkspaceRole;
  status: MemberStatus;
  departmentId: string | null;
  departmentName: string | null;
  joinedAt: string;
}

/** `GET /members/me`: the profile plus what the caller may publish (TECH-V2-core-api §15.4). */
export interface MyMemberView extends MemberView {
  publisherOf: { workspace: boolean; departmentId: string | null };
}

export interface InvitationView {
  id: string;
  email: string;
  role: WorkspaceRole;
  displayName: string | null;
  employeeCode: string | null;
  jobTitle: string | null;
  departmentId: string | null;
  departmentName: string | null;
  invitedBy: string;
  expiresAt: string;
  createdAt: string;
}

export type DocumentStatus = 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED';

export interface DocumentView {
  id: string;
  title: string;
  description: string | null;
  category: { id: string; name: string } | null;
  tags: string[];
  language: string | null;
  visibility: string;
  /** Null for plain members (masked). */
  departments: { id: string; name: string | null }[] | null;
  status: DocumentStatus;
  answerable: boolean;
  latestVersion: {
    id: string;
    versionNo: number;
    status: DocumentStatus;
    failureCode: string | null;
    failureMessage: string | null;
  };
  currentVersion: {
    id: string;
    versionNo: number;
    originalName: string;
    fileType: string;
    sizeBytes: number;
    pageCount: number | null;
    warningCodes: string[];
  } | null;
  createdBy: { id: string; displayName: string };
  createdAt: string;
  updatedAt: string;
}

export interface CategoryView {
  id: string;
  name: string;
}

export interface DownloadUrl {
  url: string;
  expiresAt: string;
}

// ---- ai-service resources (TECH-V2-ai-service §7) ----

export interface ConversationSummary {
  id: string;
  title: string | null;
  createdAt: string;
  updatedAt: string;
}

/** A citation as stored in history; the live stream's `citations` event has no `isCurrentVersion`. */
export interface StoredCitation extends Citation {
  isCurrentVersion: boolean;
}

export type HiddenReason = 'ACCESS_REVOKED' | 'DOCUMENT_DELETED';

export type HistoryMessage =
  | { id: string; role: 'USER'; createdAt: string; content: string }
  | {
      id: string;
      role: 'ASSISTANT';
      createdAt: string;
      content: string;
      outcome: string | null;
      refusalReason: RefusalReason | string | null;
      citations: StoredCitation[];
    }
  | { id: string; role: 'ASSISTANT'; createdAt: string; hidden: true; reason: HiddenReason };

export interface ConversationDetail extends ConversationSummary {
  messages: HistoryMessage[];
}

export interface KnowledgeGap {
  messageId: string;
  /** PII masked by the server. */
  question: string | null;
  outcome: string | null;
  refusalReason: string | null;
  askedAt: string;
  upvotes: number;
  downvotes: number;
  comments: { vote: number; comment: string | null }[];
  status: 'open' | 'resolved';
  resolvedAt: string | null;
  resolutionNote: string | null;
}
