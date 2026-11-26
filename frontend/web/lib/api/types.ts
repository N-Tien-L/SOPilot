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

export interface CitationChunk {
  subN: string;
  chunkId: string;
  sectionPath: string[];
  page: number | null;
  charStart: number;
  charEnd: number;
  snippet: string;
}

export interface Citation {
  n: number;
  documentId: string;
  versionId: string;
  title: string;
  page: number | null;
  charStart: number;
  charEnd: number;
  snippet: string;
  sectionPath?: string[];
  chunks?: CitationChunk[];
}

export interface AnswerWarning {
  code: string;
  values: string[];
}

export type PipelineStageId =
  | 'input_pii'
  | 'guard_rule'
  | 'classify_route'
  | 'rewrite_translate'
  | 'retrieve_dense'
  | 'retrieve_sparse'
  | 'retrieve_rrf'
  | 'retrieve_rerank'
  | 'context_prompt'
  | 'llm_generate'
  | 'post_checks';

export type PipelineStepStatus = 'pending' | 'running' | 'passed' | 'blocked' | 'skipped' | 'error';

export interface PipelineDecision {
  kind: string;
  outcome: string | null;
  reason: string | null;
  ruleId?: string | null;
  templateKey?: string | null;
}

export interface StageChunkRef {
  chunkId: string;
  rank: number;
  score: number;
  source?: 'orig' | 'alt' | 'both';
  docCodeMatch?: boolean;
  inPool?: boolean;
}

export interface StageChunkBody {
  chunkId: string;
  documentId: string;
  versionId: string;
  title: string | null;
  sectionPath: string[];
  page: number | null;
  chunkType: string;
  tokenCount: number;
  preview: string;
  content: string;
}

export interface RetrievedChunkTrace {
  rank: number;
  chunkId: string;
  documentId: string;
  versionId: string;
  title: string | null;
  sectionPath: string[];
  page: number | null;
  chunkType: string;
  tokenCount: number;
  denseScore: number | null;
  bm25Score: number | null;
  fusionScore: number | null;
  rerankScore: number | null;
  docCodeMatch: boolean;
  inContext: boolean;
  preview: string;
  content: string;
  source?: 'orig' | 'alt' | 'both';
  inPool?: boolean;
}

export interface ContextSourceTrace {
  n: number;
  documentId: string;
  versionId: string;
  title?: string | null;
  page?: number | null;
  sectionPath?: string[];
  tokens?: number;
  reduced?: boolean;
  hitChunkCount?: number;
  chunkCount?: number;
  code?: string | null;
  rev?: string | null;
  effective?: string | null;
}

export interface PromptMessageTrace {
  role: string;
  content: string;
}

export interface PipelineStepEntry {
  step: string;
  stage: PipelineStageId;
  status: PipelineStepStatus;
  durationMs?: number | null;
  decision?: PipelineDecision | null;
  summary?: string;
  detail?: Record<string, unknown>;
}

export interface PipelineTrace {
  version: number;
  messageId: string | null;
  conversationId: string | null;
  question?: string;
  mode: string;
  lang: string;
  outcome: string | null;
  refusalReason: string | null;
  totalMs: number | null;
  disclaimers?: string[];
  reconstructed?: boolean;
  hidden?: boolean;
  hiddenReason?: HiddenReason | string | null;
  steps: PipelineStepEntry[];
  chunks: RetrievedChunkTrace[];
  stageChunks?: Record<string, StageChunkBody>;
  promptMessages: PromptMessageTrace[] | null;
  live?: boolean;
}

export type StreamEvent =
  | { type: 'meta'; conversationId: string; messageId: string; mode: string; lang: string }
  | {
      type: 'step';
      step: string;
      stage: PipelineStageId;
      status: PipelineStepStatus;
      durationMs?: number;
      decision?: PipelineDecision | null;
      summary?: string;
      detail?: Record<string, unknown>;
    }
  // The model's reasoning, before the first `delta` (TECH-V2-ai-service §7.2). Absent when thinking is off.
  | { type: 'reasoning'; text: string }
  | { type: 'reasoning_done'; durationMs: number }
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
  /** Who drafted the content (a department, a person or a source); the publisher is `createdBy`. */
  preparedBy: string | null;
  category: { id: string; name: string } | null;
  tags: string[];
  language: string | null;
  visibility: DocumentVisibility | string;
  /** Null for plain members (masked). */
  departments: { id: string; name: string | null }[] | null;
  /** Managers and the responsible publisher only; null for other readers. */
  ownerDepartment?: { id: string; name: string | null } | null;
  /** Null for readers without the administrative view: its presence marks who may edit. */
  fieldSources?: FieldSources | null;
  suggestions?: DocumentSuggestions | null;
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
    /** Extracted automatically; may be wrong (V2-25), read-only in the UI. */
    docCode?: string | null;
    revisionLabel?: string | null;
    effectiveDate?: string | null;
    warningCodes: string[];
  } | null;
  createdBy: { id: string; displayName: string };
  createdAt: string;
  updatedAt: string;
}

