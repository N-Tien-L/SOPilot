'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft,
  Download,
  Trash2,
  Clock,
  User,
  File,
  History,
  Shield,
  Tag,
  Eye,
  Loader2,
  AlertCircle,
  Edit,
  Upload,
  FileText,
  FolderOpen,
} from 'lucide-react';
import {
  documentService,
  documentMetadataService,
  accessRuleService,
  categoryService,
} from '@/services/document.service';
import { AccessRuleModal } from '@/components/documents/AccessRuleModal';
import type {
  Document,
  DocumentDetail,
  DocumentVersion,
  AccessRule,
  AuditLog,
  DocumentMetadata,
} from '@/types/document';
import {
  formatFileSize,
  formatDate,
  getFileTypeConfig,
  getStatusConfig,
} from '@/types/document';
import { useAuthStore, useIsAdmin, useIsManager } from '@/store/auth-store';
import PreviewModal from '@/components/documents/PreviewModal';
import { UploadModal } from '@/components/documents/UploadModal';
import { UploadNewVersionModal } from '@/components/documents/UploadNewVersionModal';
import styles from './document-detail.module.css';

type Tab = 'detail' | 'content' | 'versions' | 'access' | 'simulation' | 'audit';

export default function DocumentDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { user: authUser } = useAuthStore();
  const isAdmin = useIsAdmin();
  const isManager = useIsManager();
  const documentId = params.id as string;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [metadata, setMetadata] = useState<DocumentMetadata | null>(null);
  const [metadataMissing, setMetadataMissing] = useState(false);
  const [accessRules, setAccessRules] = useState<AccessRule[]>([]);

  const [simulationData, setSimulationData] = useState<{
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
    }>;
  } | null>(null);
  const [simulationLoading, setSimulationLoading] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('detail');
  const [extractedContent, setExtractedContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [auditPage, setAuditPage] = useState(0);
  const [auditTotalPages, setAuditTotalPages] = useState(1);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [uploadVersionOpen, setUploadVersionOpen] = useState(false);

  const [mounted, setMounted] = useState(false);

  // Derived values - must be defined before early returns to follow Rules of Hooks
  const fileConfig = document ? getFileTypeConfig(document.fileType as unknown as string) : null;
  const statusConfig = document ? getStatusConfig(document.status) : null;
  const isOwner = document && authUser ? document.uploadedBy === authUser.id : false;
  const categoryName = metadata?.category && categories.length > 0
    ? categories.find(c => c.id === (metadata as any).category?.id)?.name
    : null;

  const tabs = useMemo(() => {
    const baseTabs = [
      { id: 'detail', label: 'Chi tiết', icon: Eye },
      { id: 'content', label: 'Nội dung', icon: FileText },
      { id: 'versions', label: 'Phiên bản', icon: History },
    ];

    // Admin sees all tabs
    if (isAdmin) {
      return [
        ...baseTabs,
        { id: 'access', label: 'Phân quyền', icon: Shield },
        { id: 'simulation', label: 'Mô phỏng', icon: Shield },
        { id: 'audit', label: 'Nhật ký', icon: Clock },
      ];
    }

    // Manager sees simulation and audit
    if (isManager) {
      return [
        ...baseTabs,
        { id: 'simulation', label: 'Mô phỏng', icon: Shield },
        { id: 'audit', label: 'Nhật ký', icon: Clock },
      ];
    }

    // Regular user sees only basic tabs + audit
    return [
      ...baseTabs,
      { id: 'audit', label: 'Nhật ký', icon: Clock },
    ];
  }, [isAdmin, isManager]);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    loadDocument();
    loadCategories();
  }, [documentId]);

  const loadCategories = async () => {
    try {
      const cats = await categoryService.getCategories();
      setCategories(cats);
    } catch (err) {
      console.error('Failed to load categories:', err);
    }
  };

  const loadDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      const doc = await documentService.getDocumentById(documentId);
      const normalizedDoc: DocumentDetail = {
        ...doc,
        versions: 'versions' in doc && Array.isArray((doc as any).versions)
          ? (doc as any).versions
          : [],
        tags: doc.tags || [],
      };
      setDocument(normalizedDoc);

      try {
        const meta = await documentMetadataService.getMetadataByDocumentId(documentId);
        setMetadata(meta);
        setMetadataMissing(false);
      } catch (err: any) {
        const errStatus = err?.status || err?.statusCode || (err?.response?.status);
        if (errStatus === 404) {
          console.log('No metadata found for document');
          setMetadataMissing(true);
        } else {
          console.error('Failed to load metadata:', err);
        }
      }

      try {
        const rules = await accessRuleService.getRulesByDocumentId(documentId);
        setAccessRules(rules);
      } catch (err) {
        console.error('Failed to load access rules:', err);
      }
    } catch (err: any) {
      // Check for access denied error
      const errStatus = err?.status || err?.statusCode || (err?.response?.status);
      if (errStatus === 403) {
        const errMsg = err?.message || err?.response?.data?.message || '';
        if (errMsg.toLowerCase().includes('access') || errMsg.toLowerCase().includes('denied') || errMsg.toLowerCase().includes('quyền')) {
          setError('Bạn không có quyền truy cập tài liệu này');
          return;
        }
      }
      setError(err.message || 'Failed to load document');
    } finally {
      setLoading(false);
    }
  };

  const loadAuditLogs = async (page = 0) => {
    try {
      const response = await documentService.getAuditLogs(documentId, { page, limit: 20 });
      setAuditLogs(response.data || []);
      setAuditTotalPages(response.totalPages);
      setAuditPage(page);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    }
  };

  const loadExtractedContent = async () => {
    if (!document) return;
    setContentLoading(true);
    try {
      const content = await documentService.getDocumentContent(documentId, document.currentVersion);
      setExtractedContent(content);
    } catch (err) {
      console.error('Failed to load extracted content:', err);
    } finally {
      setContentLoading(false);
    }
  };

  const loadSimulation = async () => {
    setSimulationLoading(true);
    setSimulationError(null);
    try {
      const result = await accessRuleService.simulateAccess(documentId);
      setSimulationData({
        ...result,
        grantedUsers: result.grantedUsers.map(u => ({ ...u })),
        deniedUsers: result.deniedUsers.map(u => ({ ...u })),
      });
    } catch (err: any) {
      setSimulationError(err?.message || err?.response?.data?.message || 'Không thể mô phỏng quyền truy cập');
    } finally {
      setSimulationLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAuditLogs();
    } else if (activeTab === 'content' && !extractedContent) {
      loadExtractedContent();
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 'simulation') {
      loadSimulation();
    }
  }, [activeTab]);

  const handleDelete = async () => {
    if (!confirm('Bạn có chắc muốn xóa tài liệu này?')) return;
    try {
      await documentService.deleteDocument(documentId);
      router.push('/documents');
    } catch (err: any) {
      alert(err.message || 'Xóa thất bại');
    }
  };

  const handleDownload = async () => {
    if (!document) return;
    try {
      await documentService.downloadDocument(documentId, document.originalFilename, document.currentVersion);
    } catch (err: any) {
      alert(err.message || 'Tải xuống thất bại');
    }
  };

  const handlePreview = () => setPreviewOpen(true);



  if (loading) {
    return (
      <div className={styles.loadingState}>
        <Loader2 className={`${styles.spinner} w-10 h-10`} />
        <p>Đang tải thông tin tài liệu...</p>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => router.back()}
            className="flex items-center text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Quay lại
          </button>
          <div className={styles.errorState}>
            <AlertCircle className="w-5 h-5 text-danger" />
            <div>
              <h3 className="text-sm font-medium text-danger">Lỗi</h3>
              <p className="mt-1 text-sm text-danger">{error || 'Không tìm thấy tài liệu'}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--background)' }}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.headerTop}>
            <button
              onClick={() => router.back()}
              className={styles.backButton}
            >
              <ArrowLeft className="w-5 h-5" />
            </button>

            <div className={styles.docInfo}>
              <div className={styles.docIcon}>{fileConfig?.icon}</div>
              <div className={styles.docTitle}>
                <h1>{document.title || document.originalFilename}</h1>
                <p className={styles.docFilename}>{document.originalFilename}</p>
              </div>
            </div>

            <div className={styles.headerActions}>
              {(['PDF', 'DOCX', 'DOC'].includes((document.fileType as unknown as string) || ''.toUpperCase())) && (
                <button
                  onClick={handlePreview}
                  className={styles.actionBtn}
                >
                  <Eye className="w-4 h-4" />
                  <span>Xem</span>
                </button>
              )}
              <button
                onClick={handleDownload}
                className={styles.actionBtn}
              >
                <Download className="w-4 h-4" />
                <span>Tải xuống</span>
              </button>
              {isAdmin && (
                <button
                  onClick={handleDelete}
                  className={`${styles.actionBtn} ${styles.actionBtnDanger}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Tabs */}
          <div className={styles.tabs}>
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as Tab)}
                className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className={styles.main}>
        {/* Status Banners */}
        {document.status === 'STAGING' && (
          <div className={`${styles.statusBanner} ${styles.statusBannerWarning}`}>
            <div className={styles.statusBannerContent}>
              <AlertCircle className="w-5 h-5" style={{ color: '#f59e0b' }} />
              <span>Tài liệu đang chờ xác nhận. Vui lòng hoàn tất thông tin.</span>
            </div>
            <button
              onClick={() => setIsConfirming(true)}
              className={`${styles.statusBannerBtn} ${styles.actionBtnPrimary}`}
            >
              Tiếp tục xác nhận
            </button>
          </div>
        )}

        {document.status === 'DUPLICATE' && (
          <div className={`${styles.statusBanner} ${styles.statusBannerError}`}>
            <div className={styles.statusBannerContent}>
              <AlertCircle className="w-5 h-5 text-danger" />
              <span>Cảnh báo: Tài liệu này được xác định là trùng lặp.</span>
            </div>
          </div>
        )}

        {/* Detail Tab */}
        {activeTab === 'detail' && (
          <div className={styles.detailGrid}>
            {/* Main Info */}
            <div>
              <div className={styles.card}>
                <div className={styles.cardHeader}>
                  <h2 className={styles.cardTitle}>
                    <File className="w-4 h-4" />
                    Thông tin tài liệu
                  </h2>
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.infoGrid}>
                    <div className={styles.infoItem}>
                      <span className={styles.infoLabel}>Loại file</span>
                      <span className={styles.infoValue}>{fileConfig?.label}</span>
                    </div>
                    <div className={styles.infoItem}>
                      <span className={styles.infoLabel}>Kích thước</span>
                      <span className={styles.infoValue}>
                        {formatFileSize(document.fileSizeBytes || document.fileSize || 0)}
                      </span>
                    </div>
                    <div className={styles.infoItem}>
                      <span className={styles.infoLabel}>Phiên bản</span>
                      <span className={styles.infoValue}>v{document.currentVersion}</span>
                    </div>
                    <div className={styles.infoItem}>
                      <span className={styles.infoLabel}>Trạng thái</span>
                      <span
                        className={styles.statusBadge}
                        style={{ backgroundColor: `${statusConfig?.color}15`, color: statusConfig?.color }}
                      >
                        {statusConfig?.label}
                      </span>
                    </div>
                    {document.pageCount && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>Số trang</span>
                        <span className={styles.infoValue}>{document.pageCount}</span>
                      </div>
                    )}
                    {document.wordCount && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>Số từ</span>
                        <span className={styles.infoValue}>
                          {document.wordCount.toLocaleString()}
                        </span>
                      </div>
                    )}
                    <div className={styles.infoItem}>
                      <span className={styles.infoLabel}>Ngôn ngữ</span>
                      <span className={styles.infoValue}>
                        {document.language === 'vi' ? 'Tiếng Việt' : document.language}
                      </span>
                    </div>
                    {document.ocrRequired && (
                      <div className={styles.infoItem}>
                        <span className={styles.infoLabel}>OCR</span>
                        <span className={styles.infoValue}>
                          Cần xử lý
                          {document.ocrConfidence && (
                            <span className="ml-2 opacity-60">
                              ({(document.ocrConfidence * 100).toFixed(0)}%)
                            </span>
                          )}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Tags & Categories */}
              {(document.tags?.length || categoryName) && (
                <div className={styles.card}>
                  <div className={styles.cardHeader}>
                    <h2 className={styles.cardTitle}>
                      <Tag className="w-4 h-4" />
                      Phân loại
                    </h2>
                  </div>
                  <div className={styles.cardBody}>
                    <div className={styles.metaTags}>
                      {categoryName && (
                        <span className={`${styles.tag} ${styles.categoryTag}`}>
                          <FolderOpen className="w-3 h-3" />
                          {categoryName}
                        </span>
                      )}
                      {document.tags?.map((tag, index) => (
                        <span key={index} className={styles.tag}>
                          <Tag className="w-3 h-3" />
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Metadata Description */}
              {metadata?.description && (
                <div className={styles.card}>
                  <div className={styles.cardHeader}>
                    <h2 className={styles.cardTitle}>
                      <FileText className="w-4 h-4" />
                      Mô tả
                    </h2>
                  </div>
                  <div className={styles.cardBody}>
                    <p style={{ color: 'var(--foreground)', fontSize: '0.875rem', lineHeight: 1.6, margin: 0 }}>
                      {metadata.description}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div>
              <div className={styles.card}>
                <div className={styles.cardHeader}>
                  <h2 className={styles.cardTitle}>
                    <Clock className="w-4 h-4" />
                    Thông tin hệ thống
                  </h2>
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.systemItem}>
                    <div className={styles.systemIcon}>
                      <User className="w-4 h-4" />
                    </div>
                    <div className={styles.systemContent}>
                      <p className={styles.systemLabel}>Người tải lên</p>
                      <p className={styles.systemValue}>
                        {document.uploadedByName || document.uploadedBy || 'Không xác định'}
                      </p>
                    </div>
                  </div>
                  <div className={styles.systemItem}>
                    <div className={styles.systemIcon}>
                      <Clock className="w-4 h-4" />
                    </div>
                    <div className={styles.systemContent}>
                      <p className={styles.systemLabel}>Ngày tạo</p>
                      <p className={styles.systemValue} suppressHydrationWarning>
                        {formatDate(document.createdAt)}
                      </p>
                    </div>
                  </div>
                  <div className={styles.systemItem}>
                    <div className={styles.systemIcon}>
                      <History className="w-4 h-4" />
                    </div>
                    <div className={styles.systemContent}>
                      <p className={styles.systemLabel}>Cập nhật lần cuối</p>
                      <p className={styles.systemValue} suppressHydrationWarning>
                        {formatDate(document.updatedAt)}
                      </p>
                    </div>
                  </div>

                  {/* Quick Stats */}
                  <div className={styles.quickStats}>
                    <div className={styles.statItem}>
                      <p className={styles.statValue}>{document.currentVersion}</p>
                      <p className={styles.statLabel}>Phiên bản</p>
                    </div>
                    <div className={styles.statItem}>
                      <p className={styles.statValue}>{document.versions?.length || 0}</p>
                      <p className={styles.statLabel}>Lịch sử</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Content Tab */}
        {activeTab === 'content' && (
          <div className={styles.contentWrapper}>
            <div className={styles.contentHeader}>
              <h2 className={styles.cardTitle}>
                <FileText className="w-4 h-4" />
                Nội dung đã trích xuất
              </h2>
              <button
                onClick={loadExtractedContent}
                disabled={contentLoading}
                className={styles.actionBtn}
              >
                {contentLoading ? (
                  <Loader2 className={`${styles.spinner} w-4 h-4`} />
                ) : (
                  <History className="w-4 h-4" />
                )}
                Làm mới
              </button>
            </div>
            <div className={styles.contentBody}>
              {contentLoading ? (
                <div className={styles.loadingState}>
                  <Loader2 className={`${styles.spinner} w-8 h-8`} />
                  <p>Đang tải nội dung...</p>
                </div>
              ) : extractedContent ? (
                <pre className={styles.contentCode}>{extractedContent}</pre>
              ) : (
                <div className={styles.emptyState}>
                  <div className={styles.emptyIcon}>
                    <FileText className="w-8 h-8" />
                  </div>
                  <p className={styles.emptyTitle}>Chưa có nội dung</p>
                  <p className={styles.emptyText}>Tài liệu chưa được trích xuất hoặc đang xử lý.</p>
                  {document.status === 'READY' && (
                    <button
                      onClick={() => documentService.triggerProcess(documentId)}
                      className={styles.actionBtn}
                      style={{ marginTop: '1rem' }}
                    >
                      Kích hoạt xử lý lại
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Versions Tab */}
        {activeTab === 'versions' && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2 className={styles.cardTitle}>
                <History className="w-4 h-4" />
                Lịch sử phiên bản
              </h2>
              {isAdmin && (
                <button
                  className={styles.actionBtn}
                  onClick={() => setUploadVersionOpen(true)}
                >
                  <Upload className="w-4 h-4" />
                  Tải lên mới
                </button>
              )}
            </div>
            {(document.versions || []).length > 0 ? (
              document.versions.map((version) => (
                <div key={version.id} className={styles.versionItem}>
                  <div className={styles.versionInfo}>
                    <div className={styles.versionNumber}>
                      v{version.versionNumber || version.version}
                    </div>
                    <div className={styles.versionDetails}>
                      <h4>
                        {version.changelog || version.changesDescription || `Phiên bản ${version.versionNumber || version.version}`}
                      </h4>
                      <p className={styles.versionMeta} suppressHydrationWarning>
                        {formatDate((version.createdAt || version.uploadedAt || ''))}
                        {formatFileSize(version.fileSizeBytes || version.fileSize || 0)}
                        {(version.uploadedByName || version.createdBy) && (
                          <> • {version.uploadedByName || version.createdBy}</>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className={styles.versionActions}>
                    {version.versionNumber === document.currentVersion && (
                      <span className={styles.currentBadge}>Hiện tại</span>
                    )}
                    <button
                      onClick={() => handlePreview()}
                      className={styles.iconBtn}
                      title="Xem trước"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => documentService.downloadVersion(documentId, version.versionNumber || version.version!, document.originalFilename)}
                      className={styles.iconBtn}
                      title="Tải xuống"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>
                  <History className="w-8 h-8" />
                </div>
                <p className={styles.emptyTitle}>Chưa có phiên bản</p>
                <p className={styles.emptyText}>Tài liệu chưa có lịch sử phiên bản.</p>
              </div>
            )}
          </div>
        )}

        {/* Access Tab - Admin Only */}
        {activeTab === 'access' && isAdmin && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2 className={styles.cardTitle}>
                <Shield className="w-4 h-4" />
                Quy tắc truy cập
              </h2>
              {metadataMissing && (
                <span className={styles.statusBadge} style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' }}>
                  Metadata chưa tồn tại
                </span>
              )}
            </div>
            <div className={styles.cardBody}>
              {metadataMissing ? (
                <div className={styles.emptyState}>
                  <div className={styles.emptyIcon}>
                    <Shield className="w-8 h-8" />
                  </div>
                  <p className={styles.emptyTitle}>Tài liệu chưa có metadata</p>
                  <p className={styles.emptyText}>Vui lòng xác nhận metadata trước khi thiết lập quyền.</p>
                </div>
              ) : accessRules.length > 0 ? (
                accessRules.map((rule) => (
                  <div key={rule.id} className={styles.accessRule}>
                    <div className={styles.accessRuleInfo}>
                      <div className={styles.accessRuleIcon}>
                        <Shield className="w-4 h-4" />
                      </div>
                      <div>
                        <p className={styles.accessRuleTitle}>
                          {rule.targetType === 'ROLE' && `Vai trò: ${rule.targetRole}`}
                          {rule.targetType === 'DEPARTMENT' && `Phòng ban: ${rule.targetDepartmentName || rule.targetDepartmentId}`}
                          {rule.targetType === 'USER' && `Người dùng: ${rule.targetUserName || rule.targetUserId}`}
                        </p>
                        <p className={styles.accessRuleType}>{rule.targetType}</p>
                      </div>
                    </div>
                    <div className={styles.accessRuleActions}>
                      <span
                        className={styles.permBadge}
                        style={{
                          backgroundColor: rule.permission === 'VIEW' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(220, 38, 38, 0.1)',
                          color: rule.permission === 'VIEW' ? '#059669' : '#dc2626'
                        }}
                      >
                        {rule.permission === 'VIEW' ? 'Cho phép' : 'Từ chối'}
                      </span>
                      {isAdmin && (
                        <>
                          <AccessRuleModal
                            documentId={documentId}
                            editingRule={rule}
                            onSuccess={async () => {
                              const rules = await accessRuleService.getRulesByDocumentId(documentId);
                              setAccessRules(rules);
                            }}
                          />
                          <button
                            onClick={async () => {
                              if (!confirm('Xóa quy tắc này?')) return;
                              try {
                                await accessRuleService.deleteRule(rule.id);
                                const rules = await accessRuleService.getRulesByDocumentId(documentId);
                                setAccessRules(rules);
                              } catch {
                                alert('Xóa thất bại');
                              }
                            }}
                            className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                            title="Xóa quy tắc"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className={styles.emptyState}>
                  <div className={styles.emptyIcon}>
                    <Shield className="w-8 h-8" />
                  </div>
                  <p className={styles.emptyTitle}>Chưa có quy tắc</p>
                  <p className={styles.emptyText}>Tài liệu có thể được truy cập công khai.</p>
                </div>
              )}
              {isAdmin && (
                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                  <AccessRuleModal
                    documentId={documentId}
                    onSuccess={async () => {
                      try {
                        const meta = await documentMetadataService.getMetadataByDocumentId(documentId);
                        setMetadata(meta);
                        setMetadataMissing(false);
                      } catch (err: any) {
                        const errStatus = err?.status || err?.statusCode || (err?.response?.status);
                        if (errStatus === 404) {
                          setMetadataMissing(true);
                        }
                      }
                      const rules = await accessRuleService.getRulesByDocumentId(documentId);
                      setAccessRules(rules);
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Simulation Tab - Admin & Manager Only */}
        {activeTab === 'simulation' && (isAdmin || isManager) && (
          <div>
            {simulationData && (
              <div className={styles.simStats}>
                <div className={styles.simStatCard}>
                  <p className={styles.simStatValue} style={{ color: 'var(--foreground)' }}>
                    {simulationData.totalCompanyUsers}
                  </p>
                  <p className={styles.simStatLabel}>Tổng nhân viên</p>
                </div>
                <div className={styles.simStatCard}>
                  <p className={styles.simStatValue} style={{ color: '#059669' }}>
                    {simulationData.usersWithAccess}
                  </p>
                  <p className={styles.simStatLabel}>Được phép truy cập</p>
                </div>
                <div className={styles.simStatCard}>
                  <p className={styles.simStatValue} style={{ color: '#dc2626' }}>
                    {simulationData.usersWithoutAccess}
                  </p>
                  <p className={styles.simStatLabel}>Không được phép</p>
                </div>
              </div>
            )}

            {simulationLoading ? (
              <div className={styles.card}>
                <div className={styles.loadingState}>
                  <Loader2 className={`${styles.spinner} w-8 h-8`} />
                  <p>Đang mô phỏng quyền truy cập...</p>
                </div>
              </div>
            ) : simulationError ? (
              <div className={styles.errorState}>
                <AlertCircle className="w-5 h-5 text-danger" />
                <div>
                  <p className="text-sm font-medium text-danger">Lỗi mô phỏng</p>
                  <p className="text-sm text-danger mt-1">{simulationError}</p>
                </div>
              </div>
            ) : simulationData ? (
              <div className={styles.userListGrid}>
                {/* Granted */}
                <div className={styles.userListCard}>
                  <div className={styles.userListHeader}>
                    <span className={styles.userListTitle}>
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#059669' }} />
                      Được phép truy cập
                    </span>
                    <span className={styles.userListCount} style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#059669' }}>
                      {simulationData.grantedUsers.length}
                    </span>
                  </div>
                  <div className={styles.userListBody}>
                    {simulationData.grantedUsers.length === 0 ? (
                      <div className={styles.emptyState} style={{ padding: '2rem' }}>
                        <p className={styles.emptyText}>Không có ai được phép</p>
                      </div>
                    ) : (
                      simulationData.grantedUsers.map((user) => (
                        <div key={user.userId} className={styles.userItem}>
                          <div className={styles.userItemInfo}>
                            <div className={styles.userAvatar} style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#059669' }}>
                              {user.fullName ? user.fullName.charAt(0).toUpperCase() : user.username.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className={styles.userName}>{user.fullName || user.username}</p>
                              <div className={styles.userRole}>
                                {user.role && (
                                  <span
                                    className={styles.roleBadge}
                                    style={{
                                      backgroundColor: user.role === 'ADMIN' ? 'rgba(139, 92, 246, 0.1)' :
                                        user.role === 'MANAGER' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(107, 114, 128, 0.1)',
                                      color: user.role === 'ADMIN' ? '#8b5cf6' :
                                        user.role === 'MANAGER' ? '#3b82f6' : '#6b7280'
                                    }}
                                  >
                                    {user.role}
                                  </span>
                                )}
                                <span style={{ opacity: 0.5 }}>•</span>
                                <span>{user.departmentName}</span>
                              </div>
                            </div>
                          </div>
                          <span
                            className={styles.userReason}
                            style={{ backgroundColor: 'rgba(16, 185, 129, 0.08)', color: '#059669' }}
                          >
                            {user.reason}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Denied */}
                <div className={styles.userListCard}>
                  <div className={styles.userListHeader}>
                    <span className={styles.userListTitle}>
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: '#dc2626' }} />
                      Không được phép
                    </span>
                    <span className={styles.userListCount} style={{ backgroundColor: 'rgba(220, 38, 38, 0.1)', color: '#dc2626' }}>
                      {simulationData.deniedUsers.length}
                    </span>
                  </div>
                  <div className={styles.userListBody}>
                    {simulationData.deniedUsers.length === 0 ? (
                      <div className={styles.emptyState} style={{ padding: '2rem' }}>
                        <p className={styles.emptyText}>Tất cả đều được phép</p>
                      </div>
                    ) : (
                      simulationData.deniedUsers.map((user) => (
                        <div key={user.userId} className={styles.userItem}>
                          <div className={styles.userItemInfo}>
                            <div className={styles.userAvatar} style={{ backgroundColor: 'rgba(220, 38, 38, 0.1)', color: '#dc2626' }}>
                              {user.fullName ? user.fullName.charAt(0).toUpperCase() : user.username.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className={styles.userName}>{user.fullName || user.username}</p>
                              <div className={styles.userRole}>
                                {user.role && (
                                  <span
                                    className={styles.roleBadge}
                                    style={{
                                      backgroundColor: user.role === 'ADMIN' ? 'rgba(139, 92, 246, 0.1)' :
                                        user.role === 'MANAGER' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(107, 114, 128, 0.1)',
                                      color: user.role === 'ADMIN' ? '#8b5cf6' :
                                        user.role === 'MANAGER' ? '#3b82f6' : '#6b7280'
                                    }}
                                  >
                                    {user.role}
                                  </span>
                                )}
                                <span style={{ opacity: 0.5 }}>•</span>
                                <span>{user.departmentName}</span>
                              </div>
                            </div>
                          </div>
                          <span
                            className={styles.userReason}
                            style={{ backgroundColor: 'rgba(220, 38, 38, 0.08)', color: '#dc2626' }}
                          >
                            {user.reason}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className={styles.card}>
                <div className={styles.emptyState}>
                  <div className={styles.emptyIcon}>
                    <Shield className="w-8 h-8" />
                  </div>
                  <p className={styles.emptyTitle}>Mô phỏng quyền truy cập</p>
                  <p className={styles.emptyText}>Nhấn nút bên dưới để xem ai có quyền truy cập</p>
                  <button
                    onClick={loadSimulation}
                    className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}
                    style={{ marginTop: '1rem' }}
                  >
                    <Shield className="w-4 h-4" />
                    Bắt đầu mô phỏng
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Audit Tab */}
        {activeTab === 'audit' && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2 className={styles.cardTitle}>
                <Clock className="w-4 h-4" />
                Nhật ký hoạt động
              </h2>
            </div>
            {auditLogs.length > 0 ? (
              <>
                {auditLogs.map((log) => (
                  <div key={log.id} className={styles.auditItem}>
                    <div className={styles.auditIcon}>
                      {log.action.charAt(0)}
                    </div>
                    <div className={styles.auditContent}>
                      <p className={styles.auditAction}>{log.action}</p>
                      <p className={styles.auditMeta} suppressHydrationWarning>
                        {log.actorUsername || log.actorId} • {formatDate(log.createdAt)}
                      </p>
                      {log.ipAddress && (
                        <p className={styles.auditIp}>IP: {log.ipAddress}</p>
                      )}
                    </div>
                  </div>
                ))}
                {auditTotalPages > 1 && (
                  <div className={styles.pagination}>
                    <span className={styles.paginationInfo}>Trang {auditPage + 1} / {auditTotalPages}</span>
                    <div className={styles.paginationBtns}>
                      <button
                        onClick={() => loadAuditLogs(auditPage - 1)}
                        disabled={auditPage === 0}
                        className={styles.pageBtn}
                      >
                        Trước
                      </button>
                      <button
                        onClick={() => loadAuditLogs(auditPage + 1)}
                        disabled={auditPage >= auditTotalPages - 1}
                        className={styles.pageBtn}
                      >
                        Sau
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>
                  <Clock className="w-8 h-8" />
                </div>
                <p className={styles.emptyTitle}>Chưa có nhật ký</p>
                <p className={styles.emptyText}>Không có hoạt động nào được ghi nhận.</p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Preview Modal */}
      {document && (
        <PreviewModal
          isOpen={previewOpen}
          onClose={() => setPreviewOpen(false)}
          documentId={documentId}
          version={document.currentVersion}
          filename={document.originalFilename || document.fileName || 'document'}
          fileType={(document.fileType as unknown as string) || 'UNKNOWN'}
          getPreviewUrl={(id, ver) => documentService.getPreviewUrl(id, ver)}
        />
      )}

      {isConfirming && document && (
        <UploadModal
          onClose={() => setIsConfirming(false)}
          onSuccess={() => {
            setIsConfirming(false);
            loadDocument();
          }}
          categories={categories}
          initialDocument={document as any}
        />
      )}

      {uploadVersionOpen && document && (
        <UploadNewVersionModal
          open={uploadVersionOpen}
          documentId={documentId}
          documentTitle={document.originalFilename || document.fileName || 'document'}
          currentVersion={document.currentVersion || 1}
          onClose={() => setUploadVersionOpen(false)}
          onSuccess={() => {
            setUploadVersionOpen(false);
            loadDocument();
          }}
        />
      )}

    </div>
  );
}
