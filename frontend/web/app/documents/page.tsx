'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  Filter,
  Upload,
  FileText,
  FileSpreadsheet,
  Image,
  File,
  MoreVertical,
  Download,
  Eye,
  Trash2,
  Clock,
  User,
  Tag,
  Grid3X3,
  List,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  X,
  CheckCircle,
  AlertCircle,
  Loader2,
  Shield,
  GitBranch,
} from 'lucide-react';
import {
  documentService,
  categoryService,
  tagService,
  accessRuleService,
} from '@/services/document.service';
import type {
  Document,
  DocumentListResponse,
  Category,
  Tag as TagType,
  FileType,
  ProcessingStatus,
} from '@/types/document';
import {
  formatFileSize,
  formatDate,
  formatDateWithSeconds,
  getFileTypeConfig,
  getStatusConfig,
} from '@/types/document';
import { useAuthStore, useIsAdmin } from '@/store/auth-store';
import { useHydrated } from '@/hooks/useHydrated';
import { useLanguage } from '@/providers';
import { Translator } from '@/lib/i18n';
import { UploadModal } from '@/components/documents/UploadModal';

const PAGE_SIZE = 20;

export default function DocumentsPage() {
  const router = useRouter();
  const { user: authUser } = useAuthStore();
  const isAdmin = useIsAdmin();
  const isHydrated = useHydrated();
  const { t } = useLanguage();

  // State
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Filters
  const [filters, setFilters] = useState<{
    fileType?: string;
    status?: string;
    categoryId?: string;
  }>({});
  const [showFilters, setShowFilters] = useState(false);

  // Filter out DUPLICATE and FAILED documents from display
  const visibleDocuments = documents.filter(
    (doc) => doc.status !== 'DUPLICATE' && doc.status !== 'FAILED'
  );

  // View mode
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Categories and tags for filter dropdowns
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<TagType[]>([]);

  // Upload modal
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Access rules count per document (admin only)
  const [accessRulesCount, setAccessRulesCount] = useState<Record<string, number>>({});

  // Actions menu
  const [actionMenuId, setActionMenuId] = useState<string | null>(null);

  // Load categories and tags on mount
  useEffect(() => {
    loadFilters();
  }, []);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load documents when filters change
  useEffect(() => {
    loadDocuments();
  }, [page, debouncedSearch, filters]);

  const loadFilters = async () => {
    // #region agent log - hypothesis A: useIsAdmin returns different value server vs client
    fetch('http://127.0.0.1:7645/ingest/8709ac07-f78f-4d7a-b7c3-50b684d2d6cd',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6369cb'},body:JSON.stringify({sessionId:'6369cb',id:'log_hydration_001',timestamp:Date.now(),location:'documents/page.tsx:121',message:'loadFilters called',data:{isAdmin,authUserRole:authUser?.role},runId:'debug',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    try {
      const [cats, tgs] = await Promise.all([
        categoryService.getCategories(),
        tagService.getPopularTags(50),
      ]);
      setCategories(cats);
      setTags(tgs);
    } catch (err) {
      console.error('Failed to load filters:', err);
    }
  };

  const loadDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await documentService.getDocuments({
        page,
        size: PAGE_SIZE,
        search: debouncedSearch,
        ...filters,
        sortBy: 'createdAt',
        sortOrder: 'desc',
      });
      setDocuments(response.data || []);
      setTotalPages(response.totalPages);
      setTotal(response.total);

      // Load access rules count for admin view
      if (isAdmin && response.data && response.data.length > 0) {
        const counts: Record<string, number> = {};
        await Promise.all(response.data.map(async (doc) => {
          try {
            const rules = await accessRuleService.getRulesByDocumentId(doc.id);
            counts[doc.id] = rules.length;
          } catch {
            counts[doc.id] = 0;
          }
        }));
        setAccessRulesCount(counts);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (doc: Document) => {
    if (!confirm(t('docs.confirm.delete').replace('{name}', doc.originalFilename))) {
      return;
    }
    try {
      await documentService.deleteDocument(doc.id);
      loadDocuments();
    } catch (err: any) {
      alert(err.message || t('docs.delete.error'));
    }
  };

  const handleDownload = async (doc: Document) => {
    try {
      await documentService.downloadDocument(doc.id, doc.originalFilename);
    } catch (err: any) {
      alert(err.message || 'Failed to download document');
    }
  };

  const handleUploadSuccess = () => {
    setShowUploadModal(false);
    loadDocuments();
    loadFilters();
  };

  const clearFilters = () => {
    setFilters({});
    setPage(1);
  };

  const getFileIcon = (type: string) => {
    const config = getFileTypeConfig(type);
    return config.icon;
  };

  const getStatusLabel = (status: string) => {
    const statusMap: Record<string, string> = {
      READY: t('docs.status.ready'),
      STAGING: t('docs.status.staging'),
      PARSING: t('docs.status.parsing'),
      FAILED: t('docs.status.failed'),
    };
    return statusMap[status] || status;
  };

  // #region agent log - hypothesis A: useIsAdmin returns different value server vs client
  fetch('http://127.0.0.1:7645/ingest/8709ac07-f78f-4d7a-b7c3-50b684d2d6cd',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'6369cb'},body:JSON.stringify({sessionId:'6369cb',id:'log_hydration_002',timestamp:Date.now(),location:'documents/page.tsx:228',message:'Rendering upload button - isAdmin check',data:{isAdmin,authUserRole:authUser?.role},runId:'debug',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card border-b border-border sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{t('docs.title')}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {total > 0 ? t('docs.count').replace('{count}', String(total)) : t('docs.count.none')}
              </p>
            </div>
            {isHydrated && isAdmin && (
              <button
                onClick={() => setShowUploadModal(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-primary-foreground bg-primary hover:bg-primary-strong focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-ring"
              >
                <Upload className="w-4 h-4 mr-2" />
                {t('docs.upload')}
              </button>
            )}
          </div>

          {/* Search and Filters */}
          <div className="mt-4 flex items-center gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder={t('docs.search.placeholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-input rounded-lg focus:ring-2 focus:ring-ring focus:border-primary bg-background text-foreground placeholder:text-placeholder"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`inline-flex items-center px-4 py-2 border rounded-lg text-sm font-medium ${
                showFilters || Object.keys(filters).length > 0
                  ? 'border-primary bg-primary-soft text-primary'
                  : 'border-input bg-card text-foreground hover:bg-muted'
              }`}
            >
              <Filter className="w-4 h-4 mr-2" />
              {t('docs.filter')}
              {Object.keys(filters).length > 0 && (
                <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-primary-soft text-primary">
                  {Object.keys(filters).length}
                </span>
              )}
            </button>
            <div className="flex items-center border border-input rounded-lg overflow-hidden">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 ${viewMode === 'grid' ? 'bg-muted' : 'bg-card hover:bg-muted'}`}
              >
                <Grid3X3 className="w-5 h-5 text-muted-foreground" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 ${viewMode === 'list' ? 'bg-muted' : 'bg-card hover:bg-muted'}`}
              >
                <List className="w-5 h-5 text-muted-foreground" />
              </button>
            </div>
            <button
              onClick={loadDocuments}
              className="p-2 border border-input rounded-lg hover:bg-muted"
              title={t('common.refresh')}
            >
              <RefreshCw className={`w-5 h-5 text-muted-foreground ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Filter Panel */}
          {showFilters && (
            <div className="mt-4 p-4 bg-muted rounded-lg border border-border">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">
                    {t('docs.filter.fileType')}
                  </label>
                  <select
                    value={filters.fileType || ''}
                    onChange={(e) => setFilters({ ...filters, fileType: e.target.value || undefined })}
                    className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring focus:border-primary bg-background text-foreground"
                  >
                    <option value="">{t('docs.filter.all')}</option>
                    <option value="PDF">PDF</option>
                    <option value="DOCX">Word</option>
                    <option value="XLSX">Excel</option>
                    <option value="TXT">Text</option>
                    <option value="PNG">Image</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">
                    {t('docs.filter.status')}
                  </label>
                  <select
                    value={filters.status || ''}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value || undefined })}
                    className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring focus:border-primary bg-background text-foreground"
                  >
                    <option value="">{t('docs.filter.all')}</option>
                    <option value="READY">{t('docs.status.ready')}</option>
                    <option value="STAGING">{t('docs.status.staging')}</option>
                    <option value="PARSING">{t('docs.status.parsing')}</option>
                    <option value="FAILED">{t('docs.status.failed')}</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1">
                    {t('docs.filter.category')}
                  </label>
                  <select
                    value={filters.categoryId || ''}
                    onChange={(e) => setFilters({ ...filters, categoryId: e.target.value || undefined })}
                    className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring focus:border-primary bg-background text-foreground"
                  >
                    <option value="">{t('docs.filter.all')}</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {Object.keys(filters).length > 0 && (
                <div className="mt-4 flex justify-end">
                  <button
                    onClick={clearFilters}
                    className="text-sm text-primary hover:text-primary-strong"
                  >
                    {t('docs.filter.clear')}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading && documents.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
            <span className="ml-2 text-muted-foreground">{t('common.loading')}</span>
          </div>
        ) : error ? (
          <div className="bg-danger-soft border border-danger rounded-lg p-4 flex items-start">
            <AlertCircle className="w-5 h-5 text-danger mt-0.5" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-danger">{t('common.error')}</h3>
              <p className="mt-1 text-sm text-danger">{error}</p>
            </div>
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12">
            <File className="w-12 h-12 text-muted-foreground mx-auto" />
            <h3 className="mt-2 text-sm font-medium text-foreground">{t('docs.empty')}</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {searchQuery || Object.keys(filters).length > 0
                ? t('docs.empty.filtered')
                : t('docs.empty.start')}
            </p>
            {isHydrated && isAdmin && !searchQuery && Object.keys(filters).length === 0 && (
              <button
                onClick={() => setShowUploadModal(true)}
                className="mt-4 inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-primary-foreground bg-primary hover:bg-primary-strong"
              >
                <Upload className="w-4 h-4 mr-2" />
                {t('docs.uploadDocument')}
              </button>
            )}
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {visibleDocuments.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                accessRulesCount={isHydrated && isAdmin ? (accessRulesCount[doc.id] || 0) : 0}
                onView={() => router.push(`/documents/${doc.id}`)}
                onDownload={() => handleDownload(doc)}
                onDelete={isHydrated && isAdmin ? () => handleDelete(doc) : undefined}
                onAction={() => setActionMenuId(actionMenuId === doc.id ? null : doc.id)}
                isActionOpen={actionMenuId === doc.id}
                t={t}
                getStatusLabel={getStatusLabel}
              />
            ))}
          </div>
        ) : (
          <div className="bg-card shadow rounded-lg overflow-hidden border border-border">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {t('docs.table.fileName')}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {t('docs.table.type')}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {t('docs.table.size')}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Version
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {t('docs.table.status')}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {t('docs.table.uploadDate')}
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {t('docs.table.actions')}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {visibleDocuments.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-muted cursor-pointer"
                    onClick={() => router.push(`/documents/${doc.id}`)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <span className="text-2xl mr-3">{getFileIcon(doc.fileType)}</span>
                        <div>
                          <div className="text-sm font-medium text-foreground">
                            {doc.title || doc.originalFilename}
                          </div>
                          <div className="text-xs text-muted-foreground">{doc.originalFilename}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-muted-foreground">
                        {getFileTypeConfig(doc.fileType).label}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {formatFileSize(doc.fileSizeBytes || doc.fileSize || 0)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-muted text-muted-foreground">
                        v{doc.currentVersion}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={doc.status} getStatusLabel={getStatusLabel} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {formatDateWithSeconds(doc.createdAt || doc.uploadedAt)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownload(doc);
                        }}
                        className="text-muted-foreground hover:text-foreground mr-3"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      {isHydrated && isAdmin && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(doc);
                          }}
                          className="text-muted-foreground hover:text-danger"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-6 flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              {t('docs.pagination.showing')
                .replace('{start}', String((page - 1) * PAGE_SIZE + 1))
                .replace('{end}', String(Math.min(page * PAGE_SIZE, total)))
                .replace('{total}', String(total))}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="p-2 border border-input rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span className="text-sm text-muted-foreground">
                {t('docs.pagination.page').replace('{page}', String(page)).replace('{totalPages}', String(totalPages))}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
                className="p-2 border border-input rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <UploadModal
          onClose={() => setShowUploadModal(false)}
          onSuccess={handleUploadSuccess}
          categories={categories}
        />
      )}
    </div>
  );
}

// Document Card Component
function DocumentCard({
  document,
  accessRulesCount,
  onView,
  onDownload,
  onDelete,
  onAction,
  isActionOpen,
  t,
  getStatusLabel,
}: {
  document: Document;
  accessRulesCount?: number;
  onView: () => void;
  onDownload: () => void;
  onDelete?: () => void;
  onAction: () => void;
  isActionOpen: boolean;
  t: Translator;
  getStatusLabel: (status: string) => string;
}) {
  const statusConfig = getStatusConfig(document.status);
  const fileConfig = getFileTypeConfig(document.fileType);

  return (
    <div className="bg-card rounded-lg shadow-sm border border-border hover:shadow-md transition-shadow">
      <div className="p-4" onClick={onView}>
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3">
              <span className="text-3xl">{fileConfig.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate" title={document.title || document.originalFilename}>
                  {document.title || document.originalFilename}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {document.originalFilename}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-2">
            {accessRulesCount !== undefined && accessRulesCount > 0 && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary-soft text-primary"
                title={`${accessRulesCount} access rules`}
              >
                <Shield className="w-3 h-3 mr-1" />
                {accessRulesCount}
              </span>
            )}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAction();
                }}
                className="p-1 rounded hover:bg-muted"
              >
                <MoreVertical className="w-5 h-5 text-muted-foreground" />
              </button>
              {isActionOpen && (
                <div className="absolute right-0 mt-1 w-48 bg-card rounded-lg shadow-lg border border-border z-10">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onView();
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-muted flex items-center"
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    {t('docs.action.viewDetail')}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDownload();
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-muted flex items-center"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    {t('docs.action.download')}
                  </button>
                  {onDelete && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete();
                      }}
                      className="w-full px-4 py-2 text-left text-sm text-danger hover:bg-danger-soft flex items-center"
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      {t('docs.action.delete')}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center">
            <File className="w-3 h-3 mr-1" />
            {formatFileSize(document.fileSizeBytes || document.fileSize || 0)}
          </span>
          <div className="flex items-center gap-3">
            <span className="flex items-center" title={`Version ${document.currentVersion}`}>
              <GitBranch className="w-3 h-3 mr-1" />
              v{document.currentVersion}
            </span>
            <span className="flex items-center">
              <Clock className="w-3 h-3 mr-1" />
              {formatDateWithSeconds(document.createdAt || document.uploadedAt)}
            </span>
          </div>
        </div>

        <div className="mt-3">
          <span
            className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium"
            style={{
              backgroundColor: `${statusConfig.color}20`,
              color: statusConfig.color,
            }}
          >
            {getStatusLabel(document.status)}
          </span>
        </div>

        {document.tags && document.tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1">
            {document.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-muted text-muted-foreground"
              >
                <Tag className="w-3 h-3 mr-1" />
                {tag}
              </span>
            ))}
            {document.tags.length > 3 && (
              <span className="text-xs text-muted-foreground">+{document.tags.length - 3}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Status Badge Component
function StatusBadge({ status, getStatusLabel }: { status: string; getStatusLabel: (status: string) => string }) {
  const config = getStatusConfig(status);
  return (
    <span
      className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium"
      style={{
        backgroundColor: `${config.color}20`,
        color: config.color,
      }}
    >
      {getStatusLabel(status)}
    </span>
  );
}
