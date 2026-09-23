/**
 * Document Management Service
 * Handles all document-related API calls including:
 * - CRUD operations (upload, list, get, delete)
 * - Versioning (upload new version, list versions)
 * - Download (streaming and signed URL)
 * - Audit logs
 * - Search and filter
 *
 * NOTE: Uses XHR for multipart uploads through the gateway.
 * All other methods use the public api.documents.*, api.metadata.* wrappers.
 */

import { api } from '@/lib/api';
import type {
  Document as KnowledgeDocument,
  DocumentDetail,
  DocumentVersion,
  DocumentSearchParams,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentMetadata,
  Category,
  CategoryTree,
  Tag,
  AccessRule,
  CreateAccessRuleRequest,
  AuditLog,
  AuditLogResponse,
  DuplicateCheckResponse,
  ConfirmResultResponse,
  ExistingDocumentInfo,
} from '@/types/document';

const KNOWLEDGE_SERVICE_URL =
  typeof window === 'undefined'
    ? 'http://knowledge-service:8083'
    : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001'}`;

const METADATA_SERVICE_URL =
  typeof window === 'undefined'
    ? 'http://metadata-service:8084'
    : 'http://localhost:8084';

// ============ Document CRUD ============

export const documentService = {
  /**
   * Get paginated list of documents with filters
   */
  async getDocuments(params: DocumentSearchParams = {}): Promise<DocumentListResponse> {
    const result = await api.documents.getAll(params);
    return {
      data: result.data,
      page: result.pagination.page,
      limit: result.pagination.limit,
      total: result.pagination.total,
      totalPages: result.pagination.totalPages,
    };
  },

  /**
   * Get document detail with versions
   */
  async getDocumentById(id: string): Promise<DocumentDetail> {
    return await api.documents.getById(id) as DocumentDetail;
  },

  /**
   * Upload a new document
   * Upload through gateway multipart endpoint
   */
  async uploadDocument(
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<DocumentUploadResponse> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          const percent = Math.round((e.loaded / e.total) * 100);
          onProgress(percent);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response.data || response);
          } catch {
            resolve(JSON.parse(xhr.responseText));
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.message || 'Upload failed'));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      const token = localStorage.getItem('accessToken');
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
      xhr.open('POST', `${apiUrl}/api/v1/documents/upload`);
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);
    });
  },

  /**
   * Upload new version of existing document
   */
  async uploadNewVersion(
    documentId: string,
    file: File,
    changelog: string,
    onProgress?: (percent: number) => void
  ): Promise<DocumentVersion> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();
      formData.append('file', file);
      formData.append('changelog', changelog);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && onProgress) {
          const percent = Math.round((e.loaded / e.total) * 100);
          onProgress(percent);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response.data || response);
          } catch {
            resolve(JSON.parse(xhr.responseText));
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.message || 'Version upload failed'));
          } catch {
            reject(new Error(`Version upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during version upload'));
      });

      const token = localStorage.getItem('accessToken');
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
      xhr.open('POST', `${apiUrl}/api/v1/documents/${documentId}/versions`);
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.send(formData);
    });
  },

  /**
   * Confirm document metadata after upload (STAGING → READY)
   */
  async confirmMetadata(
    documentId: string,
    data: {
      title: string;
      description?: string;
      categorySlug?: string;
      tags?: string[];
      language: string;
      isPolicy: boolean;
    }
  ): Promise<DocumentUploadResponse> {
    return await api.documents.confirmMetadata(documentId, {
      title: data.title,
      description: data.description || '',
      categorySlug: data.categorySlug || '',
      tags: data.tags || [],
      language: data.language,
      isPolicy: data.isPolicy,
    });
  },

  /**
   * Cancel upload (STAGING only)
   */
  async cancelUpload(documentId: string): Promise<void> {
    await api.documents.cancel(documentId);
  },

  /**
   * Soft delete document
   */
  async deleteDocument(documentId: string): Promise<void> {
    await api.documents.delete(documentId);
  },

  /**
   * Download document as blob (latest version)
   */
  async downloadDocument(documentId: string, filename: string, version?: number): Promise<void> {
    const ver = version || 1;
    const token = localStorage.getItem('accessToken');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/documents/${documentId}/versions/${ver}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`Download failed: ${res.status}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(new Blob([blob]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `v${ver}-${filename}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  /**
   * Get signed download URL
   */
  async getDownloadUrl(documentId: string): Promise<string> {
    // Direct fetch to avoid interceptor wrapping issues
    const token = localStorage.getItem('accessToken');
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001'}/api/v1/documents/${documentId}/url`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    return data.url || data.data?.url || '';
  },

  /**
   * Get preview URL for document (specific version)
   * Uses the /preview endpoint to return binary data as a blob URL for iframe embedding.
   * Works for all file types including DOCX (no need for Google Docs Viewer).
   */
  async getPreviewUrl(documentId: string, version?: number): Promise<string> {
    const ver = version || 1;
    const token = localStorage.getItem('accessToken');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

    // Fetch as blob and create object URL
    const res = await fetch(`${apiUrl}/api/v1/documents/${documentId}/versions/${ver}/preview`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`Preview failed: ${res.status}`);
    const blob = await res.blob();
    return window.URL.createObjectURL(blob);
  },

  /**
   * Download specific version
   */
  async downloadVersion(
    documentId: string,
    versionNumber: number,
    filename: string
  ): Promise<void> {
    const token = localStorage.getItem('accessToken');
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001'}/api/v1/documents/${documentId}/versions/${versionNumber}/download`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!res.ok) throw new Error(`Download failed: ${res.status}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(new Blob([blob]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `v${versionNumber}-${filename}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  // ============ Version Management ============



  async getVersions(documentId: string): Promise<DocumentVersion[]> {
    return await (api.documents.getVersions(documentId) as unknown) as DocumentVersion[];
  },



  // ============ Audit Logs ============

  /**
   * Get audit logs for a document
   */
  async getAuditLogs(
    documentId: string,
    params: {
      page?: number;
      limit?: number;
      action?: string;
      actorId?: string;
      startDate?: string;
      endDate?: string;
    } = {}
  ): Promise<AuditLogResponse> {
    const res = await api.audit.search({
      page: params.page ?? 0,
      limit: params.limit || 20,
      resourceType: 'DOCUMENT',
      resourceId: documentId,
      action: params.action,
      userId: params.actorId,
      startDate: params.startDate,
      endDate: params.endDate,
    });
    return {
      data: res.data as AuditLog[],
      page: res.pagination.page,
      limit: res.pagination.limit,
      total: res.pagination.total,
      totalPages: res.pagination.totalPages,
    };
  },

  // ============ Search ============

  /**
   * Search documents by keyword (full-text search)
   */
  async searchDocuments(keyword: string, limit = 20): Promise<KnowledgeDocument[]> {
    const result = await api.documents.getAll({ keyword, limit });
    return result.data;
  },

  /**
   * Get extracted text content of a document
   */
  async getDocumentContent(documentId: string, version?: number): Promise<string> {
    return await api.documents.getContent(documentId, version);
  },

  /**
   * Trigger document processing (parsing, chunking, embedding)
   */
  async triggerProcess(documentId: string): Promise<void> {
    await api.documents.triggerProcess(documentId);
  },

  // ============ Duplicate Check ============

  /**
   * Check if a file (by SHA-256 checksum) is a duplicate before confirming.
   * Called after upload, parallel to displaying the metadata form.
   */
  async checkDuplicate(fileChecksum: string): Promise<DuplicateCheckResponse> {
    const token = localStorage.getItem('accessToken');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(
      `${apiUrl}/api/v1/documents/check-duplicate?checksum=${encodeURIComponent(fileChecksum)}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!res.ok) throw new Error(`Check duplicate failed: ${res.status}`);
    return res.json();
  },

  /**
   * Confirm metadata and wait for sync ingestion result.
   * Returns ConfirmResultResponse with status READY, DUPLICATE, or NEAR_DUPLICATE.
   * Throws on HTTP 409 (duplicate).
   */
  async confirmMetadataSync(
    documentId: string,
    data: {
      title: string;
      description?: string;
      categorySlug?: string;
      tags?: string[];
      language: string;
      isPolicy: boolean;
      fileChecksum?: string;
    }
  ): Promise<ConfirmResultResponse> {
    const token = localStorage.getItem('accessToken');
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/documents/${documentId}/confirm`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        title: data.title,
        description: data.description || '',
        categorySlug: data.categorySlug || '',
        tags: data.tags || [],
        language: data.language,
        isPolicy: data.isPolicy,
        fileChecksum: data.fileChecksum,
      }),
    });

    if (res.status === 409) {
      const error = await res.json();
      const err = new Error(error.message || 'Duplicate document') as Error & {
        status: number;
        code: string;
        existingDocument: ExistingDocumentInfo;
      };
      err.status = 409;
      err.code = error.code;
      err.existingDocument = error.existingDocument;
      throw err;
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ message: 'Confirm failed' }));
      throw new Error(error.message || `Confirm failed: ${res.status}`);
    }
    return res.json();
  },
};

