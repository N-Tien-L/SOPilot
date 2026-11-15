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
