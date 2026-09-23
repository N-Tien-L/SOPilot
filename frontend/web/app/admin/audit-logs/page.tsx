'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  ScrollText,
  Search,
  Loader2,
  User,
  ChevronDown,
  ChevronRight,
  Clock,
  Monitor,
  Globe,
  FileText,
  CheckCircle2,
  XCircle,
  X,
} from 'lucide-react';
import { Input, Select, Badge, Modal, EmptyState } from '@/components/ui';
import { useIsAdmin } from '@/store';
import { Translator } from '@/lib/i18n';
import { useLanguage } from '@/providers';
import styles from './audit-logs.module.css';

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const seconds = String(d.getSeconds()).padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

interface AuditLog {
  id: string;
  timestamp: string;
  userId: string;
  userName: string;
  userEmail?: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  resourceName?: string;
  ipAddress: string;
  userAgent?: string;
  details?: string;
  status: 'SUCCESS' | 'FAILURE';
}

interface GroupedLogs {
  action: string;
  label: string;
  variant: string;
  count: number;
  logs: AuditLog[];
}

function getActionConfig(t: Translator) {
  return {
    LOGIN_SUCCESS: { label: t('admin.audit.action.login'), variant: 'success' },
    LOGIN_FAILED: { label: t('admin.audit.action.loginFailed'), variant: 'destructive' },
    LOGOUT: { label: t('admin.audit.action.logout'), variant: 'neutral' },
    PASSWORD_CHANGE: { label: t('admin.audit.action.passwordChange'), variant: 'warning' },
    USER_CREATE: { label: t('admin.audit.action.userCreate'), variant: 'info' },
    USER_UPDATE: { label: t('admin.audit.action.userUpdate'), variant: 'info' },
    USER_PROFILE_UPDATE: { label: t('admin.audit.action.profileUpdate'), variant: 'info' },
    USER_DEACTIVATE: { label: t('admin.audit.action.userDeactivate'), variant: 'warning' },
    USER_ACTIVATE: { label: t('admin.audit.action.userActivate'), variant: 'success' },
    USER_REVOKE: { label: t('admin.audit.action.userRevoke'), variant: 'warning' },
    USER_DELETE: { label: t('admin.audit.action.userDelete'), variant: 'destructive' },
    ROLE_CHANGE: { label: t('admin.audit.action.roleChange'), variant: 'warning' },
    STATUS_CHANGE: { label: t('admin.audit.action.statusChange'), variant: 'warning' },
    DOCUMENT_UPLOAD: { label: t('admin.audit.action.docUpload'), variant: 'info' },
    DOCUMENT_DELETE: { label: t('admin.audit.action.docDelete'), variant: 'destructive' },
    DOCUMENT_UPDATE: { label: t('admin.audit.action.docUpdate'), variant: 'info' },
    DOCUMENT_PUBLISH: { label: t('admin.audit.action.docPublish'), variant: 'info' },
    DOCUMENT_ARCHIVE: { label: t('admin.audit.action.docArchive'), variant: 'neutral' },
    DOCUMENT_VERSION_CREATE: { label: t('admin.audit.action.docVersionCreate'), variant: 'info' },
    QUESTION_ASK: { label: t('admin.audit.action.questionAsk'), variant: 'info' },
    CONVERSATION_CREATE: { label: t('admin.audit.action.conversationCreate'), variant: 'info' },
    CONVERSATION_DELETE: { label: t('admin.audit.action.conversationDelete'), variant: 'destructive' },
    FEEDBACK_SUBMIT: { label: t('admin.audit.action.feedbackSubmit'), variant: 'info' },
    SETTINGS_UPDATE: { label: t('admin.audit.action.settingsChange'), variant: 'warning' },
    USER_SETTINGS_UPDATE: { label: t('admin.audit.action.userSettingsUpdate'), variant: 'warning' },
    CATEGORY_CREATE: { label: t('admin.audit.action.categoryCreate'), variant: 'info' },
    CATEGORY_UPDATE: { label: t('admin.audit.action.categoryUpdate'), variant: 'info' },
    CATEGORY_DELETE: { label: t('admin.audit.action.categoryDelete'), variant: 'destructive' },
    TAG_CREATE: { label: t('admin.audit.action.tagCreate'), variant: 'info' },
    TAG_UPDATE: { label: t('admin.audit.action.tagUpdate'), variant: 'info' },
    TAG_DELETE: { label: t('admin.audit.action.tagDelete'), variant: 'destructive' },
    DEPARTMENT_CREATE: { label: t('admin.audit.action.departmentCreate'), variant: 'info' },
    DEPARTMENT_UPDATE: { label: t('admin.audit.action.departmentUpdate'), variant: 'info' },
    DEPARTMENT_DELETE: { label: t('admin.audit.action.departmentDelete'), variant: 'destructive' },
    BULK_IMPORT: { label: t('admin.audit.action.bulkImport'), variant: 'info' },
    REPORT_EXPORT: { label: t('admin.audit.action.reportExport'), variant: 'info' },
  };
}

