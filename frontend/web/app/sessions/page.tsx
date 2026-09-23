'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Monitor,
  Smartphone,
  Tablet,
  Globe,
  Clock,
  LogOut,
  LogOutIcon,
  RefreshCw,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { Button } from '@/components/ui';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store';
import styles from './sessions.module.css';

interface Session {
  sessionId: string;
  deviceInfo?: string;
  deviceType?: string;
  ipAddress: string;
  createdAt: string;
  expiresAt?: string;
  isCurrent?: boolean;
  isCurrentSession?: boolean;
}

export default function SessionsPage() {
  const router = useRouter();
  const { isAuthenticated, _hasHydrated } = useAuthStore();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutAllLoading, setLogoutAllLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }
    loadSessions();
  }, [_hasHydrated, isAuthenticated]);

  const loadSessions = async () => {
    try {
      setIsLoading(true);
      const data = await api.auth.getSessions();
      setSessions(data);
    } catch (err) {
      console.error('Failed to load sessions:', err);
      setMessage({ type: 'error', text: 'Không thể tải danh sách phiên hoạt động' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogoutSession = async (sessionId: string) => {
    try {
      setIsLoggingOut(true);
      await api.auth.revokeSession(sessionId);
      setMessage({ type: 'success', text: 'Đăng xuất thiết bị thành công' });
      await loadSessions();
    } catch (err) {
      console.error('Failed to logout session:', err);
      setMessage({ type: 'error', text: 'Không thể đăng xuất thiết bị này' });
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleLogoutAll = async () => {
    if (!confirm('Bạn có chắc muốn đăng xuất tất cả các thiết bị? Phiên hiện tại cũng sẽ bị đăng xuất.')) {
      return;
    }

    try {
      setLogoutAllLoading(true);
      await api.auth.logoutAll();
      setMessage({ type: 'success', text: 'Đăng xuất tất cả thiết bị thành công' });
      await loadSessions();
    } catch (err) {
      console.error('Failed to logout all:', err);
      setMessage({ type: 'error', text: 'Không thể đăng xuất tất cả thiết bị' });
    } finally {
      setLogoutAllLoading(false);
    }
  };

  const getDeviceIcon = (deviceType?: string) => {
    if (!deviceType) return <Globe size={20} />;
    const type = deviceType.toLowerCase();
    if (type.includes('mobile') || type.includes('iphone') || type.includes('android')) {
      return <Smartphone size={20} />;
    }
    if (type.includes('tablet') || type.includes('ipad')) {
      return <Tablet size={20} />;
    }
    return <Monitor size={20} />;
  };

  const getDeviceLabel = (deviceType?: string) => {
    if (!deviceType) return 'Thiết bị không xác định';
    const type = deviceType.toLowerCase();
    if (type.includes('mobile') || type.includes('iphone') || type.includes('android')) {
      return 'Di động';
    }
    if (type.includes('tablet') || type.includes('ipad')) {
      return 'Máy tính bảng';
    }
    return 'Máy tính';
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Vừa xong';
    if (minutes < 60) return `${minutes} phút trước`;
    if (hours < 24) return `${hours} giờ trước`;
    return `${days} ngày trước`;
  };

  const currentSession = sessions.find((s) => s.isCurrent || s.isCurrentSession);
  const otherSessions = sessions.filter((s) => !s.isCurrent && !s.isCurrentSession);

  if (isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>Đang tải phiên hoạt động...</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.pageTitle}>Phiên hoạt động</h1>
          <p className={styles.pageSubtitle}>
            Quản lý các thiết bị đang đăng nhập vào tài khoản của bạn
          </p>
        </div>
        {sessions.length > 1 && (
          <Button
            variant="destructive"
            onClick={handleLogoutAll}
            loading={logoutAllLoading}
            icon={<LogOutIcon size={18} />}
          >
            Đăng xuất tất cả
          </Button>
        )}
      </div>

      {message && (
        <div className={`${styles.message} ${styles[message.type]}`}>
          {message.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className={styles.closeMessage}>
            ×
          </button>
        </div>
      )}

      <div className={styles.sessionsContainer}>
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>
            <Globe size={18} />
            Phiên hiện tại ({currentSession ? 1 : 0})
          </h2>
          {currentSession ? (
            <div className={styles.currentSessionCard}>
              <div className={styles.sessionDeviceIcon}>
                {getDeviceIcon(currentSession.deviceType)}
              </div>
              <div className={styles.sessionInfo}>
                <div className={styles.sessionHeader}>
                  <span className={styles.deviceName}>
                    {currentSession.deviceInfo || getDeviceLabel(currentSession.deviceType)}
                  </span>
                  <span className={styles.currentBadge}>Hiện tại</span>
                </div>
                <div className={styles.sessionDetails}>
                  <div className={styles.detailItem}>
                    <Globe size={14} />
                    <span>{currentSession.ipAddress || 'Không xác định'}</span>
                  </div>
                  <div className={styles.detailItem}>
                    <Clock size={14} />
                    <span>Đăng nhập: {formatDate(currentSession.createdAt)}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className={styles.noSession}>Không tìm thấy phiên hiện tại</p>
          )}
        </div>

        {otherSessions.length > 0 && (
          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>
              <Monitor size={18} />
              Các phiên khác ({otherSessions.length})
            </h2>
            <div className={styles.sessionsList}>
              {otherSessions.map((session) => (
                <div key={session.sessionId} className={styles.sessionCard}>
                  <div className={styles.sessionDeviceIcon}>
                    {getDeviceIcon(session.deviceType)}
                  </div>
                  <div className={styles.sessionInfo}>
                    <div className={styles.sessionHeader}>
                      <span className={styles.deviceName}>
                        {session.deviceInfo || getDeviceLabel(session.deviceType)}
                      </span>
                      <span className={styles.lastActive}>
                        {getRelativeTime(session.createdAt)}
                      </span>
                    </div>
                    <div className={styles.sessionDetails}>
                      <div className={styles.detailItem}>
                        <Globe size={14} />
                        <span>{session.ipAddress || 'Không xác định'}</span>
                      </div>
                      <div className={styles.detailItem}>
                        <Clock size={14} />
                        <span>Đăng nhập: {formatDate(session.createdAt)}</span>
                      </div>
                    </div>
                  </div>
                  <div className={styles.sessionActions}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleLogoutSession(session.sessionId)}
                      loading={isLoggingOut}
                      icon={<LogOut size={16} />}
                    >
                      Đăng xuất
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {sessions.length === 0 && (
          <div className={styles.emptyState}>
            <Globe size={48} />
            <h2>Không có phiên hoạt động</h2>
            <p>Tài khoản của bạn hiện không có phiên hoạt động nào.</p>
            <Button variant="primary" onClick={() => router.push('/')}>
              Quay lại trang chủ
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
