// Document Types - Full Document Management System

export interface ExistingDocumentInfo {
  documentId: string;
  originalFilename: string;
  fileSizeBytes: number;
  createdAt: string;
  title: string | null;
  categorySlug: string | null;
  status: string;
  fileChecksum: string | null;
}

export interface DuplicateCheckResponse {
  isDuplicate: boolean;
  action: 'BLOCK' | 'SUGGEST_VERSION' | null;
  existingDocument: ExistingDocumentInfo | null;
  similarity: number | null;
  detectionMethod: string | null;
}

export interface ConfirmResultResponse {
  status: 'READY' | 'DUPLICATE' | 'NEAR_DUPLICATE';
  chunkCount: number | null;
  nearDuplicateOf: ExistingDocumentInfo | null;
  similarity: number | null;
}

export interface Document {
  id: string;
  title?: string;
  description?: string;
  originalFilename: string;
  fileName: string;
  fileSize: number;
  fileSizeBytes?: number;
  fileType: FileType;
  mimeType?: string;
  status: ProcessingStatus;
  currentVersion: number;
  pageCount?: number;
  wordCount?: number;
  language: string;
  bucketName?: string;
  fileKey?: string;
  downloadUrl?: string;
  ocrRequired?: boolean;
  ocrConfidence?: number;
  chunkingStrategy?: ChunkingStrategy;
  chunkSize?: number;
  chunkOverlap?: number;
  embeddingModel?: EmbeddingModel;
  uploadedBy?: string;
  uploadedByName?: string;
  category?: string;
  categoryName?: string;
  categoryId?: string;
  tags?: string[];
  department?: string;
  departmentName?: string;
  departmentId?: string;
  accessLevel?: AccessLevel;
  effectiveDate?: string;
  expireDate?: string;
  version?: number;
  uploadedAt: string;
  createdAt: string;
  updatedAt: string;
  processedAt?: string;
  deletedAt?: string;
}

export interface DocumentVersion {
  id: string;
  documentId: string;
  versionNumber: number;
  version?: number;
  fileKey: string;
  fileName?: string;
  fileSize: number;
  fileSizeBytes?: number;
  fileType?: FileType;
  changelog: string;
  changesDescription?: string;
  createdBy?: string;
  uploadedBy?: string;
  uploadedByName?: string;
  createdAt: string;
  uploadedAt?: string;
}