interface BackendAuditLog {
  id: string;
  userId: string;
  username: string;
  userRole?: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  resourceName?: string;
  ipAddress?: string;
  createdAt: string;
}

function mapBackendToAuditLog(backend: BackendAuditLog): AuditLog {
  return {
    id: backend.id,
    timestamp: backend.createdAt,
    userId: backend.userId,
    userName: backend.username,
    action: backend.action,
    resourceType: backend.resourceType,
    resourceId: backend.resourceId,
    resourceName: backend.resourceName,
    ipAddress: backend.ipAddress || '-',
    status: 'SUCCESS',
  };
}

export default function AuditLogsPage() {
  const router = useRouter();
  const isAdmin = useIsAdmin();
  const { t } = useLanguage();
  const ACTION_CONFIG = getActionConfig(t);

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [expandedActions, setExpandedActions] = useState<Set<string>>(new Set());
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [detailPage, setDetailPage] = useState(1);
  const [detailTotalPages, setDetailTotalPages] = useState(1);
  
  // Pagination state per action group
  const [groupPages, setGroupPages] = useState<Record<string, number>>({});

  const ITEMS_PER_GROUP = 10;

  const loadLogs = useCallback(async (currentPage: number, currentSearch: string, currentActionFilter: string) => {
    setLoading(true);
    setError(null);
    try {
      const { api } = await import('@/lib/api');
      const response = await api.audit.search({
        page: currentPage - 1,
        limit: 50,
        action: currentActionFilter || undefined,
        search: currentSearch || undefined,
      });
      const backendLogs = (response.data as unknown as BackendAuditLog[]) || [];
      setLogs(backendLogs.map(mapBackendToAuditLog));
      setTotalItems(response.pagination?.total ?? backendLogs.length);
      setTotalPages(response.pagination?.totalPages ?? 1);
    } catch {
      setError(t('admin.audit.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (!isAdmin) {
      router.push('/');
      return;
    }
    loadLogs(page, search, actionFilter);
  }, [isAdmin, router, page, search, actionFilter, loadLogs]);

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const handleActionChange = (value: string) => {
    setActionFilter(value);
    setPage(1);
  };

  const groupedLogs: GroupedLogs[] = React.useMemo(() => {
    const groups: Record<string, AuditLog[]> = {};
    logs.forEach(log => {
      if (!groups[log.action]) {
        groups[log.action] = [];
      }
      groups[log.action].push(log);
    });

    return Object.entries(groups)
      .map(([action, groupLogs]) => {
        const cfg = ACTION_CONFIG[action as keyof typeof ACTION_CONFIG];
        return {
          action,
          label: cfg?.label ?? action,
          variant: cfg?.variant ?? 'neutral',
          count: groupLogs.length,
          logs: groupLogs,
        };
      })
      .sort((a, b) => new Date(b.logs[0].timestamp).getTime() - new Date(a.logs[0].timestamp).getTime());
  }, [logs, ACTION_CONFIG]);

  const toggleAction = (action: string) => {
    setExpandedActions(prev => {
      const next = new Set(prev);
      if (next.has(action)) {
        next.delete(action);
      } else {
        next.add(action);
        // Reset to page 1 when expanding
        setGroupPages(prev => ({ ...prev, [action]: 1 }));
      }
      return next;
    });
  };

  const getGroupPage = (action: string): number => {
    return groupPages[action] || 1;
  };

  const setGroupPage = (action: string, page: number) => {
    setGroupPages(prev => ({ ...prev, [action]: page }));
  };

  const getPaginatedLogs = (group: GroupedLogs, pageNum: number) => {
    const start = (pageNum - 1) * ITEMS_PER_GROUP;
    return group.logs.slice(start, start + ITEMS_PER_GROUP);
  };

  const getGroupTotalPages = (count: number): number => {
    return Math.ceil(count / ITEMS_PER_GROUP);
  };

  const actionOptions = [
    { value: '', label: t('admin.audit.filter.allActions') },
    { value: 'LOGIN_SUCCESS', label: t('admin.audit.action.login') },
    { value: 'LOGIN_FAILED', label: t('admin.audit.action.loginFailed') },
    { value: 'PASSWORD_CHANGE', label: t('admin.audit.action.passwordChange') },
    { value: 'USER_PROFILE_UPDATE', label: t('admin.audit.action.profileUpdate') },
    { value: 'ROLE_CHANGE', label: t('admin.audit.action.roleChange') },
    { value: 'STATUS_CHANGE', label: t('admin.audit.action.statusChange') },
    { value: 'USER_CREATE', label: t('admin.audit.action.userCreate') },
    { value: 'USER_UPDATE', label: t('admin.audit.action.userUpdate') },
    { value: 'USER_DEACTIVATE', label: t('admin.audit.action.userDeactivate') },
    { value: 'USER_ACTIVATE', label: t('admin.audit.action.userActivate') },
    { value: 'USER_REVOKE', label: t('admin.audit.action.userRevoke') },
    { value: 'USER_DELETE', label: t('admin.audit.action.userDelete') },
    { value: 'DOCUMENT_UPLOAD', label: t('admin.audit.action.docUpload') },
    { value: 'DOCUMENT_UPDATE', label: t('admin.audit.action.docUpdate') },
    { value: 'DOCUMENT_DELETE', label: t('admin.audit.action.docDelete') },
    { value: 'DOCUMENT_PUBLISH', label: t('admin.audit.action.docPublish') },
    { value: 'DOCUMENT_ARCHIVE', label: t('admin.audit.action.docArchive') },
    { value: 'DOCUMENT_VERSION_CREATE', label: t('admin.audit.action.docVersionCreate') },
    { value: 'SETTINGS_UPDATE', label: t('admin.audit.action.settingsChange') },
    { value: 'CATEGORY_CREATE', label: t('admin.audit.action.categoryCreate') },
    { value: 'CATEGORY_UPDATE', label: t('admin.audit.action.categoryUpdate') },
    { value: 'CATEGORY_DELETE', label: t('admin.audit.action.categoryDelete') },
    { value: 'TAG_CREATE', label: t('admin.audit.action.tagCreate') },
    { value: 'TAG_UPDATE', label: t('admin.audit.action.tagUpdate') },
    { value: 'TAG_DELETE', label: t('admin.audit.action.tagDelete') },
    { value: 'DEPARTMENT_CREATE', label: t('admin.audit.action.departmentCreate') },
    { value: 'DEPARTMENT_UPDATE', label: t('admin.audit.action.departmentUpdate') },
    { value: 'DEPARTMENT_DELETE', label: t('admin.audit.action.departmentDelete') },
    { value: 'BULK_IMPORT', label: t('admin.audit.action.bulkImport') },
    { value: 'REPORT_EXPORT', label: t('admin.audit.action.reportExport') },
    { value: 'QUESTION_ASK', label: t('admin.audit.action.questionAsk') },
    { value: 'CONVERSATION_CREATE', label: t('admin.audit.action.conversationCreate') },
    { value: 'CONVERSATION_DELETE', label: t('admin.audit.action.conversationDelete') },
    { value: 'FEEDBACK_SUBMIT', label: t('admin.audit.action.feedbackSubmit') },
  ];

  return (
    <div className={styles.pageWrapper}>
      <div className={styles.pageHeader}>
        <div className={styles.pageHeaderInner}>
          <div className={styles.headerContent}>
            <div className={styles.headerIcon}>
              <ScrollText size={28} />
            </div>
            <div>
              <h1 className={styles.pageTitle}>{t('admin.audit.title')}</h1>
              <p className={styles.pageSubtitle}>{t('admin.audit.subtitle')}</p>
            </div>
          </div>
          <div className={styles.headerStats}>
            <div className={styles.statItem}>
              <span className={styles.statValue}>{totalItems}</span>
              <span className={styles.statLabel}>Tổng sự kiện</span>
            </div>
            <div className={styles.statItem}>
              <span className={styles.statValue}>{groupedLogs.length}</span>
              <span className={styles.statLabel}>Loại hành động</span>
            </div>
          </div>
        </div>
      </div>

      <div className={styles.pageBody}>
        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.toolbar}>
          <Input
            placeholder={t('admin.audit.search.placeholder')}
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            leftIcon={<Search size={18} />}
            inputSize="md"
            className={styles.searchInput}
          />
          <Select
            value={actionFilter}
            onChange={(e) => handleActionChange(e.target.value)}
            options={actionOptions}
            selectSize="md"
            className={styles.actionSelect}
          />
        </div>

        {loading ? (
          <div className={styles.loading}>
            <Loader2 size={32} className={styles.spinner} />
            <span>Đang tải dữ liệu...</span>
          </div>
        ) : groupedLogs.length === 0 ? (
          <EmptyState
            icon={<ScrollText size={40} />}
            title={t('admin.audit.empty.title')}
            description={t('admin.audit.empty.description')}
          />
        ) : (
          <div className={styles.groupsContainer}>
            {groupedLogs.map((group) => (
              <div key={group.action} className={styles.group}>
                <button
                  className={`${styles.groupHeader} ${expandedActions.has(group.action) ? styles.expanded : ''}`}
                  onClick={() => toggleAction(group.action)}
                >
                  <div className={styles.groupHeaderLeft}>
                    {expandedActions.has(group.action) ? (
                      <ChevronDown size={20} className={styles.chevron} />
                    ) : (
                      <ChevronRight size={20} className={styles.chevron} />
                    )}
                    <Badge variant={group.variant as any}>{group.label}</Badge>
                    <span className={styles.groupCount}>{group.count} sự kiện</span>
                  </div>
                  <span className={styles.groupLatest}>
                    <Clock size={14} />
                    {formatDate(group.logs[0].timestamp)}
                  </span>
                </button>

                {expandedActions.has(group.action) && (
                  <div className={styles.groupContent}>
                    <div className={styles.logList}>
                      {getPaginatedLogs(group, getGroupPage(group.action)).map((log, idx) => (
                        <div
                          key={log.id}
                          className={styles.logItem}
                          onClick={() => {
                            setSelectedLog(log);
                            setDetailPage(1);
                            setDetailTotalPages(getGroupTotalPages(group.logs.length));
                          }}
                        >
                          <div className={styles.logItemMain}>
                            <div className={styles.logItemLeft}>
                              <div className={styles.logTime}>
                                <span className={styles.logDate}>{formatDate(log.timestamp)}</span>
                                <span className={styles.logTimestamp}>{formatTime(log.timestamp)}</span>
                              </div>
                              <div className={styles.logUser}>
                                <div className={styles.userAvatar}>
                                  <User size={14} />
                                </div>
                                <span className={styles.userName}>{log.userName}</span>
                              </div>
                            </div>
                            <div className={styles.logItemRight}>
                              {log.resourceName && (
                                <div className={styles.logResource}>
                                  <FileText size={14} />
                                  <span>{log.resourceName}</span>
                                </div>
                              )}
                              <div className={styles.logMeta}>
                                <span className={styles.logIp}>
                                  <Globe size={12} />
                                  {log.ipAddress}
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className={styles.logItemArrow}>
                            <ChevronRight size={16} />
                          </div>
                        </div>
                      ))}
                    </div>
                    {getGroupTotalPages(group.logs.length) > 1 && (
                      <div className={styles.groupPagination}>
                        <button
                          className={styles.pageBtn}
                          disabled={getGroupPage(group.action) === 1}
                          onClick={() => setGroupPage(group.action, getGroupPage(group.action) - 1)}
                        >
                          <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} />
                        </button>
                        <span className={styles.pageInfo}>
                          Trang {getGroupPage(group.action)} / {getGroupTotalPages(group.logs.length)}
                        </span>
                        <button
                          className={styles.pageBtn}
                          disabled={getGroupPage(group.action) === getGroupTotalPages(group.logs.length)}
                          onClick={() => setGroupPage(group.action, getGroupPage(group.action) + 1)}
                        >
                          <ChevronRight size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={!!selectedLog}
        onClose={() => setSelectedLog(null)}
        title="Chi tiết sự kiện"
        size="lg"
        footer={
          <button className={styles.closeBtn} onClick={() => setSelectedLog(null)}>
            <X size={16} />
            Đóng
          </button>
        }
      >
        {selectedLog && (
          <div className={styles.modalContent}>
            <div className={styles.modalHeader}>
              <Badge variant={ACTION_CONFIG[selectedLog.action as keyof typeof ACTION_CONFIG]?.variant as any || 'neutral'}>
                {ACTION_CONFIG[selectedLog.action as keyof typeof ACTION_CONFIG]?.label || selectedLog.action}
              </Badge>
              <span className={styles.modalTime}>
                <Clock size={16} />
                {formatDate(selectedLog.timestamp)} lúc {formatTime(selectedLog.timestamp)}
              </span>
            </div>

            <div className={styles.modalGrid}>
              <div className={styles.modalSection}>
                <h4 className={styles.sectionTitle}>
                  <User size={16} />
                  Người thực hiện
                </h4>
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Tên</span>
                  <span className={styles.infoValue}>{selectedLog.userName}</span>
                </div>
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>ID</span>
                  <code className={styles.infoCode}>{selectedLog.userId}</code>
                </div>
              </div>

              <div className={styles.modalSection}>
                <h4 className={styles.sectionTitle}>
                  <FileText size={16} />
                  Tài nguyên
                </h4>
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Loại</span>
                  <span className={styles.infoValue}>{selectedLog.resourceType || '-'}</span>
                </div>
                {selectedLog.resourceId && (
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>ID</span>
                    <code className={styles.infoCode}>{selectedLog.resourceId}</code>
                  </div>
                )}
                {selectedLog.resourceName && (
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>Tên</span>
                    <span className={styles.infoValue}>{selectedLog.resourceName}</span>
                  </div>
                )}
              </div>

              <div className={styles.modalSection}>
                <h4 className={styles.sectionTitle}>
                  <Monitor size={16} />
                  Thông tin hệ thống
                </h4>
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Địa chỉ IP</span>
                  <code className={styles.infoCode}>{selectedLog.ipAddress}</code>
                </div>
                {selectedLog.userAgent && (
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>User Agent</span>
                    <span className={styles.infoValueSmall}>{selectedLog.userAgent}</span>
                  </div>
                )}
              </div>

              {selectedLog.details && (
                <div className={styles.modalSection}>
                  <h4 className={styles.sectionTitle}>
                    <FileText size={16} />
                    Chi tiết
                  </h4>
                  <div className={styles.detailsBox}>
                    {selectedLog.details}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