// ============ Category Management ============

export const categoryService = {
  /**
   * Get all active categories
   */
  async getCategories(): Promise<Category[]> {
    const cats = await api.metadata.getCategories();
    return cats as Category[];
  },

  /**
   * Get category tree (hierarchical structure)
   */
  async getCategoryTree(): Promise<CategoryTree[]> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(
      `${apiUrl}/api/v1/categories/active/tree`,
      { headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` } }
    );
    const data = await res.json();
    return (data.data || data) as CategoryTree[];
  },

  /**
   * Get category children by parent ID
   */
  async getCategoryChildren(parentId?: string): Promise<Category[]> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const url = parentId
      ? `${apiUrl}/api/v1/categories/active/children/${parentId}`
      : `${apiUrl}/api/v1/categories/active/children`;
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const data = await res.json();
    return (data.data || data) as Category[];
  },

  /**
   * Get category by ID
   */
  async getCategoryById(id: string): Promise<Category> {
    return await api.metadata.getCategoryById(id) as Category;
  },

  /**
   * Get category by slug
   */
  async getCategoryBySlug(slug: string): Promise<Category> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/categories/slug/${slug}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const data = await res.json();
    return (data.data || data) as Category;
  },

  /**
   * Create new category (ADMIN only)
   */
  async createCategory(data: {
    name: string;
    description?: string;
    parentId?: string;
    icon?: string;
    displayOrder?: number;
  }): Promise<Category> {
    return await api.metadata.createCategory({
      name: data.name,
      description: data.description,
      parentId: data.parentId,
      displayOrder: data.displayOrder,
    }) as Category;
  },

  /**
   * Update category (ADMIN only)
   */
  async updateCategory(
    id: string,
    data: {
      name?: string;
      description?: string;
      parentId?: string;
      icon?: string;
      displayOrder?: number;
    }
  ): Promise<Category> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/categories/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
      },
      body: JSON.stringify({
        name: data.name,
        description: data.description,
        parentId: data.parentId,
        displayOrder: data.displayOrder,
      }),
    });
    const result = await res.json();
    return (result.data || result) as Category;
  },

  /**
   * Delete category (ADMIN only) - soft delete
   */
  async deleteCategory(id: string): Promise<void> {
    await api.metadata.deleteCategory(id);
  },

  /**
   * Resolve category slug to ID
   */
  async resolveSlug(slug: string): Promise<string | null> {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
      const res = await fetch(`${apiUrl}/api/v1/categories/resolve/${slug}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
      });
      const data = await res.json();
      return data.categoryId || data.data?.categoryId || null;
    } catch {
      return null;
    }
  },
};

