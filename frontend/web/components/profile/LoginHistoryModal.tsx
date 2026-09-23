'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Clock, MapPin, Monitor, Smartphone, Globe, CheckCircle, XCircle, ChevronLeft, ChevronRight, AlertCircle, Shield, Laptop, Tablet } from 'lucide-react';
import { Modal } from '@/components/ui';
import { api } from '@/lib/api';
import styles from './LoginHistoryModal.module.css';

interface LoginHistoryModalProps {
  open: boolean;
  onClose: () => void;
  userId: string;
}

interface LoginHistoryEntry {
  id: string;
  username: string;
  ipAddress: string;
  deviceType: string;
  location: string;
  status: string;
  failureReason: string | null;
  createdAt: string;
}

interface LoginHistoryResponse {
  data: LoginHistoryEntry[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export function LoginHistoryModal({ open, onClose, userId }: LoginHistoryModalProps) {
  const [history, setHistory] = useState<LoginHistoryEntry[]>([]);
  const [pagination, setPagination] = useState({ page: 1, limit: 20, total: 0, totalPages: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async (page: number) => {
    if (!userId) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await api.users.getLoginHistory(userId, { page, limit: 20 });
      setHistory(result.data);
      setPagination(result.pagination);
    } catch {
      setError('Không thể tải lịch sử đăng nhập. Vui lòng thử lại.');
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (open && userId) {
      loadHistory(1);
    }
  }, [open, userId, loadHistory]);

  const handlePrev = () => {
    if (pagination.page > 1) loadHistory(pagination.page - 1);
  };

  const handleNext = () => {
    if (pagination.page < pagination.totalPages) loadHistory(pagination.page + 1);
  };

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getRelativeTime = (dateStr: string) => {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Vừa xong';
    if (diffMins < 60) return `${diffMins} phút trước`;
    if (diffHours < 24) return `${diffHours} giờ trước`;
    if (diffDays < 7) return `${diffDays} ngày trước`;
    return `${Math.floor(diffDays / 7)} tuần trước`;
  };

  const getStatusBadge = (status: string) => {
    const isSuccess = status === 'SUCCESS';
    return (
      <span className={`${styles.statusBadge} ${isSuccess ? styles.success : styles.failed}`}>
        {isSuccess ? <CheckCircle size={12} /> : <XCircle size={12} />}
        {isSuccess ? 'Thành công' : 'Thất bại'}
      </span>
    );
  };

  const getDeviceIcon = (deviceType: string) => {
    const d = deviceType?.toLowerCase() || '';
    if (d.includes('mobile') || d.includes('android') || d.includes('iphone')) {
      return <Smartphone size={16} className={styles.deviceIconMobile} />;
    }
    if (d.includes('tablet') || d.includes('ipad')) {
      return <Tablet size={16} className={styles.deviceIcon} />;
    }
    if (d.includes('laptop')) {
      return <Laptop size={16} className={styles.deviceIcon} />;
    }
    return <Monitor size={16} className={styles.deviceIcon} />;
  };

  // Calculate stats
  const successCount = history.filter(h => h.status === 'SUCCESS').length;
  const failedCount = history.filter(h => h.status === 'FAILED').length;
  const uniqueDevices = new Set(history.map(h => h.deviceType)).size;
  const currentSessionId = history[0]?.id;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Lịch sử đăng nhập"
      description="Các lần đăng nhập gần đây của bạn"
      size="lg"
    >
      <div className={styles.container}>
        {isLoading && (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <span>Đang tải lịch sử...</span>
          </div>
        )}

        {error && (
          <div className={styles.error}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {!isLoading && !error && history.length === 0 && (
          <div className={styles.empty}>
            <Clock size={48} className={styles.emptyIcon} />
            <p>Chưa có lịch sử đăng nhập</p>
            <span className={styles.emptyHint}>Các lần đăng nhập của bạn sẽ hiển thị tại đây</span>
          </div>
        )}

        {!isLoading && !error && history.length > 0 && (
          <>
            {/* Stats Summary */}
            <div className={styles.statsGrid}>
              <div className={styles.statCard}>
                <div className={styles.statIcon}>
                  <Shield size={20} />
                </div>
                <div className={styles.statContent}>
                  <span className={styles.statValue}>{pagination.total}</span>
                  <span className={styles.statLabel}>Tổng phiên</span>
                </div>
              </div>
              <div className={`${styles.statCard} ${styles.statSuccess}`}>
                <div className={styles.statIcon}>
                  <CheckCircle size={20} />
                </div>
                <div className={styles.statContent}>
                  <span className={styles.statValue}>{successCount}</span>
                  <span className={styles.statLabel}>Thành công</span>
                </div>
              </div>
              <div className={`${styles.statCard} ${failedCount > 0 ? styles.statDanger : ''}`}>
                <div className={styles.statIcon}>
                  <XCircle size={20} />
                </div>
                <div className={styles.statContent}>
                  <span className={styles.statValue}>{failedCount}</span>
                  <span className={styles.statLabel}>Thất bại</span>
                </div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statIcon}>
                  <Laptop size={20} />
                </div>
                <div className={styles.statContent}>
                  <span className={styles.statValue}>{uniqueDevices}</span>
                  <span className={styles.statLabel}>Thiết bị</span>
                </div>
              </div>
            </div>

            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Thời gian</th>
                    <th>Địa chỉ IP</th>
                    <th>Thiết bị</th>
                    <th>Vị trí</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((entry, index) => (
                    <tr 
                      key={entry.id} 
                      className={`${styles.tableRow} ${entry.id === currentSessionId ? styles.currentSession : ''}`}
                    >
                      <td className={styles.timeCell}>
                        <div className={styles.timeWrapper}>
                          <span className={styles.absoluteTime}>{formatDateTime(entry.createdAt)}</span>
                          <span className={styles.relativeTime}>{getRelativeTime(entry.createdAt)}</span>
                        </div>
                        {entry.id === currentSessionId && (
                          <span className={styles.currentBadge}>
                            <span className={styles.currentDot} />
                            Hiện tại
                          </span>
                        )}
                      </td>
                      <td>
                        <div className={styles.ipWrapper}>
                          <span className={styles.monoCell}>{entry.ipAddress || '—'}</span>
                          {entry.ipAddress && (
                            <a 
                              href={`https://ipapi.co/${entry.ipAddress}/json/`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={styles.ipLink}
                              title="Tra cứu IP"
                            >
                              <Globe size={12} />
                            </a>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className={styles.deviceCell}>
                          {getDeviceIcon(entry.deviceType)}
                          <span>{entry.deviceType || 'Không xác định'}</span>
                        </div>
                      </td>
                      <td>
                        <div className={styles.locationCell}>
                          <MapPin size={14} />
                          <span>{entry.location || 'Không rõ'}</span>
                        </div>
                      </td>
                      <td>
                        {getStatusBadge(entry.status)}
                        {entry.status === 'FAILED' && entry.failureReason && (
                          <span className={styles.failureReason} title={entry.failureReason}>
                            {entry.failureReason}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.paginationWrapper}>
              <div className={styles.pagination}>
                <button
                  className={styles.pageBtn}
                  onClick={handlePrev}
                  disabled={pagination.page <= 1}
                >
                  <ChevronLeft size={16} />
                  Trước
                </button>
                <div className={styles.pageInfo}>
                  <span className={styles.pageNumber}>Trang {pagination.page}</span>
                  <span className={styles.pageDivider}>/</span>
                  <span className={styles.pageTotal}>{pagination.totalPages}</span>
                </div>
                <button
                  className={styles.pageBtn}
                  onClick={handleNext}
                  disabled={pagination.page >= pagination.totalPages}
                >
                  Sau
                  <ChevronRight size={16} />
                </button>
              </div>
              {pagination.total > 0 && (
                <span className={styles.totalInfo}>
                  Hiển thị {history.length} / {pagination.total} phiên
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

export default LoginHistoryModal;