export type ArchiveStatus = 'ACTIVE' | 'ARCHIVED';

/** `GET /categories` (core-api CategoryController). `{id, name}` is all a document carries. */
export interface CategoryView {
  id: string;
  name: string;
  status?: ArchiveStatus;
}

export interface DepartmentView {
  id: string;
  name: string;
  status: ArchiveStatus;
  createdAt: string;
}

export interface TagView {
  id: string;
  name: string;
}

/** `POST /invitations`: `inviteUrl` carries the secret token and is returned once only. */
export interface CreatedInvitation {
  id: string;
  expiresAt: string;
  inviteUrl: string;
}

export interface PublisherRef {
  userId: string;
  displayName: string;
}

/** `GET /publishers` (ADR-009): who publishes for the whole workspace and for each department. */
export interface PublishersOverview {
  workspace: PublisherRef | null;
  departments: { departmentId: string; name: string; publisher: PublisherRef | null }[];
}

export interface AuditEntry {
  id: string;
  actorId: string | null;
  action: string;
  targetType: string | null;
  targetId: string | null;
  details: Record<string, unknown> | null;
  traceId: string | null;
  createdAt: string;
}

/** How a metadata field got its value (`DocumentView.fieldSources`). */
export type FieldSource = 'USER' | 'SUGGESTED' | 'SYSTEM' | string;

export interface FieldSources {
  title: FieldSource;
  description: FieldSource;
  category: FieldSource;
  tags: FieldSource;
  language: FieldSource;
}

/** Stored suggestions that are never applied automatically (V2-25). */
export interface DocumentSuggestions {
  title: string | null;
  proposedCategoryName: string | null;
}

export type DocumentVisibility = 'WORKSPACE' | 'DEPARTMENTS';

/** `PUT /documents/{id}/visibility`: `PENDING` while the change is still reaching ai-service. */
export interface VisibilityResponse {
  accessSync: 'APPLIED' | 'PENDING' | string;
}

/** `PUT /documents/{id}/ownership`: `publisherAssigned` is false when nobody can write in the new scope. */
export interface OwnershipResponse extends VisibilityResponse {
  publisherAssigned: boolean;
}

export interface DownloadUrl {
  url: string;
  expiresAt: string;
}

// ---- ai-service resources (TECH-V2-ai-service §7) ----

/** `GET /ai/v1/documents/{id}/versions/{versionId}/content` (§7.3), active version only. */
export interface ContentPage {
  page: number;
  /** Unicode code points (Python indexes). */
  charStart: number;
  charEnd: number;
  /** UTF-16 code units: the ones a browser string uses. */
  charStart16: number;
  charEnd16: number;
}

export interface ContentWarning {
  code: string;
  pages?: number[];
  count?: number;
}

export interface RemovedBlock {
  kind: string | null;
  page: number | null;
  text: string | null;
}

export interface DocumentContent {
  documentId: string;
  versionId: string;
  fileType: string;
  normalizerVersion: string;
  markdown: string;
  pages: ContentPage[];
  warnings: ContentWarning[];
  removedBlocks: RemovedBlock[];
}

// ---- processing report (V2-46, TECH-V2-ai-service §7.7) ----
export type DocFamily = 'LEGAL_ARTICLES' | 'ISO_PROCEDURE' | 'MARKDOWN' | 'PROSE';
export type ChunkType = 'SECTION' | 'PROCEDURE_STEP' | 'TABLE' | 'PROSE';

export interface FamilySignals {
  headings: number;
  articleHeadings: number;
  /** Body lines that open like an article ("Điều 3. ..."): a short decision has no article headings. */
  articleLines: number;
  sopSectionWords: string[];
  procedureTables: number;
}

export interface ProcessingChunk {
  ordinal: number;
  chunkType: ChunkType;
  sectionPath: string[];
  pageStart: number | null;
  pageEnd: number | null;
  /** Unicode code points on the canonical Markdown. Ranges can repeat (split rows and steps). */
  charStart: number;
  charEnd: number;
  tokenCount: number;
}

export interface ProcessingReport {
  documentId: string;
  versionId: string;
  fileType: string;
  language: string | null;
  docCode: string | null;
  pageCount: number | null;
  family: DocFamily;
  /** Recomputed from the stored structure; null when it could not be read. */
  signals: FamilySignals | null;
  strategy: {
    rules: string[];
    /** The current `models.yaml` values, not stored per version. */
    config: { targetTokens: number; maxTokens: number; minTokens: number };
  };
  stats: { chunks: number; avgTokens: number; maxTokens: number; byType: Partial<Record<ChunkType, number>> };
  chunks: ProcessingChunk[];
}

export interface ChunkDetail {
  ordinal: number;
  chunkType: ChunkType;
  sectionPath: string[];
  tokenCount: number;
  content: string;
  indexText: string;
}

/** GET /ai/v1/retrieval/options (V2-48). */
export interface RetrievalOptions {
  rerank: { available: boolean };
}

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