// ============ Tag Management ============

export const tagService = {
  /**
   * Get all tags
   */
  async getTags(): Promise<Tag[]> {
    const tags = await api.metadata.getTags();
    return tags as Tag[];
  },

  /**
   * Get popular tags
   */
  async getPopularTags(limit = 20): Promise<Tag[]> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/tags/popular?limit=${limit}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const data = await res.json();
    return (data.data || data) as Tag[];
  },

  /**
   * Search tags by keyword
   */
  async searchTags(keyword: string, page = 1, limit = 20): Promise<{
    data: Tag[];
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  }> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(
      `${apiUrl}/api/v1/tags/search?keyword=${encodeURIComponent(keyword)}&page=${page}&size=${limit}`,
      { headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` } }
    );
    const data = await res.json();
    return data;
  },

  /**
   * Get tag by ID
   */
  async getTagById(id: string): Promise<Tag> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/tags/${id}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const data = await res.json();
    return (data.data || data) as Tag;
  },

  /**
   * Create new tag (ADMIN only)
   */
  async createTag(data: { name: string; color?: string }): Promise<Tag> {
    return await api.metadata.createTag({ name: data.name, color: data.color }) as Tag;
  },

  /**
   * Update tag (ADMIN only)
   */
  async updateTag(id: string, data: { name?: string; color?: string }): Promise<Tag> {
    return await api.metadata.updateTag(id, { name: data.name, color: data.color }) as Tag;
  },

  /**
   * Delete tag (ADMIN only)
   */
  async deleteTag(id: string): Promise<void> {
    await api.metadata.deleteTag(id);
  },

  /**
   * Resolve tags - find or create (ADMIN/MANAGER)
   */
  async resolveTags(tagNames: string[]): Promise<Map<string, string>> {
    const tags = await api.metadata.resolveTags(tagNames);
    return new Map(tags.map((t) => [t.name, t.id]));
  },
};

// ============ Access Rule Management ============

export const accessRuleService = {
  /**
   * Get all access rules (for admin dashboard)
   */
  async getAllRules(): Promise<AccessRule[]> {
    const res = await api.metadata.getAllAccessRules();
    return res as AccessRule[];
  },

  /**
   * Get access rules by document ID (uses metadata lookup)
   */
  async getRulesByDocumentId(documentId: string): Promise<AccessRule[]> {
    const res = await api.metadata.getAccessRulesByDocumentId(documentId);
    return res as AccessRule[];
  },

  /**
   * Get access rules for a document metadata
   */
  async getRules(metadataId: string): Promise<AccessRule[]> {
    const res = await api.metadata.getAccessRules(metadataId);
    return res as AccessRule[];
  },

  /**
   * Add access rule to document (ADMIN only) - uses documentId
   */
  async addRule(documentId: string, rule: CreateAccessRuleRequest): Promise<AccessRule> {
    const result = await api.metadata.createAccessRule({ documentId, ...rule });
    return result as AccessRule;
  },

  /**
   * Update an existing access rule (ADMIN only)
   */
  async updateRule(ruleId: string, rule: {
    targetType: 'ROLE' | 'DEPARTMENT' | 'USER';
    targetRole?: string;
    targetDepartmentId?: string;
    targetUserId?: string;
    permission: 'VIEW' | 'DENY';
  }): Promise<AccessRule> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/access-rules/${ruleId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
      },
      body: JSON.stringify(rule),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ message: 'Update failed' }));
      throw new Error(error.message || `Update failed with status ${res.status}`);
    }
    const data = await res.json();
    return (data.data || data) as AccessRule;
  },

  /**
   * Delete access rule (ADMIN only)
   */
  async deleteRule(ruleId: string): Promise<void> {
    await api.metadata.deleteAccessRule(ruleId);
  },

  /**
   * Simulate access — preview who in the company has access to a document (ADMIN only)
   */
  async simulateAccess(documentId: string): Promise<{
    documentId: string;
    metadataId: string;
    totalCompanyUsers: number;
    usersWithAccess: number;
    usersWithoutAccess: number;
    grantedUsers: Array<{
      userId: string;
      username: string;
      fullName: string | null;
      role: string | null;
      departmentId: string;
      departmentName: string;
      hasAccess: boolean;
      reason: string;
      simulatedAt: string;
    }>;
    deniedUsers: Array<{
      userId: string;
      username: string;
      fullName: string | null;
      role: string | null;
      departmentId: string;
      departmentName: string;
      hasAccess: boolean;
      reason: string;
      simulatedAt: string;
    }>;
    simulatedAt: string;
  }> {
    return await api.metadata.simulateAccess(documentId);
  },
};

// ============ Document Metadata ============

export const documentMetadataService = {
  /**
   * Get document metadata
   */
  async getMetadata(id: string): Promise<DocumentMetadata> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/metadata/${id}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    const data = await res.json();
    return (data.data || data) as DocumentMetadata;
  },

  /**
   * Get metadata by document ID
   * @throws Error with `status` property if HTTP error occurs (e.g., 404, 500)
   */
  async getMetadataByDocumentId(documentId: string): Promise<DocumentMetadata> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/metadata/document/${documentId}`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}`) as Error & { status: number; statusCode: number };
      error.status = res.status;
      error.statusCode = res.status;
      throw error;
    }
    const data = await res.json();
    return (data.data || data) as DocumentMetadata;
  },

  /**
   * Create document metadata (ADMIN only)
   */
  async createMetadata(data: {
    documentId: string;
    title: string;
    description?: string;
    categoryId?: string;
    tagIds?: string[];
    documentType?: string;
    accessLevel?: string;
    effectiveDate?: string;
    expiryDate?: string;
  }): Promise<DocumentMetadata> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/metadata`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
      },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    return (result.data || result) as DocumentMetadata;
  },

  /**
   * Update document metadata (ADMIN only)
   */
  async updateMetadata(
    id: string,
    data: {
      title?: string;
      description?: string;
      categoryId?: string;
      documentType?: string;
      accessLevel?: string;
      effectiveDate?: string;
      expiryDate?: string;
    }
  ): Promise<DocumentMetadata> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/metadata/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
      },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    return (result.data || result) as DocumentMetadata;
  },

  /**
   * Publish document (ADMIN only)
   */
  async publish(id: string): Promise<void> {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';
    const res = await fetch(`${apiUrl}/api/v1/metadata/${id}/publish`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('accessToken')}` },
    });
    if (!res.ok) throw new Error('Failed to publish document');
  },
};
