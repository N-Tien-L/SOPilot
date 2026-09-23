'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2,
  Monitor,
  Smartphone,
  Globe,
  MonitorSmartphone,
  LogOut,
  RefreshCw,
} from 'lucide-react';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  PageHeader,
  Table,
  Column,
  EmptyState,
  ConfirmDialog,
  Badge,
} from '@/components/ui';
import { api } from '@/lib/api';
import type { Session } from '@/types';
import styles from './sessions.module.css';

function getDeviceIcon(userAgent?: string): React.ReactNode {
  if (!userAgent) return <Globe size={18} />;
  const ua = userAgent.toLowerCase();
  if (ua.includes('mobile') || ua.includes('android') || ua.includes('iphone')) {
    return <Smartphone size={18} />;
  }
  if (ua.includes('tablet') || ua.includes('ipad')) {
    return <MonitorSmartphone size={18} />;
  }
  return <Monitor size={18} />;
}

function parseUserAgent(userAgent?: string): { browser: string; os: string; device: React.ReactNode } {
  const ua = userAgent || 'Unknown';
  let browser = 'Trình duyệt không xác định';
  let os = 'Hệ điều hành không xác định';

  if (/chrome/i.test(ua)) browser = 'Chrome';
  else if (/firefox/i.test(ua)) browser = 'Firefox';
  else if (/safari/i.test(ua)) browser = 'Safari';
  else if (/edge/i.test(ua)) browser = 'Edge';

  if (/windows/i.test(ua)) os = 'Windows';
  else if (/mac/i.test(ua)) os = 'macOS';
  else if (/linux/i.test(ua)) os = 'Linux';
  else if (/android/i.test(ua)) os = 'Android';
  else if (/iphone|ipad/i.test(ua)) os = 'iOS';

  return { browser, os, device: getDeviceIcon(userAgent) };
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return 'Không rõ';
  const date = new Date(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return 'Vừa xong';
  if (minutes < 60) return `${minutes} phút trước`;
  if (hours < 24) return `${hours} giờ trước`;
  if (days < 30) return `${days} ngày trước`;
  return date.toLocaleDateString('vi-VN');
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [revokeTarget, setRevokeTarget] = useState<Session | null>(null);
  const [revoking, setRevoking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setActionError(null);
    try {
      const data = await api.auth.getSessions();
      setSessions(data);
    } catch {
      setActionError('Không thể tải danh sách phiên đăng nhập.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    setRevoking(true);
    setActionError(null);
    try {
      await api.auth.revokeSession(revokeTarget.sessionId);
      setSessions((prev) => prev.filter((s) => s.sessionId !== revokeTarget.sessionId));
      setRevokeTarget(null);
    } catch {
      setActionError('Không thể thu hồi phiên. Vui lòng thử lại.');
    } finally {
      setRevoking(false);
    }
  };

  const handleLogoutAll = async () => {
    setActionError(null);
    try {
      await api.auth.logoutAll();
      window.location.href = '/login';
    } catch {
      setActionError('Không thể đăng xuất tất cả. Vui lòng thử lại.');
    }
  };

  const columns: Column<Session>[] = [
    {
      key: 'device',
      header: 'Thiết bị',
      width: '3rem',
      align: 'center',
      render: (session) => {
        const { device } = parseUserAgent(session.deviceInfo);
        return <span className={styles.deviceIcon}>{device}</span>;
      },
    },
    {
      key: 'info',
      header: 'Thông tin',
      render: (session) => {
        const { browser, os } = parseUserAgent(session.deviceInfo);
        return (
          <div className={styles.sessionInfo}>
            <span className={styles.browser}>{browser} tren {os}</span>
            {session.ipAddress && (
              <span className={styles.ip}>IP: {session.ipAddress}</span>
            )}
          </div>
        );
      },
    },
    {
      key: 'createdAt',
      header: 'Đăng nhập lúc',
      render: (session) => (
        <span className={styles.time}>
          {session.createdAt ? new Date(session.createdAt).toLocaleString('vi-VN') : '-'}
        </span>
      ),
    },
    {
      key: 'lastAccessedAt',
      header: 'Hoạt động cuối',
      render: (session) => (
        <span className={styles.time}>{formatRelativeTime(session.expiresAt)}</span>
      ),
    },
    {
      key: 'status',
      header: '',
      width: '8rem',
      align: 'right',
      render: (session) => {
        const isCurrent = session.isCurrent || session.isCurrentSession;
        return (
          <div className={styles.sessionActions}>
            {isCurrent && (
              <Badge variant="info">Hiện tại</Badge>
            )}
            {!isCurrent && (
              <Button
                variant="ghost"
                size="sm"
                icon={<LogOut size={14} />}
                onClick={(e) => {
                  e.stopPropagation();
                  setRevokeTarget(session);
                }}
              >
                Thu hồi
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className={styles.container}>
      <PageHeader
        title="Phiên đăng nhập"
        description="Quản lý các thiết bị đang đăng nhập vào tài khoản của bạn."
        actions={
          <Button
            variant="destructive"
            size="sm"
            icon={<LogOut size={16} />}
            onClick={handleLogoutAll}
          >
            Đăng xuất tất cả
          </Button>
        }
      />

      {actionError && (
        <div className={styles.error}>{actionError}</div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Thiết bị đang hoạt động</CardTitle>
        </CardHeader>
        <CardContent className={styles.cardContent}>
          {loading ? (
            <div className={styles.loading}>
              <Loader2 size={24} className={styles.spinner} />
              <span>Đang tải...</span>
            </div>
          ) : sessions.length === 0 ? (
            <EmptyState
              icon={<Monitor size={32} />}
              title="Không có phiên đăng nhập"
              description="Không tìm thấy phiên hoạt động nào."
              action={
                <Button variant="secondary" size="sm" onClick={loadSessions} icon={<RefreshCw size={16} />}>
                  Tải lại
                </Button>
              }
            />
          ) : (
            <Table
              columns={columns}
              data={sessions}
              keyExtractor={(s) => s.sessionId}
              className={styles.table}
            />
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={!!revokeTarget}
        onClose={() => setRevokeTarget(null)}
        onConfirm={handleRevoke}
        loading={revoking}
        title="Thu hồi phiên đăng nhập?"
        message={
          revokeTarget ? (
            <>
              Bạn có chắc muốn đăng xuất khỏi thiết bị này?{' '}
              {parseUserAgent(revokeTarget.deviceInfo).browser} tren{' '}
              {parseUserAgent(revokeTarget.deviceInfo).os}.
            </>
          ) : null
        }
        confirmLabel="Thu hồi"
        cancelLabel="Hủy"
        variant="warning"
      />
    </div>
  );
}