export interface DocumentMetadata {
  id: string;
  documentId: string;
  title: string;
  description?: string;
  category?: string;
  categoryName?: string;
  tags: string[];
  effectiveDate?: string;
  expireDate?: string;
  status: DocumentStatus;
  accessLevel: AccessLevel;
  department?: string;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentDetail extends Document {
  versions: DocumentVersion[];
  metadata?: DocumentMetadata;
}

export interface DocumentSearchParams {
  page?: number;
  size?: number;
  limit?: number;
  search?: string;
  keyword?: string;
  fileType?: string;
  status?: string;
  categoryId?: string;
  uploadedBy?: string;
  startDate?: string;
  endDate?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface DocumentListResponse {
  data: Document[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

export interface DocumentUploadResponse {
  id: string;
  originalFilename: string;
  fileType: string;
  fileSizeBytes: number;
  mimeType: string;
  status: ProcessingStatus;
  currentVersion: number;
  language: string;
  createdAt: string;
  updatedAt: string;
  suggestedLanguage?: string | null;
  suggestedCategorySlug?: string | null;
  suggestedTitle?: string | null;
  suggestedDescription?: string | null;
  suggestedTags?: string[];
  suggestedIsPolicy?: boolean | null;
}

export interface UploadDocumentRequest {
  file: File;
  title?: string;
  description?: string;
  categorySlug?: string;
  tags?: string[];
  language?: string;
  isPolicy?: boolean;
  effectiveDate?: string;
  expireDate?: string;
  changelog?: string;
}

// Category Types
export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  parentId?: string;
  parentName?: string;
  icon?: string;
  displayOrder?: number;
  isActive?: boolean;
  documentCount?: number;
  createdAt: string;
  updatedAt?: string;
  children?: Category[];
}

export interface CategoryTree {
  id: string;
  name: string;
  slug: string;
  description?: string;
  parentId?: string;
  icon?: string;
  displayOrder?: number;
  isActive?: boolean;
  createdAt: string;
  updatedAt?: string;
  children: CategoryTree[];
}

// Tag Types
export interface Tag {
  id: string;
  name: string;
  slug: string;
  color?: string;
  icon?: string;
  usageCount?: number;
  createdAt?: string;
}

export interface TagSearchResponse {
  data: Tag[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

// Access Rule Types
export interface AccessRule {
  id: string;
  documentMetadataId: string;
  targetType: 'ROLE' | 'DEPARTMENT' | 'USER';
  targetRole?: string;
  targetDepartmentId?: string;
  targetDepartmentName?: string;
  targetUserId?: string;
  targetUserName?: string;
  permission: 'VIEW' | 'DENY';
  createdBy?: string;
  createdAt: string;
}

export interface CreateAccessRuleRequest {
  documentId?: string;
  documentMetadataId?: string;
  targetType: 'ROLE' | 'DEPARTMENT' | 'USER';
  targetRole?: string;
  targetDepartmentId?: string;
  targetUserId?: string;
  permission: 'VIEW' | 'DENY';
}

// Audit Log Types
export interface AuditLog {
  id: string;
  documentId?: string;
  action: string;
  actorId?: string;
  actorUsername?: string;
  oldValues?: Record<string, unknown>;
  newValues?: Record<string, unknown>;
  ipAddress?: string;
  userAgent?: string;
  createdAt: string;
}

export interface AuditLogResponse {
  data: AuditLog[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
}

// Enums
export enum FileType {
  PDF = 'PDF',
  DOCX = 'DOCX',
  DOC = 'DOC',
  XLSX = 'XLSX',
  XLS = 'XLS',
  TXT = 'TXT',
  PNG = 'PNG',
  JPG = 'JPG',
  JPEG = 'JPEG',
  MD = 'MD',
  UNKNOWN = 'UNKNOWN',
}

export enum ProcessingStatus {
  STAGING = 'STAGING',
  UPLOADED = 'UPLOADED',
  PARSING = 'PARSING',
  PARSED = 'PARSED',
  CHUNKING = 'CHUNKING',
  CHUNKED = 'CHUNKED',
  EMBEDDING = 'EMBEDDING',
  EMBEDDED = 'EMBEDDED',
  INDEXING = 'INDEXING',
  INDEXED = 'INDEXED',
  READY = 'READY',
  FAILED = 'FAILED',
  CANCELLED = 'CANCELLED',
  DUPLICATE = 'DUPLICATE',
}

export enum DocumentStatus {
  DRAFT = 'DRAFT',
  PUBLISHED = 'PUBLISHED',
  ARCHIVED = 'ARCHIVED',
  EXPIRED = 'EXPIRED',
}

export enum AccessLevel {
  PUBLIC = 'PUBLIC',
  DEPARTMENT_ONLY = 'DEPARTMENT_ONLY',
  RESTRICTED = 'RESTRICTED',
}

export enum ChunkingStrategy {
  SENTENCE = 'SENTENCE',
  PARAGRAPH = 'PARAGRAPH',
  PAGE = 'PAGE',
  FIXED_SIZE = 'FIXED_SIZE',
  RECURSIVE = 'RECURSIVE',
}

export enum EmbeddingModel {
  MULTILINGUAL_E5 = 'MULTILINGUAL_E5',
  SENTENCE_BERT = 'SENTENCE_BERT',
  OPENAI_ADA = 'OPENAI_ADA',
}

// Action types for audit logs
export enum DocumentAction {
  UPLOAD = 'UPLOAD',
  VERSION_CREATED = 'VERSION_CREATED',
  METADATA_UPDATED = 'METADATA_UPDATED',
  SOFT_DELETE = 'SOFT_DELETE',
  CANCEL_UPLOAD = 'CANCEL_UPLOAD',
  PROCESSING_STARTED = 'PROCESSING_STARTED',
  PROCESSING_COMPLETED = 'PROCESSING_COMPLETED',
  PROCESSING_FAILED = 'PROCESSING_FAILED',
  PUBLISHED = 'PUBLISHED',
  ARCHIVED = 'ARCHIVED',
}

// File type display names and icons
export const FILE_TYPE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  PDF: { label: 'PDF', color: '#ef4444', icon: '📄' },
  DOCX: { label: 'Word', color: '#2563eb', icon: '📝' },
  DOC: { label: 'Word', color: '#2563eb', icon: '📝' },
  XLSX: { label: 'Excel', color: '#16a34a', icon: '📊' },
  XLS: { label: 'Excel', color: '#16a34a', icon: '📊' },
  TXT: { label: 'Text', color: '#6b7280', icon: '📃' },
  PNG: { label: 'Image', color: '#8b5cf6', icon: '🖼️' },
  JPG: { label: 'Image', color: '#8b5cf6', icon: '🖼️' },
  JPEG: { label: 'Image', color: '#8b5cf6', icon: '🖼️' },
  UNKNOWN: { label: 'File', color: '#6b7280', icon: '📁' },
};

// Status display names and colors
export const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  STAGING: { label: 'Chờ xác nhận', color: '#f59e0b' },
  UPLOADED: { label: 'Đã tải lên', color: '#3b82f6' },
  PARSING: { label: 'Đang phân tích', color: '#8b5cf6' },
  PARSED: { label: 'Đã phân tích', color: '#06b6d4' },
  CHUNKING: { label: 'Đang chia nhỏ', color: '#8b5cf6' },
  CHUNKED: { label: 'Đã chia nhỏ', color: '#06b6d4' },
  EMBEDDING: { label: 'Đang tạo vector', color: '#8b5cf6' },
  EMBEDDED: { label: 'Đã tạo vector', color: '#06b6d4' },
  INDEXING: { label: 'Đang lập chỉ mục', color: '#8b5cf6' },
  INDEXED: { label: 'Đã lập chỉ mục', color: '#06b6d4' },
  READY: { label: 'Sẵn sàng', color: '#22c55e' },
  FAILED: { label: 'Thất bại', color: '#ef4444' },
  CANCELLED: { label: 'Đã hủy', color: '#6b7280' },
  DUPLICATE: { label: 'Trùng lặp', color: '#ef4444' },
  DRAFT: { label: 'Nháp', color: '#6b7280' },
  PUBLISHED: { label: 'Đã xuất bản', color: '#22c55e' },
  ARCHIVED: { label: 'Đã lưu trữ', color: '#f59e0b' },
  EXPIRED: { label: 'Hết hạn', color: '#ef4444' },
};

// Helper functions
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatDateWithSeconds(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

export function getFileTypeConfig(type: string): { label: string; color: string; icon: string } {
  return FILE_TYPE_CONFIG[type] || FILE_TYPE_CONFIG.UNKNOWN;
}

export function getStatusConfig(status: string): { label: string; color: string } {
  return STATUS_CONFIG[status] || { label: status, color: '#6b7280' };
}
